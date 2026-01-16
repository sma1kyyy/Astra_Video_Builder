# Модуль на Python для разбора входного скрипта
# Валидация синтаксиса и логики
# Преобразование в промежуточный AST (Abstract Syntax Tree)
# Поддержка различных форматов (JSON, YAML)

import json
import os

def load_script(path):
    if not os.path.exists(path):
        raise FileNotFoundError(f"Файл сценария не найден: {path}")

    with open(path, "r", encoding="utf-8") as file:
        data = json.load(file)

    if "scenes" not in data:
        raise ValueError("В сценарии отсутствует список сцен")

    return data