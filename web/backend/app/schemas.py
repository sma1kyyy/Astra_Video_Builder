"""Pydantic-модели входящего payload конструктора и сборка YAML.

Конструктор присылает структуру:
    {
      "metadata": { ... },
      "scenes": [
         { "fields": {...}, "annotations": [ {...}, ... ] },
         ...
      ]
    }

Здесь:
- ScriptPayload валидирует payload (типы, обязательные поля, диапазоны).
- to_yaml_dict собирает словарь в формате core/parser.py
  (acts → act_1 → scenes → scene_N → annotations → annotation_N).
"""
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


_RES_PATTERN = r"^\d+x\d+$"
_TITLE_PATTERN = r"^[a-zA-Z0-9а-яА-Я._\-]+$"


class MetadataPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(..., pattern=_TITLE_PATTERN)
    resolution: str = Field("1920x1080", pattern=_RES_PATTERN)
    fps: int = Field(24, gt=0, le=240)
    language: Literal["ru", "en"] = "ru"
    description: str = ""

    def to_yaml(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            "title": self.title,
            "resolution": self.resolution,
            "mode": "screenshot",
            "fps": self.fps,
            "language": self.language,
        }
        if self.description:
            out["description"] = self.description
        return out


class AnnotationPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["square", "arrow", "line", "darrow"] = "square"
    transparency: float = Field(0.3, ge=0.0, le=1.0)
    start_x: int = Field(0, ge=0)
    start_y: int = Field(0, ge=0)
    end_x: int = Field(100, ge=0)
    end_y: int = Field(100, ge=0)
    wait: float = Field(0.0, ge=0.0)
    duration: float = Field(0.0, ge=0.0)
    target_text: str = ""
    ocr: bool = False
    text: str = ""

    def to_yaml(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            "type": self.type,
            "transparency": self.transparency,
            "start_x": self.start_x,
            "start_y": self.start_y,
            "end_x": self.end_x,
            "end_y": self.end_y,
            "wait": self.wait,
            "duration": self.duration,
        }
        if self.target_text:
            out["target_text"] = self.target_text
        if self.ocr:
            out["ocr"] = True
        if self.text and self.type == "square":
            out["text"] = self.text
        return out


class ScenePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = "scene"
    path: str = Field(..., min_length=1)
    duration: float = Field(4.0, gt=0)
    tts: str = ""
    voice: Literal["jane", "zahar"] = "jane"
    subtitles: bool = False
    subtitle_style: Literal["classic", "minimal", "contrast", "cinematic"] = "classic"
    subtitle_font_size: int = Field(40, ge=16)
    transition: Literal[
        "without", "slideRight", "slideLeft", "slideUp", "slideDown", "blackout"
    ] = "without"
    annotations: List[AnnotationPayload] = Field(default_factory=list)

    def to_yaml(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            "name": self.name,
            "path": self.path,
            "duration": self.duration,
            "voice": self.voice,
            "subtitles": self.subtitles,
            "subtitle_style": self.subtitle_style,
            "subtitle_font_size": self.subtitle_font_size,
            "transition": self.transition,
        }
        if self.tts:
            out["tts"] = self.tts
        if self.annotations:
            out["annotations"] = {
                f"annotation_{idx + 1}": ann.to_yaml()
                for idx, ann in enumerate(self.annotations)
            }
        return out


class ScriptPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metadata: MetadataPayload
    scenes: List[ScenePayload] = Field(..., min_length=1)
    act_name: Optional[str] = "main"

    @field_validator("scenes")
    @classmethod
    def _non_empty(cls, value: List[ScenePayload]) -> List[ScenePayload]:
        if not value:
            raise ValueError("scenes must not be empty")
        return value

    def to_yaml_dict(self) -> Dict[str, Any]:
        scenes_dict = {
            f"scene_{idx + 1}": scene.to_yaml()
            for idx, scene in enumerate(self.scenes)
        }
        return {
            "metadata": self.metadata.to_yaml(),
            "acts": {
                "act_1": {
                    "name": self.act_name or "main",
                    "scenes": scenes_dict,
                }
            },
        }


class JobCreatedResponse(BaseModel):
    job_id: str


class JobStatusResponse(BaseModel):
    job_id: str
    status: Literal["queued", "running", "done", "failed", "cancelled"]
    created_at: float
    started_at: Optional[float] = None
    finished_at: Optional[float] = None
    error: Optional[str] = None
    output_dir: Optional[str] = None
    output_files: List[str] = Field(default_factory=list)
    log_tail: List[str] = Field(default_factory=list)
