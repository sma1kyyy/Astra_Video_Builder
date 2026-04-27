import os
import platform
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from engines.live import screen_recorder as sr
from engines.live.screen_recorder import (
    ScreenRecorderError,
    UnsupportedPlatformError,
    _send_quit_via_stdin,
    _send_sigint,
    get_input_params,
    start_record,
    stop_record,
)


class TestGetInputParams:
    def test_windows(self):
        with patch.object(platform, "system", return_value="Windows"):
            assert get_input_params() == ("gdigrab", "desktop")

    def test_linux_xorg(self):
        with patch.object(platform, "system", return_value="Linux"), \
             patch.dict(os.environ, {}, clear=True):
            assert get_input_params() == ("x11grab", ":0.0")

    def test_linux_wayland_via_xdg(self):
        with patch.object(platform, "system", return_value="Linux"), \
             patch.dict(os.environ, {"XDG_SESSION_TYPE": "wayland"}, clear=True):
            assert get_input_params() == ("gpu-screen-recorder", "")

    def test_linux_wayland_via_display_var(self):
        with patch.object(platform, "system", return_value="Linux"), \
             patch.dict(os.environ, {"WAYLAND_DISPLAY": "wayland-1"}, clear=True):
            assert get_input_params() == ("gpu-screen-recorder", "")

    def test_unsupported_os(self):
        with patch.object(platform, "system", return_value="Plan9"):
            with pytest.raises(UnsupportedPlatformError):
                get_input_params()

    def test_macos_dynamic_screen_index(self):
        ffmpeg_output = (
            "[AVFoundation indev @ 0x...] AVFoundation video devices:\n"
            "[AVFoundation indev @ 0x...] [0] FaceTime HD Camera\n"
            "[AVFoundation indev @ 0x...] [1] Capture screen 0\n"
            "[AVFoundation indev @ 0x...] [2] Capture screen 1\n"
        )
        fake_result = MagicMock(stderr=ffmpeg_output, stdout="")
        with patch.object(platform, "system", return_value="Darwin"), \
             patch.object(subprocess, "run", return_value=fake_result):
            backend, device = get_input_params()
            assert backend == "avfoundation"
            assert device == "1:none"

    def test_macos_no_capture_screen_raises(self):
        fake_result = MagicMock(stderr="no screens found", stdout="")
        with patch.object(platform, "system", return_value="Darwin"), \
             patch.object(subprocess, "run", return_value=fake_result):
            with pytest.raises(UnsupportedPlatformError, match="Capture screen"):
                get_input_params()

    def test_macos_ffmpeg_missing(self):
        with patch.object(platform, "system", return_value="Darwin"), \
             patch.object(subprocess, "run", side_effect=FileNotFoundError("ffmpeg")):
            with pytest.raises(UnsupportedPlatformError):
                get_input_params()


class TestStartRecord:
    @pytest.fixture
    def metadata(self):
        from core.schemas.metadata_object import MetadataObject
        return MetadataObject(title="T", resolution="1920x1080", fps=30, cursor=False)

    def test_start_record_wayland_calls_gpu_recorder(self, metadata, tmp_path):
        with patch.object(sr, "get_input_params", return_value=("gpu-screen-recorder", "")), \
             patch.object(subprocess, "Popen") as popen:
            popen.return_value = MagicMock()
            start_record(metadata, str(tmp_path))
            args = popen.call_args[0][0]
            assert "gpu-screen-recorder" in args
            assert "-cursor" in args
            assert "no" in args
            assert str(tmp_path) in " ".join(args)

    def test_start_record_wayland_cursor_true(self, metadata, tmp_path):
        metadata_cursor = type(metadata)(
            title="T", resolution="1920x1080", fps=30, cursor=True,
        )
        with patch.object(sr, "get_input_params", return_value=("gpu-screen-recorder", "")), \
             patch.object(subprocess, "Popen") as popen:
            popen.return_value = MagicMock()
            start_record(metadata_cursor, str(tmp_path))
            args = popen.call_args[0][0]
            idx = args.index("-cursor")
            assert args[idx + 1] == "yes"

    def test_start_record_gpu_recorder_missing(self, metadata, tmp_path):
        with patch.object(sr, "get_input_params", return_value=("gpu-screen-recorder", "")), \
             patch.object(subprocess, "Popen", side_effect=FileNotFoundError("gpu-screen-recorder")):
            with pytest.raises(ScreenRecorderError):
                start_record(metadata, str(tmp_path))

    def test_start_record_x11grab_uses_ffmpeg_with_draw_mouse(self, metadata, tmp_path):
        captured = {}

        class FakeFFmpeg:
            def input(self, device, **kwargs):
                captured["device"] = device
                captured["kwargs"] = kwargs
                return self
            def output(self, *args, **kwargs):
                return self
            def overwrite_output(self):
                return self
            def run_async(self, **kwargs):
                return MagicMock()

        with patch.object(sr, "get_input_params", return_value=("x11grab", ":0.0")), \
             patch.object(sr, "ffmpeg", FakeFFmpeg()):
            start_record(metadata, str(tmp_path))
        assert captured["kwargs"]["format"] == "x11grab"
        assert captured["kwargs"]["draw_mouse"] == 0

    def test_start_record_avfoundation_uses_capture_cursor(self, metadata, tmp_path):
        captured = {}

        class FakeFFmpeg:
            def input(self, device, **kwargs):
                captured["device"] = device
                captured["kwargs"] = kwargs
                return self
            def output(self, *args, **kwargs):
                return self
            def overwrite_output(self):
                return self
            def run_async(self, **kwargs):
                return MagicMock()

        with patch.object(sr, "get_input_params", return_value=("avfoundation", "1:none")), \
             patch.object(sr, "ffmpeg", FakeFFmpeg()):
            start_record(metadata, str(tmp_path))
        assert captured["kwargs"]["format"] == "avfoundation"
        assert captured["kwargs"]["capture_cursor"] == 0
        assert "draw_mouse" not in captured["kwargs"]


class TestStopRecord:
    def test_none_process_safe(self):
        stop_record(None)

    def test_already_dead_process_skipped(self):
        proc = MagicMock()
        proc.poll.return_value = 0
        stop_record(proc)
        proc.send_signal.assert_not_called()

    def test_sigint_path(self):
        proc = MagicMock()
        proc.poll.return_value = None
        proc.wait.return_value = None
        stop_record(proc)
        proc.send_signal.assert_called_once()

    def test_falls_through_to_kill(self):
        proc = MagicMock()
        proc.poll.return_value = None
        proc.send_signal.side_effect = OSError("nope")
        proc.stdin = None
        proc.terminate.return_value = None
        proc.wait.side_effect = subprocess.TimeoutExpired("x", 1)
        stop_record(proc)
        proc.kill.assert_called_once()

    def test_send_quit_via_stdin_no_stdin(self):
        proc = MagicMock()
        proc.stdin = None
        assert _send_quit_via_stdin(proc) is False

    def test_send_quit_via_stdin_writes_q(self):
        proc = MagicMock()
        proc.stdin = MagicMock()
        proc.wait.return_value = None
        assert _send_quit_via_stdin(proc) is True
        proc.stdin.write.assert_called_with(b"q\n")

    def test_send_sigint_handles_timeout(self):
        proc = MagicMock()
        proc.wait.side_effect = subprocess.TimeoutExpired("x", 1)
        assert _send_sigint(proc) is False
