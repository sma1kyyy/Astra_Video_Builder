from __future__ import annotations

from web.backend.app.generator.browser_agent import compact_dom


def test_compact_dom_keeps_interactive_tags():
    html = """
    <html><body>
        <div>Just text</div>
        <button id="login">Войти</button>
        <a href="/about">About</a>
        <input name="q" placeholder="Поиск" type="search">
    </body></html>
    """
    dom, truncated, _ = compact_dom(html, limit=10_000)
    assert "button" in dom and "Войти" in dom
    assert "id=\"login\"" in dom
    assert "<a " in dom and 'href="/about"' in dom
    assert 'placeholder="Поиск"' in dom
    assert "Just text" not in dom
    assert truncated is False


def test_compact_dom_keeps_elements_with_testid_or_role():
    html = """
    <html><body>
        <div role="button" aria-label="close">X</div>
        <span data-testid="submit-btn">Submit</span>
        <div>noise</div>
    </body></html>
    """
    dom, _, _ = compact_dom(html, limit=10_000)
    assert 'role="button"' in dom
    assert 'aria-label="close"' in dom
    assert 'data-testid="submit-btn"' in dom
    assert "noise" not in dom


def test_compact_dom_strips_script_and_style():
    html = """
    <html><body>
        <script>alert('x')</script>
        <style>.a{color:red}</style>
        <button id="b">B</button>
    </body></html>
    """
    dom, _, _ = compact_dom(html, limit=10_000)
    assert "alert" not in dom
    assert "color:red" not in dom
    assert "id=\"b\"" in dom


def test_compact_dom_truncates_when_too_large():
    items = "".join(f'<button id="btn{i}">Item {i}</button>' for i in range(200))
    html = f"<html><body>{items}</body></html>"
    dom, truncated, _ = compact_dom(html, limit=500)
    assert truncated is True
    assert len(dom) <= 500


def test_compact_dom_dedupes_identical_signatures():
    html = """
    <html><body>
        <button>Click</button>
        <button>Click</button>
        <button>Click</button>
    </body></html>
    """
    dom, _, _ = compact_dom(html, limit=10_000)
    assert dom.count("<button text=\"Click\">") == 1


def test_compact_dom_truncates_long_attribute_values():
    long_label = "x" * 300
    html = f'<html><body><button aria-label="{long_label}">btn</button></body></html>'
    dom, _, _ = compact_dom(html, limit=10_000)
    assert "..." in dom
    assert long_label not in dom
