# Selenium WebDriver или Puppeteer (Node.js) для управления браузером
# Воспроизведение действий из скрипта (режим Live Recording)
# Обработка ошибок и ожиданий
# Снимки состояния браузера при ошибке

# basic lib imports
from typing import List
from time import sleep

# external lib imports
from selenium import webdriver
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service

# schemas imports
from src.schemas.action_object import ActionObject

def start_actions(actions: List[ActionObject]):
    """Запускает работу selenium с webdriver хрома на основе списка действий"""
    # подключение сервиса (управляет веб-драйвером)
    service = Service(executable_path=ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service) # сам веб-драйвер

    # выполнение каждого действия в зависимости от типа
    for action in actions:
        match(action.type):
            case "navigate": driver.get(action.url)
            case "wait": sleep(action.duration) # пока временное решение. Оно блокирует поток выполнения
            case "click":
                splitter = action.selector.split("_")
                tag = splitter[0]
                params = splitter[1:]
                driver.find_element("xpath", f"//{tag}[{" and ".join(params)}]").click()