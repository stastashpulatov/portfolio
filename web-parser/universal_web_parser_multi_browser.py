import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.firefox import GeckoDriverManager
import time
import json
import csv
import logging
from urllib.parse import urljoin
import os
import hashlib
import jmespath # Для парсинга JSON по JSONPath

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    handlers=[
                        logging.FileHandler("parser_multi_browser.log", encoding='utf-8'),
                        logging.StreamHandler()
                    ])

class WebParser:
    def __init__(self, parsing_mode='requests', headless=True, browser='chrome'):
        self.parsing_mode = parsing_mode.lower()
        self.driver = None
        self.browser = browser.lower()

        if self.parsing_mode == 'selenium':
            self._setup_selenium_driver(headless)

    def _setup_selenium_driver(self, headless):
        try:
            if self.browser == 'chrome':
                options = ChromeOptions()
                service = ChromeService(ChromeDriverManager().install())
            elif self.browser == 'firefox':
                options = FirefoxOptions()
                service = FirefoxService(GeckoDriverManager().install())
            else:
                logging.error(f"Unsupported browser: {self.browser}. Use 'chrome' or 'firefox'.")
                self.parsing_mode = 'requests' # Fallback
                return

            if headless:
                options.add_argument("--headless")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
            
            if self.browser == 'chrome':
                self.driver = webdriver.Chrome(service=service, options=options)
            elif self.browser == 'firefox':
                self.driver = webdriver.Firefox(service=service, options=options)

            logging.info(f"Selenium WebDriver for {self.browser.capitalize()} launched successfully.")
        except Exception as e:
            logging.error(f"Error launching Selenium WebDriver for {self.browser.capitalize()}: {e}")
            self.parsing_mode = 'requests' # Fallback
            self.driver = None

    def fetch_html(self, url, delay=1, retries=3):
        logging.info(f"Fetching HTML for: {url}")
        time.sleep(delay)

        if self.parsing_mode == 'selenium' and self.driver:
            try:
                self.driver.get(url)
                time.sleep(delay * 2) # Увеличиваем задержку для динамических сайтов
                return self.driver.page_source
            except Exception as e:
                logging.error(f"Selenium error fetching {url}: {e}")
                return None
        elif self.parsing_mode == 'requests':
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            for i in range(retries):
                try:
                    response = requests.get(url, headers=headers, timeout=15)
                    response.raise_for_status()
                    return response.text
                except requests.exceptions.RequestException as e:
                    logging.warning(f"Attempt {i+1}/{retries} Error requesting {url}: {e}")
                    time.sleep(delay * (i + 1))
            logging.error(f"Failed to fetch HTML for {url} after {retries} attempts.")
            return None
        else:
            logging.error(f"Invalid parsing mode '{self.parsing_mode}' for HTML fetching.")
            return None

    def fetch_api_data(self, url, headers=None, delay=1, retries=3):
        logging.info(f"Fetching API data from: {url}")
        time.sleep(delay)
        
        req_headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'application/json'
        }
        if headers:
            req_headers.update(headers)

        for i in range(retries):
            try:
                response = requests.get(url, headers=req_headers, timeout=15)
                response.raise_for_status()
                return response.json()
            except requests.exceptions.RequestException as e:
                logging.warning(f"Attempt {i+1}/{retries} Error requesting API {url}: {e}")
                time.sleep(delay * (i + 1))
            except json.JSONDecodeError as e:
                logging.error(f"Failed to decode JSON from API response for {url}: {e}")
                logging.error(f"Response content: {response.text[:500]}...") # Log part of response for debugging
                return None
        logging.error(f"Failed to fetch API data for {url} after {retries} attempts.")
        return None

    def parse_html(self, html_content):
        if not html_content:
            return None
        return BeautifulSoup(html_content, 'html.parser')

    def extract_data_from_html_element(self, element, selector, attribute=None):
        found_element = element.select_one(selector)
        if found_element:
            if attribute:
                return found_element.get(attribute, None)
            else:
                return found_element.get_text(strip=True)
        return None
    
    def extract_data_from_json_element(self, json_data, json_path):
        """
        Extracts data from a JSON object using JMESPath.
        json_path examples: "title", "data.items[0].name", "results[*].id"
        """
        try:
            return jmespath.search(json_path, json_data)
        except Exception as e:
            logging.warning(f"JMESPath error for path '{json_path}': {e}")
            return None

    def extract_multiple_items(self, source_data, main_item_selector, item_fields_patterns, is_json=False):
        all_extracted_items = []
        if not source_data:
            return all_extracted_items

        if is_json:
            # Main item selector is now a JMESPath for the list of items
            items_list = self.extract_data_from_json_element(source_data, main_item_selector)
            if not isinstance(items_list, list):
                logging.error(f"JSON main item selector '{main_item_selector}' did not return a list. Got: {type(items_list)}")
                return all_extracted_items
            
            for item_data_dict in items_list:
                item_data = {}
                for field_name, (field_selector, _) in item_fields_patterns.items(): # Attribute is not used for JSON
                    value = self.extract_data_from_json_element(item_data_dict, field_selector)
                    if value is not None:
                        item_data[field_name] = value
                if item_data:
                    all_extracted_items.append(item_data)
        else: # HTML parsing
            main_elements = source_data.select(main_item_selector)
            for item_element in main_elements:
                item_data = {}
                for field_name, (field_selector, field_attribute) in item_fields_patterns.items():
                    value = self.extract_data_from_html_element(item_element, field_selector, field_attribute)
                    if value is not None:
                        item_data[field_name] = value
                if item_data:
                    all_extracted_items.append(item_data)
        return all_extracted_items

    def follow_pagination(self, start_url, next_page_selector, max_pages=5, delay_between_pages=2):
        all_soups = []
        current_url = start_url
        page_count = 0

        while current_url and page_count < max_pages:
            logging.info(f"Parsing page {page_count + 1}: {current_url}")
            html_content = self.fetch_html(current_url, delay=delay_between_pages)
            if not html_content:
                logging.error(f"Failed to get HTML for {current_url}. Aborting pagination.")
                break
            
            soup = self.parse_html(html_content)
            if not soup:
                logging.error(f"Failed to parse HTML for {current_url}. Aborting pagination.")
                break

            all_soups.append(soup)
            page_count += 1

            next_link_tag = soup.select_one(next_page_selector)
            if next_link_tag and next_link_tag.has_attr('href'):
                next_page_href = next_link_tag['href']
                current_url = urljoin(current_url, next_page_href)
                logging.info(f"Next page found: {current_url}")
            else:
                logging.info("Next page link not found. Finishing pagination.")
                current_url = None

        logging.info(f"Pagination parsing completed. Processed {page_count} pages.")
        return all_soups

    def close_driver(self):
        if self.driver:
            self.driver.quit()
            logging.info("Selenium WebDriver closed.")

