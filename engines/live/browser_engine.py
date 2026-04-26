import json
from time import sleep, time
from typing import List, Optional

from selenium import webdriver
from selenium.common.exceptions import (
    NoSuchElementException,
    StaleElementReferenceException,
    WebDriverException,
)
from selenium.webdriver import ChromeOptions, Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.remote.webdriver import WebDriver
from requests.exceptions import ConnectionError as RequestsConnectionError
from webdriver_manager.chrome import ChromeDriverManager

from core.schemas.action_object import ActionObject
from core.utils.logger import LoggerFactory

log = LoggerFactory.get_logger(__name__)


class BrowserDriverError(RuntimeError):
    pass


class ActionExecutionError(RuntimeError):
    pass


_driver: Optional[WebDriver] = None


def _build_options() -> ChromeOptions:
    options = ChromeOptions()
    options.add_argument("--kiosk")
    options.add_argument(
        "user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/51.0.2704.103 Safari/537.36"
    )
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    return options


def get_driver() -> WebDriver:
    """Лениво инициализирует и возвращает singleton webdriver.

    Кидает BrowserDriverError при любых проблемах с установкой/запуском.
    """
    global _driver
    if _driver is not None:
        return _driver

    try:
        service = Service(ChromeDriverManager().install())
    except RequestsConnectionError as exc:
        raise BrowserDriverError(
            "Нет доступа в интернет для установки ChromeDriver. "
            "Проверьте соединение."
        ) from exc
    except Exception as exc:
        raise BrowserDriverError(
            f"Не удалось установить ChromeDriver через webdriver_manager: "
            f"{type(exc).__name__}: {exc}"
        ) from exc

    # На некоторых системах (Fedora с IPv6) `localhost` резолвится первым в `::1`,
    # и обращение к chromedriver через IPv6 виснет. Принудительно используем 127.0.0.1.
    _force_ipv4_service_url()

    try:
        _driver = webdriver.Chrome(service=service, options=_build_options())
    except WebDriverException as exc:
        raise BrowserDriverError(f"Не удалось запустить Chrome WebDriver: {exc}") from exc

    return _driver


_ipv4_patched = False


def _force_ipv4_service_url() -> None:
    """Заменяет `localhost` на `127.0.0.1` в Service.service_url.

    Идемпотентно: применяется один раз на процесс.
    """
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
    """Безопасно закрывает webdriver, если он был запущен."""
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
    """Возвращает первый видимый и активный элемент.

    Игнорирует stale-элементы, чтобы не падать при динамическом DOM.
    """
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
