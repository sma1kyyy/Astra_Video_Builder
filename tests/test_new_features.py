"""
Тесты новых возможностей screenshot engine:
- Аннотации line и darrow
- Субтитры subplace (up/center/down)
- Синхронизация субтитров ±200ms
- Slide-переходы
- Checkpointing
"""
import json
import math
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


#Аннотации: line и darrow

class TestAnnotationTypes:
    def test_line_annotation_accepted(self):
        from core.schemas.annotation_object import AnnotationObject

        a = AnnotationObject(
            type="line",
            transparency=0.1,
            start_x=100,
            start_y=100,
            end_x=500,
            end_y=300,
        )
        assert a.type == "line"

    def test_darrow_annotation_accepted(self):
        from core.schemas.annotation_object import AnnotationObject

        a = AnnotationObject(
            type="darrow",
            transparency=0.0,
            start_x=50,
            start_y=200,
            end_x=800,
            end_y=200,
        )
        assert a.type == "darrow"

    def test_invalid_annotation_type_rejected(self):
        from pydantic import ValidationError
        from core.schemas.annotation_object import AnnotationObject

        with pytest.raises(ValidationError):
            AnnotationObject(type="circle", transparency=0.1)

    def test_line_coords_not_swapped(self):
        """Для line координаты НЕ должны автоматически нормализоваться (start < end)."""
        from core.schemas.annotation_object import AnnotationObject

        # Намеренно start > end — для line это допустимо (направление линии)
        a = AnnotationObject(
            type="line",
            transparency=0.0,
            start_x=800,
            start_y=500,
            end_x=100,
            end_y=100,
        )
        assert a.start_x == 800
        assert a.end_x == 100

    def test_square_coords_auto_normalized(self):
        """Для square перепутанные координаты должны нормализоваться."""
        from core.schemas.annotation_object import AnnotationObject

        a = AnnotationObject(
            type="square",
            transparency=0.0,
            start_x=800,
            start_y=500,
            end_x=100,
            end_y=100,
            has_manual_coords=True,
        )
        assert a.start_x < a.end_x
        assert a.start_y < a.end_y

    def test_ocr_disabled_for_line(self):
        from core.schemas.annotation_object import AnnotationObject

        a = AnnotationObject(
            type="line",
            transparency=0.0,
            start_x=0,
            start_y=0,
            end_x=100,
            end_y=100,
            ocr=True,
        )
        # OCR должен быть автоматически отключён для не-square типов
        assert a.ocr is False

    def test_ocr_disabled_for_darrow(self):
        from core.schemas.annotation_object import AnnotationObject

        a = AnnotationObject(
            type="darrow",
            transparency=0.0,
            start_x=0,
            start_y=0,
            end_x=100,
            end_y=100,
            ocr=True,
        )
        assert a.ocr is False


#Graphics utils: line и darrow

class TestGraphicsUtils:
    def _make_image(self, annot_type, start=(100, 100), end=(500, 300)):
        from engines.screenshot.graphics_utils import create_annotation_image

        img = create_annotation_image(
            width=640,
            height=360,
            annot_type=annot_type,
            start=start,
            end=end,
            color=(255, 50, 50),
            thickness=6,
        )
        return img

    def test_line_returns_correct_shape(self):
        img = self._make_image("line")
        assert img.shape == (360, 640, 4)

    def test_darrow_returns_correct_shape(self):
        img = self._make_image("darrow")
        assert img.shape == (360, 640, 4)

    def test_arrow_returns_correct_shape(self):
        img = self._make_image("arrow")
        assert img.shape == (360, 640, 4)

    def test_square_returns_correct_shape(self):
        img = self._make_image("square")
        assert img.shape == (360, 640, 4)

    def test_line_has_non_zero_pixels(self):
        img = self._make_image("line", start=(50, 50), end=(590, 310))
        # Альфа-канал должен содержать непрозрачные пиксели (нарисована линия)
        assert img[:, :, 3].max() > 0

    def test_darrow_has_pixels_near_both_ends(self):
        """darrow должна иметь пиксели у обоих концов (два наконечника)."""
        img = self._make_image("darrow", start=(50, 180), end=(590, 180))
        alpha = img[:, :, 3]
        left_region = alpha[:, :100]
        right_region = alpha[:, 540:]
        assert left_region.max() > 0, "Нет пикселей у левого конца darrow"
        assert right_region.max() > 0, "Нет пикселей у правого конца darrow"


#Slide transition

