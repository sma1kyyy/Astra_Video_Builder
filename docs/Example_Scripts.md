# Примеры Live Recording Mode
Готовые файлы в репозитории:
- `examples/liveRecording/astra_doc_example.yaml`
- `examples/screenshot/screenshot_minimal.yaml`
- `examples/screenshot/screenshot_extended_demo.yaml`

## 1. Документация Astra Automation (Chrome, с TTS)
```yaml
metadata:
    title: TestVideo
    resolution: 1920x1080
    description: Демонстрация документации Astra Automation
    language: ru
    mode: live
    browser: chrome
    cursor: false
    fps: 30
    save_files: false

acts:
  act_1:
    scenes:
      scene_1:
        duration: 5
        tts: Проверка работы режима Live Recording. Переходим в документацию Astra Automation.
        voice: zahar
        actions:
          action_1:
            type: navigate
            url: https://docs.astra-automation.ru/2.0/
          action_2:
            type: wait
            duration: 1
      scene_2:
        tts: Для начала работы, следует перейти в быстрый старт.
        voice: zahar
        duration: 5
        actions:
          action_3:
            type: click
            selector: //span[@class='toctree-toggle']
          action_4:
            type: wait
            duration: 1
          action_5:
            type: click
            selector: //a[text()='Быстрый старт']
          action_6:
            type: wait
            duration: 1
      scene_3:
        tts: Для демонстрации проекта, можно воспользоваться поиском.
        voice: zahar
        duration: 5
        actions:
          action_8:
            type: input
            selector: //input[@class='form-control']
            text: тестирование
          action_9:
            type: wait
            duration: 2
      scene_4:
        tts: Скроллинг на динамических страницах зависит от качества соединения.
        voice: zahar
        duration: 5
        actions:
          action_9:
            type: wait
            duration: 1
          action_10:
            type: scrollDown
            point: 500
          action_11:
            type: wait
            duration: 2
          action_12:
            type: scrollUp
            point: 500
          action_13:
            type: click
            selector: //button[@class='btn btn-sm nav-link pst-navbar-icon theme-switch-button pst-js-only']
          action_14:
            type: wait
            duration: 2
      scene_5:
        tts: Хорошего дня!
        voice: jane
        duration: 5
        actions:
          action_1:
            type: wait
            duration: 3
```

## 2. The-internet (Firefox, с курсором)
```yaml
metadata:
    title: TestVideo2
    resolution: 1920x1080
    description: Демонстрация автоматизации браузера на the-internet.herokuapp.com
    language: ru
    mode: live
    browser: firefox
    cursor: true
    fps: 30
    save_files: false

acts:
  act_1:
    scenes:
      scene_1:
        duration: 5
        tts: Проверка различных возможностей автоматизации браузера. Переходим на сайт the-internet, на котором предоставлено множество вариантов для автоматизации тестирования.
        voice: jane
        actions:
          action_1:
            type: navigate
            url: https://the-internet.herokuapp.com/
          action_2:
            type: wait
            duration: 1
      scene_2:
        tts: Для начала, попробуем находить элементы и взаимодействовать с ними. Переходим по ссылке Add/Remove elements. После этого нажимаем на кнопку добавить элемент.
        voice: jane
        duration: 5
        actions:
          action_1:
            type: wait
            duration: 1
          action_2:
            type: navigate
            url: https://the-internet.herokuapp.com/add_remove_elements/
          action_3:
            type: wait
            duration: 1
          action_4:
            type: click
            selector: //button[text()='Add Element']
          action_5:
            type: wait
            duration: 1
      scene_3:
        tts: Как видно, на странице добавился новый элемент. Его можно легко удалить, просто нажав на нужную кнопку.
        voice: jane
        duration: 5
        actions:
          action_1:
            type: wait
            duration: 1
          action_2:
            type: click
            selector: //button[text()='Delete']
          action_3:
            type: wait
            duration: 2
      scene_4:
        tts: На этом всё. До свидания.
        voice: jane
        duration: 5
        actions:
          action_1:
            type: wait
            duration: 2
```

