
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.firefox import GeckoDriverManager # Для Firefox
import time
import json
import csv
import logging
import os

# Настройка логирования
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    handlers=[
                        logging.FileHandler("parser_multi_browser.log", encoding='utf-8'),
                        logging.StreamHandler()
                    ])

class WebParser:
    def __init__(self, use_selenium=False, headless=True, browser='chrome'):
        self.use_selenium = use_selenium
        self.driver = None
        self.browser = browser.lower() # 'chrome' или 'firefox'

        if self.use_selenium:
            self._setup_selenium_driver(headless)

    def _setup_selenium_driver(self, headless):
        """Настраивает Selenium WebDriver для выбранного браузера."""
        try:
            if self.browser == 'chrome':
                options = ChromeOptions()
                service = ChromeService(ChromeDriverManager().install())
            elif self.browser == 'firefox':
                options = FirefoxOptions()
                service = FirefoxService(GeckoDriverManager().install())
            else:
                logging.error(f"Неподдерживаемый браузер: {self.browser}. Используйте 'chrome' или 'firefox'.")
                self.use_selenium = False
                return

            if headless:
                options.add_argument("--headless") # Запуск браузера в фоновом режиме
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            # Общий User-Agent, можно уточнить для конкретного браузера
            options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
            
            if self.browser == 'chrome':
                self.driver = webdriver.Chrome(service=service, options=options)
            elif self.browser == 'firefox':
                self.driver = webdriver.Firefox(service=service, options=options)

            logging.info(f"Selenium WebDriver для {self.browser.capitalize()} запущен успешно.")
        except Exception as e:
            logging.error(f"Ошибка при запуске Selenium WebDriver для {self.browser.capitalize()}: {e}")
            self.use_selenium = False # Отключаем Selenium, если не удалось запустить
            self.driver = None

    def fetch_html(self, url, delay=1, retries=3):
        """Получает HTML-код страницы, используя requests или Selenium."""
        logging.info(f"Получение HTML для: {url}")
        time.sleep(delay) # Задержка перед запросом

        if self.use_selenium and self.driver:
            try:
                self.driver.get(url)
                # Дополнительная задержка для загрузки динамического контента
                time.sleep(delay * 2)
                return self.driver.page_source
            except Exception as e:
                logging.error(f"Selenium-ошибка при получении {url}: {e}")
                return None
        else:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            for i in range(retries):
                try:
                    response = requests.get(url, headers=headers, timeout=15)
                    response.raise_for_status()
                    return response.text
                except requests.exceptions.RequestException as e:
                    logging.warning(f"Попытка {i+1}/{retries} Ошибка при запросе к {url}: {e}")
                    time.sleep(delay * (i + 1)) # Увеличиваем задержку при повторной попытке
            logging.error(f"Не удалось получить HTML для {url} после {retries} попыток.")
            return None

    def parse_html(self, html_content):
        """Парсит HTML-контент с помощью BeautifulSoup."""
        if not html_content:
            return None
        return BeautifulSoup(html_content, 'html.parser')

    def extract_elements(self, soup, selector_type='css', selector='body'):
        """
        Извлекает элементы по заданному селектору.
        selector_type: 'css' (по умолчанию) или 'xpath' (если используется Selenium для поиска)
        selector: CSS-селектор или XPath выражение.
        Возвращает список извлеченного текста или объектов BeautifulSoup.
        """
        extracted_data = []
        if soup:
            if selector_type == 'css':
                elements = soup.select(selector)
                for element in elements:
                    extracted_data.append(element.get_text(strip=True))
            # Для XPath можно использовать soup.find_all(attrs={'xpath': ...})
            # но для сложных XPath лучше использовать driver.find_elements
            # if selector_type == 'xpath' and self.driver:
            #     # Это работает только если вы уже загрузили страницу через Selenium
            #     # и теперь ищете элементы через драйвер
            #     elements = self.driver.find_elements(By.XPATH, selector)
            #     for element in elements:
            #         extracted_data.append(element.text.strip())
            # else:
            #     logging.warning(f"Неподдерживаемый тип селектора: {selector_type} или Selenium драйвер неактивен для XPath.")
        return extracted_data

    def extract_multiple_data(self, soup, data_patterns):
        """
        Извлекает различные типы данных на основе словаря шаблонов.
        data_patterns: {'data_name': 'css_selector_for_data', ...}
        Возвращает словарь извлеченных данных.
        """
        results = {}
        if soup:
            for name, selector in data_patterns.items():
                elements = soup.select(selector)
                if len(elements) == 1:
                    results[name] = elements[0].get_text(strip=True)
                elif len(elements) > 1:
                    results[name] = [el.get_text(strip=True) for el in elements]
                else:
                    results[name] = None
        return results

    def follow_pagination(self, start_url, next_page_selector, max_pages=5, delay_between_pages=2):
        """
        Парсит несколько страниц, следуя ссылке "следующая страница".
        next_page_selector: CSS-селектор для кнопки/ссылки "следующая страница".
        """
        all_pages_html = []
        current_url = start_url
        page_count = 0

        while current_url and page_count < max_pages:
            logging.info(f"Парсинг страницы {page_count + 1}: {current_url}")
            html_content = self.fetch_html(current_url, delay=delay_between_pages)
            if not html_content:
                logging.error(f"Не удалось получить HTML для {current_url}. Прерываем пагинацию.")
                break
            
            soup = self.parse_html(html_content)
            if not soup:
                logging.error(f"Не удалось распарсить HTML для {current_url}. Прерываем пагинацию.")
                break

            all_pages_html.append(soup)
            page_count += 1

            # Ищем ссылку на следующую страницу
            next_link_tag = soup.select_one(next_page_selector)
            if next_link_tag and next_link_tag.has_attr('href'):
                next_page_href = next_link_tag['href']
                if not next_page_href.startswith(('http://', 'https://')):
                    # Если ссылка относительная, формируем абсолютную
                    base_url = requests.compat.urlparse(current_url).scheme + "://" + requests.compat.urlparse(current_url).netloc
                    current_url = requests.compat.urljoin(base_url, next_page_href)
                else:
                    current_url = next_page_href
                logging.info(f"Найдена следующая страница: {current_url}")
            else:
                logging.info("Ссылка на следующую страницу не найдена. Завершаем пагинацию.")
                current_url = None # Завершаем цикл

        logging.info(f"Парсинг пагинации завершен. Обработано {page_count} страниц.")
        return all_pages_html

    def close_driver(self):
        """Закрывает Selenium WebDriver."""
        if self.driver:
            self.driver.quit()
            logging.info("Selenium WebDriver закрыт.")

