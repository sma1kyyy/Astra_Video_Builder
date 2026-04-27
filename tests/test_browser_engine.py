from unittest.mock import MagicMock, patch

import pytest

from engines.live import browser_engine as be
from engines.live.browser_engine import (
    ActionExecutionError,
    BrowserDriverError,
    _build_chrome_options,
    _build_firefox_options,
    _find_displayed,
    _resolve_element,
    get_driver,
    quit_driver,
    start_actions,
)


@pytest.fixture(autouse=True)
def reset_driver():
    be._driver = None
    yield
    be._driver = None


@pytest.fixture
def fake_driver():
    drv = MagicMock()
    drv.get_window_size.return_value = {"width": 1920, "height": 1080}
    drv.execute_script.return_value = [1920, 1080]
    return drv


class TestOptionsBuilders:
    def test_chrome_options(self):
        opts = _build_chrome_options()
        args = opts.arguments
        assert any("--kiosk" in a for a in args)
        assert any("user-agent" in a for a in args)

    def test_firefox_options(self):
        opts = _build_firefox_options()
        args = opts.arguments
        assert any("--kiosk" in a for a in args)


class TestGetDriver:
    def test_chrome_singleton(self, fake_driver):
        with patch.object(be, "_start_chrome", return_value=fake_driver) as starter, \
             patch.object(be, "_park_cursor"):
            d1 = get_driver("chrome")
            d2 = get_driver("chrome")
            assert d1 is d2 is fake_driver
            starter.assert_called_once()

    def test_firefox_path(self, fake_driver):
        with patch.object(be, "_start_firefox", return_value=fake_driver) as starter, \
             patch.object(be, "_park_cursor"):
            d = get_driver("firefox")
            assert d is fake_driver
            starter.assert_called_once()

    def test_unknown_browser(self):
        with pytest.raises(BrowserDriverError):
            get_driver("safari")

    def test_park_cursor_called_on_init(self, fake_driver):
        with patch.object(be, "_start_chrome", return_value=fake_driver), \
             patch.object(be, "_park_cursor") as park:
            get_driver("chrome")
            park.assert_called_once_with(fake_driver)


class TestInstallDriver:
    def test_no_internet_raises(self):
        from requests.exceptions import ConnectionError as RCE

        installer = MagicMock()
        installer.return_value.install.side_effect = RCE("no net")
        with pytest.raises(BrowserDriverError, match="интернет"):
            be._install_driver(installer, "X")

    def test_generic_error_wrapped(self):
        installer = MagicMock()
        installer.return_value.install.side_effect = RuntimeError("boom")
        with pytest.raises(BrowserDriverError):
            be._install_driver(installer, "X")


class TestForceIPv4:
    def test_idempotent(self):
        be._ipv4_patched = False
        be._force_ipv4_service_url()
        first = be._ipv4_patched
        be._force_ipv4_service_url()
        assert first is True
        assert be._ipv4_patched is True

    def test_localhost_replaced(self):
        be._ipv4_patched = False
        be._force_ipv4_service_url()
        from selenium.webdriver.common.service import Service

        svc = MagicMock(spec=Service)
        svc._port = 1234
        svc._path = "/x"

        url = Service.service_url.fget(MagicMock(host="localhost", port=4444))
        assert "127.0.0.1" in url
        assert "localhost" not in url


class TestQuitDriver:
    def test_quit_when_none(self):
        be._driver = None
        quit_driver()

    def test_quit_calls_quit(self, fake_driver):
        be._driver = fake_driver
        quit_driver()
        fake_driver.quit.assert_called_once()
        assert be._driver is None

    def test_quit_swallows_exception(self, fake_driver):
        fake_driver.quit.side_effect = RuntimeError("boom")
        be._driver = fake_driver
        quit_driver()
        assert be._driver is None


class TestResolveElement:
    def test_returns_displayed(self, fake_driver):
        elem = MagicMock()
        elem.is_displayed.return_value = True
        elem.is_enabled.return_value = True
        fake_driver.find_elements.return_value = [elem]
        assert _resolve_element(fake_driver, "//x") is elem

    def test_skips_hidden(self, fake_driver):
        hidden = MagicMock()
        hidden.is_displayed.return_value = False
        visible = MagicMock()
        visible.is_displayed.return_value = True
        visible.is_enabled.return_value = True
        fake_driver.find_elements.return_value = [hidden, visible]
        assert _resolve_element(fake_driver, "//x") is visible

    def test_no_displayed_raises(self, fake_driver):
        elem = MagicMock()
        elem.is_displayed.return_value = False
        fake_driver.find_elements.return_value = [elem]
        with pytest.raises(ActionExecutionError):
            _resolve_element(fake_driver, "//x")

    def test_empty_raises(self, fake_driver):
        fake_driver.find_elements.return_value = []
        with pytest.raises(ActionExecutionError):
            _resolve_element(fake_driver, "//x")

    def test_stale_skipped(self, fake_driver):
        from selenium.common.exceptions import StaleElementReferenceException

        stale = MagicMock()
        stale.is_displayed.side_effect = StaleElementReferenceException()
        good = MagicMock()
        good.is_displayed.return_value = True
        good.is_enabled.return_value = True
        fake_driver.find_elements.return_value = [stale, good]
        assert _resolve_element(fake_driver, "//x") is good

    def test_find_displayed_helper_empty(self):
        assert _find_displayed([]) is None


