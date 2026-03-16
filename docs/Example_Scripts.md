# Примеры Live Recording Mode
1.
```
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

2.
```
metadata:
    title: TestVideo2
    resolution: 1920x1080
    cursor: true

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

3.
```
metadata:
        title: TestVideo2
        resolution: 1920x1080
        cursor: false

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
        tts: Что выделяет Astra Automation среди конкурентов? Снижение стоимости владения проектами, единый фреймворк автоматизации, сокращение времени развертывания программного обеспечения ну и конечно же снижение времени на устранение аварийных ситуаций.
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
            action_5:
              type: wait
              duration: 1
            action_6:
              type: input
              selector: //*[@id='firstname']
              text: Вадим
            action_7:
              type: wait
              duration: 1
            action_8:
              type: input
              selector: //*[@id='middlename']
              text: Сергеевич
            action_9:
              type: wait
              duration: 1
            action_10:
              type: input
              selector: //*[@id='phone']
              text: 88005553535
            action_11:
              type: wait
              duration: 1
            action_12:
              type: input
              selector: //*[@id='email']
              text: myemail@mail.ru
            action_13:
              type: wait
              duration: 1
            action_14:
              type: input
              selector: //*[@id="company"]
              text: Astra
            action_15:
              type: wait
              duration: 1
            action_16:
              type: input
              selector: //*[@id="message"]
              text: Видишь? Это очень просто!
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