# --- НОВЫЕ КЛАССЫ И ФУНКЦИИ (без изменений, т.к. они для отправки, а не для парсинга) ---

class ApiSender:
    def __init__(self, api_url, headers=None):
        self.api_url = api_url
        self.headers = headers if headers is not None else {'Content-Type': 'application/json'}
        if not self.api_url:
            logging.error("API URL for sending is not set. API sending will not work.")

    def send_data(self, data_list, method='POST'):
        if not self.api_url:
            logging.error("Cannot send data, API URL for sending is not configured.")
            return []
        if not data_list:
            logging.info("No data to send via API.")
            return []

        successful_sends = []
        for item_data in data_list:
            try:
                # --- ВАЖНО: Адаптируйте payload под требования вашего целевого API ---
                # Пример простого маппинга:
                payload_data = {
                    "title": item_data.get("title", ""),
                    "link": item_data.get("link", ""),
                    "date": item_data.get("date", ""),
                    "image_src": item_data.get("image_src", "")
                    # Добавьте или переименуйте поля в соответствии с API
                }
                payload = json.dumps(payload_data, ensure_ascii=False)

                logging.info(f"Sending data to API: {self.api_url} with payload (first 100 chars): {payload[:100]}...")
                if method.upper() == 'POST':
                    response = requests.post(self.api_url, data=payload, headers=self.headers, timeout=15)
                elif method.upper() == 'PUT':
                    # Для PUT может потребоваться ID элемента в URL, это сложнее.
                    # Если API поддерживает PUT для массового обновления или ID в теле запроса,
                    # то вам потребуется настроить это здесь.
                    logging.warning("PUT method for API is more complex and might require item IDs in URL or specific payload structure.")
                    response = requests.put(self.api_url, data=payload, headers=self.headers, timeout=15) # Пример, возможно потребуется доработка
                else:
                    logging.error(f"Unsupported API method for sending: {method}")
                    continue

                response.raise_for_status() # Вызывает HTTPError для плохих ответов (4xx, 5xx)
                logging.info(f"Successfully sent data to API. Status: {response.status_code}. Response: {response.text[:100]}...")
                successful_sends.append(item_data)
            except requests.exceptions.RequestException as e:
                logging.error(f"Error sending data to API: {e}")
                if hasattr(e, 'response') and e.response is not None:
                    logging.error(f"API Response Error ({e.response.status_code}): {e.response.text}")
            except json.JSONDecodeError as e:
                logging.error(f"Error encoding JSON payload for API: {e}")
            except Exception as e:
                logging.error(f"An unexpected error occurred during API send: {e}")
        return successful_sends