class TestStartActions:
    @pytest.fixture
    def patch_get_driver(self, fake_driver):
        with patch.object(be, "get_driver", return_value=fake_driver), \
             patch("engines.live.browser_engine.sleep"):
            yield fake_driver

    def test_navigate(self, patch_get_driver, make_action):
        a = make_action(type="navigate", url="https://example.com")
        start_actions([a], tts_time=0.0)
        patch_get_driver.get.assert_called_with("https://example.com")

    def test_wait_only_sleeps(self, patch_get_driver, make_action):
        a = make_action(type="wait", duration=2)
        start_actions([a], tts_time=0.0)
        patch_get_driver.get.assert_not_called()

    def test_click_resolves_and_clicks(self, patch_get_driver, make_action):
        elem = MagicMock()
        elem.is_displayed.return_value = True
        elem.is_enabled.return_value = True
        patch_get_driver.find_elements.return_value = [elem]
        a = make_action(type="click", selector="//button")
        start_actions([a], tts_time=0.0)
        elem.click.assert_called_once()

    def test_input_sends_keys_with_enter(self, patch_get_driver, make_action):
        elem = MagicMock()
        elem.is_displayed.return_value = True
        elem.is_enabled.return_value = True
        patch_get_driver.find_elements.return_value = [elem]
        a = make_action(type="input", selector="//input", text="hi", enter=True)
        start_actions([a], tts_time=0.0)
        from selenium.webdriver import Keys
        calls = [c.args[0] for c in elem.send_keys.call_args_list]
        assert "hi" in calls
        assert Keys.ENTER in calls

    def test_input_no_enter(self, patch_get_driver, make_action):
        elem = MagicMock()
        elem.is_displayed.return_value = True
        elem.is_enabled.return_value = True
        patch_get_driver.find_elements.return_value = [elem]
        a = make_action(type="input", selector="//input", text="hi", enter=False)
        start_actions([a], tts_time=0.0)
        from selenium.webdriver import Keys
        calls = [c.args[0] for c in elem.send_keys.call_args_list]
        assert "hi" in calls
        assert Keys.ENTER not in calls

    def test_input_text_int_coerced(self, patch_get_driver, make_action):
        elem = MagicMock()
        elem.is_displayed.return_value = True
        elem.is_enabled.return_value = True
        patch_get_driver.find_elements.return_value = [elem]
        a = make_action(type="input", selector="//input", text=12345, enter=False)
        start_actions([a], tts_time=0.0)
        calls = [c.args[0] for c in elem.send_keys.call_args_list]
        assert "12345" in calls

    def test_scroll_down_calls_execute_script(self, patch_get_driver, make_action):
        a = make_action(type="scrollDown", point=500)
        start_actions([a], tts_time=0.0)
        script = patch_get_driver.execute_script.call_args[0][0]
        assert "scrollBy" in script
        assert "500" in script

    def test_scroll_up_negates_point(self, patch_get_driver, make_action):
        a = make_action(type="scrollUp", point=500)
        start_actions([a], tts_time=0.0)
        script = patch_get_driver.execute_script.call_args[0][0]
        assert "-500" in script

    def test_scroll_to_uses_scroll_into_view(self, patch_get_driver, make_action):
        elem = MagicMock()
        elem.is_displayed.return_value = True
        elem.is_enabled.return_value = True
        patch_get_driver.find_elements.return_value = [elem]
        a = make_action(type="scrollTo", selector="//div")
        start_actions([a], tts_time=0.0)
        script = patch_get_driver.execute_script.call_args[0][0]
        assert "scrollIntoView" in script

    def test_unknown_type_raises(self, patch_get_driver):
        bogus = MagicMock()
        bogus.type = "teleport"
        bogus.wait = 0
        with pytest.raises(ActionExecutionError):
            start_actions([bogus], tts_time=0.0)


class TestParkCursor:
    def test_park_uses_window_size(self, fake_driver):
        with patch("engines.live.browser_engine.ActionBuilder") as AB:
            builder = MagicMock()
            AB.return_value = builder
            be._park_cursor(fake_driver)
            builder.pointer_action.move_to_location.assert_called_with(1919, 1079)
            builder.perform.assert_called_once()

    def test_park_swallows_webdriver_exception(self, fake_driver):
        from selenium.common.exceptions import WebDriverException
        fake_driver.execute_script.side_effect = WebDriverException("nope")
        be._park_cursor(fake_driver)