class TestSlideTransition:
    def _make_frames(self):
        frame_a = np.zeros((360, 640, 3), dtype=np.uint8)
        frame_a[:, :] = [255, 0, 0]   # красный
        frame_b = np.zeros((360, 640, 3), dtype=np.uint8)
        frame_b[:, :] = [0, 0, 255]   # синий
        return frame_a, frame_b

    @pytest.mark.parametrize("direction", [
        "slideRight", "slideLeft", "slideUp", "slideDown"
    ])
    def test_transition_start_is_frame_a(self, direction):
        from engines.screenshot.graphics_utils import make_slide_transition_frame

        frame_a, frame_b = self._make_frames()
        result = make_slide_transition_frame(frame_a, frame_b, 0.0, direction)
        # При progress=0 должен быть полностью frame_a
        assert result.shape == frame_a.shape
        np.testing.assert_array_equal(result, frame_a)

    @pytest.mark.parametrize("direction", [
        "slideRight", "slideLeft", "slideUp", "slideDown"
    ])
    def test_transition_end_is_frame_b(self, direction):
        from engines.screenshot.graphics_utils import make_slide_transition_frame

        frame_a, frame_b = self._make_frames()
        result = make_slide_transition_frame(frame_a, frame_b, 1.0, direction)
        np.testing.assert_array_equal(result, frame_b)

    @pytest.mark.parametrize("direction", [
        "slideRight", "slideLeft", "slideUp", "slideDown"
    ])
    def test_transition_midpoint_has_both_colors(self, direction):
        from engines.screenshot.graphics_utils import make_slide_transition_frame

        frame_a, frame_b = self._make_frames()
        result = make_slide_transition_frame(frame_a, frame_b, 0.5, direction)
        # На середине должны быть пиксели и от A и от B
        has_red = np.any(result[:, :, 0] == 255)
        has_blue = np.any(result[:, :, 2] == 255)
        assert has_red and has_blue, (
            f"Переход {direction} на 50% не содержит оба кадра"
        )

    def test_unknown_direction_returns_frame_a(self):
        from engines.screenshot.graphics_utils import make_slide_transition_frame

        frame_a, frame_b = self._make_frames()
        result = make_slide_transition_frame(frame_a, frame_b, 0.5, "unknown")
        np.testing.assert_array_equal(result, frame_a)

    def test_output_shape_preserved(self):
        from engines.screenshot.graphics_utils import make_slide_transition_frame

        frame_a, frame_b = self._make_frames()
        for direction in ["slideRight", "slideLeft", "slideUp", "slideDown"]:
            result = make_slide_transition_frame(frame_a, frame_b, 0.5, direction)
            assert result.shape == frame_a.shape


#Subtitle sync

class TestSubtitleSync:
    def test_sync_within_200ms_tolerance(self):
        from engines.screenshot.screenshot_engine import _compute_subtitle_timing

        audio_duration = 4.5
        scene_duration = 6.0
        start, end = _compute_subtitle_timing(audio_duration, scene_duration)

        # Субтитры должны начаться в самом начале сцены
        assert start == 0.0

        # Конец субтитров не должен отклоняться от конца аудио более чем на 200ms
        assert abs(end - audio_duration) <= 0.2, (
            f"Субтитры заканчиваются в {end:.3f}s, аудио в {audio_duration}s — "
            f"разница {abs(end - audio_duration)*1000:.0f}ms > 200ms"
        )

    def test_subtitle_end_does_not_exceed_scene(self):
        from engines.screenshot.screenshot_engine import _compute_subtitle_timing

        # Аудио длиннее сцены — субтитры не должны выходить за сцену
        start, end = _compute_subtitle_timing(
            audio_duration=10.0, scene_duration=5.0
        )
        assert end <= 5.0

    def test_no_audio_falls_back_to_095_scene(self):
        from engines.screenshot.screenshot_engine import _compute_subtitle_timing

        start, end = _compute_subtitle_timing(
            audio_duration=0.0, scene_duration=4.0
        )
        assert abs(end - 4.0 * 0.95) < 0.01

    def test_short_audio_uses_audio_duration(self):
        from engines.screenshot.screenshot_engine import _compute_subtitle_timing

        start, end = _compute_subtitle_timing(
            audio_duration=1.5, scene_duration=8.0
        )
        assert end <= 1.5 + 0.2  # не более аудио + tolerance


#Subplace positioning

