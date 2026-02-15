# Модуль на Python для разбора входного скрипта
# Валидация синтаксиса и логики
# Преобразование в промежуточный AST (Abstract Syntax Tree)
# Поддержка различных форматов (JSON, YAML)

# basic lib imports
from yaml import safe_load
import logging as log
from typing import List
from traceback import print_exc

# schemas imports
from src.schemas.video_object import VideoObject
from src.schemas.metadata_object import MetadataObject
from src.schemas.scene_object import SceneObject
from src.schemas.image_object import ImageObject
from src.schemas.text_object import TextObject
from src.schemas.audio_object import AudioObject
from src.schemas.action_object import ActionObject
from src.schemas.annotation_object import AnnotationObject

# errors imports
from src.errors.no_required_attribute import NoRequiredAttribute
from src.errors.extra_attributes import ExtraAttributes
from src.errors.object_id_is_not_correct import ObjectIdIsntValid
from src.errors.no_value import NoValue
from src.errors.incorrect_mode import IncorrectMode

def parse(filePath: str) -> VideoObject:
    """Парсит yaml-скрипт по пути filePath. Возвращает объект-python video_object."""

    try:
        # открытие файла и преобразование его в словарь
        with open(filePath, encoding="utf-8") as stream:
            file = safe_load(stream)

        metadata = file.get("metadata", None) # попытка достать словарь с metadata
        scenes = file.get("scenes", None) # попытка достать словарь с scenes

        if not metadata: # metadata - обязательный параметр. Если его нет, возбуждается исключение
            raise NoRequiredAttribute("metadata")
        elif not scenes:
            raise NoRequiredAttribute("scenes")
        
        # парсинг отдельных частей скрипта
        metadata_object = __parse_metadata(metadata)
        scenes_list = __parse_scenes(scenes, metadata_object.mode)
        
        # создание из отпаршенных параметров итогового объекта
        return VideoObject(
            metadata = metadata_object,
            scenes = scenes_list
        )
    except AttributeError as e:
        print_exc() # ПОЗЖЕ УБРАТЬ ================================================================================================================
        log.error("Invalid syntax.")
    except BaseException as e:
        print_exc()
        log.error(e)

def __parse_metadata(metadata: dict) -> MetadataObject:
    """
    Парсит словарь делая ставку на то, что он заполнен аттрибутами metadata.
    Возвращает MetadataObject.
    """
    # попытка достать обязательные параметры
    title = metadata.get("title", None)
    resolution = metadata.get("resolution", None)

    if not title:
        raise NoRequiredAttribute("metadata/title")
    elif not resolution:
        raise NoRequiredAttribute("metadata/resolution")
    
    needed_keys = MetadataObject.__dict__["__static_attributes__"] # список всех аттрибутов. Он подтягивается из соответствующего класса автоматом (из self.)
    
    # проверка, чтобы в поле не было аттрибутов, которых не должно быть
    for key in metadata.keys():
        if key not in needed_keys:
            raise ExtraAttributes(f"metadata/{key}")
    
    # Обязательные параметры есть, лишних параметров нет, можно создавать объект
    return MetadataObject(**metadata)

def __parse_scenes(scenes: dict, mode: str) -> List[SceneObject]:
    """
    Парсит словарь делая ставку на то, что он заполнен аттрибутами scenes.
    Возвращает список с объектами SceneObject.
    mode - режим. live - live recording mode. screenshot - screenshot mode
    """
    # сортировка словаря по ID + проверка правильности ID + проверка, что нет лишних объектов
    for key in scenes.keys():
        if not key.startswith("scene_"):
            raise ExtraAttributes(f"scenes/{key}") # есть какой-то атрибут кроме сцены 
    try:
        scenes = {k: v for k, v in sorted(scenes.items(), key = lambda key: int(key[0].split("_")[1]))}
    except ValueError as e:
        # узнаём более подробно, у какого конкретно объекта ошибка
        for key in scenes.keys():
            try:
                int(key.split("_")[1]) # попытка получить id scene
            except Exception:
                raise ObjectIdIsntValid(f"scenes/{key}")
        raise ObjectIdIsntValid()
    except Exception as e: # для остальных случаев
        raise Exception(e)

    scenes_list = [] # список с объектами сцен. Заполняется в порядке по id. Если id одинаковый - рандом.
    for key in scenes.keys():
        scene = __parse_scene(scenes[key], key, mode)
        scenes_list.append(scene) # вставка происходит по id, что автоматически делает список отсортированным. В будущем можно сортировать словарь
        # для автоматизации, если потребуется
    
    return scenes_list

