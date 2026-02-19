# FFmpeg для объединения видео, аудио, субтитров
# MoviePy или другой Python-фреймворк для программного монтажа
# Применение переходов, эффектов, добавление текста
import os
from typing import List
from os import path

from moviepy import VideoFileClip, CompositeAudioClip, AudioFileClip, concatenate_videoclips

def live_recording_render(
        output_path: str,
        title: str,
        scene_times: List[List[int]],
        save_files: bool = True
):
    """
    Рендерит видео в режиме live recording. Собирает все элементы: аудио, текст и т. д. для монтажа и обработки.
    После удаляет всё лишнее, если стоит нужный флаг.
    :param output_path: Путь для сохранения видео, где хранятся аудио, текст и т.д.
    :param title: Название итогового видео
    :param scene_times: Тайминги длительности сцен. Список по следующему формату: [номер сцены, начало, конец]
    :param save_files: True - оставляет все файлы, кроме итогового обработанного видео. False - удаляет, кроме записанного и обработанного.
    :return: Возвращает путь до обработанного видео
    """
    # Объект видео. Сразу обрезается на 1 секунду из-за загрузки браузера.
    recorder_path = f"{output_path}/{title}_recorded.mp4"
    video_clip = VideoFileClip(recorder_path) # .subclipped(1)

    scenes_len = len(scene_times)

    scenes = []

    # object lists
    tts_list = []

    print("SCENE_LEN:", scenes_len)
    print("SCENE_TIMES:", scene_times)

    for i, start, end in scene_times:
        print("I:", i)
        if i == scenes_len - 1: # если сцена последняя, скорее всего её конец посчитан неправильно, а потому обрезаем до конца видео
            print("the last one")
            scene = video_clip.subclipped(start)
        else:
            scene = video_clip.subclipped(start, end)

        # Наложение TTS
        tts_path = f"{output_path}/scene_{i}.wav"
        if path.exists(tts_path):
            print("let tts work!")
            scene.audio = CompositeAudioClip(
                [AudioFileClip(tts_path)]).with_duration(scene.duration)

        scenes.append(scene)

    print("SCENES BEFORE POP:", scenes)
    scenes.pop(0) # удаляем первую сцену - загрузку браузера

    print("SCENES AFTER POP:", scenes)
    video_clip = concatenate_videoclips(scenes)

    video_clip.write_videofile(f"{output_path}/{title}.mp4")

    video_clip.close()

    # удаляем лишние файлы
    if not save_files:
        for i, start, end in scene_times:
            tts_path = f"{output_path}/scene_{i}.wav"
            if path.exists(tts_path):
                os.remove(tts_path)
