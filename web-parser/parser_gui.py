
import tkinter as tk
from tkinter import messagebox, scrolledtext, filedialog
import threading # Для выполнения парсинга в фоновом режиме, чтобы GUI не зависал
import sys
import os
import logging

# Добавляем путь к каталогу, где находится universal_web_parser_multi_browser.py,
# если он не в той же папке, что и этот скрипт.
# В данном случае, предполагаем, что они в одной папке.
from universal_web_parser_multi_browser import WebParser, save_data_to_csv, save_data_to_json

class ParserApp:
    def __init__(self, master):
        self.master = master
        master.title("Универсальный Веб-Парсер")
        master.geometry("800x700")

        self.parser = None # Будет инициализирован при запуске парсинга

        # --- Настройка GUI элементов ---

        # Frame для URL и выбора режима
        self.input_frame = tk.LabelFrame(master, text="Настройки URL и режима парсинга", padx=10, pady=10)
        self.input_frame.pack(padx=10, pady=5, fill="x")

        tk.Label(self.input_frame, text="URL:").grid(row=0, column=0, sticky="w", pady=2)
        self.url_entry = tk.Entry(self.input_frame, width=80)
        self.url_entry.grid(row=0, column=1, padx=5, pady=2, sticky="ew")
        self.url_entry.insert(0, "https://quotes.toscrape.com/js/") # Пример URL

        tk.Label(self.input_frame, text="Тип парсинга:").grid(row=1, column=0, sticky="w", pady=2)
        self.parsing_type_var = tk.StringVar(master)
        self.parsing_type_var.set("Requests (статический)") # Значение по умолчанию
        self.parsing_type_menu = tk.OptionMenu(self.input_frame, self.parsing_type_var, 
                                               "Requests (статический)", "Selenium (динамический)")
        self.parsing_type_menu.grid(row=1, column=1, padx=5, pady=2, sticky="ew")
        self.parsing_type_var.trace("w", self._on_parsing_type_change) # Отслеживание изменения

        tk.Label(self.input_frame, text="Браузер (Selenium):").grid(row=2, column=0, sticky="w", pady=2)
        self.browser_var = tk.StringVar(master)
        self.browser_var.set("Chrome")
        self.browser_menu = tk.OptionMenu(self.input_frame, self.browser_var, "Chrome", "Firefox")
        self.browser_menu.grid(row=2, column=1, padx=5, pady=2, sticky="ew")
        self.browser_menu.config(state="disabled") # По умолчанию отключено

        self.headless_var = tk.BooleanVar(master)
        self.headless_var.set(True)
        self.headless_checkbox = tk.Checkbutton(self.input_frame, text="Скрытый режим (headless)", variable=self.headless_var)
        self.headless_checkbox.grid(row=3, column=1, sticky="w", padx=5, pady=2)
        self.headless_checkbox.config(state="disabled") # По умолчанию отключено

        self.input_frame.grid_columnconfigure(1, weight=1) # Растягиваем поле ввода URL

        # Frame для селекторов и опций сохранения
        self.options_frame = tk.LabelFrame(master, text="Настройки извлечения и сохранения", padx=10, pady=10)
        self.options_frame.pack(padx=10, pady=5, fill="x")

        tk.Label(self.options_frame, text="CSS Селектор для данных (основной):").grid(row=0, column=0, sticky="w", pady=2)
        self.selector_entry = tk.Entry(self.options_frame, width=80)
        self.selector_entry.grid(row=0, column=1, padx=5, pady=2, sticky="ew")
        self.selector_entry.insert(0, "div.quote") # Пример селектора для quotes.toscrape.com/js/

        tk.Label(self.options_frame, text="Селектор для заголовка/поля1 (опц.):").grid(row=1, column=0, sticky="w", pady=2)
        self.selector1_entry = tk.Entry(self.options_frame, width=80)
        self.selector1_entry.grid(row=1, column=1, padx=5, pady=2, sticky="ew")
        self.selector1_entry.insert(0, "span.text") # Пример для цитаты

        tk.Label(self.options_frame, text="Селектор для автора/поля2 (опц.):").grid(row=2, column=0, sticky="w", pady=2)
        self.selector2_entry = tk.Entry(self.options_frame, width=80)
        self.selector2_entry.grid(row=2, column=1, padx=5, pady=2, sticky="ew")
        self.selector2_entry.insert(0, "small.author") # Пример для автора

        self.save_csv_var = tk.BooleanVar(master)
        self.save_csv_var.set(True)
        tk.Checkbutton(self.options_frame, text="Сохранить в CSV", variable=self.save_csv_var).grid(row=3, column=0, sticky="w", pady=2)

        self.save_json_var = tk.BooleanVar(master)
        self.save_json_var.set(True)
        tk.Checkbutton(self.options_frame, text="Сохранить в JSON", variable=self.save_json_var).grid(row=3, column=1, sticky="w", pady=2)
        
        self.options_frame.grid_columnconfigure(1, weight=1)

        # Кнопки управления
        self.button_frame = tk.Frame(master, padx=10, pady=5)
        self.button_frame.pack(padx=10, pady=5, fill="x")

        self.start_button = tk.Button(self.button_frame, text="Начать парсинг", command=self.start_parsing, height=2, bg="green", fg="white")
        self.start_button.pack(side="left", expand=True, fill="x", padx=5)

        self.clear_button = tk.Button(self.button_frame, text="Очистить", command=self.clear_output, height=2, bg="orange", fg="white")
        self.clear_button.pack(side="left", expand=True, fill="x", padx=5)

        # Область вывода логов/результатов
        self.output_frame = tk.LabelFrame(master, text="Логи и Результаты", padx=10, pady=10)
        self.output_frame.pack(padx=10, pady=5, fill="both", expand=True)

        self.log_text = scrolledtext.ScrolledText(self.output_frame, wrap=tk.WORD, width=90, height=20, state='disabled')
        self.log_text.pack(expand=True, fill="both")

        # Перенаправление stdout/stderr в текстовое поле GUI
        self.text_handler = TextHandler(self.log_text)
        sys.stdout = self.text_handler
        sys.stderr = self.text_handler

        self._on_parsing_type_change() # Инициализируем состояние элементов управления

    def _on_parsing_type_change(self, *args):
        """Обрабатывает изменение выбора типа парсинга."""
        selected_type = self.parsing_type_var.get()
        if selected_type == "Selenium (динамический)":
            self.browser_menu.config(state="normal")
            self.headless_checkbox.config(state="normal")
        else:
            self.browser_menu.config(state="disabled")
            self.headless_checkbox.config(state="disabled")

    def log_message(self, message):
        self.log_text.config(state='normal')
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END) # Автопрокрутка до конца
        self.log_text.config(state='disabled')

    def clear_output(self):
        self.log_text.config(state='normal')
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state='disabled')

    def start_parsing(self):
        url = self.url_entry.get()
        main_selector = self.selector_entry.get()
        selector1 = self.selector1_entry.get()
        selector2 = self.selector2_entry.get()
        use_selenium = (self.parsing_type_var.get() == "Selenium (динамический)")
        browser = self.browser_var.get().lower()
        headless = self.headless_var.get()
        save_csv = self.save_csv_var.get()
        save_json = self.save_json_var.get()

        if not url:
            messagebox.showerror("Ошибка", "Пожалуйста, введите URL.")
            return
        if not main_selector:
            messagebox.showerror("Ошибка", "Пожалуйста, введите основной CSS-селектор.")
            return

        self.log_message(f"Начинаю парсинг: {url}")
        self.start_button.config(state="disabled") # Отключаем кнопку во время парсинга

        # Запускаем парсинг в отдельном потоке, чтобы GUI не зависал
        threading.Thread(target=self._run_parser_thread, args=(
            url, main_selector, selector1, selector2, use_selenium, browser, headless, save_csv, save_json
        )).start()

    def _run_parser_thread(self, url, main_selector, selector1, selector2, use_selenium, browser, headless, save_csv, save_json):
        try:
            self.parser = WebParser(use_selenium=use_selenium, headless=headless, browser=browser)
            
            html_content = self.parser.fetch_html(url)
            if not html_content:
                self.log_message("Ошибка: Не удалось получить HTML-контент.")
                return

            soup = self.parser.parse_html(html_content)
            if not soup:
                self.log_message("Ошибка: Не удалось распарсить HTML.")
                return
            
            all_extracted_items = []
            
            # Извлекаем основные элементы по главному селектору
            main_elements = soup.select(main_selector)
            
            for item_element in main_elements:
                item_data = {}
                # Если есть основной селектор, пытаемся извлечь его текст как 'main_content'
                if item_element.get_text(strip=True):
                    item_data['main_content'] = item_element.get_text(strip=True)

                # Попытка извлечь доп. поля, если селекторы указаны
                if selector1:
                    field1_element = item_element.select_one(selector1)
                    if field1_element:
                        item_data['field1'] = field1_element.get_text(strip=True)
                
                if selector2:
                    field2_element = item_element.select_one(selector2)
                    if field2_element:
                        item_data['field2'] = field2_element.get_text(strip=True)
                
                if item_data: # Добавляем только если что-то извлекли
                    all_extracted_items.append(item_data)

            self.log_message(f"Парсинг завершен. Извлечено {len(all_extracted_items)} элементов.")
            
            if all_extracted_items:
                if save_csv:
                    save_data_to_csv(all_extracted_items, "parsed_data.csv")
                if save_json:
                    save_data_to_json(all_extracted_items, "parsed_data.json")
            else:
                self.log_message("Не удалось извлечь данные по указанным селекторам.")

        except Exception as e:
            self.log_message(f"Произошла непредвиденная ошибка: {e}")
            # Логируем полный трассировку стека для отладки
            import traceback
            self.log_message(traceback.format_exc())
        finally:
            if self.parser:
                self.parser.close_driver()
            self.start_button.config(state="normal") # Включаем кнопку обратно

class TextHandler(logging.Handler):
    """Класс для перенаправления вывода логов в текстовое поле Tkinter."""
    def __init__(self, text_widget):
        super().__init__()
        self.text_widget = text_widget
        # Добавляем свой обработчик в корневой логгер, чтобы перехватывать логи
        # из universal_web_parser_multi_browser.py
        logging.getLogger().addHandler(self) 

    def emit(self, record):
        msg = self.format(record)
        self.text_widget.config(state='normal')
        self.text_widget.insert(tk.END, msg + "\n")
        self.text_widget.see(tk.END)
        self.text_widget.config(state='disabled')


if __name__ == "__main__":
    root = tk.Tk()
    app = ParserApp(root)
    root.mainloop()