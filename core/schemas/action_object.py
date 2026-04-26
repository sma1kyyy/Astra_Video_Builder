from pydantic.dataclasses import dataclass
from pydantic import Field, ConfigDict, model_validator, field_validator
from typing import Optional, Literal

from core.schemas.ComponentObject import ComponentObject

ActionType = Literal[
    "navigate", "click", "input", "scrollUp", "scrollDown", "scrollTo", "wait"
]

_SCROLL_ALIASES = {
    "scrollup": "scrollUp",
    "scrolldown": "scrollDown",
    "scrollto": "scrollTo",
}


@dataclass(config=ConfigDict(arbitrary_types_allowed=True))
class ActionObject(ComponentObject):
    type: ActionType = Field(
        ...,
        description="Тип действия.",
    )
    url: Optional[str] = Field(
        default=None,
        description="URL (для типа Navigate)",
        pattern=r"(https?://[^\s/$.?#].[^\s]*)",
    )
    selector: Optional[str] = Field(
        default=None,
        description="Selector для XPath (selenium)",
        pattern=r"^(/.+|\(.+\).*)$",
    )
    text: Optional[str] = Field(default="", description="Вводимый в поле ввода текст.")
    duration: Optional[int] = Field(
        default=0,
        description="Длительность для wait, в секундах.",
        ge=0,
    )
    point: Optional[int] = Field(
        default=0,
        description="Количество поинтов скролла.",
        ge=0,
    )
    behavior: Literal["smooth", "none"] = Field(
        default="none",
        description="Поведение скролла.",
    )
    wait: int = Field(
        default=1,
        description="Пауза перед действием в секундах.",
        ge=0,
    )

    @field_validator("type", mode="before")
    @classmethod
    def _normalize_type(cls, value):
        if isinstance(value, str):
            return _SCROLL_ALIASES.get(value.lower(), value)
        return value

    @field_validator("text", "url", "selector", mode="before")
    @classmethod
    def _coerce_str(cls, value):
        if value is None or isinstance(value, str):
            return value
        if isinstance(value, bool):
            return str(value).lower()
        if isinstance(value, (int, float)):
            return str(value)
        return value

    @model_validator(mode="after")
    def _validate_required_fields(self) -> "ActionObject":
        if self.behavior == "none":
            self.behavior = None

        match self.type:
            case "navigate":
                assert self.url is not None, "With navigate must be URL!"
            case "click" | "input" | "scrollTo":
                assert self.selector is not None, f"With {self.type} must be SELECTOR!"

        return self
