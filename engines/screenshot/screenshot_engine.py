# главный движок screenshot mode
# рендерит последовательность сцен с точными координатами, tts, субтитрами, анимациями
# все картинки 1920x1080, координаты из yaml — абсолютные пиксели
# рендерит последовательность сцен с аннотациями, tts, субтитрами, ocr
import json
import os
from difflib import SequenceMatcher
from typing import List, Tuple

import numpy as np
from PIL import Image

from moviepy import *
from moviepy.video.VideoClip import TextClip, ImageClip, ColorClip
from moviepy.video.compositing.CompositeVideoClip import CompositeVideoClip
from moviepy.video.io.VideoFileClip import VideoFileClip, AudioFileClip
from moviepy import vfx

from core.schemas.video_object import VideoObject
from core.schemas.scene_object import SceneObject
from core.schemas.annotation_object import AnnotationObject
from engines.screenshot.graphics_utils import (
    create_annotation_image,
    create_focus_mask,
    create_text_bg,
    ease_in_out,
)
from core.utils.speech import generate_speech
from engines.screenshot.ocr_utils import extract_roi, run_ocr, detect_text_candidates, is_ocr_available

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(BASE_DIR, ".."))


class ScreenshotEngine:
    def __init__(self, output_dir: str):
        # создает папки для вывода и кэша аудио
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        os.makedirs(os.path.join(output_dir, "audio_cache"), exist_ok=True)
        self.ocr_results = []

    # def _px_to_rel_pos(
    #     self,
    #     x: int,
    #     y: int,
    #     video_w: int,
    #     video_h: int,
    #     clip_w: int = None,
    #     clip_h: int = None,
    # ) -> Tuple[float, float]:
    #     # конвертирует абсолютные пиксели из yaml в относительные координаты moviepy (0.0-1.0)
    #     if clip_w is None:
    #         clip_w, clip_h = video_w, video_h

    #     rel_x = max(0.0, min(1.0, x / video_w))
    #     rel_y = max(0.0, min(1.0, y / video_h))

    #     # центрирует по размеру наложения
    #     pos_x = rel_x - (clip_w / 2) / video_w
    #     pos_y = rel_y - (clip_h / 2) / video_h

    #     return pos_x, pos_y

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

    # def _apply_fadein_animation(
    #     self, clip: VideoFileClip, duration: float, fade_dur: float = 2.0
    # ) -> VideoFileClip:
    #     # плавное появление скрина за 2 секунды
    #     return clip.with_effects([vfx.FadeIn(fade_dur)]).with_duration(duration)

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
    
    def _similarity(self, a: str, b: str) -> float:
        return SequenceMatcher(None, (a or "").lower().strip(), (b or "").lower().strip()).ratio()

    def _find_target_bbox(self, scene_np: np.ndarray, annot: AnnotationObject) -> tuple[int, int, int, int] | None:
        if not annot.target_text:
            return None

        candidates = detect_text_candidates(scene_np, lang=annot.ocr_lang, min_conf=max(annot.ocr_min_conf, 0.2))
        if not candidates:
            return None

        scored = sorted(
            [
                (self._similarity(annot.target_text, c.get("text", "")), c)
                for c in candidates
            ],
            key=lambda x: x[0],
            reverse=True,
        )

        if not scored or scored[0][0] < 0.55:
            return None

        # если совпадений несколько, можно выбрать target_index
        selected_idx = min(max(0, annot.target_index), len(scored) - 1)
        _, selected = scored[selected_idx]
        x1, y1, x2, y2 = selected["bbox"]

        x1 -= annot.auto_padding + annot.auto_expand_width
        y1 -= annot.auto_padding + annot.auto_expand_height
        x2 += annot.auto_padding + annot.auto_expand_width
        y2 += annot.auto_padding + annot.auto_expand_height

        h, w = scene_np.shape[:2]
        x1 = max(0, min(w - 2, x1))
        y1 = max(0, min(h - 2, y1))
        x2 = max(x1 + 1, min(w - 1, x2))
        y2 = max(y1 + 1, min(h - 1, y2))

        return int(x1), int(y1), int(x2), int(y2)

    def _fallback_bbox(self, video_w: int, video_h: int) -> tuple[int, int, int, int]:
        """безопасный bbox по центру кадра, если OCR недоступен и нет ручных координат."""
        box_w = int(video_w * 0.32)
        box_h = int(video_h * 0.22)
        x1 = max(0, (video_w - box_w) // 2)
        y1 = max(0, (video_h - box_h) // 2)
        x2 = min(video_w - 1, x1 + box_w)
        y2 = min(video_h - 1, y1 + box_h)
        return x1, y1, x2, y2

    def _resolve_annotation_geometry(
        self,
        annot: AnnotationObject,
        scene_np: np.ndarray,
        video_w: int,
        video_h: int,
    ) -> AnnotationObject | None:
        # копия с перезаписью координат, чтобы исходная модель не мутировалась
        resolved = AnnotationObject(**annot.__dict__.copy())

        auto_bbox = self._find_target_bbox(scene_np, resolved)
        if resolved.target_text and not auto_bbox:
            # если таргет не найден, пытаемся сначала взять ручные координаты,
            # а если их нет — рисуем безопасный fallback bbox по центру.
            if resolved.has_manual_coords and resolved.use_manual_fallback:
                auto_bbox = (resolved.start_x, resolved.start_y, resolved.end_x, resolved.end_y)
            elif resolved.use_manual_fallback:
                auto_bbox = self._fallback_bbox(video_w, video_h)
            else:
                return None

        if auto_bbox:
            resolved.start_x, resolved.start_y, resolved.end_x, resolved.end_y = auto_bbox

            # для стрелки автоматически выбираем точку старта вне bbox
            if resolved.type == "arrow":
                cx = (resolved.start_x + resolved.end_x) // 2
                cy = (resolved.start_y + resolved.end_y) // 2
                offset = max(120, int(min(video_w, video_h) * 0.09))

                if resolved.auto_from == "left":
                    resolved.start_x = max(0, cx - offset)
                    resolved.start_y = cy
                elif resolved.auto_from == "right":
                    resolved.start_x = min(video_w - 1, cx + offset)
                    resolved.start_y = cy
                elif resolved.auto_from == "top":
                    resolved.start_x = cx
                    resolved.start_y = max(0, cy - offset)
                elif resolved.auto_from == "bottom":
                    resolved.start_x = cx
                    resolved.start_y = min(video_h - 1, cy + offset)
                else:
                    # auto/center: диагональ сверху-слева
                    resolved.start_x = max(0, cx - offset)
                    resolved.start_y = max(0, cy - offset)

                resolved.end_x = cx
                resolved.end_y = cy

        return resolved

    def _build_subtitle_clips(
        self,
        scene: SceneObject,
        subtitle_text: str,
        scene_duration: float,
        video_w: int,
        video_h: int,
    ) -> List[VideoFileClip]:
        # динамическая подрезка длины
        capped = subtitle_text[: scene.subtitle_max_chars].strip()
        if len(subtitle_text) > scene.subtitle_max_chars:
            capped += "..."

        font_path = os.path.join("assets/fonts", "Regular.ttf")
        text_clip = TextClip(
            text=capped,
            font=font_path,
            font_size=scene.subtitle_font_size,
            color="white",
            stroke_color="black",
            stroke_width=2,
            size=(int(video_w * 0.9), None),
            method="caption",
        ).with_duration(scene_duration * 0.95)

        style = scene.subtitle_style

        if style == "minimal":
            text_clip = text_clip.with_position(("center", video_h - 90)).with_effects([vfx.FadeIn(0.3), vfx.FadeOut(0.3)])
            return [text_clip]

        if style == "contrast":
            bg = (
                ColorClip((int(video_w * 0.92), text_clip.h + 24), color=(0, 0, 0))
                .with_opacity(scene.subtitle_bg_opacity)
                .with_position(("center", video_h - text_clip.h - 40))
                .with_duration(scene_duration * 0.95)
            )
            text_clip = text_clip.with_position(("center", video_h - text_clip.h - 28)).with_effects([vfx.FadeIn(0.35), vfx.FadeOut(0.35)])
            return [bg, text_clip]

        if style == "cinematic":
            # lower-third с более сильной подложкой
            bar_h = max(120, int(video_h * 0.16))
            bar = (
                ColorClip((video_w, bar_h), color=(0, 0, 0))
                .with_opacity(min(0.75, scene.subtitle_bg_opacity + 0.15))
                .with_position((0, video_h - bar_h))
                .with_duration(scene_duration)
            )
            text_clip = text_clip.with_position(("center", video_h - bar_h + 20)).with_effects([vfx.FadeIn(0.45), vfx.FadeOut(0.45)])
            return [bar, text_clip]

        # classic
        bg = (
            ColorClip((int(video_w * 0.9), text_clip.h + 18), color=(0, 0, 0))
            .with_opacity(scene.subtitle_bg_opacity)
            .with_position(("center", video_h - text_clip.h - 32))
            .with_duration(scene_duration * 0.9)
        )
        text_clip = text_clip.with_position(("center", video_h - text_clip.h - 24)).with_effects([vfx.FadeIn(0.4), vfx.FadeOut(0.4)])
        return [bg, text_clip]

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

        # основной фон со зум-анимацией + fadein
        bg_clip = (
            ImageClip(scene.path)
            .with_duration(scene_duration)
            .resized((video_w, video_h))
            .with_effects(
                [
                    vfx.Resize(lambda t: 1 + 0.02 * ease_in_out(min(t / max(scene_duration, 0.01), 1))),
                    vfx.FadeIn(1.0),
                ]
            )
        )

        # применяет эффекты (черно-белый)
        if scene.effect == "black_white":
            bg_clip = bg_clip.with_effects([vfx.BlackAndWhite()])

        layers: List[VideoFileClip] = [bg_clip]

        # загружаем изображение как матрицу для OCR/умных аннотаций
        scene_np = np.array(Image.open(scene.path).convert("RGB").resize((video_w, video_h)))

        resolved_annotations: List[AnnotationObject] = []
        for a in scene.annotations:
            resolved = self._resolve_annotation_geometry(a, scene_np, video_w, video_h)
            if resolved is not None:
                resolved_annotations.append(resolved)


        # фокусные маски (квадраты затемнения)
        for annot_index, annot in enumerate(resolved_annotations, start=1):
            if annot.type == "square":
                mask_img = create_focus_mask(
                    video_w,
                    video_h,
                    annot.start_x,
                    annot.start_y,
                    annot.end_x,
                    annot.end_y,
                    opacity=int((1.0 - annot.transparency) * 90),
                )
                focus_clip = (
                    ImageClip(mask_img)
                    .with_start(annot.wait)
                    .with_duration(annot.duration or (scene_duration - annot.wait))
                    .with_effects([vfx.FadeIn(0.35), vfx.FadeOut(0.35)])
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
                            "target_text": annot.target_text,
                        }
                    )

        # графические аннотации (стрелки)
        for annot in resolved_annotations:
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
                .with_position((txt.start_x, txt.start_y))
            )

            # text_pos = (txt.start_x, txt.start_y)
            # text_clip = text_clip.with_position(text_pos)

            bg_img = create_text_bg(video_w, video_h, txt.start_x, txt.start_y, text_w, text_h, padding=25)
            bg_clip = (
                ImageClip(bg_img)
                .with_start(txt.wait)
                .with_duration(txt.duration or (scene_duration - txt.wait))
                .with_effects([vfx.FadeIn(0.4), vfx.FadeOut(0.4)])
                # .with_position(text_pos)
                .with_position((txt.start_x, txt.start_y))
            )

            layers.extend([bg_clip, text_clip])

        font_path = os.path.join("assets/fonts", "Regular.ttf")

        # субтитры с несколькими стилями 
        if tts_text and scene.subtitles:
        #     subtitle_text = (tts_text[:120] + "...") if len(tts_text) > 120 else tts_text
        #     subtitle_clip = (
        #         TextClip(
        #             text=subtitle_text,
        #             font=font_path,
        #             font_size=40,
        #             color="white",
        #             stroke_color="black",
        #             stroke_width=2,
        #             size=(int(video_w * 0.9), None),
        #             method="caption",
        #         )
        #         .with_position(("center", video_h - 100))
        #         .with_duration(scene_duration * 0.8)
        #         .with_effects([vfx.FadeIn(0.6), vfx.FadeOut(0.6)])
        #     )
        #     layers.append(subtitle_clip)

        # # 1. собираем всю визуальную композицию
        # final_scene = CompositeVideoClip(layers, size=(video_w, video_h))
            layers.extend(self._build_subtitle_clips(scene, tts_text, scene_duration, video_w, video_h))

        # # 2. длительность видео (важно сделать это ДО наложения аудио)
        # final_scene = final_scene.with_duration(scene_duration)
        final_scene = CompositeVideoClip(layers, size=(video_w, video_h)).with_duration(scene_duration)

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

        # # sidecar OCR metadata
        # if self.ocr_results:
        #     ocr_path = os.path.join(self.output_dir, f"{video_obj.metadata.title}_ocr.json")
        # всегда формируем путь заранее, чтобы исключить unboundlocal в любых ветках/исключениях
        ocr_path = os.path.join(self.output_dir, f"{video_obj.metadata.title}_ocr.json")
        try:
            with open(ocr_path, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "title": video_obj.metadata.title,
                        "resolution": video_obj.metadata.resolution,
                        "ocr_available": is_ocr_available(),
                        "results": self.ocr_results,
                    },
                    f,
                    ensure_ascii=False,
                    indent=2,
                )
            print(f"ocr metadata: {ocr_path}")
        except Exception as error:
            print(f"предупреждение: не удалось сохранить ocr metadata: {error}")

        print(f"готово: {output_file}")
        final_video.close()


def process_screenshot_video(video: VideoObject, output_path: str):
    engine = ScreenshotEngine(output_path)
    engine.render(video)