## 3. Astra Automation landing (форма обратной связи)
```yaml
metadata:
    title: TestVideo3
    resolution: 1920x1080
    description: Заполнение формы обратной связи на astra-automation.ru
    language: ru
    mode: live
    browser: chrome
    cursor: false
    fps: 30
    save_files: true

acts:
  act_1:
    scenes:
      scene_1:
        duration: 5
        tts: Astra Automation? Не просто очередная технология, про которую легко можно забыть!
        voice: jane
        actions:
          action_1:
            type: navigate
            url: https://astra-automation.ru/
          action_2:
            type: wait
            duration: 1
      scene_2:
        tts: Каждый проект требует автоматизации. А что, если автоматизировать саму автоматизацию?
        voice: jane
        duration: 5
        actions:
          action_1:
            type: wait
            duration: 1
      scene_3:
        tts: Astra Automation даст ответы на все вопросы!
        voice: jane
        duration: 5
        actions:
          action_1:
            type: wait
            duration: 2
          action_2:
            type: scrollTo
            selector: //div[@class='advantages-block']
          action_3:
            type: wait
            duration: 2
      scene_4:
        tts: Что выделяет Astra Automation среди конкурентов? Снижение стоимости владения и единый фреймворк автоматизации.
        voice: jane
        duration: 5
        actions:
          action_1:
            type: wait
            duration: 2

      scene_4b:
        tts: Также сокращение времени развертывания ПО и устранения аварийных ситуаций.
        voice: jane
        duration: 5
        actions:
          action_1:
            type: wait
            duration: 2

      scene_5:
        tts: Для чего применять? Например, установка, обновление и настройка ПО. Но это лишь малая часть функционала.
        voice: jane
        duration: 5
        actions:
          action_1:
            type: scrollTo
            selector: //div[@class='scenaries-block']
          action_2:
            type: wait
            duration: 2
      
      scene_6:
        tts: Установка и настройка через различные утилиты в несколько кликов!
        voice: jane
        duration: 5
        actions:
          action_1:
            type: scrollTo
            selector: //div[@class='methods-block']
          action_2:
            type: wait
            duration: 2
      scene_7:
        tts: Регестрируйся уже сейчас! Перейди на сайт astra-automation.ru, пролистай в самый низ, а после введи свои данные!
        voice: jane
        duration: 5
        actions:
            action_1:
              type: wait
              duration: 1
            action_2:
              type: scrollTo
              selector: //div[@class='feedback_block']
            action_3:
              type: wait
              duration: 1
            action_4:
              type: input
              selector: //*[@id='lastname']
              text: Гутник
              enter: false
            action_5:
              type: wait
              duration: 1
            action_6:
              type: input
              selector: //*[@id='firstname']
              text: Вадим
              enter: false
            action_7:
              type: wait
              duration: 1
            action_8:
              type: input
              selector: //*[@id='middlename']
              text: Сергеевич
              enter: false
            action_9:
              type: wait
              duration: 1
            action_10:
              type: input
              selector: //*[@id='phone']
              text: 88005553535
              enter: false
            action_11:
              type: wait
              duration: 1
            action_12:
              type: input
              selector: //*[@id='email']
              text: myemail@mail.ru
              enter: false
            action_13:
              type: wait
              duration: 1
            action_14:
              type: input
              selector: //*[@id="company"]
              text: Astra
              enter: false
            action_15:
              type: wait
              duration: 1
            action_16:
              type: input
              selector: //*[@id="message"]
              text: Видишь? Это очень просто!
              enter: false
            action_17:
              type: wait
              duration: 1
        
      scene_8:
        tts: Не забудь нажать галочки соглашений, это просто условность. До скорых встреч!
        voice: jane
        duration: 5
        actions:
          action_1:
            type: click
            selector: /html/body/section[9]/div/div[4]/div[2]/form/div[5]/label[1]/span[1]
          action_2:
            type: wait
            duration: 1
          action_3:
            type: click
            selector: /html/body/section[9]/div/div[4]/div[2]/form/div[5]/label[2]/span[1]
          action_4:
            type: wait
            duration: 1
```
# Примеры Screenshot Mode
## 1. screenshot minimal
```
metadata:
  title: demo_screenshot
  resolution: 1920x1080
  mode: screenshot
  fps: 24

acts:
  act_1:
    name: intro
    scenes:
      scene_1:
        name: screen one
        path: input/screen1.png
        duration: 4
        tts: "это стартовый экран и демонстрация smart аннотаций"
        subtitles: true
        subtitle_style: contrast
        subtitle_font_size: 38
        subtitle_max_chars: 92
        subtitle_bg_opacity: 0.58
        annotations:
          annotation_1:
            type: square
            transparency: 0.25
            target_text: "Astra"
            start_x: 120
            start_y: 90
            end_x: 580
            end_y: 320
            auto_padding: 18
            ocr: true
            ocr_target: both
          annotation_2:
            type: arrow
            transparency: 0.05
            target_text: "Astra"
            start_x: 100
            start_y: 220
            end_x: 460
            end_y: 220
            auto_from: left
```

**что демонстрирует:**
- базовый screenshot pipeline,
- subtitle style,
- smart annotation по `target_text`,
- ocr metadata sidecar.

