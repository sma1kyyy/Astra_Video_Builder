"""Тесты схемы ActionObject (валидация полей, normalization, type coercion)."""
import pytest
from pydantic import ValidationError

from core.schemas.action_object import ActionObject


class TestActionObjectValidation:
    def test_navigate_requires_url(self):
        with pytest.raises((ValidationError, AssertionError)):
            ActionObject(type="navigate")

    def test_navigate_with_url_ok(self):
        a = ActionObject(type="navigate", url="https://example.com")
        assert a.url == "https://example.com"

    def test_click_requires_selector(self):
        with pytest.raises((ValidationError, AssertionError)):
            ActionObject(type="click")

    def test_input_requires_selector(self):
        with pytest.raises((ValidationError, AssertionError)):
            ActionObject(type="input", text="hello")

    def test_scrollto_requires_selector(self):
        with pytest.raises((ValidationError, AssertionError)):
            ActionObject(type="scrollTo")

    def test_wait_no_extras_required(self):
        a = ActionObject(type="wait", duration=2)
        assert a.duration == 2

    def test_scrollup_with_point(self):
        a = ActionObject(type="scrollUp", point=100)
        assert a.type == "scrollUp"
        assert a.point == 100


class TestActionObjectNormalization:
    @pytest.mark.parametrize("input_type,expected", [
        ("scrollup", "scrollUp"),
        ("scrolldown", "scrollDown"),
        ("scrollto", "scrollTo"),
        ("SCROLLUP", "scrollUp"),
        ("ScrollDown", "scrollDown"),
        ("scrollUp", "scrollUp"),
        ("navigate", "navigate"),
    ])
    def test_scroll_aliases_normalized(self, input_type, expected):
        kwargs = {"type": input_type}
        if expected == "scrollTo":
            kwargs["selector"] = "//div"
        elif expected.startswith("scroll"):
            kwargs["point"] = 10
        elif expected == "navigate":
            kwargs["url"] = "https://example.com"
        a = ActionObject(**kwargs)
        assert a.type == expected


class TestActionObjectTextCoercion:
    def test_text_int_to_str(self):
        a = ActionObject(type="input", selector="//input", text=12345)
        assert a.text == "12345"

    def test_text_float_to_str(self):
        a = ActionObject(type="input", selector="//input", text=3.14)
        assert a.text == "3.14"

    def test_text_str_passthrough(self):
        a = ActionObject(type="input", selector="//input", text="hello")
        assert a.text == "hello"

    def test_text_none_default(self):
        a = ActionObject(type="wait", duration=1)
        assert a.text == ""


class TestActionObjectEnterField:
    def test_enter_default_true(self):
        a = ActionObject(type="input", selector="//x", text="t")
        assert a.enter is True

    def test_enter_explicit_false(self):
        a = ActionObject(type="input", selector="//x", text="t", enter=False)
        assert a.enter is False


class TestActionObjectBehavior:
    def test_behavior_none_becomes_python_none(self):
        a = ActionObject(type="scrollUp", point=10, behavior="none")
        assert a.behavior is None

    def test_behavior_smooth_preserved(self):
        a = ActionObject(type="scrollUp", point=10, behavior="smooth")
        assert a.behavior == "smooth"


class TestActionObjectConstraints:
    def test_negative_duration_rejected(self):
        with pytest.raises(ValidationError):
            ActionObject(type="wait", duration=-1)

    def test_negative_point_rejected(self):
        with pytest.raises(ValidationError):
            ActionObject(type="scrollUp", point=-1)

    def test_negative_wait_rejected(self):
        with pytest.raises(ValidationError):
            ActionObject(type="wait", duration=1, wait=-1)

    def test_invalid_url_pattern(self):
        with pytest.raises(ValidationError):
            ActionObject(type="navigate", url="not_a_url")

    def test_invalid_selector_pattern(self):
        with pytest.raises(ValidationError):
            ActionObject(type="click", selector="just_text_no_xpath")
