# FFmpeg для объединения видео, аудио, субтитров
# MoviePy или другой Python-фреймворк для программного монтажа
# Применение переходов, эффектов, добавление текста
import os
from typing import List
from os import path

from moviepy import VideoFileClip, CompositeAudioClip, AudioFileClip

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
    video_clip = VideoFileClip(recorder_path).subclipped(1)

    # Наложение tts
    tts_list = []

    for i, start, end in scene_times:
        # Наложение TTS
        tts_path = f"{output_path}/scene_{i}.wav"
        if path.exists(tts_path):
            tts_list.append(AudioFileClip(tts_path))

    composited_tts = CompositeAudioClip(tts_list).with_duration(video_clip.duration)
    video_clip.audio = composited_tts

    video_clip.write_videofile(f"{output_path}/{title}.mp4")

    # удаляем лишние файлы
    if not save_files:
        for i, start, end in scene_times:
            tts_path = f"{output_path}/scene_{i}.wav"
            if path.exists(tts_path):
                os.remove(tts_path)
