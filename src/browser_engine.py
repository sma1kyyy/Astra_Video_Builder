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
from selenium.webdriver import ChromeOptions, Keys
from selenium.webdriver.common.action_chains import ActionChains

# schemas imports
from src.schemas.action_object import ActionObject

# подключение сервиса (управляет веб-драйвером)
service = Service(executable_path=ChromeDriverManager().install())

# базовая настройка
options = ChromeOptions()

options.add_argument("--kiosk")
options.add_argument(
    "user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/51.0.2704.103 Safari/537.36"
)
options.add_argument("--disable-blink-features=AutomationControlled")
options.add_experimental_option("excludeSwitches", ['enable-automation'])

driver = webdriver.Chrome(service=service, options=options) # сам веб-драйвер

def start_actions(actions: List[ActionObject]):
    """Запускает работу selenium с webdriver хрома на основе списка действий"""
    # выполнение каждого действия в зависимости от типа
    for action in actions:
        match(action.type):
            case "navigate": driver.get(action.url)
            case "wait": sleep(action.duration) # пока временное решение. Оно блокирует поток выполнения
            case "click":
                splitter = action.selector.split("|")
                tag = splitter[0]
                params = splitter[1:]
                driver.find_element("xpath", f"//{tag}[{" and ".join(params)}]").click()
            case "input":
                splitter = action.selector.split("|")
                tag = splitter[0]
                params = splitter[1:]
                search_input = driver.find_element("xpath", f"//{tag}[{" and ".join(params)}]")
                search_input.send_keys(action.text)
                search_input.send_keys(Keys.ENTER)