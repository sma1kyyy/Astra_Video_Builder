import os
import sys
import wave
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from engines.live import video_engine as ve


def _make_silent_wav(path: Path, duration: float = 1.0, rate: int = 16000) -> None:
    frames = int(duration * rate)
    with wave.open(str(path), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(rate)
        f.writeframes(b"\x00\x00" * frames)


@pytest.fixture
def fake_clip():
    clip = MagicMock()
    clip.duration = 60.0
    clip.subclipped = MagicMock(return_value=MagicMock(duration=5.0, audio=None))
    return clip


class TestLiveRecordingRender:
    def test_missing_recorded_file(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            ve.live_recording_render(str(tmp_path), "Title", [[1, 0.0, 5.0]])

    def test_skips_scene_outside_video(self, tmp_path, fake_clip):
        rec = tmp_path / "T_recorded.mp4"
        rec.write_bytes(b"x")
        fake_clip.duration = 4.0

        with patch.object(ve, "VideoFileClip", return_value=fake_clip), \
             patch.object(ve, "concatenate_videoclips", return_value=MagicMock(write_videofile=MagicMock(), close=MagicMock())):
            scene_times = [[1, 0.0, 2.0], [2, 10.0, 12.0]]
            ve.live_recording_render(str(tmp_path), "T", scene_times)

    def test_no_valid_scenes_raises(self, tmp_path, fake_clip):
        rec = tmp_path / "T_recorded.mp4"
        rec.write_bytes(b"x")
        fake_clip.duration = 1.0

        with patch.object(ve, "VideoFileClip", return_value=fake_clip):
            with pytest.raises(RuntimeError, match="Не осталось"):
                ve.live_recording_render(str(tmp_path), "T", [[1, 100.0, 200.0]])

    def test_attaches_tts_audio_when_wav_exists(self, tmp_path, fake_clip):
        rec = tmp_path / "T_recorded.mp4"
        rec.write_bytes(b"x")
        wav = tmp_path / "scene_1.wav"
        _make_silent_wav(wav, duration=1.0)

        scene = MagicMock(duration=5.0)
        fake_clip.subclipped.return_value = scene
        final_mock = MagicMock()

        audio_clip = MagicMock(close=MagicMock())
        composite_mock = MagicMock()
        composite_mock.with_duration.return_value = MagicMock()

        with patch.object(ve, "VideoFileClip", return_value=fake_clip), \
             patch.object(ve, "AudioFileClip", return_value=audio_clip), \
             patch.object(ve, "CompositeAudioClip", return_value=composite_mock), \
             patch.object(ve, "concatenate_videoclips", return_value=final_mock):
            ve.live_recording_render(str(tmp_path), "T", [[1, 0.0, 5.0]])

        composite_mock.with_duration.assert_called_with(5.0)

    def test_save_files_false_removes_wavs(self, tmp_path, fake_clip):
        rec = tmp_path / "T_recorded.mp4"
        rec.write_bytes(b"x")
        wav = tmp_path / "scene_1.wav"
        _make_silent_wav(wav)

        with patch.object(ve, "VideoFileClip", return_value=fake_clip), \
             patch.object(ve, "AudioFileClip", return_value=MagicMock(close=MagicMock())), \
             patch.object(ve, "CompositeAudioClip", return_value=MagicMock(with_duration=MagicMock(return_value=MagicMock()))), \
             patch.object(ve, "concatenate_videoclips", return_value=MagicMock()):
            ve.live_recording_render(str(tmp_path), "T", [[1, 0.0, 5.0]], save_files=False)
        assert not wav.exists()

    def test_save_files_true_keeps_wavs(self, tmp_path, fake_clip):
        rec = tmp_path / "T_recorded.mp4"
        rec.write_bytes(b"x")
        wav = tmp_path / "scene_1.wav"
        _make_silent_wav(wav)

        with patch.object(ve, "VideoFileClip", return_value=fake_clip), \
             patch.object(ve, "AudioFileClip", return_value=MagicMock(close=MagicMock())), \
             patch.object(ve, "CompositeAudioClip", return_value=MagicMock(with_duration=MagicMock(return_value=MagicMock()))), \
             patch.object(ve, "concatenate_videoclips", return_value=MagicMock()):
            ve.live_recording_render(str(tmp_path), "T", [[1, 0.0, 5.0]], save_files=True)
        assert wav.exists()

    def test_last_scene_uses_open_subclip(self, tmp_path, fake_clip):
        rec = tmp_path / "T_recorded.mp4"
        rec.write_bytes(b"x")

        with patch.object(ve, "VideoFileClip", return_value=fake_clip), \
             patch.object(ve, "concatenate_videoclips", return_value=MagicMock()):
            scene_times = [[1, 0.0, 5.0], [2, 5.0, 10.0]]
            ve.live_recording_render(str(tmp_path), "T", scene_times)

        calls = fake_clip.subclipped.call_args_list
        assert len(calls) == 2
        last = calls[-1]
        assert len(last.args) == 1
