# Selenium WebDriver или Puppeteer (Node.js) для управления браузером
# Воспроизведение действий из скрипта (режим Live Recording)
# Обработка ошибок и ожиданий
# Снимки состояния браузера при ошибке
import traceback
# basic lib imports
from typing import List
from time import sleep, time

# external lib imports
from selenium import webdriver
from selenium.common import TimeoutException
from selenium.webdriver.remote.webelement import WebElement
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
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

def start_actions(actions: List[ActionObject], tts_time: int):
    """
    Запускает работу selenium с webdriver хрома на основе списка действий.
    tts_time - время, сколько длится tts в этой сцене.
    """
    print(f"TTS_TIME: {tts_time}")
    # выполнение каждого действия в зависимости от типа
    start_actions_time = time()
    try:
        for action in actions:
            match(action.type.lower()):
                case "navigate": driver.get(action.url)
                case "wait": sleep(action.duration) # пока временное решение, но рабочее. Оно блокирует поток выполнения
                case "click":
                    sleep(1)
                    splitter = action.selector.split("|")
                    tag = splitter[0]
                    params = splitter[1:]

                    elem = return_displayed_if_exists(
                        driver.find_elements("xpath", f"//{tag}[{" and ".join(params)}]"))

                    if elem:
                        elem.click()
                    else:
                        raise Exception(f"Element {splitter} not found")
                case "input":
                    sleep(1)
                    splitter = action.selector.split("|")
                    tag = splitter[0]
                    params = splitter[1:]
                    search_input = return_displayed_if_exists(
                        driver.find_elements("xpath", f"//{tag}[{" and ".join(params)}]"))

                    if search_input:
                        search_input.click()
                        search_input.send_keys(action.text)
                        sleep(1)
                        search_input.send_keys(Keys.ENTER)
                    else:
                        raise Exception(f"Element {splitter} not found")
                case "scrollup":
                    sleep(1)
                    params = {"top": f"-{action.point}", "left": 0} # , "behavior": "smooth"

                    driver.execute_script(f"window.scrollBy({params});")
                case "scrolldown":
                    sleep(1)
                    params = {"top": f"{action.point}", "left": 0} # , "behavior": "smooth"
                    driver.execute_script(f"window.scrollBy({params});")
    except Exception as e:
        print(e)
        traceback.print_exc()
    # если действия закончились, и пора переходить к следующей сцене, но TTS ещё не завершился
    actions_time = int(time() - start_actions_time)
    print(f"ACTIONS_TIME: {actions_time}")
    if tts_time > actions_time:
        print("БОЛЬШЕ")
        sleep(tts_time - actions_time + 1) # +1 потому, что int округляет вниз. Лучше перебдеть, чем недобдеть.

def return_displayed_if_exists(elements: List[WebElement]):
    for elem in elements:
        if elem.is_displayed() and elem.is_enabled():
            return elem
    return None
