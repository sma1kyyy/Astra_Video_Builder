import inspect

from engines.screenshot.screenshot_engine import ScreenshotEngine


def test_build_subtitle_clips_signature_matches_call_site_contract():
    signature = inspect.signature(ScreenshotEngine._build_subtitle_clips)
    assert list(signature.parameters.keys()) == [
        "self",
        "scene",
        "subtitle_text",
        "scene_duration",
        "audio_duration",
        "video_w",
        "video_h",
    ]
