from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By

from web.backend.app.generator.yaml_verifier import (
    SelectorIssue,
    VerificationResult,
    _by_for,
    format_issues_for_llm,
    verify_yaml_by_replay,
)


def test_by_for_xpath():
    assert _by_for("//button") == (By.XPATH, "//button")
    assert _by_for("(//a)[1]") == (By.XPATH, "(//a)[1]")


def test_by_for_css():
    assert _by_for("#login") == (By.CSS_SELECTOR, "#login")
    assert _by_for("button.primary") == (By.CSS_SELECTOR, "button.primary")


class FakeDriver:
    def __init__(self, *, fail_on_selectors: set[str] | None = None):
        self.fail_on_selectors = fail_on_selectors or set()
        self.gets: list[str] = []
        self.scrolls: list[int] = []
        self.clicks: list[str] = []
        self.inputs: list[tuple[str, str]] = []

    def get(self, url):
        self.gets.append(url)

    def execute_script(self, script):
        if "scrollBy" in script:
            self.scrolls.append(script)
        return None

    def find_element(self, by, value):
        if value in self.fail_on_selectors:
            from selenium.common.exceptions import NoSuchElementException
            raise NoSuchElementException(f"not found: {value}")
        el = MagicMock()
        el.click = lambda: self.clicks.append(value)
        el.clear = lambda: None
        el.send_keys = lambda text: self.inputs.append((value, text))
        return el

    def find_elements(self, by, value):
        if value in self.fail_on_selectors:
            return []
        return [MagicMock()]

    @property
    def current_url(self):
        return self.gets[-1] if self.gets else ""

    @property
    def title(self):
        return ""


class FakeAgent:
    def __init__(self, *, fail_on_selectors: set[str] | None = None):
        self.driver = FakeDriver(fail_on_selectors=fail_on_selectors)

    def _wait_ready(self):
        pass

    def _settle_js(self, *, extra_delay=None):
        pass


def _patch_wait(monkeypatch, fail_selectors: set[str]):
    from selenium.common.exceptions import NoSuchElementException
    from web.backend.app.generator import yaml_verifier as mod

    class FakeWait:
        def __init__(self, driver, timeout):
            self.driver = driver

        def until(self, predicate):
            try:
                result = predicate(self.driver)
            except NoSuchElementException as exc:
                raise TimeoutException(str(exc))
            if not result:
                raise TimeoutException("predicate returned falsy")
            return result

    monkeypatch.setattr(mod, "WebDriverWait", FakeWait)


def test_empty_yaml():
    result = verify_yaml_by_replay("", FakeAgent())
    assert result.ok is False
    assert result.yaml_parse_error == "empty YAML"


def test_yaml_parse_error():
    result = verify_yaml_by_replay("not: valid: yaml: :", FakeAgent())
    assert result.ok is False
    assert "parse error" in result.yaml_parse_error


def test_yaml_root_not_mapping():
    result = verify_yaml_by_replay("- just\n- a\n- list", FakeAgent())
    assert result.ok is False
    assert "not a mapping" in result.yaml_parse_error


def test_navigate_action_succeeds(monkeypatch):
    _patch_wait(monkeypatch, set())
    yaml_text = """
acts:
  act_1:
    scenes:
      scene_1:
        actions:
          action_1:
            type: navigate
            url: https://example.com
"""
    agent = FakeAgent()
    result = verify_yaml_by_replay(yaml_text, agent)
    assert result.ok is True
    assert result.selectors_checked == 0
    assert agent.driver.gets == ["https://example.com"]


def test_click_with_valid_selector(monkeypatch):
    _patch_wait(monkeypatch, set())
    yaml_text = """
acts:
  act_1:
    scenes:
      scene_1:
        actions:
          action_1:
            type: click
            selector: //button[@id='ok']
"""
    agent = FakeAgent()
    result = verify_yaml_by_replay(yaml_text, agent)
    assert result.ok is True
    assert result.selectors_checked == 1
    assert agent.driver.clicks == ["//button[@id='ok']"]


def test_click_with_invalid_selector(monkeypatch):
    bad = "//button[@id='missing']"
    _patch_wait(monkeypatch, {bad})
    yaml_text = f"""
acts:
  act_1:
    scenes:
      scene_1:
        actions:
          action_1:
            type: click
            selector: {bad}
"""
    result = verify_yaml_by_replay(yaml_text, FakeAgent(fail_on_selectors={bad}))
    assert result.ok is False
    assert len(result.issues) == 1
    assert result.issues[0].action_type == "click"
    assert result.issues[0].selector == bad
    assert "not found" in result.issues[0].reason


def test_input_action(monkeypatch):
    _patch_wait(monkeypatch, set())
    yaml_text = """
acts:
  act_1:
    scenes:
      scene_1:
        actions:
          action_1:
            type: input
            selector: input[name=q]
            text: hello
"""
    agent = FakeAgent()
    result = verify_yaml_by_replay(yaml_text, agent)
    assert result.ok is True
    assert agent.driver.inputs == [("input[name=q]", "hello")]


def test_scroll_actions(monkeypatch):
    _patch_wait(monkeypatch, set())
    yaml_text = """
acts:
  act_1:
    scenes:
      scene_1:
        actions:
          action_1:
            type: scrollDown
            point: 300
          action_2:
            type: scrollUp
            point: 200
"""
    agent = FakeAgent()
    result = verify_yaml_by_replay(yaml_text, agent)
    assert result.ok is True
    assert len(agent.driver.scrolls) == 2


def test_missing_selector_for_click(monkeypatch):
    _patch_wait(monkeypatch, set())
    yaml_text = """
acts:
  act_1:
    scenes:
      scene_1:
        actions:
          action_1:
            type: click
"""
    result = verify_yaml_by_replay(yaml_text, FakeAgent())
    assert result.ok is False
    assert result.issues[0].reason == "missing selector"


def test_full_scenario_with_multiple_issues(monkeypatch):
    bad = "//button[@id='broken']"
    _patch_wait(monkeypatch, {bad})
    yaml_text = f"""
acts:
  act_1:
    scenes:
      scene_1:
        actions:
          action_1:
            type: navigate
            url: https://example.com
          action_2:
            type: click
            selector: //a[@href='/ok']
          action_3:
            type: click
            selector: {bad}
"""
    result = verify_yaml_by_replay(yaml_text, FakeAgent(fail_on_selectors={bad}))
    assert result.ok is False
    assert result.selectors_checked == 2
    assert len(result.issues) == 1
    assert result.issues[0].selector == bad


def test_format_issues_for_llm_empty():
    result = VerificationResult(ok=True, issues=[], selectors_checked=3)
    msg = format_issues_for_llm(result)
    assert "успешно прошли проверку" in msg


def test_format_issues_for_llm_with_issues():
    result = VerificationResult(
        ok=False,
        selectors_checked=2,
        issues=[
            SelectorIssue("act_1/scene_3", "action_1", "click", "//bad", "not found in DOM"),
            SelectorIssue("act_2/scene_1", "action_2", "input", "#ghost", "not found in DOM"),
        ],
    )
    msg = format_issues_for_llm(result)
    assert "найдено 2 ошибок" in msg
    assert "//bad" in msg
    assert "#ghost" in msg
    assert "act_1/scene_3" in msg
    assert "act_2/scene_1" in msg


def test_format_issues_for_llm_parse_error():
    result = VerificationResult(ok=False, issues=[], selectors_checked=0, yaml_parse_error="bad yaml")
    msg = format_issues_for_llm(result)
    assert "невалиден" in msg
    assert "bad yaml" in msg
