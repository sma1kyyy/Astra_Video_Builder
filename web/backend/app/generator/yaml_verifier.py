from __future__ import annotations

import logging
import time
from dataclasses import dataclass

import yaml
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from web.backend.app.generator.browser_agent import BrowserAgent

log = logging.getLogger(__name__)


@dataclass
class SelectorIssue:
    scene_path: str
    action_path: str
    action_type: str
    selector: str
    reason: str


@dataclass
class VerificationResult:
    ok: bool
    issues: list[SelectorIssue]
    selectors_checked: int
    yaml_parse_error: str | None = None


def _by_for(selector: str) -> tuple[str, str]:
    if selector.startswith("/") or selector.startswith("("):
        return (By.XPATH, selector)
    return (By.CSS_SELECTOR, selector)


def _walk_actions(parsed: dict):
    acts = (parsed or {}).get("acts") or {}
    if not isinstance(acts, dict):
        return
    for act_key, act in acts.items():
        if not isinstance(act, dict):
            continue
        scenes = act.get("scenes") or {}
        if not isinstance(scenes, dict):
            continue
        for scene_key, scene in scenes.items():
            if not isinstance(scene, dict):
                continue
            actions = scene.get("actions") or {}
            if not isinstance(actions, dict):
                continue
            for action_key, action in actions.items():
                if not isinstance(action, dict):
                    continue
                yield f"{act_key}/{scene_key}", action_key, action


def _verify_action(
    agent: BrowserAgent,
    action: dict,
    wait_seconds: float,
) -> tuple[bool, str | None]:
    action_type = action.get("type")
    driver = agent.driver

    if action_type == "navigate":
        url = action.get("url")
        if not url or not isinstance(url, str):
            return False, "missing url"
        try:
            driver.get(url)
            agent._wait_ready()
            agent._settle_js(extra_delay=0.5)
        except WebDriverException as exc:
            return False, f"navigate failed: {exc}"
        return True, None

    if action_type == "wait":
        duration = float(action.get("duration", 1))
        time.sleep(min(duration, 3.0))
        return True, None

    if action_type in {"scrollUp", "scrollDown"}:
        pixels = int(action.get("point", 500))
        delta = pixels if action_type == "scrollDown" else -pixels
        try:
            driver.execute_script(f"window.scrollBy(0, {delta});")
        except WebDriverException as exc:
            return False, f"scroll failed: {exc}"
        return True, None

    if action_type in {"click", "input", "scrollTo"}:
        selector = action.get("selector")
        if not selector or not isinstance(selector, str):
            return False, "missing selector"
        by, value = _by_for(selector)
        try:
            WebDriverWait(driver, wait_seconds).until(
                EC.presence_of_element_located((by, value))
            )
        except TimeoutException:
            return False, "selector not found in DOM"
        except WebDriverException as exc:
            return False, f"selector check failed: {exc}"
        if action_type == "click":
            try:
                el = driver.find_element(by, value)
                el.click()
                agent._settle_js(extra_delay=0.3)
            except WebDriverException as exc:
                return False, f"click failed: {exc}"
        elif action_type == "input":
            try:
                el = driver.find_element(by, value)
                text = action.get("text", "")
                el.clear()
                el.send_keys(text)
            except WebDriverException as exc:
                return False, f"input failed: {exc}"
        return True, None

    return True, None


def verify_yaml_by_replay(
    yaml_text: str, agent: BrowserAgent, *, selector_wait: float = 3.0
) -> VerificationResult:
    if not yaml_text or not yaml_text.strip():
        return VerificationResult(False, [], 0, "empty YAML")

    try:
        parsed = yaml.safe_load(yaml_text)
    except yaml.YAMLError as exc:
        return VerificationResult(False, [], 0, f"YAML parse error: {exc}")

    if not isinstance(parsed, dict):
        return VerificationResult(False, [], 0, "YAML root is not a mapping")

    issues: list[SelectorIssue] = []
    checked = 0

    for scene_path, action_key, action in _walk_actions(parsed):
        action_type = action.get("type")
        if action_type in {"click", "input", "scrollTo"}:
            checked += 1

        ok, reason = _verify_action(agent, action, selector_wait)
        if not ok:
            selector = action.get("selector", "") if isinstance(action, dict) else ""
            issues.append(
                SelectorIssue(
                    scene_path=scene_path,
                    action_path=action_key,
                    action_type=action_type or "?",
                    selector=selector,
                    reason=reason or "unknown",
                )
            )

    return VerificationResult(ok=not issues, issues=issues, selectors_checked=checked)


def format_issues_for_llm(result: VerificationResult) -> str:
    if result.yaml_parse_error:
        return f"YAML невалиден: {result.yaml_parse_error}"
    if not result.issues:
        return "Все шаги YAML успешно прошли проверку в живом браузере."
    lines = [
        f"При попытке проиграть твой YAML в реальном браузере найдено {len(result.issues)} ошибок:"
    ]
    for i, issue in enumerate(result.issues, 1):
        sel_part = f" селектор={issue.selector!r}" if issue.selector else ""
        lines.append(
            f"  {i}. {issue.scene_path}/{issue.action_path} (type={issue.action_type}){sel_part} — {issue.reason}"
        )
    lines.append("")
    lines.append(
        "Переделай YAML, исправив именно эти проблемы. Если какой-то селектор не существует "
        "на нужной странице — либо найди через тулы реальный селектор, либо упрости сценарий "
        "(пропусти этот шаг). Не выдумывай новые селекторы наугад."
    )
    return "\n".join(lines)
