from typing import List
import logging as log
from traceback import print_exc
from yaml import safe_load

# импорт схем
from core.schemas.video_object import VideoObject
from core.schemas.metadata_object import MetadataObject
from core.schemas.act_object import ActObject
from core.schemas.scene_object import SceneObject
from core.schemas.image_object import ImageObject
from core.schemas.text_object import TextObject
from core.schemas.audio_object import AudioObject
from core.schemas.action_object import ActionObject
from core.schemas.annotation_object import AnnotationObject

# импорт ошибок
from core.errors.no_required_attribute import NoRequiredAttribute
from core.errors.extra_attributes import ExtraAttributes
from core.errors.object_id_is_not_correct import ObjectIdIsntValid
from core.errors.no_value import NoValue
from core.errors.incorrect_mode import IncorrectMode
from core.errors.incorrect_value import IncorrectValue

VALID_OCR_TARGETS = {"overlay", "metadata", "both"}

def parse(filePath: str) -> VideoObject:
    """парсит yaml-скрипт и возвращает объект видео с актами"""
    try:
        with open(filePath, encoding="utf-8") as stream:
            file = safe_load(stream)

        metadata = file.get("metadata")
        acts = file.get("acts")

        if not metadata:
            raise NoRequiredAttribute("metadata")
        if not acts:
            raise NoRequiredAttribute("acts")

        metadata_object = __parse_metadata(metadata)
        acts_list = __parse_acts(acts, metadata_object.mode)

        return VideoObject(metadata=metadata_object, acts=acts_list)
    except Exception as error:
        print_exc()
        log.error(f"критическая ошибка парсинга: {error}")
        raise

def __parse_acts(acts: dict, mode: str) -> List[ActObject]:
    """проверяет структуру актов и сортирует их по id"""
    for key in acts.keys():
        if not key.startswith("act_"):
            raise ExtraAttributes(f"acts/{key}")

    try:
        sorted_keys = sorted(acts.keys(), key=lambda k: int(k.split("_")[1]))
    except Exception:
        raise ObjectIdIsntValid("ошибка в id акта")

    acts_list = []
    for key in sorted_keys:
        act = __parse_act(acts[key], key, mode)
        acts_list.append(act)
    return acts_list

def __parse_act(act: dict, act_key: str, mode: str) -> ActObject:
    """парсит конкретный акт и его внутренние сцены"""
    if not act:
        raise NoValue(act_key)

    scenes_raw = act.get("scenes")
    if not scenes_raw:
        raise NoRequiredAttribute(f"acts/{act_key}/scenes")

    name = act.get("name", act_key)
    scenes_list = __parse_scenes(scenes_raw, mode)

    return ActObject(name=name, scenes=scenes_list)

def __parse_scenes(scenes: dict, mode: str) -> List[SceneObject]:
    """сортировка и парсинг сцен внутри акта"""
    for key in scenes.keys():
        if not key.startswith("scene_"):
            raise ExtraAttributes(f"scenes/{key}")
    try:
        sorted_keys = sorted(scenes.keys(), key=lambda k: int(k.split("_")[1]))
    except Exception:
        raise ObjectIdIsntValid("ошибка в id сцены")

    scenes_list = []
    for key in sorted_keys:
        scene = __parse_scene(scenes[key], key, mode)
        scenes_list.append(scene)
    return scenes_list

def __parse_scene(scene: dict, scene_key: str, mode: str) -> SceneObject:
    """детальный разбор параметров сцены"""
    if not scene:
        raise NoValue(scene_key)

    scene_payload = dict(scene)

    # 1) забираем вложенные структуры
    name = scene_payload.pop("name", "New Scene")
    path = scene_payload.pop("path", None)
    images = __parse_images(scene_payload.pop("images", {}))
    texts = __parse_texts(scene_payload.pop("texts", {}))
    audio = __parse_audios(scene_payload.pop("audio", {}))
    actions_raw = scene_payload.pop("actions", {})
    annotations_raw = scene_payload.pop("annotations", {})

    # 2) валидация оставшихся простых полей
    valid_fields = SceneObject.get_static_attributes()
    for key in list(scene_payload.keys()):
        if key not in valid_fields:
            raise ExtraAttributes(f"scenes/{scene_key}/{key}")

    # 3) проверка обязательных полей для режима
    if mode == "screenshot" and not path:
        raise NoRequiredAttribute(f"scenes/{scene_key}/path")

    # 4) сборка объекта
    if mode == "live":
        actions = __parse_actions(actions_raw)
        return SceneObject(
            name=name,
            path=path or "",
            images=images,
            texts=texts,
            audio=audio,
            actions=actions,
            **scene_payload,
        )

    if mode == "screenshot":
        annotations = __parse_annotations(annotations_raw)
        return SceneObject(
            name=name,
            path=path or "",
            images=images,
            texts=texts,
            audio=audio,
            annotations=annotations,
            **scene_payload,
        )

    raise IncorrectMode(mode)

