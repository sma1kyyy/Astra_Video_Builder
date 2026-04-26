import os
from os import path
from typing import List

from moviepy import AudioFileClip, CompositeAudioClip, VideoFileClip, concatenate_videoclips

from core.utils.logger import LoggerFactory

log = LoggerFactory.get_logger(__name__)


def live_recording_render(
    output_path: str,
    title: str,
    scene_times: List[List[float]],
    save_files: bool = False,
    warmup_offset: float = 0.0,
) -> str:
    """Финальный монтаж live recording.

    scene_times: список вида [scene_id, start_sec, end_sec]. Первая запись — это
    "warmup"-сцена с фактическим временем загрузки браузера, она будет вырезана
    из итогового видео.
    save_files: оставлять ли промежуточные TTS-файлы.
    warmup_offset: опциональное доп. смещение в секундах (если хочется срезать
    немного больше, чем длилась холодная загрузка браузера).
    """
    recorder_path = f"{output_path}/{title}_recorded.mp4"
    if not path.exists(recorder_path):
        raise FileNotFoundError(f"Запись экрана не найдена: {recorder_path}")

    video_clip = VideoFileClip(recorder_path)
    audio_clips: List[AudioFileClip] = []
    scenes = []

    try:
        warmup_end = scene_times[0][2] + warmup_offset if scene_times else 0.0
        warmup_end = max(0.0, warmup_end)

        scene_count = len(scene_times)

        for idx, (scene_id, start, end) in enumerate(scene_times):
            if idx == 0:
                continue

            adjusted_start = max(0.0, start)
            if adjusted_start >= video_clip.duration:
                log.warning("Пропускаем сцену %s — старт %.2f выходит за видео %.2f",
                            scene_id, adjusted_start, video_clip.duration)
                continue

            if idx == scene_count - 1:
                scene = video_clip.subclipped(adjusted_start)
            else:
                scene = video_clip.subclipped(adjusted_start, min(end, video_clip.duration))

            tts_path = f"{output_path}/scene_{scene_id}.wav"
            if path.exists(tts_path):
                audio_clip = AudioFileClip(tts_path)
                audio_clips.append(audio_clip)
                scene.audio = CompositeAudioClip([audio_clip]).with_duration(scene.duration)

            scenes.append(scene)

        if not scenes:
            raise RuntimeError("После обрезки warmup-сцены не осталось ни одной сцены для рендера.")

        final_clip = concatenate_videoclips(scenes)
        final_path = f"{output_path}/{title}.mp4"
        final_clip.write_videofile(final_path)
        final_clip.close()
    finally:
        video_clip.close()
        for ac in audio_clips:
            try:
                ac.close()
            except Exception:
                pass

    if not save_files:
        for scene_id, _, _ in scene_times:
            tts_path = f"{output_path}/scene_{scene_id}.wav"
            if path.exists(tts_path):
                try:
                    os.remove(tts_path)
                except OSError as exc:
                    log.warning("Не удалось удалить %s: %s", tts_path, exc)

    return final_path
