# Замечания по проекту

## README.md

* В требованиях стоит версия Python 1.13+. Видимо должна быть 3.13+?
* Нет шага на переход к виртуальному окружению Python, которое созданко в результате выполнения uv sync.
* Написано, что FFMPEG нужен для Live recording, однако в режиме Screeshot тоже потребовался. 

## Getting started guide

* Следует добавить переход к виртуальному окружению:

  `source .venv/bin/activate`

* Скрипт main.py следует сделать исполнямым, добавив shebang и задав x mode.
* В примерной команде дана ссылка на отсутствующий каталог examples/. Кстати, не надо использовать слово директорий. Правильно - каталог.
* Раз уж режим screenshot объявлен основным, то с него и надо начать. После него - Live recording.
* Выполнение команды:

  `uv run python main.py -f examples/screenshot_minimal.yaml -o output`

  Получил отказ с сообщениеями вида:

  - <project_path>/.venv/lib/python3.14/site-packages/pydub/utils.py:300: SyntaxWarning: "\(" is an invalid escape sequence. Such sequences will not work in the future. Did you mean "\\("? A raw string is also an option.
  - <project_path>/.venv/lib/python3.14/site-packages/pydub/utils.py:170: RuntimeWarning: Couldn't find ffmpeg or avconv - defaulting to ffmpeg, but may not work
  warn("Couldn't find ffmpeg or avconv - defaulting to ffmpeg, but may not work", RuntimeWarning)
YANDEX_API_KEY не найден в .env файле
чтение скрипта: mytest/examples/screenshot_minimal.yaml
произошла критическая ошибка: [Errno 2] No such file or directory: 'ffmpeg'
  - FileNotFoundError: [Errno 2] No such file or directory: 'ffmpeg'

На Macbook с установленной ffmpeg процесс запустился с показом экранов из документации, созданы 5 файлов вида scene_X.wav.
Сообщения об ошибках те же (про mpeg конечно сообщений не было). В результате не был создан файл mpeg:

- FileNotFoundError: 'mytest/output/TestVideo_recorded.mp4' not found