import wave
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def _make_silent_wav(path: Path, duration: float = 1.0, rate: int = 16000) -> None:
    frames = int(duration * rate)
    with wave.open(str(path), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(rate)
        f.writeframes(b"\x00\x00" * frames)


class TestRunLiveModeOrder:
    def test_first_action_must_be_navigate(self, make_metadata, make_scene, make_action, tmp_path):
        from main import _run_live_mode

        wait_action = make_action(type="wait", duration=1)
        scene = make_scene(actions=[wait_action])
        video = MagicMock(metadata=make_metadata(), acts=[MagicMock(scenes=[scene])])

        with patch("engines.live.browser_engine.get_driver") as gd, \
             patch("engines.live.browser_engine.quit_driver"), \
             patch("engines.live.browser_engine.start_actions"), \
             patch("engines.live.screen_recorder.start_record") as sr, \
             patch("engines.live.screen_recorder.stop_record"), \
             patch("engines.live.video_engine.live_recording_render"):
            gd.return_value = MagicMock()
            _run_live_mode(video, str(tmp_path))
            sr.assert_not_called()

    def test_browser_started_before_recording(self, make_metadata, make_scene, make_action, tmp_path):
        from main import _run_live_mode

        order = []

        def gd_track(*a, **kw):
            order.append("driver")
            return MagicMock()

        def sr_track(*a, **kw):
            order.append("record")
            return MagicMock()

        scene = make_scene(actions=[make_action(type="navigate", url="https://x.com")])
        video = MagicMock(metadata=make_metadata(), acts=[MagicMock(scenes=[scene])])

        with patch("engines.live.browser_engine.get_driver", side_effect=gd_track), \
             patch("engines.live.browser_engine.quit_driver"), \
             patch("engines.live.browser_engine.start_actions"), \
             patch("engines.live.screen_recorder.start_record", side_effect=sr_track), \
             patch("engines.live.screen_recorder.stop_record"), \
             patch("engines.live.video_engine.live_recording_render"):
            _run_live_mode(video, str(tmp_path))

        assert order.index("driver") < order.index("record")

    def test_first_navigate_executed_before_record(self, make_metadata, make_scene, make_action, tmp_path):
        from main import _run_live_mode

        order = []
        driver = MagicMock()
        driver.get.side_effect = lambda url: order.append(("nav", url))

        def sr_track(*a, **kw):
            order.append(("record",))
            return MagicMock()

        scene = make_scene(actions=[
            make_action(type="navigate", url="https://example.com"),
            make_action(type="wait", duration=1),
        ])
        video = MagicMock(metadata=make_metadata(), acts=[MagicMock(scenes=[scene])])

        with patch("engines.live.browser_engine.get_driver", return_value=driver), \
             patch("engines.live.browser_engine.quit_driver"), \
             patch("engines.live.browser_engine.start_actions"), \
             patch("engines.live.screen_recorder.start_record", side_effect=sr_track), \
             patch("engines.live.screen_recorder.stop_record"), \
             patch("engines.live.video_engine.live_recording_render"):
            _run_live_mode(video, str(tmp_path))

        nav_idx = next(i for i, e in enumerate(order) if e[0] == "nav")
        rec_idx = next(i for i, e in enumerate(order) if e[0] == "record")
        assert nav_idx < rec_idx
        assert order[nav_idx][1] == "https://example.com"

    def test_first_navigate_popped_from_actions(self, make_metadata, make_scene, make_action, tmp_path):
        from main import _run_live_mode

        nav = make_action(type="navigate", url="https://x.com")
        wait_a = make_action(type="wait", duration=1)
        scene = make_scene(actions=[nav, wait_a])
        video = MagicMock(metadata=make_metadata(), acts=[MagicMock(scenes=[scene])])

        with patch("engines.live.browser_engine.get_driver", return_value=MagicMock()), \
             patch("engines.live.browser_engine.quit_driver"), \
             patch("engines.live.browser_engine.start_actions") as sa, \
             patch("engines.live.screen_recorder.start_record", return_value=MagicMock()), \
             patch("engines.live.screen_recorder.stop_record"), \
             patch("engines.live.video_engine.live_recording_render"):
            _run_live_mode(video, str(tmp_path))

        actions_passed_first_call = sa.call_args_list[0].args[0]
        assert nav not in actions_passed_first_call
        assert wait_a in actions_passed_first_call


class TestTTSPreGeneration:
    def test_tts_generated_before_recording(self, make_metadata, make_scene, make_action, tmp_path):
        from main import _run_live_mode

        order = []

        def speech_track(filepath, *a, **kw):
            order.append("tts")
            _make_silent_wav(Path(filepath), duration=1.0)

        def record_track(*a, **kw):
            order.append("record")
            return MagicMock()

        scene = make_scene(
            actions=[make_action(type="navigate", url="https://x.com")],
            tts="hello",
        )
        video = MagicMock(metadata=make_metadata(), acts=[MagicMock(scenes=[scene])])

        with patch("engines.live.browser_engine.get_driver", return_value=MagicMock()), \
             patch("engines.live.browser_engine.quit_driver"), \
             patch("engines.live.browser_engine.start_actions"), \
             patch("core.utils.speech.start_speech", side_effect=speech_track), \
             patch("engines.live.screen_recorder.start_record", side_effect=record_track), \
             patch("engines.live.screen_recorder.stop_record"), \
             patch("engines.live.video_engine.live_recording_render"):
            _run_live_mode(video, str(tmp_path))

        assert order == ["tts", "record"]

    def test_tts_skipped_when_empty(self, make_metadata, make_scene, make_action, tmp_path):
        from main import _run_live_mode

        scene = make_scene(actions=[make_action(type="navigate", url="https://x.com")], tts="")
        video = MagicMock(metadata=make_metadata(), acts=[MagicMock(scenes=[scene])])

        with patch("engines.live.browser_engine.get_driver", return_value=MagicMock()), \
             patch("engines.live.browser_engine.quit_driver"), \
             patch("engines.live.browser_engine.start_actions"), \
             patch("core.utils.speech.start_speech") as ss, \
             patch("engines.live.screen_recorder.start_record", return_value=MagicMock()), \
             patch("engines.live.screen_recorder.stop_record"), \
             patch("engines.live.video_engine.live_recording_render"):
            _run_live_mode(video, str(tmp_path))

        ss.assert_not_called()


class TestErrorRecovery:
    def test_render_called_in_finally_after_action_error(self, make_metadata, make_scene, make_action, tmp_path):
        from main import _run_live_mode

        scene = make_scene(actions=[
            make_action(type="navigate", url="https://x.com"),
            make_action(type="wait", duration=1),
        ])
        video = MagicMock(metadata=make_metadata(), acts=[MagicMock(scenes=[scene])])

        with patch("engines.live.browser_engine.get_driver", return_value=MagicMock()), \
             patch("engines.live.browser_engine.quit_driver"), \
             patch("engines.live.browser_engine.start_actions", side_effect=RuntimeError("boom")), \
             patch("engines.live.screen_recorder.start_record", return_value=MagicMock()), \
             patch("engines.live.screen_recorder.stop_record") as stop, \
             patch("engines.live.video_engine.live_recording_render"):
            _run_live_mode(video, str(tmp_path))

        stop.assert_called_once()

    def test_quit_driver_called_in_finally(self, make_metadata, make_scene, make_action, tmp_path):
        from main import _run_live_mode

        scene = make_scene(actions=[make_action(type="navigate", url="https://x.com")])
        video = MagicMock(metadata=make_metadata(), acts=[MagicMock(scenes=[scene])])

        with patch("engines.live.browser_engine.get_driver", return_value=MagicMock()), \
             patch("engines.live.browser_engine.quit_driver") as qd, \
             patch("engines.live.browser_engine.start_actions"), \
             patch("engines.live.screen_recorder.start_record", return_value=MagicMock()), \
             patch("engines.live.screen_recorder.stop_record"), \
             patch("engines.live.video_engine.live_recording_render"):
            _run_live_mode(video, str(tmp_path))

        qd.assert_called_once()