def __parse_scene(scene: dict, scene_key: str, mode: str) -> SceneObject:
    """
    Парсит конкретную сцену и возвращает объект сцены.
    scene - словарь с параметрами сцены
    scene_key - название его в scenes
    mode - режим. live - live recording mode. screenshot - screenshot mode
    """
    if not scene:
        raise NoValue(scene_key)

    # попытка достать обязательные параметры
    duration = scene.get("duration", None)
    if not duration:
        raise NoRequiredAttribute(f"scenes/{scene_key}/duration")

    # парсинг вложенных параметров, то есть тех, у которых есть ещё параметры
    # сразу удаляем эти элементы, чтобы не передавать их через *scene в return
    images = scene.pop("images", [])
    if images:
        images = __parse_images(images)

    texts = scene.pop("texts", [])
    if texts:
        texts = __parse_texts(texts)

    audio = scene.pop("audio", [])
    if audio:
        audio = __parse_audios(audio)

    needed_keys = SceneObject.__dict__["__static_attributes__"] # список всех аттрибутов. Он подтягивается из соответствующего класса автоматом (из self.)
    
    # проверка, чтобы в поле не было аттрибутов, которых не должно быть
    for key in scene.keys():
        if key not in needed_keys:
            raise ExtraAttributes(f"scenes/{scene_key}/{key}")

    if mode == "live":
        actions = scene.pop("actions", [])
        if actions: # если список действий не пуст, то его надо отпарсить
            actions = __parse_actions(actions)
        return SceneObject(
            images = images,
            texts = texts,
            audio = audio,
            actions = actions,
            **scene # это работает, потому что вложенные параметры уже удалены из этого словаря
        )
    elif mode == "screenshot":
        path = scene.get("path", None)  # обязательное поле для screenshot mode
        if not path:
            raise NoRequiredAttribute(f"scenes/{scene_key}/path")

        annotations = scene.pop("annotations", [])
        if annotations:
            annotations = __parse_annotations(annotations)

        return SceneObject(
            images=images,
            texts=texts,
            audio=audio,
            annotations=annotations,
            **scene  # это работает, потому что вложенные параметры уже удалены из этого словаря
        )
    else:
        raise IncorrectMode(mode) # режим неправильный

def __parse_annotations(annotations: dict) -> List[AnnotationObject]:
    """
        Парсит список аннотаций для screenshot Mode
        :param annotations: Словарь с annotation_object формата annotation_id
        :return: Список с объектами AnnotationObject
        """
    # сортировка словаря по ID + проверка правильности ID + проверка, что нет лишних объектов
    for key in annotations.keys():
        if not key.startswith("annotation_"):
            raise ExtraAttributes(f"annotations/{key}")  # есть какой-то атрибут кроме сцены
    try:
        annotations = {k: v for k, v in sorted(annotations.items(), key=lambda key: int(key[0].split("_")[1]))}
    except ValueError as e:
        # узнаём более подробно, у какого конкретно объекта ошибка
        for key in annotations.keys():
            try:
                int(key.split("_")[1])  # попытка получить id scene
            except Exception:
                raise ObjectIdIsntValid(f"annotations/{key}")
        raise ObjectIdIsntValid(str(e))
    except Exception as e:  # для остальных случаев
        raise Exception(e)

    annotation_list = []

    for key in annotations.keys():
        annotation = __parse_annotation(annotations[key], key)
        annotation_list.append(annotation)

    return annotation_list

