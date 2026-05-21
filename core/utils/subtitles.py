from __future__ import annotations

import os
from typing import List, Tuple

from moviepy import vfx
from moviepy.video.VideoClip import ColorClip, TextClip

from core.schemas.scene_object import SceneObject

_SUBTITLE_SYNC_TOLERANCE = 0.2

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FONTS_DIR = os.path.join(_PROJECT_ROOT, "assets", "fonts")


def compute_subtitle_timing(
    audio_duration: float,
    scene_duration: float,
    fade_in: float = 0.3,
    fade_out: float = 0.3,
) -> Tuple[float, float]:
    """Compute subtitle start/end aligned to audio within ±200ms."""
    subtitle_start = 0.0
    if audio_duration > 0:
        raw_end = min(audio_duration, scene_duration)
        subtitle_end = max(raw_end, fade_in + fade_out + _SUBTITLE_SYNC_TOLERANCE)
        subtitle_end = min(subtitle_end, scene_duration)
    else:
        subtitle_end = scene_duration * 0.95
    return subtitle_start, subtitle_end


def build_subtitle_clips(
    scene: SceneObject,
    subtitle_text: str,
    scene_duration: float,
    audio_duration: float,
    video_w: int,
    video_h: int,
) -> List:
    """Build subtitle MoviePy clips for a scene.

    Supports subplace (up/center/down) and 4 styles (classic/minimal/contrast/cinematic).
    Returns an empty list if there's nothing to render.
    """
    if not subtitle_text or not subtitle_text.strip():
        return []

    capped = subtitle_text[: scene.subtitle_max_chars].strip()
    if len(subtitle_text) > scene.subtitle_max_chars:
        capped += "..."

    font_path = os.path.join(FONTS_DIR, "Regular.ttf")

    fade_in_dur = 0.3
    fade_out_dur = 0.3
    sub_start, sub_end = compute_subtitle_timing(
        audio_duration, scene_duration, fade_in_dur, fade_out_dur
    )
    sub_duration = max(sub_end - sub_start, 0.1)

    text_clip = (
        TextClip(
            text=capped,
            font=font_path,
            font_size=scene.subtitle_font_size,
            color="white",
            stroke_color="black",
            stroke_width=2,
            size=(int(video_w * 0.9), None),
            method="caption",
        )
        .with_start(sub_start)
        .with_duration(sub_duration)
    )

    subplace = getattr(scene, "subplace", "down")

    def _text_y_pos(clip_h: int) -> int:
        margin = 32
        if subplace == "up":
            return margin
        if subplace == "center":
            return (video_h - clip_h) // 2
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
        text_clip = text_clip.with_position(("center", text_y + 12)).with_effects(
            [vfx.FadeIn(fade_in_dur), vfx.FadeOut(fade_out_dur)]
        )
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

    text_y = _text_y_pos(text_clip.h + 18)
    bg = (
        ColorClip((int(video_w * 0.9), text_clip.h + 18), color=(0, 0, 0))
        .with_opacity(scene.subtitle_bg_opacity)
        .with_start(sub_start)
        .with_duration(sub_duration)
        .with_position(("center", text_y))
    )
    text_clip = text_clip.with_position(("center", text_y + 9)).with_effects(
        [vfx.FadeIn(fade_in_dur), vfx.FadeOut(fade_out_dur)]
    )
    return [bg, text_clip]
