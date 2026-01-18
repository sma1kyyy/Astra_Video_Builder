# FFmpeg для захвата и кодирования видео (режим Live Recording)
# Настройка разрешения, FPS, кодека
# Встраивание видеокодека H.264 для MP4

# basic lib imports
import os
import time
import platform

# external lib imports
import ffmpeg

# schemas imports
from src.schemas.metadata_object import MetadataObject

def get_input_params():
    """Проверка какая ОС и графичекое окружение используется. Запись экрана на разных ОС осуществляется
    по разному. FFMPEG работает со всеми ОС, однако в Linux бывают разные графические окружения.
    FFMPEG может обрабатывать только xORG, поэтому для обработки wayland используется отдельная
    утилита wf-recorder"""
    os_name = platform.system()
    if os_name == "Windows":
        return "gdigrab", "desktop"
    elif os_name == "Darwin": # macOS
        return "avfoundation", "1:0" 
    elif os_name == "Linux":
        is_wayland = os.environ.get("XDG_SESSION_TYPE") == "wayland" or \
            os.environ.get("WAYLAND_DISPLAY") is not None
        
        if is_wayland:
            return "wf-recorder", "" # wayland
        else:
            return "x11grab", ":0.0" #xORG

def start_record(metadata: MetadataObject):
    """
    Начать запись экрана в дополнительном процессе
    """
    input_format, input_device = get_input_params()

    if input_format == "wf-recorder": # wayland so we use wf-recorder
        os.system(f"wf-recorder --file=test/{metadata.title}.mp4")
    else: # xorg or other OS so we use ffmpeg
        process = (
            ffmpeg
            .input(input_device, format=input_format, framerate=metadata.fps)
            .output(f"test/{metadata.title}.mp4", vcodec="libx264", pix_fmt="yuv420p")
            .overwrite_output()
            .run_async(pipe_stdin=True)
        )