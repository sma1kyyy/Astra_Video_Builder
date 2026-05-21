from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from typing import Optional

from bs4 import BeautifulSoup, Tag
from selenium import webdriver
from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver import ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.common import service as _selenium_service
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

log = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 10
_DEFAULT_DOM_LIMIT = 3000
_DEFAULT_SETTLE_DELAY = 1.2
_DEFAULT_MIN_ELEMENTS = 5
_INTERACTIVE_TAGS = ("a", "button", "input", "select", "textarea", "label")
_USEFUL_ATTRS = (
    "id",
    "name",
    "type",
    "role",
    "aria-label",
    "placeholder",
    "data-testid",
    "data-test",
    "data-cy",
    "href",
    "value",
)


class BrowserAgentError(RuntimeError):
    pass


@dataclass
class AgentObservation:
    url: str
    title: str
    dom: str
    truncated: bool
    element_count: int = 0
    likely_unrendered: bool = False
    note: str = ""


def _build_options(headless: bool) -> ChromeOptions:
    opts = ChromeOptions()
    if headless:
        opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument("--window-size=1280,900")
    opts.add_argument("--disable-notifications")
    opts.add_argument("--disable-popup-blocking")
    opts.add_argument("--no-first-run")
    opts.add_argument("--no-default-browser-check")
    opts.add_argument("--disable-infobars")
    opts.add_argument("--disable-features=WidevineCdmComponent,MediaRouter,AutofillServerCommunication,Translate,InterestFeedContentSuggestions")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)
    opts.add_experimental_option("prefs", {
        "profile.default_content_setting_values.notifications": 2,
        "profile.default_content_setting_values.media_stream": 2,
        "profile.default_content_setting_values.geolocation": 2,
        "profile.default_content_setting_values.protected_media_identifier": 2,
        "credentials_enable_service": False,
        "profile.password_manager_enabled": False,
        "translate.enabled": False,
    })
    return opts


_ipv4_patched = False


def _force_ipv4_service_url() -> None:
    # На системах где localhost резолвится в ::1 первым (типичный Fedora/IPv6),
    # selenium-обращение к chromedriver через IPv6 виснет навсегда без таймаута.
    # Принудительно используем 127.0.0.1 — тот же фикс что в engines/live/browser_engine.
    global _ipv4_patched
    if _ipv4_patched:
        return
    original = _selenium_service.Service.service_url.fget

    def patched(self):
        return original(self).replace("localhost", "127.0.0.1")

    _selenium_service.Service.service_url = property(patched)
    _ipv4_patched = True


def _node_signature(tag: Tag) -> str:
    parts: list[str] = [tag.name]
    for attr in _USEFUL_ATTRS:
        val = tag.attrs.get(attr)
        if val is None:
            continue
        if isinstance(val, list):
            val = " ".join(val)
        val = str(val).strip()
        if not val:
            continue
        if len(val) > 80:
            val = val[:77] + "..."
        parts.append(f'{attr}="{val}"')
    text = (tag.get_text(strip=True) or "")[:80]
    if text:
        parts.append(f'text="{text}"')
    return "<" + " ".join(parts) + ">"


def compact_dom(html: str, limit: int = _DEFAULT_DOM_LIMIT) -> tuple[str, bool, int]:
    """Compress raw HTML into an LLM-friendly listing of interactive elements.

    Returns (compact_text, truncated_flag, element_count). Keeps only tags that
    LLMs can reliably act on (a/button/input/select/textarea/label) and elements
    with role/data-testid/aria-label/id-like attributes regardless of tag.
    """
    soup = BeautifulSoup(html, "lxml")
    for unwanted in soup(["script", "style", "noscript", "svg", "path"]):
        unwanted.decompose()

    seen: set[str] = set()
    lines: list[str] = []
    for tag in soup.find_all(True):
        if not isinstance(tag, Tag):
            continue
        keep = tag.name in _INTERACTIVE_TAGS or any(
            tag.attrs.get(a) for a in ("role", "aria-label", "data-testid", "data-test", "data-cy", "id")
        )
        if not keep:
            continue
        sig = _node_signature(tag)
        if sig in seen:
            continue
        seen.add(sig)
        lines.append(sig)

    total = len(lines)
    joined = "\n".join(lines)
    truncated = False
    if len(joined) > limit:
        joined = joined[:limit].rsplit("\n", 1)[0]
        truncated = True
    return joined, truncated, total