class DuplicateChecker:
    def __init__(self, history_file="processed_items_history.json", id_field='link'):
        self.history_file = history_file
        self.id_field = id_field
        self.processed_ids = self._load_history()
        logging.info(f"Loaded {len(self.processed_ids)} processed items from {self.history_file}.")

    def _load_history(self):
        if os.path.exists(self.history_file):
            with open(self.history_file, 'r', encoding='utf-8') as f:
                try:
                    return set(json.load(f))
                except json.JSONDecodeError:
                    logging.warning(f"Error decoding {self.history_file}. File might be corrupted or empty. Starting with empty history.")
                    return set()
            return set() # Fallback for empty/malformed file
        return set()

    def _save_history(self):
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(list(self.processed_ids), f, ensure_ascii=False, indent=4)
            logging.info(f"Saved {len(self.processed_ids)} processed items to {self.history_file}.")
        except IOError as e:
            logging.error(f"Error saving history file {self.history_file}: {e}")

    def get_item_id(self, item):
        item_id = item.get(self.id_field)
        if item_id:
            return item_id
        
        combined_string = ""
        for key in ['title', 'date', 'link']: # Поля, которые предположительно уникальны в совокупности
            combined_string += str(item.get(key, ''))
        
        if combined_string:
            return hashlib.sha256(combined_string.encode('utf-8')).hexdigest()
        
        logging.warning(f"Could not generate unique ID for item: {item}")
        return None

    def filter_new_items(self, items):
        new_items = []
        for item in items:
            item_id = self.get_item_id(item)
            if item_id:
                if item_id not in self.processed_ids:
                    new_items.append(item)
            else:
                logging.warning(f"Skipping duplicate check for item due to no identifiable ID: {item}")
        return new_items

    def mark_as_processed(self, items):
        if not items:
            return
        initial_count = len(self.processed_ids)
        for item in items:
            item_id = self.get_item_id(item)
            if item_id:
                self.processed_ids.add(item_id)
        if len(self.processed_ids) > initial_count:
            self._save_history()
            logging.info(f"Added {len(self.processed_ids) - initial_count} new IDs to history.")
        else:
            logging.info("No new unique IDs to add to history.")


def save_data_to_csv(data_list, filename="output.csv"):
    if not data_list:
        logging.warning("No data to save to CSV.")
        return

    try:
        all_keys = sorted(list(set(key for d in data_list for key in d.keys())))
        with open(filename, 'w', newline='', encoding='utf-8') as output_file:
            dict_writer = csv.DictWriter(output_file, fieldnames=all_keys)
            dict_writer.writeheader()
            dict_writer.writerows(data_list)
        logging.info(f"Data successfully saved to {filename}")
    except IOError as e:
        logging.error(f"Error saving CSV file {filename}: {e}")

def save_data_to_json(data_list, filename="output.json"):
    if not data_list:
        logging.warning("No data to save to JSON.")
        return

    try:
        with open(filename, 'w', encoding='utf-8') as output_file:
            json.dump(data_list, output_file, ensure_ascii=False, indent=4)
        logging.info(f"Data successfully saved to {filename}")
    except IOError as e:
        logging.error(f"Error saving JSON file {filename}: {e}")


if __name__ == "__main__":
    logging.info("This file is intended to be imported by parser_gui.py.")
    logging.info("Running a simple test for API Sender and Duplicate Checker:")

    # --- Test ApiSender ---
    test_api_url = "https://jsonplaceholder.typicode.com/posts" # Пример публичного API
    test_headers = {"Content-Type": "application/json"}
    api_sender = ApiSender(test_api_url, test_headers)

    test_data_to_send = [
        {"title": "Test Post 1", "body": "This is a test post from parser.", "userId": 1},
        {"title": "Test Post 2", "body": "Another test post.", "userId": 1}
    ]
    logging.info("\n--- Testing API Sender ---")
    successfully_sent = api_sender.send_data(test_data_to_send, method='POST')
    logging.info(f"API Test: Successfully sent {len(successfully_sent)} items.")

    # --- Test DuplicateChecker ---
    duplicate_checker = DuplicateChecker(history_file="test_processed_items.json", id_field='title') # Используем title как ID для теста

    initial_items = [
        {"title": "Item A", "content": "Content A", "link": "linkA"},
        {"title": "Item B", "content": "Content B", "link": "linkB"},
    ]
    new_items_to_check = [
        {"title": "Item B", "content": "Content B updated", "link": "linkB"}, # Duplicate
        {"title": "Item C", "content": "Content C", "link": "linkC"},      # New
        {"title": "Item D", "content": "Content D", "link": "linkD"},      # New
    ]

    logging.info("\n--- Testing Duplicate Checker ---")
    duplicate_checker.mark_as_processed(initial_items)
    filtered_items = duplicate_checker.filter_new_items(new_items_to_check)
    logging.info(f"Duplicate Checker Test: Found {len(filtered_items)} new items.")
    for item in filtered_items:
        logging.info(f"  New: {item.get('title')}")
    
    duplicate_checker.mark_as_processed(filtered_items)
    logging.info(f"Current processed IDs: {duplicate_checker.processed_ids}")