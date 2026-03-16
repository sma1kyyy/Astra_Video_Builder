from pydantic.dataclasses import dataclass
from pydantic import Field, ConfigDict, model_validator
from typing import List, Optional, Literal
from core.schemas.ComponentObject import ComponentObject

@dataclass(config=ConfigDict(arbitrary_types_allowed=True))
class ActionObject(ComponentObject):
    """Шаблон для всех объектов Actions"""
    type: Literal["navigate", "click", "input", "scrollUp", "scrollDown", "scrollTo", "wait"] = Field(
        ...,
        description="Тип действия."
    )
    url: Optional[str] = Field(
        default=None,
        description="URL (для типа Navigate)",
        pattern=r"(https?://[^\s/$.?#].[^\s]*)" # for url
    )
    selector: Optional[str] = Field(
        default=None,
        description="Selector для XPath (selenium)",
        pattern=r"^(/(?:[^/]+|\[[^\]]+\])*|//[^/]+(?:/[^/]+|\[[^\]]+\])*|\(.*\))$" # for xpath
    )
    text: Optional[str] = Field(
        default="",
        description="Вводимый в поле ввода текст."
    )
    duration: Optional[int] = Field(
        default=0,
        description="Длительность для wait.",
        ge=0
    )
    point: Optional[int] = Field(
        default=0,
        description="Количество поинтов, на которое будет осуществлен скролл.",
        ge=0
    )
    behavior: Literal["smooth", "none"] = Field(
        default="none",
        description="Поведение скролла."
    )
    wait: Optional[int] = Field(
        default=0,
        description="Ожидать перед следующим кадром в секундах.",
        ge=0
    )

    @model_validator(mode="after")
    def validate_behavior(self) -> "ActionObject":
        if self.behavior == "none":
            self.behavior = None

        # "navigate", "click", "input", "scrollUp", "scrollDown", "scrollTo", "wait"
        match self.type:
            case "navigate":
                assert self.url is not None, "With navigate must be URL!"
            case "click":
                assert self.selector is not None, "With click must be SELECTOR!"
            case "input":
                assert self.selector is not None, "With input must be SELECTOR!"
            case "scrollTo":
                assert self.selector is not None, "With scrollTo must be SELECTOR!"
        
        return self