def save_data_to_csv(data_list, filename="output.csv"):
    """Сохраняет список словарей в CSV файл."""
    if not data_list:
        logging.warning("Нет данных для сохранения в CSV.")
        return

    try:
        # Убедимся, что все элементы имеют одинаковые ключи для заголовков CSV
        # Можно использовать union of keys, если структуры могут отличаться
        all_keys = sorted(list(set(key for d in data_list for key in d.keys())))
        
        with open(filename, 'w', newline='', encoding='utf-8') as output_file:
            dict_writer = csv.DictWriter(output_file, fieldnames=all_keys)
            dict_writer.writeheader()
            dict_writer.writerows(data_list)
        logging.info(f"Данные успешно сохранены в {filename}")
    except IOError as e:
        logging.error(f"Ошибка при сохранении CSV файла {filename}: {e}")

def save_data_to_json(data_list, filename="output.json"):
    """Сохраняет список словарей в JSON файл."""
    if not data_list:
        logging.warning("Нет данных для сохранения в JSON.")
        return

    try:
        with open(filename, 'w', encoding='utf-8') as output_file:
            json.dump(data_list, output_file, ensure_ascii=False, indent=4)
        logging.info(f"Данные успешно сохранены в {filename}")
    except IOError as e:
        logging.error(f"Ошибка при сохранении JSON файла {filename}: {e}")