class TestSubplacePositioning:
    """Проверяем что subplace up/center/down дают разные Y-координаты."""

    def _get_subtitle_y(self, subplace: str, style: str = "classic") -> int:
        """Извлекает Y-позицию субтитров через mock."""
        from unittest.mock import patch, MagicMock

        with patch("core.utils.subtitles.TextClip") as MockText, \
             patch("core.utils.subtitles.ColorClip") as MockColor, \
             patch("core.utils.subtitles.vfx"):

            # TextClip mock
            text_instance = MagicMock()
            text_instance.h = 60
            text_instance.size = (1728, 60)
            text_instance.with_start.return_value = text_instance
            text_instance.with_duration.return_value = text_instance
            text_instance.with_position.return_value = text_instance
            text_instance.with_effects.return_value = text_instance
            MockText.return_value = text_instance

            # ColorClip mock — перехватываем with_position чтобы узнать Y
            captured_y = []
            color_instance = MagicMock()
            color_instance.h = 78

            def capture_position(pos):
                if isinstance(pos, tuple) and len(pos) == 2:
                    captured_y.append(pos[1])
                elif isinstance(pos, str):
                    pass
                return color_instance

            color_instance.with_position.side_effect = capture_position
            color_instance.with_opacity.return_value = color_instance
            color_instance.with_start.return_value = color_instance
            color_instance.with_duration.return_value = color_instance
            MockColor.return_value = color_instance

            from core.schemas.scene_object import SceneObject
            scene = SceneObject(
                path="x.png",
                subplace=subplace,
                subtitle_style=style,
                subtitle_font_size=40,
                subtitle_max_chars=90,
                subtitle_bg_opacity=0.55,
            )

            from engines.screenshot.screenshot_engine import ScreenshotEngine
            engine = ScreenshotEngine("/tmp")
            engine._build_subtitle_clips(
                scene=scene,
                subtitle_text="test text",
                scene_duration=3.0,
                audio_duration=3.0,
                video_w=1920,
                video_h=1080,
            )

            return captured_y[0] if captured_y else -1

    def test_down_has_larger_y_than_up(self):
        y_up = self._get_subtitle_y("up", "classic")
        y_down = self._get_subtitle_y("down", "classic")
        assert y_up < y_down, (
            f"up Y={y_up} должен быть меньше down Y={y_down}"
        )

    def test_center_is_between_up_and_down(self):
        y_up = self._get_subtitle_y("up", "classic")
        y_center = self._get_subtitle_y("center", "classic")
        y_down = self._get_subtitle_y("down", "classic")
        assert y_up < y_center < y_down, (
            f"center Y={y_center} должен быть между up={y_up} и down={y_down}"
        )


#Checkpointing

class TestCheckpointing:
    def test_checkpoint_save_and_load(self, tmp_path):
        from engines.screenshot.screenshot_engine import (
            _save_checkpoint,
            _load_checkpoint,
        )

        data = {
            "scenes": {
                "scene_1": {"scene_name": "intro", "audio_duration": 3.5},
                "scene_2": {"scene_name": "main", "audio_duration": 5.0},
            },
            "total": 2,
        }
        _save_checkpoint(str(tmp_path), "TestVideo", data)
        loaded = _load_checkpoint(str(tmp_path), "TestVideo")

        assert loaded["total"] == 2
        assert "scene_1" in loaded["scenes"]
        assert loaded["scenes"]["scene_2"]["audio_duration"] == 5.0

    def test_checkpoint_file_created(self, tmp_path):
        from engines.screenshot.screenshot_engine import (
            _save_checkpoint,
            _checkpoint_path,
        )

        _save_checkpoint(str(tmp_path), "MyVideo", {"scenes": {}, "total": 0})
        cp_path = _checkpoint_path(str(tmp_path), "MyVideo")
        assert os.path.exists(cp_path)

    def test_checkpoint_cleared_on_success(self, tmp_path):
        from engines.screenshot.screenshot_engine import (
            _save_checkpoint,
            _clear_checkpoint,
            _checkpoint_path,
        )

        _save_checkpoint(str(tmp_path), "MyVideo", {"scenes": {}, "total": 0})
        assert os.path.exists(_checkpoint_path(str(tmp_path), "MyVideo"))

        _clear_checkpoint(str(tmp_path), "MyVideo")
        assert not os.path.exists(_checkpoint_path(str(tmp_path), "MyVideo"))

    def test_load_missing_checkpoint_returns_empty(self, tmp_path):
        from engines.screenshot.screenshot_engine import _load_checkpoint

        result = _load_checkpoint(str(tmp_path), "NonExistent")
        assert result == {}

    def test_load_corrupt_checkpoint_returns_empty(self, tmp_path):
        from engines.screenshot.screenshot_engine import (
            _load_checkpoint,
            _checkpoint_path,
        )

        cp_path = _checkpoint_path(str(tmp_path), "Corrupt")
        with open(cp_path, "w") as f:
            f.write("not valid json {{{")

        result = _load_checkpoint(str(tmp_path), "Corrupt")
        assert result == {}

    def test_checkpoint_survives_reraise(self, tmp_path):
        """Checkpoint должен остаться после ошибки (для resume)."""
        from engines.screenshot.screenshot_engine import (
            _save_checkpoint,
            _checkpoint_path,
        )

        _save_checkpoint(
            str(tmp_path),
            "CrashVideo",
            {"scenes": {"scene_1": {"scene_name": "ok"}}, "total": 1},
        )

        # Симулируем упавший рендер — checkpoint НЕ должен удаляться
        cp_path = _checkpoint_path(str(tmp_path), "CrashVideo")
        assert os.path.exists(cp_path)

        loaded = json.loads(Path(cp_path).read_text())
        assert loaded["scenes"]["scene_1"]["scene_name"] == "ok"

    def test_checkpoint_not_present_after_successful_render(self, tmp_path):
        """После успешного рендера checkpoint должен исчезнуть."""
        from engines.screenshot.screenshot_engine import (
            _save_checkpoint,
            _clear_checkpoint,
            _checkpoint_path,
        )

        _save_checkpoint(str(tmp_path), "Done", {"scenes": {}, "total": 3})
        _clear_checkpoint(str(tmp_path), "Done")

        assert not os.path.exists(_checkpoint_path(str(tmp_path), "Done"))