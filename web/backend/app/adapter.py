"""Адаптер: VideoObject (после core.parser.parse) → ScriptPayload (форма web-конструктора).

Используется эндпоинтом POST /api/scripts/parse, чтобы загруженный YAML можно было
сразу подставить в конструктор. Парсинг и валидация остаются в core/parser.py —
здесь только маппинг полей.
"""
from __future__ import annotations

import os
from typing import Any

from core.schemas.video_object import VideoObject

from web.backend.app.schemas import (
    AnnotationPayload,
    MetadataPayload,
    ScenePayload,
    ScriptPayload,
)


def _basename(value: str | None) -> str:
    if not value:
        return ""
    return os.path.basename(value)


def _annotation_to_payload(ann: Any) -> AnnotationPayload:
    return AnnotationPayload(
        type=getattr(ann, "type", "square"),
        transparency=float(getattr(ann, "transparency", 0.0) or 0.0),
        start_x=int(getattr(ann, "start_x", 0) or 0),
        start_y=int(getattr(ann, "start_y", 0) or 0),
        end_x=int(getattr(ann, "end_x", 0) or 0),
        end_y=int(getattr(ann, "end_y", 0) or 0),
        wait=float(getattr(ann, "wait", 0.0) or 0.0),
        duration=float(getattr(ann, "duration", 0.0) or 0.0),
        target_text=getattr(ann, "target_text", "") or "",
        ocr=bool(getattr(ann, "ocr", False)),
        text=getattr(ann, "text", "") or "",
    )


def _scene_to_payload(scene: Any) -> ScenePayload:
    return ScenePayload(
        name=getattr(scene, "name", "scene") or "scene",
        path=_basename(getattr(scene, "path", "")),
        duration=float(getattr(scene, "duration", 1.0) or 1.0) or 0.1,
        tts=getattr(scene, "tts", "") or "",
        voice=getattr(scene, "voice", "jane") or "jane",
        subtitles=bool(getattr(scene, "subtitles", False)),
        subtitle_style=getattr(scene, "subtitle_style", "classic") or "classic",
        subtitle_font_size=int(getattr(scene, "subtitle_font_size", 40) or 40),
        transition=getattr(scene, "transition", "without") or "without",
        annotations=[
            _annotation_to_payload(a) for a in (getattr(scene, "annotations", None) or [])
        ],
    )


def video_to_payload(video: VideoObject) -> ScriptPayload:
    md = video.metadata
    metadata = MetadataPayload(
        title=md.title,
        resolution=md.resolution,
        fps=int(md.fps or 24),
        language=md.language or "ru",
        description=md.description or "",
    )

    if not video.acts:
        scenes: list[ScenePayload] = []
    else:
        scenes = [_scene_to_payload(s) for s in video.acts[0].scenes]

    return ScriptPayload(
        metadata=metadata,
        scenes=scenes,
        act_name=video.acts[0].name if video.acts else "main",
    )
