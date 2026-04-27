import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture
def make_action():
    from core.schemas.action_object import ActionObject

    def _make(**kwargs):
        defaults = {"type": "wait", "duration": 0, "wait": 0}
        defaults.update(kwargs)
        return ActionObject(**defaults)

    return _make


@pytest.fixture
def make_metadata():
    from core.schemas.metadata_object import MetadataObject

    def _make(**kwargs):
        defaults = {
            "title": "TestVideo",
            "resolution": "1920x1080",
            "mode": "live",
            "browser": "chrome",
            "cursor": False,
            "fps": 30,
            "save_files": False,
        }
        defaults.update(kwargs)
        return MetadataObject(**defaults)

    return _make


@pytest.fixture
def make_scene(make_action):
    from core.schemas.scene_object import SceneObject

    def _make(actions=None, tts="", voice="jane", duration=1.0, name="scene"):
        return SceneObject(
            name=name,
            duration=duration,
            tts=tts,
            voice=voice,
            actions=actions or [],
        )

    return _make