def __parse_annotation(annotation: dict, annotation_key: str) -> AnnotationObject:
    """
    Парсит конкретную аннотацию для screenshot mode
    :param annotation: Список параметров действия
    :param annotation_key: Название action_object в формате annotation_id
    :return: Возвращает объект AnnotationObject
    """
    if not annotation:
        raise NoValue(annotation_key)

    # попытка достать обязательные параметры
    type = annotation.get("type", None)
    transparency = annotation.get("transparency", None)
    start_x = annotation.get("start_x", None)
    start_y = annotation.get("start_y", None)
    end_x = annotation.get("end_x", None)
    end_y = annotation.get("end_y", None)
    
    # кирилл: используем "is None", чтобы число 0 считалось валидным значением
    if not type:
        raise NoRequiredAttribute(f"scenes/{annotation_key}/type")
    elif transparency is None:
        raise NoRequiredAttribute(f"scenes/{annotation_key}/transparency")
    elif start_x is None:
        raise NoRequiredAttribute(f"scenes/{annotation_key}/start_x")
    elif start_y is None:
        raise NoRequiredAttribute(f"scenes/{annotation_key}/start_y")
    elif end_x is None:
        raise NoRequiredAttribute(f"scenes/{annotation_key}/end_x")
    elif end_y is None:
        raise NoRequiredAttribute(f"scenes/{annotation_key}/end_y")

    # Тут меньше обязательных параметров, чем в live recording mode, поэтому проще проверить,
    # что нет параметров, которые не могут быть использованы с определенными типами
    text = annotation.get("text", None)
    if text and type != "square": # text может быть только для типа square (временно)
        raise ExtraAttributes(f"scenes/{annotation_key}/text")

    # Список всех атрибутов. Он подтягивается из соответствующего класса автоматом (из self.)
    needed_keys = AnnotationObject.__dict__[
        "__static_attributes__"]

    # проверка, чтобы в поле не было атрибутов, которых не должно быть
    for key in annotation.keys():
        if key not in needed_keys:
            raise ExtraAttributes(f"annotations/{key}")

    # Обязательные параметры есть, лишних параметров нет, можно создавать объект
    return AnnotationObject(**annotation)

# парсинг actions
def __parse_actions(actions: dict) -> List[ActionObject]:
    """
    Парсит список действий для LiveRecording Mode
    :param actions: Словарь с action_objects формата action_id
    :return: Список с объектами ActionObject
    """
    # сортировка словаря по ID + проверка правильности ID + проверка, что нет лишних объектов
    for key in actions.keys():
        if not key.startswith("action_"):
            raise ExtraAttributes(f"actions/{key}")  # есть какой-то атрибут кроме сцены
    try:
        actions = {k: v for k, v in sorted(actions.items(), key=lambda key: int(key[0].split("_")[1]))}
    except ValueError as e:
        # узнаём более подробно, у какого конкретно объекта ошибка
        for key in actions.keys():
            try:
                int(key.split("_")[1])  # попытка получить id scene
            except Exception:
                raise ObjectIdIsntValid(f"actions/{key}")
        raise ObjectIdIsntValid(str(e))
    except Exception as e:  # для остальных случаев
        raise Exception(e)

    action_list = []

    for key in actions.keys():
        action = __parse_action(actions[key], key)
        action_list.append(action)

    return action_list

def __parse_action(action: dict, action_key: str) -> ActionObject:
    """
    Парсит конкретное действие для LiveRecording mode
    :param action: Список параметров действия
    :param action_key: Название action_object в формате action_id
    :return: Возвращает объект ActionObject
    """
    if not action: # Параметр объекта действия есть, но внутри он пуст. Иначе бы передался None, у которого нет
        # метода get, который используется ниже
        raise NoValue(action_key)
    # попытка достать обязательные параметры
    type = action.get("type", None)
    if not type:
        raise NoRequiredAttribute(f"scenes/{action_key}/type")

    # Для каждого типа свои обязательные параметры. Тут они проверяются
    match(type):
        case "navigate":
            url = action.get("url", None)
            if not url:
                raise NoRequiredAttribute(f"scenes/{action_key}/url")
        case "click":
            selector = action.get("selector", None)
            if not selector:
                raise NoRequiredAttribute(f"scenes/{action_key}/selector")
        case "wait":
            duration = action.get("duration", None)
            if not duration:
                raise NoRequiredAttribute(f"scenes/{action_key}/duration")
        case "input":
            selector = action.get("selector", None)
            text = action.get("text", None)
            if not selector:
                raise NoRequiredAttribute(f"scenes/{action_key}/selector")
            elif not text:
                raise NoRequiredAttribute(f"scenes/{action_key}/text")
        case "scrollUp":
            point = action.get("point", None)
            if not point:
                raise NoRequiredAttribute(f"scenes/{action_key}/point")
        case "scrollDown":
            point = action.get("point", None)
            if not point:
                raise NoRequiredAttribute(f"scenes/{action_key}/point")

    # Список всех атрибутов. Он подтягивается из соответствующего класса автоматом (из self.)
    needed_keys = ActionObject.__dict__[
        "__static_attributes__"]

    # проверка, чтобы в поле не было атрибутов, которых не должно быть
    for key in action.keys():
        if key not in needed_keys:
            raise ExtraAttributes(f"actions/{key}")

    # Обязательные параметры есть, лишних параметров нет, можно создавать объект
    return ActionObject(**action)

