import os
import platform
import re
import signal
import subprocess
from typing import Optional, Tuple

import ffmpeg

from core.schemas.metadata_object import MetadataObject
from core.utils.logger import LoggerFactory

log = LoggerFactory.get_logger(__name__)


class UnsupportedPlatformError(RuntimeError):
    pass


class ScreenRecorderError(RuntimeError):
    pass


def _detect_macos_screen_index() -> str:
    # avfoundation назначает индексы устройств динамически (зависят от подключённой
    # периферии: iPhone Continuity Camera, OBS virtual cam и т. д.). Парсим вывод
    # `-list_devices` и ищем первый "Capture screen N".
    try:
        result = subprocess.run(
            ["ffmpeg", "-f", "avfoundation", "-list_devices", "true", "-i", ""],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        raise UnsupportedPlatformError(
            f"Не удалось определить screen device через ffmpeg: {exc}"
        ) from exc

    output = (result.stderr or "") + (result.stdout or "")
    match = re.search(r"\[(\d+)\]\s+Capture screen \d+", output)
    if not match:
        raise UnsupportedPlatformError(
            "ffmpeg не сообщил ни одного 'Capture screen' устройства. "
            "Проверьте разрешение Screen Recording в System Settings → Privacy."
        )
    return match.group(1)


def get_input_params() -> Tuple[str, str]:
    """Определяет бэкенд записи экрана и input device для текущей ОС/среды.

    Возвращает кортеж (backend, input_device).
    Поддерживаются: Windows (gdigrab), macOS (avfoundation), Linux+Xorg (x11grab),
    Linux+Wayland (gpu-screen-recorder).

    Кидает UnsupportedPlatformError для всего остального.
    """
    try:
        os_name = platform.system()
        if os_name == "Windows":
            return "gdigrab", "desktop"
        if os_name == "Darwin":
            screen_idx = _detect_macos_screen_index()
            return "avfoundation", f"{screen_idx}:none"
        if os_name == "Linux":
            is_wayland = (
                os.environ.get("XDG_SESSION_TYPE") == "wayland"
                or os.environ.get("WAYLAND_DISPLAY") is not None
            )
            if is_wayland:
                return "gpu-screen-recorder", ""
            return "x11grab", ":0.0"
        raise UnsupportedPlatformError(f"Unsupported OS: {os_name}")
    except UnsupportedPlatformError:
        raise
    except Exception as exc:
        raise UnsupportedPlatformError(
            f"Не удалось определить параметры записи экрана: {type(exc).__name__}: {exc}"
        ) from exc


def _start_gpu_screen_recorder(filepath: str, fps: int, cursor: bool) -> subprocess.Popen:
    """Запуск gpu-screen-recorder для Wayland.

    Поддерживает выключение курсора через флаг -cursor no.
    """
    cmd = [
        "gpu-screen-recorder",
        "-w", "screen",
        "-f", str(fps),
        "-cursor", "yes" if cursor else "no",
        "-o", filepath,
    ]
    log.info("Starting gpu-screen-recorder: %s", " ".join(cmd))
    try:
        return subprocess.Popen(cmd, stdin=subprocess.PIPE)
    except FileNotFoundError as exc:
        raise ScreenRecorderError(
            "gpu-screen-recorder не найден в PATH. Установите его для записи Wayland-сессий."
        ) from exc


def _start_ffmpeg(filepath: str, input_format: str, input_device: str,
                  fps: int, cursor: bool) -> subprocess.Popen:
    """Запуск ffmpeg для Xorg/Windows/macOS."""
    input_kwargs = {"format": input_format, "framerate": fps}
    if input_format == "avfoundation":
        input_kwargs["capture_cursor"] = 1 if cursor else 0
    elif not cursor:
        input_kwargs["draw_mouse"] = 0

    return (
        ffmpeg
        .input(input_device, **input_kwargs)
        .output(filepath, vcodec="libx264", pix_fmt="yuv420p")
        .overwrite_output()
        .run_async(pipe_stdin=True)
    )


def start_record(metadata: MetadataObject, output: str) -> subprocess.Popen:
    """Запуск записи экрана в фоновом процессе."""
    input_format, input_device = get_input_params()
    filepath = f"{output}/{metadata.title}_recorded.mp4"

    if input_format == "gpu-screen-recorder":
        return _start_gpu_screen_recorder(filepath, metadata.fps, metadata.cursor)

    return _start_ffmpeg(filepath, input_format, input_device, metadata.fps, metadata.cursor)


def _send_quit_via_stdin(process: subprocess.Popen) -> bool:
    """Завершение ffmpeg через 'q' в stdin."""
    if process.stdin is None:
        return False
    try:
        process.stdin.write(b"q\n")
        process.stdin.flush()
        process.wait(timeout=2)
        return True
    except (BrokenPipeError, subprocess.TimeoutExpired, OSError):
        return False


def _send_sigint(process: subprocess.Popen) -> bool:
    """Корректное завершение через SIGINT (Linux/macOS) или CTRL_C_EVENT (Windows)."""
    try:
        if platform.system() == "Windows":
            sig = getattr(signal, "CTRL_C_EVENT", signal.SIGINT)
        else:
            sig = signal.SIGINT
        process.send_signal(sig)
        process.wait(timeout=3)
        return True
    except (subprocess.TimeoutExpired, ValueError, OSError):
        return False


def stop_record(process: Optional[subprocess.Popen]) -> None:
    """Безопасная остановка процесса записи."""
    if process is None:
        return
    log.info("Останавливаем запись экрана.")

    if process.poll() is not None:
        return

    if _send_sigint(process):
        return

    if _send_quit_via_stdin(process):
        return

    try:
        process.terminate()
        process.wait(timeout=2)
        return
    except subprocess.TimeoutExpired:
        pass

    log.warning("Запись экрана не завершилась штатно, kill.")
    process.kill()
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        pass
