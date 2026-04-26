# СИСТЕМА ГЕНЕРАЦИИ ДЕМОНСТРАЦИОННЫХ РОЛИКОВ НА ОСНОВЕ СКРИПТОВ
Этот проект из себя представляет систему модулей для генерации демонстрационных видео-роликов Astra Automation с использованием YAML-скриптов.

Эта система позволит сотрудникам создавать видео-ролики, презентующие новую технологию или обучающий материал, гораздо быстрее, чем это было бы при ручном монтаже.

**В ключевые особенности входит:**
- Поддержка двух режимов записи: Live Recording и Screenshot Mode
- Функционал для воспроизведения аудио с использованием TTS и субтитров к нему
- Множество эффектов монтажа, такие как переходы между кадрами, наложение различных изображений или вставка музыки

# Как использовать
## Необходимые требования к окружению
- [Python версии 3.13+](https://www.python.org/downloads/release/python-31311/)
- [Пакетный менеджер UV для установки зависимостей](https://docs.astral.sh/uv/getting-started/installation/)
- [FFMPEG](https://www.ffmpeg.org/) — нужен и для Live Recording, и для Screenshot Mode (под капотом MoviePy вызывает ffmpeg при сборке итогового видео).
##### Дополнительно для режима Live Recording
- [Утилита gpu-screen-recorder для записи Wayland-сессий](https://git.dec05eba.com/gpu-screen-recorder/)

    *Примечание. Для Wayland (Hyprland, GNOME, KDE Plasma) используется gpu-screen-recorder. Поддерживает скрытие курсора (`-cursor no`).*
- [Chrome Browser](https://www.google.com/intl/ru_ru/chrome/)

    *Поддержка Firefox на данный момент не реализована.*

## Установка
Склонируйте репозиторий в директорию с проектом или установите последнюю версюю релиза
```
git clone https://gitflic.ru/project/student-projects/aa-video-builder.git
```
После этого установите зависимости:
```
uv sync
```
Для windows:
```
python -m uv sync
```

Для использования перейдите в [руководство для начинающих](docs/Getting_Started_Guide.md).

# Документация
1. [Руководство по использованию CLI или API](docs/API_Reference.md)
2. [Руководство модулей системы](docs/Architecture_Document.md)
3. [Руководство разработчика](docs/Developer_Guide.md)
4. [Примеры YAML-скриптов](docs/Example_Scripts.md)
5. [Руководство режима Live Recording](docs/Live_Recording_Mode_Guide.md)
6. [Руководство Screenshot Mode](docs/Screenshot_Mode_Guide.md)
7. [Руководство по оптимизации](docs/Performance_Tuning.md)
8. [Руководство по написанию YAML-скриптов](docs/Script_Format_Specification.md)
9. [FAQ](docs/Troubleshooting_Guide.md)