def __parse_images(images: dict) -> List[ImageObject]:
    """
    Парсит словарь image_objects и возвращает список с ImageObject.
    
    :param images: Словарь со словарями image_object
    :type images: dict
    :return: Список с объектами ImageObject
    :rtype: List[ImageObject]
    """
    # сортировка словаря по ID + проверка правильности ID + проверка, что нет лишних объектов
    for key in images.keys():
        if not key.startswith("image_"):
            raise ExtraAttributes(f"images/{key}") # есть какой-то атрибут кроме сцены 
    try:
        images = {k: v for k, v in sorted(images.items(), key = lambda key: int(key[0].split("_")[1]))}
    except ValueError as e:
        # узнаём более подробно, у какого конкретно объекта ошибка
        for key in images.keys():
            try:
                int(key.split("_")[1]) # попытка получить id scene
            except Exception:
                raise ObjectIdIsntValid(f"images/{key}")
        raise ObjectIdIsntValid()
    except Exception as e: # для остальных случаев
        raise Exception(e)

    image_list = []

    for key in images.keys():
        image = __parse_image(images[key], key)
        image_list.append(image)
    
    return image_list


def __parse_image(image: dict, image_key: str) -> ImageObject:
    """
    Парсит непосредственно image_object
    
    :param image: Словарь с параметрами image_object
    :type image: dict
    :param image_key: image_id
    :type image_key: str
    :return: Объект ImageObject
    :rtype: ImageObject
    """
    if not image:
        raise NoValue(image_key)
    # попытка достать обязательные параметры
    path = image.get("path", None)
    start_x = image.get("start_x", None)
    start_y = image.get("start_y", None)
    resolution = image.get("resolution", None)
    if not path:
        raise NoRequiredAttribute(f"scenes/{image_key}/path")
    elif not start_x:
        raise NoRequiredAttribute(f"scenes/{image_key}/start_x")
    elif not start_y:
        raise NoRequiredAttribute(f"scenes/{image_key}/start_y")
    elif not resolution:
        raise NoRequiredAttribute(f"scenes/{image_key}/resolution")
    
    needed_keys = ImageObject.__dict__["__static_attributes__"] # список всех аттрибутов. Он подтягивается из соответствующего класса автоматом (из self.)
    
    # проверка, чтобы в поле не было аттрибутов, которых не должно быть
    for key in image.keys():
        if key not in needed_keys:
            raise ExtraAttributes(f"image/{key}")
    
    # Обязательные параметры есть, лишних параметров нет, можно создавать объект
    return ImageObject(**image)
    

def __parse_texts(texts: dict) -> List[TextObject]:
    """
    Парсит словарь text_objects и возвращает список с TextObject.
    
    :param texts: Словарь со словарями text_object
    :type texts: dict
    :return: Список с объектами TextObject
    :rtype: List[TextObject]
    """
    # сортировка словаря по ID + проверка правильности ID + проверка, что нет лишних объектов
    for key in texts.keys():
        if not key.startswith("text_"):
            raise ExtraAttributes(f"texts/{key}") # есть какой-то атрибут кроме сцены 
    try:
        texts = {k: v for k, v in sorted(texts.items(), key = lambda key: int(key[0].split("_")[1]))}
    except ValueError as e:
        # узнаём более подробно, у какого конкретно объекта ошибка
        for key in texts.keys():
            try:
                int(key.split("_")[1]) # попытка получить id scene
            except Exception:
                raise ObjectIdIsntValid(f"texts/{key}")
        raise ObjectIdIsntValid()
    except Exception as e: # для остальных случаев
        raise Exception(e)

    text_list = []

    # Проверка, что нет лишних полей + сразу парсит
    for key in texts.keys():
        text = __parse_text(texts[key], key)
        text_list.append(text)
    
    return text_list

