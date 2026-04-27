import pytest

from web.backend.app.schemas import (
    AnnotationPayload,
    MetadataPayload,
    ScenePayload,
    ScriptPayload,
)


def _payload(**overrides):
    base = {
        "metadata": {"title": "demo", "resolution": "1920x1080", "fps": 24},
        "scenes": [
            {"name": "s1", "path": "screen1.png", "duration": 4.0,
             "annotations": []},
        ],
    }
    base.update(overrides)
    return base


def test_metadata_validates_title_pattern():
    with pytest.raises(Exception):
        MetadataPayload(title="bad name!", resolution="1920x1080")


def test_metadata_validates_resolution():
    with pytest.raises(Exception):
        MetadataPayload(title="demo", resolution="HD")


def test_metadata_fps_bounds():
    with pytest.raises(Exception):
        MetadataPayload(title="demo", resolution="1920x1080", fps=0)


def test_annotation_transparency_bounds():
    with pytest.raises(Exception):
        AnnotationPayload(transparency=1.5)


def test_scene_requires_path():
    with pytest.raises(Exception):
        ScenePayload(name="s1", path="", duration=2.0)


def test_scene_duration_must_be_positive():
    with pytest.raises(Exception):
        ScenePayload(name="s1", path="x.png", duration=0)


def test_script_payload_minimal_ok():
    script = ScriptPayload(**_payload())
    assert script.metadata.title == "demo"
    assert len(script.scenes) == 1


def test_script_payload_rejects_empty_scenes():
    with pytest.raises(Exception):
        ScriptPayload(**_payload(scenes=[]))


def test_script_payload_rejects_unknown_field():
    bad = _payload()
    bad["scenes"][0]["unknown_field"] = 42
    with pytest.raises(Exception):
        ScriptPayload(**bad)


def test_to_yaml_dict_shape():
    script = ScriptPayload(**_payload(scenes=[
        {"name": "s1", "path": "screen1.png", "duration": 3.0,
         "annotations": [
             {"type": "square", "transparency": 0.3,
              "start_x": 10, "start_y": 10, "end_x": 50, "end_y": 50,
              "ocr": True, "text": "hi"}
         ]},
    ]))
    data = script.to_yaml_dict()
    assert data["metadata"]["mode"] == "screenshot"
    assert "act_1" in data["acts"]
    scenes = data["acts"]["act_1"]["scenes"]
    assert "scene_1" in scenes
    ann = scenes["scene_1"]["annotations"]["annotation_1"]
    assert ann["ocr"] is True
    assert ann["text"] == "hi"


def test_to_yaml_dict_omits_text_for_non_square():
    script = ScriptPayload(**_payload(scenes=[
        {"name": "s1", "path": "screen1.png", "duration": 3.0,
         "annotations": [
             {"type": "arrow", "text": "ignored"}
         ]},
    ]))
    ann = script.to_yaml_dict()["acts"]["act_1"]["scenes"]["scene_1"]["annotations"]["annotation_1"]
    assert "text" not in ann