def __parse_annotations(annotations: dict) -> List[AnnotationObject]:
    """полная валидация каждой аннотации + OCR полей"""
    if not annotations:
        return []

    for key in annotations.keys():
        if not key.startswith("annotation_"):
            raise ExtraAttributes(f"annotations/{key}")

    try:
        sorted_keys = sorted(annotations.keys(), key=lambda k: int(k.split("_")[1]))
    except Exception:
        raise ObjectIdIsntValid("ошибка в id annotation")

    valid_fields = AnnotationObject.get_static_attributes()
    result = []

    for key in sorted_keys:
        item = annotations[key]
        if not item:
            raise NoValue(f"annotations/{key}")

        required = ["type", "transparency", "start_x", "start_y", "end_x", "end_y"]
        for req in required:
            if item.get(req) is None:
                raise NoRequiredAttribute(f"annotations/{key}/{req}")

        for field_name in item.keys():
            if field_name not in valid_fields:
                raise ExtraAttributes(f"annotations/{key}/{field_name}")

        if item.get("text") and item.get("type") != "square":
            raise ExtraAttributes(f"annotations/{key}/text")

        # OCR валидация
        ocr_target = item.get("ocr_target", "overlay")
        if ocr_target not in VALID_OCR_TARGETS:
            raise IncorrectValue(f"annotations/{key}/ocr_target={ocr_target}")

        ocr_min_conf = item.get("ocr_min_conf", 0.0)
        try:
            ocr_min_conf = float(ocr_min_conf)
        except (TypeError, ValueError):
            raise IncorrectValue(f"annotations/{key}/ocr_min_conf={ocr_min_conf}")

        if not (0.0 <= ocr_min_conf <= 1.0):
            raise IncorrectValue(f"annotations/{key}/ocr_min_conf={ocr_min_conf}")

        if item.get("ocr", False) and item.get("type") != "square":
            log.warning("OCR для %s поддерживается только для type=square.", key)
            item["ocr"] = False

        result.append(AnnotationObject(**item))

    return result

def __parse_actions(actions: dict) -> List[ActionObject]:
    """детальная валидация действий с match-case"""
    if not actions:
        return []

    sorted_keys = sorted(actions.keys(), key=lambda k: int(k.split("_")[1]))
    result = []

    for key in sorted_keys:
        action = actions[key]
        if not action:
            raise NoValue(f"actions/{key}")

        a_type = action.get("type")
        if not a_type:
            raise NoRequiredAttribute(f"actions/{key}/type")

        match a_type:
            case "navigate":
                if not action.get("url"):
                    raise NoRequiredAttribute(f"actions/{key}/url")
            case "click" | "input":
                if not action.get("selector"):
                    raise NoRequiredAttribute(f"actions/{key}/selector")
                if a_type == "input" and not action.get("text"):
                    raise NoRequiredAttribute(f"actions/{key}/text")
            case "wait":
                if not action.get("duration"):
                    raise NoRequiredAttribute(f"actions/{key}/duration")
            case "scrollUp" | "scrollDown":
                if not action.get("point"):
                    raise NoRequiredAttribute(f"actions/{key}/point")

        result.append(ActionObject(**action))
    return result

def __parse_images(images: dict) -> List[ImageObject]:
    result = []
    for key, img in images.items():
        required = ["path", "start_x", "start_y", "resolution"]
        if not all(k in img for k in required):
            raise NoRequiredAttribute(f"images/{key}")
        result.append(ImageObject(**img))
    return result

def __parse_texts(texts: dict) -> List[TextObject]:
    result = []
    for key, txt in texts.items():
        required = ["text", "start_x", "start_y", "size"]
        if not all(k in txt for k in required):
            raise NoRequiredAttribute(f"texts/{key}")
        result.append(TextObject(**txt))
    return result

def __parse_audios(audios: dict) -> List[AudioObject]:
    result = []
    for key, aud in audios.items():
        required = ["path", "_from", "duration"]
        if not all(k in aud for k in required):
            raise NoRequiredAttribute(f"audio/{key}")
        result.append(AudioObject(**aud))
    return result

def __parse_metadata(metadata: dict) -> MetadataObject:
    if not metadata.get("title") or not metadata.get("resolution"):
        raise NoRequiredAttribute("metadata (title/resolution)")
    return MetadataObject(**metadata)