# FFmpeg для захвата и кодирования видео (режим Live Recording)
# Настройка разрешения, FPS, кодека
# Встраивание видеокодека H.264 для MP4

# basic lib imports
import os
import time
import platform
import subprocess

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

def start_record(metadata: MetadataObject, output: str):
    """
    Начать запись экрана в дополнительном процессе
    """
    input_format, input_device = get_input_params()

    filepath = f"{output}/{metadata.title}_recorded.mp4"

    if input_format == "wf-recorder": # wayland so we use wf-recorder
        if metadata.cursor:
            process = subprocess.Popen([
                "wf-recorder", 
                f"--file={filepath}",
                f"--framerate={metadata.fps}"
            ], shell=False)
        else:
            process = subprocess.Popen([
                "wf-recorder",
                f"--file={filepath}",
                f"--framerate={metadata.fps}"
            ], shell=False)
        return process
    else: # xorg or other OS so we use ffmpeg
        if metadata.cursor:
            process = (
                ffmpeg
                .input(
                    input_device,
                    format=input_format,
                    framerate=metadata.fps
                       )
                .output(f"{filepath}", vcodec="libx264", pix_fmt="yuv420p")
                .overwrite_output()
                .run_async(pipe_stdin=True)
            )
        else:
            process = (
                ffmpeg
                .input(
                    input_device,
                    format=input_format,
                    framerate=metadata.fps,
                    draw_mouse=0
                )
                .output(f"{filepath}", vcodec="libx264", pix_fmt="yuv420p")
                .overwrite_output()
                .run_async(pipe_stdin=True)
            )
        return process

def stop_record(process):
    """
    Остановка фонового процесса записи
    """

    if process.poll() is None:  # если процесс жив
        try: # по умолчанию ffmpeg останавливает запись через q
            process.stdin.write(b'q\n')
            process.stdin.flush()
            process.wait(timeout=2)
            return
        except (BrokenPipeError, subprocess.TimeoutExpired):
            pass

        try: # если не помогло, пытаемся юзать ctrl+C
            process.send_signal(0x40010003)  # CTRL_C_EVENT
            process.wait(timeout=2)
            return
        except:
            pass

        try: # пытаемся остановить процесс программно
            process.terminate()
            process.wait(timeout=1)
            return
        except subprocess.TimeoutExpired:
            pass

        process.kill() # просто убиваем его, если ничего выше не помогло
        process.wait()