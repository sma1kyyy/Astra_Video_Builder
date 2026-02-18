# главный движок screenshot mode
# рендерит последовательность сцен с точными координатами, tts, субтитрами, анимациями
# все картинки 1920x1080, координаты из yaml — абсолютные пиксели
import json
import os
from typing import List, Tuple

import numpy as np
from PIL import Image

from moviepy import *
from moviepy.video.VideoClip import TextClip, ImageClip
from moviepy.video.compositing.CompositeVideoClip import CompositeVideoClip
from moviepy.video.io.VideoFileClip import VideoFileClip, AudioFileClip
from moviepy import vfx

from core.schemas.video_object import VideoObject
from core.schemas.scene_object import SceneObject
from engines.screenshot.graphics_utils import (
    create_annotation_image,
    create_focus_mask,
    create_text_bg,
    ease_in_out,
)
from core.utils.speech import generate_speech
from engines.screenshot.ocr_utils import extract_roi, run_ocr

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(BASE_DIR, ".."))


class ScreenshotEngine:
    def __init__(self, output_dir: str):
        # создает папки для вывода и кэша аудио
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        os.makedirs(os.path.join(output_dir, "audio_cache"), exist_ok=True)
        self.ocr_results = []

    def _px_to_rel_pos(
        self,
        x: int,
        y: int,
        video_w: int,
        video_h: int,
        clip_w: int = None,
        clip_h: int = None,
    ) -> Tuple[float, float]:
        # конвертирует абсолютные пиксели из yaml в относительные координаты moviepy (0.0-1.0)
        if clip_w is None:
            clip_w, clip_h = video_w, video_h

        rel_x = max(0.0, min(1.0, x / video_w))
        rel_y = max(0.0, min(1.0, y / video_h))

        # центрирует по размеру наложения
        pos_x = rel_x - (clip_w / 2) / video_w
        pos_y = rel_y - (clip_h / 2) / video_h

        return pos_x, pos_y

    def _get_text_size(self, text: str, fontsize: int) -> Tuple[int, int]:
        font_path = os.path.join("assets/fonts", "Regular.ttf")
        test_clip = TextClip(
            text=text,
            font=font_path,
            font_size=fontsize,
            color="white",
            size=(1000, None),
            method="caption",
        )
        w, h = test_clip.size
        test_clip.close()
        return w, h

    def _apply_fadein_animation(
        self, clip: VideoFileClip, duration: float, fade_dur: float = 2.0
    ) -> VideoFileClip:
        # плавное появление скрина за 2 секунды
        return clip.with_effects([vfx.FadeIn(fade_dur)]).with_duration(duration)

    def _make_ocr_overlay(self, text: str, bbox: tuple[int, int, int, int], duration: float, wait: float):
        x1, y1, x2, _ = bbox
        width = max(220, (x2 - x1) + 80)
        label_x = x1
        label_y = max(20, y1 - 58)

        txt = TextClip(
            text=text,
            font=os.path.join("assets/fonts", "SemiBold.ttf"),
            font_size=30,
            color="white",
            method="caption",
            size=(width, None),
        )

        bg = (
            ColorClip((txt.size[0] + 24, txt.size[1] + 16), color=(0, 0, 0))
            .with_opacity(0.65)
            .with_start(wait)
            .with_duration(duration)
            .with_position((label_x - 12, label_y - 8))
        )

        txt = (
            txt.with_start(wait)
            .with_duration(duration)
            .with_position((label_x, label_y))
            .with_effects([vfx.FadeIn(0.25), vfx.FadeOut(0.25)])
        )

        return [bg, txt]

    def _process_scene(self, scene: SceneObject, res: Tuple[int, int], scene_index: int) -> VideoFileClip:
        # обрабатывает одну сцену: фон + анимации + текст + аннотации + tts + субтитры
        video_w, video_h = res

        # генерирует tts из scene.tts или объединяет все тексты сцены
        tts_text = scene.tts or " ".join([txt.text for txt in scene.texts])
        audio_path, audio_duration = generate_speech(tts_text, scene.voice)
        scene_duration = max(scene.duration, audio_duration) if audio_path else scene.duration

        # проверяет наличие фона
        if not os.path.exists(scene.path):
            raise FileNotFoundError(f"файл не найден: {scene.path}")

        # основной фон со зум-анимацией + fadein 2 сек
        bg_clip = (
            ImageClip(scene.path)
            .with_duration(scene_duration)
            .resized((video_w, video_h))
            .with_effects(
                [
                    vfx.Resize(lambda t: 1 + 0.02 * ease_in_out(min(t / scene_duration, 1))),
                    vfx.FadeIn(2.0),
                ]
            )
        )

        # применяет эффекты (черно-белый)
        if scene.effect == "black_white":
            bg_clip = bg_clip.with_effects([vfx.BlackAndWhite()])

        layers: List[VideoFileClip] = [bg_clip]

        # загружаем изображение как матрицу для OCR
        scene_np = np.array(Image.open(scene.path).convert("RGB").resize((video_w, video_h)))

        # фокусные маски (квадраты затемнения)
        for annot_index, annot in enumerate(scene.annotations, start=1):
            if annot.type == "square":
                mask_img = create_focus_mask(
                    video_w,
                    video_h,
                    annot.start_x,
                    annot.start_y,
                    annot.end_x,
                    annot.end_y,
                    opacity=int(255 * annot.transparency),
                )
                focus_clip = (
                    ImageClip(mask_img)
                    .with_start(annot.wait)
                    .with_duration(annot.duration or (scene_duration - annot.wait))
                    .with_effects([vfx.FadeIn(0.4), vfx.FadeOut(0.4)])
                )
                layers.append(focus_clip)

            # OCR для square аннотации
            if annot.ocr and annot.type == "square":
                roi, bbox = extract_roi(
                    scene_np,
                    annot.start_x,
                    annot.start_y,
                    annot.end_x,
                    annot.end_y,
                )

                ocr_data = run_ocr(roi, annot.ocr_lang, annot.ocr_min_conf)
                ocr_text = str(ocr_data.get("text", "")).strip()
                ocr_conf = float(ocr_data.get("confidence", 0.0))

                overlay_needed = annot.ocr_target in ["overlay", "both"]
                metadata_needed = annot.ocr_target in ["metadata", "both"]
                clip_duration = annot.duration or (scene_duration - annot.wait)

                if overlay_needed and ocr_text:
                    layers.extend(self._make_ocr_overlay(ocr_text, bbox, clip_duration, annot.wait))

                if metadata_needed:
                    self.ocr_results.append(
                        {
                            "scene_index": scene_index,
                            "annotation_index": annot_index,
                            "bbox": {
                                "left": bbox[0],
                                "top": bbox[1],
                                "right": bbox[2],
                                "bottom": bbox[3],
                            },
                            "lang": annot.ocr_lang,
                            "min_conf": annot.ocr_min_conf,
                            "confidence": ocr_conf,
                            "text": ocr_text,
                        }
                    )

        # графические аннотации (стрелки)
        for annot in scene.annotations:
            if annot.type == "arrow":
                arrow_img = create_annotation_image(
                    video_w,
                    video_h,
                    annot.type,
                    (annot.start_x, annot.start_y),
                    (annot.end_x, annot.end_y),
                    thickness=10,
                )
                arrow_clip = (
                    ImageClip(arrow_img)
                    .with_start(annot.wait)
                    .with_duration(annot.duration or (scene_duration - annot.wait))
                    .with_opacity(1.0 - annot.transparency)
                    .with_effects([vfx.FadeIn(0.3), vfx.FadeOut(0.3)])
                )
                layers.append(arrow_clip)

        # текстовые блоки с подложкой
        for txt in scene.texts:
            text_w, text_h = self._get_text_size(txt.text, int(txt.size))

            font_path = os.path.join("assets/fonts", "SemiBold.ttf")

            text_clip = (
                TextClip(
                    text=txt.text,
                    font=font_path,
                    font_size=int(txt.size),
                    color="white",
                    stroke_color="black",
                    stroke_width=3,
                    size=(int(text_w * 0.95), None),
                    method="caption",
                )
                .with_start(txt.wait)
                .with_duration(txt.duration or (scene_duration - txt.wait))
                .with_effects([vfx.FadeIn(0.4), vfx.FadeOut(0.4)])
            )

            text_pos = (txt.start_x, txt.start_y)
            text_clip = text_clip.with_position(text_pos)

            bg_img = create_text_bg(video_w, video_h, txt.start_x, txt.start_y, text_w, text_h, padding=25)
            bg_clip = (
                ImageClip(bg_img)
                .with_start(txt.wait)
                .with_duration(txt.duration or (scene_duration - txt.wait))
                .with_effects([vfx.FadeIn(0.4), vfx.FadeOut(0.4)])
                .with_position(text_pos)
            )

            layers.extend([bg_clip, text_clip])

        font_path = os.path.join("assets/fonts", "Regular.ttf")

        # субтитры снизу экрана
        if tts_text and scene.subtitles:
            subtitle_text = (tts_text[:120] + "...") if len(tts_text) > 120 else tts_text
            subtitle_clip = (
                TextClip(
                    text=subtitle_text,
                    font=font_path,
                    font_size=40,
                    color="white",
                    stroke_color="black",
                    stroke_width=2,
                    size=(int(video_w * 0.9), None),
                    method="caption",
                )
                .with_position(("center", video_h - 100))
                .with_duration(scene_duration * 0.8)
                .with_effects([vfx.FadeIn(0.6), vfx.FadeOut(0.6)])
            )
            layers.append(subtitle_clip)

        # 1. собираем всю визуальную композицию
        final_scene = CompositeVideoClip(layers, size=(video_w, video_h))

        # 2. длительность видео (важно сделать это ДО наложения аудио)
        final_scene = final_scene.with_duration(scene_duration)

        # 3. визуальные переходы
        if scene.transition == "blackout":
            final_scene = final_scene.with_effects([vfx.FadeIn(scene.transpeed)])

        if final_scene.audio is None:
            from moviepy.audio.AudioClip import AudioClip

            silent_audio = AudioClip(lambda t: np.zeros((1,)), duration=final_scene.duration, fps=44100)
            final_scene = final_scene.with_audio(silent_audio)

        # накладывает tts аудио
        if audio_path and os.path.exists(audio_path):
            audio_clip = AudioFileClip(audio_path)
            safe_duration = min(audio_clip.duration, scene_duration) - 0.01
            if safe_duration > 0:
                audio_clip = audio_clip.subclipped(0, safe_duration)
            final_scene = final_scene.with_audio(audio_clip)

        return final_scene

    def render(self, video_obj: VideoObject):
        print(f"рендер проекта: {video_obj.metadata.title}")

        res = tuple(map(int, video_obj.metadata.resolution.lower().split("x")))
        print(f"разрешение: {res[0]}x{res[1]}, fps: {video_obj.metadata.fps}")

        all_scenes = []

        for act in video_obj.acts:
            print(f"акт: {act.name}")
            for scene_index, scene in enumerate(act.scenes, start=1):
                print(f"  сцена: {scene.name} ({scene.duration}s)")
                scene_clip = self._process_scene(scene, res, scene_index)
                all_scenes.append(scene_clip)

        final_video = concatenate_videoclips(all_scenes, method="chain")
        output_file = os.path.join(self.output_dir, f"{video_obj.metadata.title}.mp4")

        final_video.write_videofile(
            output_file,
            fps=video_obj.metadata.fps,
            codec="libx264",
            audio_codec="libmp3lame",
            audio_bitrate="192k",
            remove_temp=True,
            audio_fps=44100,
            write_logfile=True,
            threads=4,
            logger="bar",
        )

        # sidecar OCR metadata
        if self.ocr_results:
            ocr_path = os.path.join(self.output_dir, f"{video_obj.metadata.title}_ocr.json")
            with open(ocr_path, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "title": video_obj.metadata.title,
                        "resolution": video_obj.metadata.resolution,
                        "results": self.ocr_results,
                    },
                    f,
                    ensure_ascii=False,
                    indent=2,
                )
            print(f"ocr metadata: {ocr_path}")

        print(f"готово: {output_file}")
        final_video.close()


def process_screenshot_video(video: VideoObject, output_path: str):
    engine = ScreenshotEngine(output_path)
    engine.render(video)