class BrowserAgent:
    """Headless Chrome wrapper exposing a tiny tool surface for the LLM agent."""

    def __init__(
        self,
        *,
        headless: bool = True,
        timeout: int = _DEFAULT_TIMEOUT,
        dom_limit: int = _DEFAULT_DOM_LIMIT,
        settle_delay: float = _DEFAULT_SETTLE_DELAY,
        min_elements: int = _DEFAULT_MIN_ELEMENTS,
    ) -> None:
        self._headless = headless
        self._timeout = timeout
        self._dom_limit = dom_limit
        self._settle_delay = settle_delay
        self._min_elements = min_elements
        self._driver: Optional[WebDriver] = None
        self._driver_lock = threading.Lock()

    def __enter__(self) -> "BrowserAgent":
        self._start_driver()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def _start_driver(self) -> None:
        if self._driver is not None:
            return
        try:
            log.info("[browser] installing chromedriver via webdriver_manager...")
            driver_path = ChromeDriverManager().install()
            log.info("[browser] chromedriver path: %s", driver_path)
            _force_ipv4_service_url()
            service = ChromeService(driver_path)
            log.info("[browser] starting Chrome (headless=%s)...", self._headless)
            self._driver = webdriver.Chrome(service=service, options=_build_options(self._headless))
            self._driver.set_page_load_timeout(20)
            log.info("[browser] Chrome started")
        except WebDriverException as exc:
            raise BrowserAgentError(f"Failed to start headless Chrome: {exc}") from exc

    def close(self) -> None:
        if self._driver is None:
            return
        with self._driver_lock:
            try:
                self._driver.quit()
            except WebDriverException as exc:
                log.warning("Error while closing driver: %s", exc)
            finally:
                self._driver = None

    @property
    def driver(self) -> WebDriver:
        if self._driver is None:
            raise BrowserAgentError("Driver is not started")
        return self._driver

    def _by_for(self, selector: str) -> tuple[str, str]:
        if selector.startswith("/") or selector.startswith("("):
            return (By.XPATH, selector)
        return (By.CSS_SELECTOR, selector)

    def _wait_ready(self) -> None:
        try:
            WebDriverWait(self.driver, self._timeout).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
        except TimeoutException:
            log.warning("document.readyState did not reach 'complete' in %ss", self._timeout)

    def _settle_js(self, extra_delay: float | None = None) -> None:
        # SPA-страницы рендерят DOM после readyState=complete. Дополнительно ждём
        # пока браузер не отрисует хоть какие-то интерактивные элементы — иначе
        # LLM получит пустой DOM-снимок и подставит выдуманные селекторы.
        time.sleep(extra_delay if extra_delay is not None else self._settle_delay)
        deadline = time.monotonic() + self._timeout
        while time.monotonic() < deadline:
            try:
                count = self.driver.execute_script(
                    "return document.querySelectorAll('a,button,input,select,textarea,[role],[data-testid],[aria-label]').length;"
                )
            except WebDriverException:
                return
            if isinstance(count, int) and count >= self._min_elements:
                return
            time.sleep(0.3)

    def observe(self, *, extra_delay: float | None = None) -> AgentObservation:
        self._wait_ready()
        self._settle_js(extra_delay=extra_delay)
        html = self.driver.page_source
        dom, truncated, element_count = compact_dom(html, self._dom_limit)
        likely_unrendered = element_count < self._min_elements
        note = ""
        if likely_unrendered:
            note = (
                f"WARNING: страница вернула только {element_count} интерактивных элементов. "
                "Это вероятно SPA, который ещё не отрендерил контент. Сделай wait(3) и observe() снова, "
                "прежде чем использовать селекторы из этого снимка."
            )
        return AgentObservation(
            url=self.driver.current_url,
            title=self.driver.title or "",
            dom=dom,
            truncated=truncated,
            element_count=element_count,
            likely_unrendered=likely_unrendered,
            note=note,
        )

    def navigate(self, url: str) -> AgentObservation:
        try:
            self.driver.get(url)
        except WebDriverException as exc:
            raise BrowserAgentError(f"navigate failed for {url!r}: {exc}") from exc
        return self.observe(extra_delay=self._settle_delay)

    def click(self, selector: str) -> AgentObservation:
        by, value = self._by_for(selector)
        try:
            elem = WebDriverWait(self.driver, self._timeout).until(
                EC.element_to_be_clickable((by, value))
            )
            elem.click()
        except (TimeoutException, NoSuchElementException) as exc:
            raise BrowserAgentError(f"click failed for selector {selector!r}: {exc}") from exc
        return self.observe()

    def type_text(self, selector: str, text: str, *, submit: bool = False) -> AgentObservation:
        by, value = self._by_for(selector)
        try:
            elem = WebDriverWait(self.driver, self._timeout).until(
                EC.visibility_of_element_located((by, value))
            )
            elem.clear()
            elem.send_keys(text)
            if submit:
                from selenium.webdriver.common.keys import Keys

                elem.send_keys(Keys.ENTER)
        except (TimeoutException, NoSuchElementException) as exc:
            raise BrowserAgentError(f"type_text failed for selector {selector!r}: {exc}") from exc
        return self.observe()

    def scroll(self, direction: str, pixels: int = 500) -> AgentObservation:
        if direction not in ("up", "down", "top", "bottom"):
            raise BrowserAgentError(f"unsupported scroll direction: {direction}")
        script_map = {
            "down": f"window.scrollBy(0, {pixels});",
            "up": f"window.scrollBy(0, -{pixels});",
            "top": "window.scrollTo(0, 0);",
            "bottom": "window.scrollTo(0, document.body.scrollHeight);",
        }
        self.driver.execute_script(script_map[direction])
        return self.observe()

    def wait(self, seconds: float) -> AgentObservation:
        seconds = max(0.0, min(seconds, 10.0))
        time.sleep(seconds)
        return self.observe()