def __parse_text(text_object: dict, text_key: str) -> TextObject:
    """
    Парсит непосредственно text_object
    
    :param text_object: Словарь с параметрами text_object
    :type text_object: dict
    :param text_key: text_id
    :type text_key: str
    :return: Объект TextObject
    :rtype: TextObject
    """
    if not text_object:
        raise NoValue(text_key)
    # попытка достать обязательные параметры
    text = text_object.get("text", None)
    start_x = text_object.get("start_x", None)
    start_y = text_object.get("start_y", None)
    size = text_object.get("size", None)
    if not text:
        raise NoRequiredAttribute(f"scenes/{text_key}/text")
    elif not start_x:
        raise NoRequiredAttribute(f"scenes/{text_key}/start_x")
    elif not start_y:
        raise NoRequiredAttribute(f"scenes/{text_key}/start_y")
    elif not size:
        raise NoRequiredAttribute(f"scenes/{text_key}/size")
    
    needed_keys = TextObject.__dict__["__static_attributes__"] # список всех аттрибутов. Он подтягивается из соответствующего класса автоматом (из self.)
    
    # проверка, чтобы в поле не было аттрибутов, которых не должно быть
    for key in text_object.keys():
        if key not in needed_keys:
            raise ExtraAttributes(f"texts/{key}")
    
    # Обязательные параметры есть, лишних параметров нет, можно создавать объект
    return TextObject(**text_object)

def __parse_audios(audios: dict) -> List[AudioObject]:
    """
    Парсит словарь audio_objects и возвращает список с TextAudioObjectObject.
    
    :param audios: Словарь со словарями audio_object
    :type audios: dict
    :return: Список с объектами AudioObject
    :rtype: List[AudioObject]
    """
    # сортировка словаря по ID + проверка правильности ID + проверка, что нет лишних объектов
    for key in audios.keys():
        if not key.startswith("audio_"):
            raise ExtraAttributes(f"audios/{key}") # есть какой-то атрибут кроме сцены 
    try:
        audios = {k: v for k, v in sorted(audios.items(), key = lambda key: int(key[0].split("_")[1]))}
    except ValueError as e: # ID неправильного формата
        # узнаём более подробно, у какого конкретно объекта ошибка
        for key in audios.keys():
            try:
                int(key.split("_")[1]) # попытка получить id scene
            except Exception:
                raise ObjectIdIsntValid(f"audios/{key}")
        raise ObjectIdIsntValid()
    except Exception as e: # для остальных случаев
        raise Exception(e)

    audio_list = []

    # Проверка, что нет лишних полей + сразу парсит
    for key in audios.keys():
        audio = __parse_audio(audios[key], key)
        audio_list.append(audio)
    
    return audio_list

def __parse_audio(audio: dict, audio_key: str) -> AudioObject:
    """
    Парсит непосредственно audio_object
    
    :param image: Словарь с параметрами audio_object
    :type audio: dict
    :param audio_key: audio_id
    :type audio_key: str
    :return: Объект AudioObject
    :rtype: AudioObject
    """
    if not audio:
        raise NoValue(audio_key)
    # попытка достать обязательные параметры
    path = audio.get("path", None)
    _from = audio.get("_from", None)
    duration = audio.get("duration", None)
    if not path:
        raise NoRequiredAttribute(f"scenes/{audio_key}/path")
    elif not _from:
        raise NoRequiredAttribute(f"scenes/{audio_key}/_from")
    elif not duration:
        raise NoRequiredAttribute(f"scenes/{audio_key}/duration")
    
    needed_keys = AudioObject.__dict__["__static_attributes__"] # список всех аттрибутов. Он подтягивается из соответствующего класса автоматом (из self.)
    
    # проверка, чтобы в поле не было аттрибутов, которых не должно быть
    for key in audio.keys():
        if key not in needed_keys:
            raise ExtraAttributes(f"audio/{key}")
    
    # Обязательные параметры есть, лишних параметров нет, можно создавать объект
    return AudioObject(**audio)