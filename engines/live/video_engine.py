import os
from os import path
from typing import Dict, List, Optional, Sequence

from moviepy import AudioFileClip, CompositeAudioClip, VideoFileClip, concatenate_videoclips
from moviepy.video.compositing.CompositeVideoClip import CompositeVideoClip

from core.schemas.scene_object import SceneObject
from core.utils.logger import LoggerFactory
from core.utils.subtitles import build_subtitle_clips

log = LoggerFactory.get_logger(__name__)


def _overlay_subtitles(
    scene_clip,
    scene_obj: SceneObject,
    audio_duration: float,
):
    if not getattr(scene_obj, "subtitles", False):
        return scene_clip
    tts_text = (scene_obj.tts or "").strip()
    if not tts_text:
        return scene_clip
    overlays = build_subtitle_clips(
        scene=scene_obj,
        subtitle_text=tts_text,
        scene_duration=scene_clip.duration,
        audio_duration=audio_duration,
        video_w=scene_clip.w,
        video_h=scene_clip.h,
    )
    if not overlays:
        return scene_clip
    composed = CompositeVideoClip([scene_clip, *overlays], size=(scene_clip.w, scene_clip.h))
    composed = composed.with_duration(scene_clip.duration)
    if scene_clip.audio is not None:
        composed.audio = scene_clip.audio
    return composed


def live_recording_render(
    output_path: str,
    title: str,
    scene_times: List[List[float]],
    save_files: bool = False,
    scene_objects: Optional[Sequence[SceneObject]] = None,
) -> str:
    """Финальный монтаж live recording.

    scene_times: список вида [scene_id, start_sec, end_sec], где время отсчитывается
    от старта первой сцены (рекордер уже работает на чистом окне браузера).
    save_files: оставлять ли промежуточные TTS-файлы.
    scene_objects: исходные SceneObject в том же порядке, что в scene_times — нужны
        для наложения субтитров (поля tts/subtitles/subtitle_*). Если None — субтитры
        не накладываются, поведение как раньше.
    """
    recorder_path = f"{output_path}/{title}_recorded.mp4"
    if not path.exists(recorder_path):
        raise FileNotFoundError(f"Запись экрана не найдена: {recorder_path}")

    video_clip = VideoFileClip(recorder_path)
    audio_clips: List[AudioFileClip] = []
    scenes = []

    scene_objects_by_id: Dict[int, SceneObject] = {}
    if scene_objects is not None:
        for idx, scene_obj in enumerate(scene_objects):
            scene_objects_by_id[idx + 1] = scene_obj

    try:
        scene_count = len(scene_times)

        for idx, (scene_id, start, end) in enumerate(scene_times):
            adjusted_start = max(0.0, start)
            if adjusted_start >= video_clip.duration:
                log.warning("Пропускаем сцену %s — старт %.2f выходит за видео %.2f",
                            scene_id, adjusted_start, video_clip.duration)
                continue

            if idx == scene_count - 1:
                scene = video_clip.subclipped(adjusted_start)
            else:
                scene = video_clip.subclipped(adjusted_start, min(end, video_clip.duration))

            audio_duration = 0.0
            tts_path = f"{output_path}/scene_{scene_id}.wav"
            if path.exists(tts_path):
                audio_clip = AudioFileClip(tts_path)
                audio_clips.append(audio_clip)
                audio_duration = audio_clip.duration
                scene.audio = CompositeAudioClip([audio_clip]).with_duration(scene.duration)

            scene_obj = scene_objects_by_id.get(scene_id)
            if scene_obj is not None:
                scene = _overlay_subtitles(scene, scene_obj, audio_duration)

            scenes.append(scene)

        if not scenes:
            raise RuntimeError("Не осталось ни одной сцены для рендера.")

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