# --- Пример использования расширенного парсера ---
if __name__ == "__main__":
    # Пример 1: Парсинг статической страницы с requests (без Selenium)
    print("\n--- Пример 1: Парсинг статической страницы (Википедия) с Requests ---")
    parser_requests = WebParser(use_selenium=False)
    
    wiki_url = "https://ru.wikipedia.org/wiki/%D0%9F%D0%B0%D1%80%D1%81%D0%B8%D0%BD%D0%B3"
    html_content_wiki = parser_requests.fetch_html(wiki_url)
    
    if html_content_wiki:
        soup_wiki = parser_requests.parse_html(html_content_wiki)
        wiki_data_patterns = {
            'title': 'h1.firstHeading',
            'first_paragraph': 'div.mw-parser-output > p:nth-of-type(1)',
            'toc_items': 'div#toc ul li a' # Элементы оглавления
        }
        extracted_wiki_data = parser_requests.extract_multiple_data(soup_wiki, wiki_data_patterns)
        
        print(f"Заголовок: {extracted_wiki_data.get('title')}")
        print(f"Первый параграф: {extracted_wiki_data.get('first_paragraph')[:200]}...")
        print(f"Элементы оглавления (первые 5): {extracted_wiki_data.get('toc_items')[:5]}")
        save_data_to_json([extracted_wiki_data], "wiki_parsing_data.json")

    # Пример 2: Парсинг динамической страницы с Selenium (Chrome)
    print("\n--- Пример 2: Парсинг динамической страницы (quotes.toscrape.com/js/) с Chrome ---")
    # target_dynamic_url = "https://www.amazon.com/Best-Sellers-Books/zgbs/books" # Пример сложной динамической страницы
    target_dynamic_url_js = "https://quotes.toscrape.com/js/" # Простой сайт для тестирования JS-парсинга

    parser_chrome = WebParser(use_selenium=True, headless=True, browser='chrome') 

    if parser_chrome.driver:
        html_content_dynamic_chrome = parser_chrome.fetch_html(target_dynamic_url_js, delay=3)
        if html_content_dynamic_chrome:
            soup_dynamic_chrome = parser_chrome.parse_html(html_content_dynamic_chrome)
            quotes_data_chrome = []
            quote_elements_chrome = soup_dynamic_chrome.select('div.quote')
            for quote_div in quote_elements_chrome:
                text = quote_div.select_one('span.text').get_text(strip=True)
                author = quote_div.select_one('small.author').get_text(strip=True)
                tags = [tag.get_text(strip=True) for tag in quote_div.select('div.tags a.tag')]
                quotes_data_chrome.append({'text': text, 'author': author, 'tags': tags})
            
            print(f"Извлечено {len(quotes_data_chrome)} цитат (Chrome):")
            for q in quotes_data_chrome[:3]:
                print(f"  - '{q['text'][:50]}...' by {q['author']}")

            save_data_to_csv(quotes_data_chrome, "quotes_data_chrome.csv")
            save_data_to_json(quotes_data_chrome, "quotes_data_chrome.json")
        parser_chrome.close_driver()
    else:
        print("Selenium (Chrome) не был инициализирован. Пропуск примера с динамическим парсингом.")

    # Пример 3: Парсинг динамической страницы с Selenium (Firefox)
    print("\n--- Пример 3: Парсинг динамической страницы (quotes.toscrape.com/js/) с Firefox ---")
    parser_firefox = WebParser(use_selenium=True, headless=True, browser='firefox') 

    if parser_firefox.driver:
        html_content_dynamic_firefox = parser_firefox.fetch_html(target_dynamic_url_js, delay=3)
        if html_content_dynamic_firefox:
            soup_dynamic_firefox = parser_firefox.parse_html(html_content_dynamic_firefox)
            quotes_data_firefox = []
            quote_elements_firefox = soup_dynamic_firefox.select('div.quote')
            for quote_div in quote_elements_firefox:
                text = quote_div.select_one('span.text').get_text(strip=True)
                author = quote_div.select_one('small.author').get_text(strip=True)
                tags = [tag.get_text(strip=True) for tag in quote_div.select('div.tags a.tag')]
                quotes_data_firefox.append({'text': text, 'author': author, 'tags': tags})
            
            print(f"Извлечено {len(quotes_data_firefox)} цитат (Firefox):")
            for q in quotes_data_firefox[:3]:
                print(f"  - '{q['text'][:50]}...' by {q['author']}")

            save_data_to_csv(quotes_data_firefox, "quotes_data_firefox.csv")
            save_data_to_json(quotes_data_firefox, "quotes_data_firefox.json")
        parser_firefox.close_driver()
    else:
        print("Selenium (Firefox) не был инициализирован. Пропуск примера с динамическим парсингом.")

    print("\nРасширенный веб-парсер с поддержкой нескольких браузеров завершил работу.")