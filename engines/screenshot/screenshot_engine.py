# главный движок screenshot mode
# рендерит последовательность сцен с точными координатами, tts, субтитрами,
# аннотациями (square/line/arrow/darrow), slide-переходами и checkpointing.
import json
import os
from difflib import SequenceMatcher
import shutil
from dataclasses import replace
from typing import List, Optional, Tuple

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
    make_slide_transition_frame,
)
from core.utils.speech import generate_speech
from engines.screenshot.ocr_utils import (
    extract_roi,
    run_ocr,
    detect_text_candidates,
    is_ocr_available,
)
from core.utils.logger import LoggerFactory

log = LoggerFactory.get_logger(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(BASE_DIR, "../.."))
FONTS_DIR = os.path.join(PROJECT_ROOT, "assets", "fonts")

# Типы аннотаций, которые рисуются как линии (не требуют focus-mask)
_LINE_TYPES = {"line", "arrow", "darrow"}
# Типы slide-переходов
_SLIDE_TRANSITIONS = {"slideRight", "slideLeft", "slideUp", "slideDown"}


#Checkpoint helpers

def _checkpoint_path(output_dir: str, title: str) -> str:
    return os.path.join(output_dir, f".{title}_checkpoint.json")


def _load_checkpoint(output_dir: str, title: str) -> dict:
    """Загружает checkpoint если он существует и валиден."""
    path = _checkpoint_path(output_dir, title)
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        log.info("Найден checkpoint: %d сцен уже обработано", len(data.get("scenes", {})))
        return data
    except Exception as exc:
        log.warning("Не удалось прочитать checkpoint: %s — начинаем заново", exc)
        return {}


def _save_checkpoint(output_dir: str, title: str, data: dict) -> None:
    """Сохраняет текущее состояние обработки."""
    path = _checkpoint_path(output_dir, title)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as exc:
        log.warning("Не удалось сохранить checkpoint: %s", exc)


def _clear_checkpoint(output_dir: str, title: str) -> None:
    path = _checkpoint_path(output_dir, title)
    try:
        if os.path.exists(path):
            os.remove(path)
    except Exception:
        pass


#Subtitle sync

# Допустимая погрешность синхронизации субтитров в секундах (ТЗ: ±200ms)
_SUBTITLE_SYNC_TOLERANCE = 0.2


def _compute_subtitle_timing(
    audio_duration: float,
    scene_duration: float,
    fade_in: float = 0.3,
    fade_out: float = 0.3,
) -> Tuple[float, float]:
    """
    Вычисляет start/end субтитров так, чтобы они точно совпадали
    с озвучкой в пределах ±200ms (требование ТЗ раздел 8).

    Возвращает (subtitle_start, subtitle_end).
    """
    # Субтитры появляются вместе со звуком (start = 0 для сцены)
    subtitle_start = 0.0

    if audio_duration > 0:
        # Заканчиваем субтитры ровно с концом аудио, но не позже сцены
        raw_end = min(audio_duration, scene_duration)
        # Убеждаемся что fade_out не выходит за границу
        subtitle_end = max(raw_end, fade_in + fade_out + _SUBTITLE_SYNC_TOLERANCE)
        subtitle_end = min(subtitle_end, scene_duration)
    else:
        subtitle_end = scene_duration * 0.95

    return subtitle_start, subtitle_end


#Slide transition

def _build_slide_transition_clip(
    clip_a: ImageClip,
    clip_b: ImageClip,
    direction: str,
    duration: float,
    video_w: int,
    video_h: int,
) -> VideoFileClip:
    """
    Строит клип slide-перехода между clip_a (уходящий) и clip_b (входящий).
    Длительность перехода — duration секунд.
    """
    fps = 30

    # Берём последний кадр clip_a и первый кадр clip_b как статичные изображения
    frame_a = clip_a.get_frame(clip_a.duration - 0.001)
    frame_b = clip_b.get_frame(0)

    # Убеждаемся что форма совпадает
    if frame_a.shape != frame_b.shape:
        img_b = Image.fromarray(frame_b.astype(np.uint8)).resize(
            (video_w, video_h), Image.LANCZOS
        )
        frame_b = np.array(img_b)

    def make_frame(t: float) -> np.ndarray:
        progress = t / max(duration, 1e-6)
        return make_slide_transition_frame(
            frame_a.astype(np.uint8),
            frame_b.astype(np.uint8),
            progress,
            direction,
        )

    transition = VideoClip(make_frame, duration=duration)
    transition = transition.with_fps(fps)
    return transition


