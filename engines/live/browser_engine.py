import json
from time import sleep, time
from typing import List, Optional

from selenium import webdriver
from selenium.common.exceptions import (
    StaleElementReferenceException,
    WebDriverException,
)
from selenium.webdriver import ChromeOptions, FirefoxOptions, Keys
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.actions.action_builder import ActionBuilder
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.remote.webdriver import WebDriver
from requests.exceptions import ConnectionError as RequestsConnectionError
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.firefox import GeckoDriverManager

from core.schemas.action_object import ActionObject
from core.utils.logger import LoggerFactory

log = LoggerFactory.get_logger(__name__)


class BrowserDriverError(RuntimeError):
    pass


class ActionExecutionError(RuntimeError):
    pass


_driver: Optional[WebDriver] = None
_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/51.0.2704.103 Safari/537.36"
)


def _build_chrome_options() -> ChromeOptions:
    options = ChromeOptions()
    options.add_argument("--kiosk")
    options.add_argument(f"user-agent={_USER_AGENT}")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    return options


def _build_firefox_options() -> FirefoxOptions:
    options = FirefoxOptions()
    options.add_argument("--kiosk")
    options.set_preference("general.useragent.override", _USER_AGENT)
    options.set_preference("dom.webdriver.enabled", False)
    options.set_preference("useAutomationExtension", False)
    return options


def _install_driver(installer, label: str):
    try:
        return installer().install()
    except RequestsConnectionError as exc:
        raise BrowserDriverError(
            f"Нет доступа в интернет для установки {label}. Проверьте соединение."
        ) from exc
    except Exception as exc:
        raise BrowserDriverError(
            f"Не удалось установить {label}: {type(exc).__name__}: {exc}"
        ) from exc


def _start_chrome() -> WebDriver:
    driver_path = _install_driver(ChromeDriverManager, "ChromeDriver")
    _force_ipv4_service_url()
    try:
        return webdriver.Chrome(
            service=ChromeService(driver_path),
            options=_build_chrome_options(),
        )
    except WebDriverException as exc:
        raise BrowserDriverError(f"Не удалось запустить Chrome WebDriver: {exc}") from exc


def _start_firefox() -> WebDriver:
    driver_path = _install_driver(GeckoDriverManager, "GeckoDriver")
    _force_ipv4_service_url()
    try:
        return webdriver.Firefox(
            service=FirefoxService(driver_path),
            options=_build_firefox_options(),
        )
    except WebDriverException as exc:
        raise BrowserDriverError(f"Не удалось запустить Firefox WebDriver: {exc}") from exc


def _park_cursor(driver: WebDriver) -> None:
    # Парковка курсора в правый нижний угол окна — единственный способ убрать
    # его из записи на Wayland-композиторах, где software cursor plane всегда
    # попадает в захват независимо от флагов рекордера.
    try:
        size = driver.get_window_size()
        x, y = int(size["width"]) - 1, int(size["height"]) - 1
        builder = ActionBuilder(driver)
        builder.pointer_action.move_to_location(x, y)
        builder.perform()
    except WebDriverException as exc:
        log.debug("Не удалось припарковать курсор: %s", exc)


def get_driver(browser: str = "chrome") -> WebDriver:
    """Лениво инициализирует и возвращает singleton webdriver для указанного браузера."""
    global _driver
    if _driver is not None:
        return _driver

    match browser:
        case "chrome":
            _driver = _start_chrome()
        case "firefox":
            _driver = _start_firefox()
        case _:
            raise BrowserDriverError(f"Неизвестный браузер: {browser}")

    log.info("WebDriver запущен: %s", browser)
    _park_cursor(_driver)
    return _driver


_ipv4_patched = False


def _force_ipv4_service_url() -> None:
    # На некоторых системах (Fedora с IPv6) `localhost` резолвится первым в `::1`,
    # и обращение к webdriver через IPv6 виснет. Принудительно используем 127.0.0.1.
    global _ipv4_patched
    if _ipv4_patched:
        return
    from selenium.webdriver.common import service as svc

    original = svc.Service.service_url.fget

    def patched(self):  # type: ignore[no-untyped-def]
        return original(self).replace("localhost", "127.0.0.1")

    svc.Service.service_url = property(patched)
    _ipv4_patched = True


def quit_driver() -> None:
    global _driver
    if _driver is None:
        return
    try:
        _driver.quit()
    except Exception as exc:
        log.warning("Ошибка при закрытии webdriver: %s", exc)
    finally:
        _driver = None


def _find_displayed(elements: List[WebElement]) -> Optional[WebElement]:
    for elem in elements:
        try:
            if elem.is_displayed() and elem.is_enabled():
                return elem
        except StaleElementReferenceException:
            continue
    return None


def _resolve_element(driver: WebDriver, selector: str) -> WebElement:
    elements = driver.find_elements("xpath", selector)
    elem = _find_displayed(elements)
    if elem is None:
        log.error("Element not found: selector=%s", selector)
        raise ActionExecutionError(f"Element not found: {selector}")
    return elem


def _scroll_by(driver: WebDriver, point: int, behavior: Optional[str]) -> None:
    params = {"top": point, "left": 0}
    if behavior:
        params["behavior"] = behavior
    driver.execute_script(f"window.scrollBy({json.dumps(params)});")


def _scroll_into_view(driver: WebDriver, elem: WebElement, behavior: Optional[str]) -> None:
    params = {"block": "center"}
    if behavior:
        params["behavior"] = behavior
    driver.execute_script(
        f"arguments[0].scrollIntoView({json.dumps(params)});", elem
    )


def _park_cursor(driver: WebDriver) -> None:
    # Парковка курсора в правый нижний угол окна — единственный способ убрать
    # его из записи на Wayland-композиторах, где KMS-захват включает software
    # cursor plane независимо от флагов рекордера.
    try:
        size = driver.execute_script(
            "return [window.innerWidth, window.innerHeight];"
        )
        x, y = int(size[0]) - 1, int(size[1]) - 1
        builder = ActionBuilder(driver)
        builder.pointer_action.move_to_location(x, y)
        builder.perform()
    except WebDriverException as exc:
        log.debug("Не удалось припарковать курсор: %s", exc)


def start_actions(actions: List[ActionObject], tts_time: float) -> None:
    """Выполняет действия для одной сцены в браузере.

    tts_time — длительность TTS этой сцены в секундах. Если действия закончились
    раньше — добиваем sleep, чтобы аудио успело доиграть.
    """
    driver = get_driver()

    log.debug("TTS time for scene: %.2fs", tts_time)
    start_actions_time = time()

    for action in actions:
        sleep(action.wait)
        a_type = action.type
        match a_type:
            case "navigate":
                driver.get(action.url)
            case "wait":
                sleep(action.duration)
            case "click":
                _resolve_element(driver, action.selector).click()
            case "input":
                elem = _resolve_element(driver, action.selector)
                elem.click()
                elem.send_keys(action.text)
                if action.enter:
                    sleep(1)
                    elem.send_keys(Keys.ENTER)
            case "scrollUp":
                _scroll_by(driver, -action.point, action.behavior)
            case "scrollDown":
                _scroll_by(driver, action.point, action.behavior)
            case "scrollTo":
                elem = _resolve_element(driver, action.selector)
                _scroll_into_view(driver, elem, action.behavior)
            case _:
                raise ActionExecutionError(f"Unknown action type: {a_type}")

    actions_time = time() - start_actions_time
    log.debug("Actions wall time: %.2fs", actions_time)
    if tts_time > actions_time:
        sleep(tts_time - actions_time + 1)
