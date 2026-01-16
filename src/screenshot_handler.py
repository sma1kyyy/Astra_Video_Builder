# Загрузка и валидация файлов снимков экрана
# Создание видеопоследовательности из снимков
# Применение переходов и эффектов
# Добавление аннотаций на снимки

def build_timeline(script):
    timeline = []

    for scene in script["scenes"]:
        timeline.append({
            "image": scene["image"],
            "duration": scene["duration"]
        })

    return timeline