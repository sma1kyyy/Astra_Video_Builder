# Примеры Live Recording Mode
1. ```
   metadata:
      title: TestVideo
      resolution: 1920x1080
      cursor: false

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
                selector: span[@class='toctree-toggle']
              action_4:
                type: wait
                duration: 1
              action_5:
                type: click
                selector: a[text()='Быстрый старт']
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
                selector: input[@class='form-control']
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
                selector: button[@class='btn btn-sm nav-link pst-navbar-icon theme-switch-button pst-js-only']
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