**запуск:**
```bash
mkdir -p output
uv run python main.py -f examples/screenshot/screenshot_minimal.yaml -o output
```

**примечание:**
- в extended demo у smart-аннотаций добавлены и ручные координаты как fallback,
  поэтому даже без tesseract вы увидите понятную разметку.

## 2. шаблон ручной разметки
```yaml
metadata:
  title: manual_annotations_demo
  resolution: 1920x1080
  mode: screenshot
  fps: 24

acts:
  act_1:
    scenes:
      scene_1:
        path: input/screen1.png
        duration: 4
        tts: "ручная аннотация"
        subtitles: true
        subtitle_style: classic
        annotations:
          annotation_1:
            type: square
            transparency: 0.2
            start_x: 120
            start_y: 80
            end_x: 620
            end_y: 320
```

## 3. шаблон smart разметки
```yaml
metadata:
  title: smart_annotations_demo
  resolution: 1920x1080
  mode: screenshot
  fps: 24

acts:
  act_1:
    scenes:
      scene_1:
        path: input/screen1.png
        duration: 5
        tts: "smart поиск текста"
        subtitles: true
        subtitle_style: contrast
        annotations:
          annotation_1:
            type: square
            transparency: 0.24
            target_text: "Templates"
            auto_padding: 16
            ocr: true
            ocr_target: both
          annotation_2:
            type: arrow
            transparency: 0.07
            target_text: "Templates"
            auto_from: left
```

## 3.1 шаблон line / darrow + subplace
```yaml
metadata:
  title: lines_and_distance_demo
  resolution: 1920x1080
  mode: screenshot
  fps: 24

acts:
  act_1:
    scenes:
      scene_1:
        path: input/screen1.png
        duration: 5
        tts: "показываем связь и расстояние между элементами"
        subtitles: true
        subplace: up
        subtitle_style: contrast
        annotations:
          annotation_1:
            type: line
            transparency: 0.0
            start_x: 210
            start_y: 170
            end_x: 760
            end_y: 420
          annotation_2:
            type: darrow
            transparency: 0.0
            start_x: 300
            start_y: 500
            end_x: 1200
            end_y: 500
```

## 4. расширенный демонстрационный сценарий
```
metadata:
  title: demo_screenshot_extended
  resolution: 1920x1080
  mode: screenshot
  fps: 24

acts:
  act_1:
    name: onboarding
    scenes:
      scene_1:
        name: welcome
        path: input/screen1.png
        duration: 6
        tts: "добро пожаловать в демонстрацию screenshot mode. сначала посмотрим главный экран"
        subtitles: true
        subtitle_style: classic
        subtitle_font_size: 40
        subtitle_max_chars: 96
        subtitle_bg_opacity: 0.58
        annotations:
          annotation_1:
            type: square
            transparency: 0.35
            target_text: "Astra"
            start_x: 80
            start_y: 80
            end_x: 760
            end_y: 360
            auto_padding: 24
            ocr: true
            ocr_lang: rus+eng
            ocr_min_conf: 0.2
            ocr_target: both

      scene_2:
        name: second screen and smart arrow
        path: input/screen2.png
        duration: 7
        tts: "теперь покажем второй экран и автоматически направим стрелку на ключевую надпись"
        subtitles: true
        subtitle_style: contrast
        subtitle_font_size: 38
        subtitle_max_chars: 100
        subtitle_bg_opacity: 0.62
        annotations:
          annotation_1:
            type: arrow
            transparency: 0.08
            target_text: "Astra"
            start_x: 120
            start_y: 220
            end_x: 620
            end_y: 220
            auto_from: left
            auto_padding: 18
          annotation_2:
            type: square
            transparency: 0.4
            start_x: 160
            start_y: 120
            end_x: 780
            end_y: 420
            ocr: true
            ocr_target: metadata

      scene_3:
        name: login screen cinematic subtitles
        path: input/login_screen.png
        duration: 8
        tts: "в финале используем cinematic стиль субтитров и ручную аннотацию для формы логина"
        subtitles: true
        subtitle_style: cinematic
        subtitle_font_size: 42
        subtitle_max_chars: 110
        subtitle_bg_opacity: 0.68
        annotations:
          annotation_1:
            type: square
            transparency: 0.32
            start_x: 520
            start_y: 220
            end_x: 1420
            end_y: 760

```

что показывает:
- 3 сцены подряд (длиннее и нагляднее),
- разные стили субтитров (`classic`, `contrast`, `cinematic`),
- smart + manual аннотации,
- ocr sidecar metadata.

запуск:
```bash
mkdir -p output
uv run python main.py -f examples/screenshot/screenshot_extended_demo.yaml -o output
```