#Main engine

class ScreenshotEngine:
    def __init__(self, output_dir: str):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        os.makedirs(os.path.join(output_dir, "audio_cache"), exist_ok=True)
        self.ocr_results: List[dict] = []

    def _get_text_size(self, text: str, fontsize: int) -> Tuple[int, int]:
        font_path = os.path.join(FONTS_DIR, "Regular.ttf")
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

    def _make_ocr_overlay(
        self,
        text: str,
        bbox: tuple,
        duration: float,
        wait: float,
    ) -> List:
        x1, y1, x2, _ = bbox
        width = max(220, (x2 - x1) + 80)
        label_x = x1
        label_y = max(20, y1 - 58)

        txt = TextClip(
            text=text,
            font=os.path.join(FONTS_DIR, "SemiBold.ttf"),
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
        return SequenceMatcher(
            None,
            (a or "").lower().strip(),
            (b or "").lower().strip(),
        ).ratio()

    def _find_target_bbox(
        self,
        scene_np: np.ndarray,
        annot: AnnotationObject,
    ) -> Optional[Tuple[int, int, int, int]]:
        if not annot.target_text:
            return None

        candidates = detect_text_candidates(
            scene_np, lang=annot.ocr_lang, min_conf=annot.ocr_min_conf
        )
        if not candidates:
            return None

        scored = sorted(
            [
                (self._similarity(annot.target_text, c.get("text", "")), c)
                for c in candidates
            ],
            key=lambda x: (-x[0], x[1]["bbox"][1], x[1]["bbox"][0]),
        )

        if not scored or scored[0][0] < 0.55:
            return None
        
        if annot.target_index >= len(scored):
            log.warning(
                "target_index=%d вне диапазона (кандидатов=%d), выбран последний.",
                annot.target_index,
                len(scored),
            )

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

    def _fallback_bbox(
        self, video_w: int, video_h: int
    ) -> Tuple[int, int, int, int]:
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
    ) -> Optional[AnnotationObject]:
        resolved = replace(annot)

        auto_bbox = self._find_target_bbox(scene_np, resolved)
        if resolved.target_text and not auto_bbox:
            if resolved.has_manual_coords and resolved.use_manual_fallback:
                auto_bbox = (
                    resolved.start_x,
                    resolved.start_y,
                    resolved.end_x,
                    resolved.end_y,
                )
            elif resolved.use_manual_fallback:
                auto_bbox = self._fallback_bbox(video_w, video_h)
            else:
                return None

        if auto_bbox:
            resolved.start_x, resolved.start_y, resolved.end_x, resolved.end_y = auto_bbox

            if resolved.type == "arrow" and not resolved.has_manual_coords:
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
        audio_duration: float,
        #subtitle_duration: float,
        video_w: int,
        video_h: int,
    ) -> List:
        """
        Строит субтитры с:
        - поддержкой subplace (up / center / down)
        - точной синхронизацией с аудио ±200ms (требование ТЗ раздел 8)
        - 4 стилями
        """
        capped = subtitle_text[: scene.subtitle_max_chars].strip()
        if len(subtitle_text) > scene.subtitle_max_chars:
            capped += "..."

        font_path = os.path.join(FONTS_DIR, "Regular.ttf")

        #Точная синхронизация с аудио
        fade_in_dur = 0.3
        fade_out_dur = 0.3
        sub_start, sub_end = _compute_subtitle_timing(
            audio_duration, scene_duration, fade_in_dur, fade_out_dur
        )
        sub_duration = max(sub_end - sub_start, 0.1)

        text_clip = TextClip(
            text=capped,
            font=font_path,
            font_size=scene.subtitle_font_size,
            color="white",
            stroke_color="black",
            stroke_width=2,
            size=(int(video_w * 0.9), None),
            method="caption",
        ).with_start(sub_start).with_duration(sub_duration)

        #Позиционирование: subplace
        subplace = getattr(scene, "subplace", "down")

        def _text_y_pos(clip_h: int) -> int:
            margin = 32
            if subplace == "up":
                return margin
            elif subplace == "center":
                return (video_h - clip_h) // 2
            else:  # down (default)
                return video_h - clip_h - margin

        style = scene.subtitle_style

        if style == "minimal":
            text_y = _text_y_pos(text_clip.h)
            text_clip = text_clip.with_position(("center", text_y)).with_effects(
                [vfx.FadeIn(fade_in_dur), vfx.FadeOut(fade_out_dur)]
            )
            return [text_clip]

        if style == "contrast":
            text_y = _text_y_pos(text_clip.h + 24)
            bg = (
                ColorClip((int(video_w * 0.92), text_clip.h + 24), color=(0, 0, 0))
                .with_opacity(scene.subtitle_bg_opacity)
                .with_start(sub_start)
                .with_duration(sub_duration)
                .with_position(("center", text_y))
            )
            text_clip = text_clip.with_position(
                ("center", text_y + 12)
            ).with_effects([vfx.FadeIn(fade_in_dur), vfx.FadeOut(fade_out_dur)])
            return [bg, text_clip]

        if style == "cinematic":
            bar_h = max(120, int(video_h * 0.16))
            if subplace == "up":
                bar_y = 0
                text_y = 20
            elif subplace == "center":
                bar_y = (video_h - bar_h) // 2
                text_y = bar_y + 20
            else:
                bar_y = video_h - bar_h
                text_y = bar_y + 20

            bar = (
                ColorClip((video_w, bar_h), color=(0, 0, 0))
                .with_opacity(min(0.75, scene.subtitle_bg_opacity + 0.15))
                .with_start(sub_start)
                .with_duration(sub_duration)
                .with_position((0, bar_y))
            )
            text_clip = text_clip.with_position(("center", text_y)).with_effects(
                [vfx.FadeIn(0.45), vfx.FadeOut(0.45)]
            )
            return [bar, text_clip]

        # classic (default)
        text_y = _text_y_pos(text_clip.h + 18)
        bg = (
            ColorClip((int(video_w * 0.9), text_clip.h + 18), color=(0, 0, 0))
            .with_opacity(scene.subtitle_bg_opacity)
            .with_start(sub_start)
            .with_duration(sub_duration)
            .with_position(("center", text_y))
        )
        text_clip = text_clip.with_position(
            ("center", text_y + 9)
        ).with_effects([vfx.FadeIn(fade_in_dur), vfx.FadeOut(fade_out_dur)])
        return [bg, text_clip]

    def _process_scene(
        self,
        scene: SceneObject,
        res: Tuple[int, int],
        scene_index: int,
        cached_clip: Optional[dict] = None,
    ) -> Tuple[VideoFileClip, dict]:
        """
        Обрабатывает одну сцену.

        Возвращает (clip, cache_entry) где cache_entry — данные для checkpoint.
        Если cached_clip передан и валиден — пропускает тяжёлые шаги (TTS уже есть).
        """
        video_w, video_h = res

        tts_text = (scene.tts or "").strip()
        audio_path, audio_duration = generate_speech(tts_text, scene.voice) if tts_text else ("", 0.0)
        base_duration = max(float(scene.duration), 0.5)
        scene_duration = max(base_duration, audio_duration) if audio_path else base_duration

        if not os.path.exists(scene.path):
            raise FileNotFoundError(f"Файл не найден: {scene.path}")

        bg_clip = (
            ImageClip(scene.path)
            .with_duration(scene_duration)
            .resized((video_w, video_h))
            .with_effects(
                [
                    vfx.Resize(
                        lambda t: 1 + 0.02 * ease_in_out(
                            min(t / max(scene_duration, 0.01), 1)
                        )
                    ),
                    vfx.FadeIn(1.0),
                ]
            )
        )

        if scene.effect == "black_white":
            bg_clip = bg_clip.with_effects([vfx.BlackAndWhite()])

        layers: List = [bg_clip]

        scene_np = np.array(
            Image.open(scene.path).convert("RGB").resize((video_w, video_h))
        )

        #Resolve all annotation geometries
        resolved_annotations: List[AnnotationObject] = []
        for a in scene.annotations:
            resolved = self._resolve_annotation_geometry(a, scene_np, video_w, video_h)
            if resolved is not None:
                resolved_annotations.append(resolved)

        #Focus masks (только для square) 
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

            # OCR для square
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
                clip_duration = annot.duration or (scene_duration - annot.wait)

                if annot.ocr_target in ["overlay", "both"] and ocr_text:
                    layers.extend(
                        self._make_ocr_overlay(ocr_text, bbox, clip_duration, annot.wait)
                    )

                if annot.ocr_target in ["metadata", "both"]:
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

        #Линейные аннотации: line, arrow, darrow 
        for annot in resolved_annotations:
            if annot.type in _LINE_TYPES:
                annot_img = create_annotation_image(
                    video_w,
                    video_h,
                    annot.type,
                    (annot.start_x, annot.start_y),
                    (annot.end_x, annot.end_y),
                    thickness=10,
                )
                annot_clip = (
                    ImageClip(annot_img)
                    .with_start(annot.wait)
                    .with_duration(annot.duration or (scene_duration - annot.wait))
                    .with_opacity(1.0 - annot.transparency)
                    .with_effects([vfx.FadeIn(0.3), vfx.FadeOut(0.3)])
                )
                layers.append(annot_clip)

        #Текстовые блоки 
        font_path = os.path.join(FONTS_DIR, "Regular.ttf")
        semibold_path = os.path.join(FONTS_DIR, "SemiBold.ttf")

        for txt in scene.texts:
            text_w, text_h = self._get_text_size(txt.text, int(txt.size))
            text_clip = (
                TextClip(
                    text=txt.text,
                    font=semibold_path,
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
            bg_img = create_text_bg(
                video_w, video_h, txt.start_x, txt.start_y, text_w, text_h, padding=25
            )
            bg_clip = (
                ImageClip(bg_img)
                .with_start(txt.wait)
                .with_duration(txt.duration or (scene_duration - txt.wait))
                .with_effects([vfx.FadeIn(0.4), vfx.FadeOut(0.4)])
                .with_position((txt.start_x, txt.start_y))
            )
            layers.extend([bg_clip, text_clip])

        #Субтитры с точной синхронизацией 
        if tts_text and scene.subtitles:
            layers.extend(
                self._build_subtitle_clips(
                    scene,
                    tts_text,
                    scene_duration,
                    audio_duration,
                    video_w,
                    video_h,
                )
            )

        final_scene = CompositeVideoClip(layers, size=(video_w, video_h)).with_duration(
            scene_duration
        )

        # Blackout-переход применяется на уровне сцены
        if scene.transition == "blackout":
            final_scene = final_scene.with_effects(
                [vfx.FadeIn(scene.transpeed)]
            )

        # Тихая дорожка если нет аудио
        if final_scene.audio is None:
            from moviepy.audio.AudioClip import AudioClip
            silent = AudioClip(
                lambda t: np.zeros((1,)), duration=final_scene.duration, fps=44100
            )
            final_scene = final_scene.with_audio(silent)

        # TTS аудио
        if audio_path and os.path.exists(audio_path):
            audio_clip = AudioFileClip(audio_path)
            safe_duration = min(audio_clip.duration, scene_duration) - 0.01
            if safe_duration > 0:
                audio_clip = audio_clip.subclipped(0, safe_duration)
            final_scene = final_scene.with_audio(audio_clip)

        cache_entry = {
            "scene_name": scene.name,
            "audio_path": audio_path,
            "audio_duration": audio_duration,
            "scene_duration": scene_duration,
            "transition": scene.transition,
            "transpeed": scene.transpeed,
        }

        return final_scene, cache_entry

    def render(self, video_obj: VideoObject) -> str:
        """
        Основной метод рендера.

        Поддерживает:
        - Checkpointing: если рендер упал, при повторном запуске пропускает
          уже обработанные сцены и продолжает с последней успешной точки.
        - Slide-переходы: slideRight/Left/Up/Down между сценами.
        - Синхронизацию субтитров ±200ms с аудио.
        - Аннотации всех типов: square, line, arrow, darrow.
        - Субтитры с позиционированием: up/center/down.
        """
        title = video_obj.metadata.title
        log.info("Рендер проекта: %s", title)

        res = tuple(map(int, video_obj.metadata.resolution.lower().split("x")))
        video_w, video_h = res
        log.info("Разрешение: %dx%d, FPS: %d", video_w, video_h, video_obj.metadata.fps)

        #Загрузка checkpoint 
        checkpoint = _load_checkpoint(self.output_dir, title)
        processed_scenes = checkpoint.get("scenes", {})

        all_scene_clips: List = []
        scene_cache_data = dict(processed_scenes)
        global_scene_index = 0

        for act in video_obj.acts:
            log.info("Акт: %s", act.name)
            for scene in act.scenes:
                global_scene_index += 1
                scene_key = f"scene_{global_scene_index}"
                log.info("  Сцена %d: %s (%ss)", global_scene_index, scene.name, scene.duration)

                try:
                    scene_clip, cache_entry = self._process_scene(
                        scene,
                        res,
                        global_scene_index,
                        cached_clip=processed_scenes.get(scene_key),
                    )
                    all_scene_clips.append((scene_clip, scene))
                    scene_cache_data[scene_key] = cache_entry

                    # Сохраняем checkpoint после каждой успешно обработанной сцены
                    _save_checkpoint(
                        self.output_dir,
                        title,
                        {"scenes": scene_cache_data, "total": global_scene_index},
                    )
                    log.info("  ✓ Checkpoint сохранён (%d/%d)", global_scene_index, global_scene_index)

                except Exception:
                    log.exception(
                        "Ошибка при обработке сцены %d (%s). "
                        "Checkpoint сохранён — можно продолжить с этой точки.",
                        global_scene_index,
                        scene.name,
                    )
                    raise

        if not all_scene_clips:
            raise RuntimeError("Нет сцен для рендера.")

        #Сборка финального видео со slide-переходами 
        final_clips: List = []

        for i, (clip, scene) in enumerate(all_scene_clips):
            final_clips.append(clip)

            # Slide-переход между текущей и следующей сценой
            if (
                scene.transition in _SLIDE_TRANSITIONS
                and i + 1 < len(all_scene_clips)
            ):
                next_clip, _ = all_scene_clips[i + 1]
                transpeed = max(0.1, scene.transpeed or 0.5)
                transition_clip = _build_slide_transition_clip(
                    clip,
                    next_clip,
                    scene.transition,
                    transpeed,
                    video_w,
                    video_h,
                )
                log.info(
                    "  Slide-переход %s (%.1fs) между сценами %d и %d",
                    scene.transition,
                    transpeed,
                    i + 1,
                    i + 2,
                )
                final_clips.append(transition_clip)

        final_video = concatenate_videoclips(final_clips, method="chain")
        output_file = os.path.join(self.output_dir, f"{title}.mp4")

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

        #OCR sidecar
        if self.ocr_results:
            ocr_path = os.path.join(self.output_dir, f"{title}_ocr.json")
            try:
                with open(ocr_path, "w", encoding="utf-8") as f:
                    json.dump(
                        {
                            "title": title,
                            "resolution": video_obj.metadata.resolution,
                            "ocr_available": is_ocr_available(),
                            "results": self.ocr_results,
                        },
                        f,
                        ensure_ascii=False,
                        indent=2,
                    )
                log.info("OCR metadata: %s", ocr_path)
            except Exception as exc:
                log.warning("Не удалось сохранить OCR metadata: %s", exc)

        #очистка checkpoint после успешного рендера
        _clear_checkpoint(self.output_dir, title)
        log.info("Checkpoint удалён — рендер завершён успешно.")

        log.info("Готово: %s", output_file)
        final_video.close()
        return output_file


def process_screenshot_video(video: VideoObject, output_path: str) -> str:
    engine = ScreenshotEngine(output_path)
    return engine.render(video)