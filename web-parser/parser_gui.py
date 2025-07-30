import tkinter as tk
from tkinter import messagebox, scrolledtext, filedialog
from tkinter import ttk # Импортируем ttk для стилизованных виджетов
import threading
import sys
import os
import logging
import json
import time

# Импортируем классы из нашего парсера
from universal_web_parser_multi_browser import WebParser, save_data_to_csv, save_data_to_json, ApiSender, DuplicateChecker

# Настройка логирования
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    handlers=[
                        logging.StreamHandler()
                    ])

class ParserApp:
    def __init__(self, master):
        self.master = master
        master.title("Универсальный Веб-Парсер (v1.0)")
        master.geometry("1000x1080") # Увеличиваем размер окна
        master.resizable(True, True) # Разрешаем изменение размера окна

        # Создаем стиль для ttk виджетов
        self.style = ttk.Style()
        self.style.theme_use('clam') # Выбираем тему 'clam' для современного вида

        # Добавляем свои стили для кнопок
        self.style.configure('Start.TButton', background='green', foreground='white', font=('Helvetica', 10, 'bold'))
        self.style.map('Start.TButton', background=[('active', 'darkgreen')])
        self.style.configure('Stop.TButton', background='red', foreground='white', font=('Helvetica', 10, 'bold'))
        self.style.map('Stop.TButton', background=[('active', 'darkred')])
        self.style.configure('MonitorStart.TButton', background='purple', foreground='white', font=('Helvetica', 10, 'bold'))
        self.style.map('MonitorStart.TButton', background=[('active', 'darkmagenta')])


        self.text_handler = TextHandler(self)
        sys.stdout = self.text_handler
        sys.stderr = self.text_handler

        self.parser = None
        self.monitoring_timer = None
        self.stop_event = threading.Event()
        self.duplicate_checker = DuplicateChecker(history_file="processed_items_history.json", id_field='link')

        # --- Раздел 1: Основные настройки парсинга ---
        self.general_settings_frame = ttk.LabelFrame(master, text="1. Основные настройки (Источник данных)", padding=(10, 10))
        self.general_settings_frame.pack(padx=15, pady=8, fill="x", expand=False)

        ttk.Label(self.general_settings_frame, text="URL Источника:").grid(row=0, column=0, sticky="w", pady=2, padx=5)
        self.url_entry = ttk.Entry(self.general_settings_frame, width=80)
        self.url_entry.grid(row=0, column=1, padx=5, pady=2, sticky="ew")
        self.url_entry.insert(0, "https://www.spbu.uz/")

        ttk.Label(self.general_settings_frame, text="Метод парсинга:").grid(row=1, column=0, sticky="w", pady=2, padx=5)
        self.parsing_type_var = tk.StringVar(master)
        self.parsing_type_var.set("Запросы (Статика)")
        self.parsing_type_menu = ttk.OptionMenu(self.general_settings_frame, self.parsing_type_var,
                                               "Запросы (Статика)", "Selenium (Динамика)", "API (JSON)")
        self.parsing_type_menu.grid(row=1, column=1, padx=5, pady=2, sticky="ew")
        self.parsing_type_var.trace("w", self._on_parsing_type_change) # Отслеживание изменения

        # Настройки Selenium (изначально скрыты)
        self.selenium_options_frame = ttk.Frame(self.general_settings_frame)
        self.selenium_options_frame.grid(row=2, column=0, columnspan=2, sticky="ew")
        
        ttk.Label(self.selenium_options_frame, text="Браузер (Selenium):").grid(row=0, column=0, sticky="w", pady=2, padx=5)
        self.browser_var = tk.StringVar(master)
        self.browser_var.set("Chrome")
        self.browser_menu = ttk.OptionMenu(self.selenium_options_frame, self.browser_var, "Chrome", "Firefox")
        self.browser_menu.grid(row=0, column=1, padx=5, pady=2, sticky="ew")

        self.headless_var = tk.BooleanVar(master)
        self.headless_var.set(True)
        self.headless_checkbox = ttk.Checkbutton(self.selenium_options_frame, text="Режим без окна (Headless)", variable=self.headless_var)
        self.headless_checkbox.grid(row=1, column=1, sticky="w", padx=5, pady=2)
        self.selenium_options_frame.grid_columnconfigure(1, weight=1)

        # Настройки API источника (изначально скрыты)
        self.source_api_options_frame = ttk.Frame(self.general_settings_frame)
        self.source_api_options_frame.grid(row=3, column=0, columnspan=2, sticky="ew")

        ttk.Label(self.source_api_options_frame, text="Заголовки API (JSON):", wraplength=150).grid(row=0, column=0, sticky="nw", pady=2, padx=5)
        self.source_api_headers_text = scrolledtext.ScrolledText(self.source_api_options_frame, wrap=tk.WORD, width=50, height=3, font=('Helvetica', 9))
        self.source_api_headers_text.grid(row=0, column=1, padx=5, pady=2, sticky="ew")
        self.source_api_headers_text.insert(tk.END, '{}')
        ttk.Label(self.source_api_options_frame, text="*В формате JSON, например: {\"Authorization\": \"Bearer токен\"}", font=('Helvetica', 7), foreground='gray').grid(row=1, column=1, sticky="w", padx=5)
        self.source_api_options_frame.grid_columnconfigure(1, weight=1)

        self.general_settings_frame.grid_columnconfigure(1, weight=1)

        # --- Раздел 2: Извлечение данных ---
        self.extraction_frame = ttk.LabelFrame(master, text="2. Извлечение данных (Определение элементов)", padding=(10, 10))
        self.extraction_frame.pack(padx=15, pady=8, fill="x", expand=False)

        # Селекторы для HTML-парсинга (изначально видимы)
        self.html_extraction_frame = ttk.Frame(self.extraction_frame)
        self.html_extraction_frame.pack(fill="x", expand=True)
        
        ttk.Label(self.html_extraction_frame, text="CSS-селектор контейнера элемента:").grid(row=0, column=0, sticky="w", pady=2, padx=5)
        self.main_container_selector_entry = ttk.Entry(self.html_extraction_frame, width=80)
        self.main_container_selector_entry.grid(row=0, column=1, padx=5, pady=2, sticky="ew")
        self.main_container_selector_entry.insert(0, "div.news-item-single-small")
        ttk.Label(self.html_extraction_frame, text="*Селектор для каждого отдельного блока новости/поста (например, '.post-item')", font=('Helvetica', 7), foreground='gray').grid(row=1, column=1, sticky="w", padx=5)
        self.html_extraction_frame.grid_columnconfigure(1, weight=1)

        # Селекторы для JSON-парсинга (изначально скрыты)
        self.json_extraction_frame = ttk.Frame(self.extraction_frame)
        self.json_extraction_frame.pack(fill="x", expand=True)

        ttk.Label(self.json_extraction_frame, text="JSON-путь к списку элементов:").grid(row=0, column=0, sticky="w", pady=2, padx=5)
        self.json_root_path_entry = ttk.Entry(self.json_extraction_frame, width=80)
        self.json_root_path_entry.grid(row=0, column=1, padx=5, pady=2, sticky="ew")
        self.json_root_path_entry.insert(0, "[]") # Пример: "results", "data.items", "[]"
        ttk.Label(self.json_extraction_frame, text="*JMESPath к массиву объектов (например, 'data.items' или '[]')", font=('Helvetica', 7), foreground='gray').grid(row=1, column=1, sticky="w", padx=5)
        self.json_extraction_frame.grid_columnconfigure(1, weight=1)


        self.field_entries_container = ttk.Frame(self.extraction_frame)
        self.field_entries_container.pack(fill="x", expand=True, pady=(10,0))
        ttk.Label(self.field_entries_container, text="Определение полей для извлечения:").grid(row=0, column=0, columnspan=4, sticky="w", padx=5)
        self.field_entries = []
        self.current_field_row = 1

        self.add_field_button = ttk.Button(self.extraction_frame, text="Добавить поле", command=self._add_field)
        self.add_field_button.pack(pady=5)

        # Примеры полей для spbu.uz (HTML)
        self._add_field(field_name_default="title", selector_default="a.news-item-single-small__title")
        self._add_field(field_name_default="link", selector_default="a.news-item-single-small__title", attribute_default="href")
        self._add_field(field_name_default="date", selector_default="span.news-item-single-small__date")
        self._add_field(field_name_default="image_src", selector_default="img.news-item-single-small__img", attribute_default="src")

        # --- Раздел 3: Настройки пагинации (только для HTML/Selenium) ---
        self.pagination_frame = ttk.LabelFrame(master, text="3. Настройки пагинации (переход по страницам)", padding=(10, 10))
        self.pagination_frame.pack(padx=15, pady=8, fill="x", expand=False)

        self.pagination_var = tk.BooleanVar(master)
        self.pagination_var.set(False)
        self.pagination_checkbox = ttk.Checkbutton(self.pagination_frame, text="Включить пагинацию", variable=self.pagination_var, command=self._on_pagination_change)
        self.pagination_checkbox.grid(row=0, column=0, sticky="w", pady=2, padx=5)

        ttk.Label(self.pagination_frame, text="CSS-селектор кнопки 'Следующая':").grid(row=1, column=0, sticky="w", pady=2, padx=5)
        self.next_page_selector_entry = ttk.Entry(self.pagination_frame, width=60, state="disabled")
        self.next_page_selector_entry.grid(row=1, column=1, padx=5, pady=2, sticky="ew")
        self.next_page_selector_entry.insert(0, "li.next a")
        ttk.Label(self.pagination_frame, text="*Селектор для ссылки, ведущей на следующую страницу.", font=('Helvetica', 7), foreground='gray').grid(row=2, column=1, sticky="w", padx=5)

        ttk.Label(self.pagination_frame, text="Макс. страниц:").grid(row=3, column=0, sticky="w", pady=2, padx=5)
        self.max_pages_entry = ttk.Entry(self.pagination_frame, width=10, state="disabled")
        self.max_pages_entry.grid(row=3, column=1, sticky="w", padx=5, pady=2)
        self.max_pages_entry.insert(0, "3")
        ttk.Label(self.pagination_frame, text="*Сколько страниц максимально нужно пройти.", font=('Helvetica', 7), foreground='gray').grid(row=4, column=1, sticky="w", padx=5)

        self.pagination_frame.grid_columnconfigure(1, weight=1)

        # --- Раздел 4: Отправка данных по API (Целевой API) ---
        self.api_sending_frame = ttk.LabelFrame(master, text="4. Отправка данных по API (Целевой сервер)", padding=(10, 10))
        self.api_sending_frame.pack(padx=15, pady=8, fill="x", expand=False)

        self.enable_api_var = tk.BooleanVar(master)
        self.enable_api_var.set(False)
        ttk.Checkbutton(self.api_sending_frame, text="Включить отправку данных по API", variable=self.enable_api_var).grid(row=0, column=0, sticky="w", columnspan=2, padx=5, pady=2)

        ttk.Label(self.api_sending_frame, text="URL целевого API:").grid(row=1, column=0, sticky="w", pady=2, padx=5)
        self.api_url_entry = ttk.Entry(self.api_sending_frame, width=60)
        self.api_url_entry.grid(row=1, column=1, padx=5, pady=2, sticky="ew")
        self.api_url_entry.insert(0, "ВАШ_API_URL_ЗДЕСЬ")

        ttk.Label(self.api_sending_frame, text="Метод API:").grid(row=2, column=0, sticky="w", pady=2, padx=5)
        self.api_method_var = tk.StringVar(master)
        self.api_method_var.set("POST")
        self.api_method_menu = ttk.OptionMenu(self.api_sending_frame, self.api_method_var, "POST", "PUT")
        self.api_method_menu.grid(row=2, column=1, padx=5, pady=2, sticky="ew")

        ttk.Label(self.api_sending_frame, text="Заголовки API (JSON):", wraplength=150).grid(row=3, column=0, sticky="nw", pady=2, padx=5)
        self.api_headers_text = scrolledtext.ScrolledText(self.api_sending_frame, wrap=tk.WORD, width=50, height=4, font=('Helvetica', 9))
        self.api_headers_text.grid(row=3, column=1, padx=5, pady=2, sticky="ew")
        self.api_headers_text.insert(tk.END, '{}')
        ttk.Label(self.api_sending_frame, text="*В формате JSON, для аутентификации или типа контента", font=('Helvetica', 7), foreground='gray').grid(row=4, column=1, sticky="w", padx=5)
        self.api_sending_frame.grid_columnconfigure(1, weight=1)

        # --- Раздел 5: Мониторинг в реальном времени ---
        self.monitoring_frame = ttk.LabelFrame(master, text="5. Мониторинг в реальном времени", padding=(10, 10))
        self.monitoring_frame.pack(padx=15, pady=8, fill="x", expand=False)

        self.enable_monitoring_var = tk.BooleanVar(master)
        self.enable_monitoring_var.set(False)
        ttk.Checkbutton(self.monitoring_frame, text="Включить постоянный мониторинг", variable=self.enable_monitoring_var).grid(row=0, column=0, sticky="w", columnspan=2, padx=5, pady=2)

        ttk.Label(self.monitoring_frame, text="Интервал проверки (секунды):").grid(row=1, column=0, sticky="w", pady=2, padx=5)
        self.monitoring_interval_entry = ttk.Entry(self.monitoring_frame, width=10)
        self.monitoring_interval_entry.grid(row=1, column=1, sticky="w", padx=5, pady=2)
        self.monitoring_interval_entry.insert(0, "300") # 5 минут по умолчанию

        self.start_monitoring_button = ttk.Button(self.monitoring_frame, text="Старт мониторинга", command=self._start_monitoring, style='MonitorStart.TButton')
        self.start_monitoring_button.grid(row=2, column=0, sticky="ew", pady=5, padx=2)
        self.stop_monitoring_button = ttk.Button(self.monitoring_frame, text="Стоп мониторинга", command=self._stop_monitoring, state="disabled", style='Stop.TButton')
        self.stop_monitoring_button.grid(row=2, column=1, sticky="ew", pady=5, padx=2)
        self.monitoring_frame.grid_columnconfigure(1, weight=1)

        # --- Раздел 6: Сохранение результатов ---
        self.save_options_frame = ttk.LabelFrame(master, text="6. Сохранение результатов", padding=(10, 10))
        self.save_options_frame.pack(padx=15, pady=8, fill="x", expand=False)

        self.save_csv_var = tk.BooleanVar(master)
        self.save_csv_var.set(True)
        ttk.Checkbutton(self.save_options_frame, text="Сохранить в CSV", variable=self.save_csv_var).pack(side="left", padx=5)

        self.save_json_var = tk.BooleanVar(master)
        self.save_json_var.set(True)
        ttk.Checkbutton(self.save_options_frame, text="Сохранить в JSON", variable=self.save_json_var).pack(side="left", padx=5)

        # --- Раздел 7: Действия ---
        self.button_frame = ttk.Frame(master, padding=(10, 5))
        self.button_frame.pack(padx=15, pady=8, fill="x", expand=False)

        self.start_button = ttk.Button(self.button_frame, text="Начать разовый парсинг", command=self.start_single_parsing, style='Start.TButton')
        self.start_button.pack(side="left", expand=True, fill="x", padx=5)

        self.clear_button = ttk.Button(self.button_frame, text="Очистить логи", command=self.clear_output, style='Stop.TButton')
        self.clear_button.pack(side="left", expand=True, fill="x", padx=5)

        self.save_config_button = ttk.Button(self.button_frame, text="Сохранить настройки", command=self._save_config)
        self.save_config_button.pack(side="left", expand=True, fill="x", padx=5)

        self.load_config_button = ttk.Button(self.button_frame, text="Загрузить настройки", command=self._load_config)
        self.load_config_button.pack(side="left", expand=True, fill="x", padx=5)

        # --- Раздел 8: Логи и результаты ---
        self.output_frame = ttk.LabelFrame(master, text="8. Логи и результаты выполнения", padding=(10, 10))
        self.output_frame.pack(padx=15, pady=8, fill="both", expand=True)

        self.log_text = scrolledtext.ScrolledText(self.output_frame, wrap=tk.WORD, height=15, font=('Consolas', 9), state='disabled', bg="#f0f0f0")
        self.log_text.pack(expand=True, fill="both")

        # Инициализация состояния UI
        self._on_parsing_type_change()
        self._on_pagination_change()
        
    def _add_field(self, field_name_default="", selector_default="", attribute_default=""):
        row = self.current_field_row

        frame = ttk.Frame(self.field_entries_container)
        frame.grid(row=row, column=0, columnspan=4, sticky="ew", pady=2, padx=5) # Вставляем в контейнер
        frame.grid_columnconfigure(1, weight=1)
        frame.grid_columnconfigure(3, weight=1)

        ttk.Label(frame, text="Имя поля:").grid(row=0, column=0, sticky="w")
        field_name_entry = ttk.Entry(frame, width=15)
        field_name_entry.grid(row=0, column=1, padx=2, sticky="ew")
        field_name_entry.insert(0, field_name_default)

        self.selector_label = ttk.Label(frame, text="Селектор (CSS/JSONPath):")
        self.selector_label.grid(row=0, column=2, sticky="w")
        selector_entry = ttk.Entry(frame, width=30)
        selector_entry.grid(row=0, column=3, padx=2, sticky="ew")
        selector_entry.insert(0, selector_default)

        self.attribute_label = ttk.Label(frame, text="Атрибут (опц.):")
        self.attribute_label.grid(row=0, column=4, sticky="w")
        attribute_entry = ttk.Entry(frame, width=10)
        attribute_entry.grid(row=0, column=5, padx=2, sticky="ew")
        attribute_entry.insert(0, attribute_default)

        remove_button = ttk.Button(frame, text="X", command=lambda: self._remove_field(frame), width=3)
        remove_button.grid(row=0, column=6, padx=2)

        self.field_entries.append({'frame': frame, 'name': field_name_entry, 'selector': selector_entry, 'attribute': attribute_entry,
                                   'selector_label': self.selector_label, 'attribute_label': self.attribute_label})
        self.current_field_row += 1
        self._update_field_labels() # Обновить тексты меток после добавления поля
        
    def _remove_field(self, frame_to_remove):
        for i, field_dict in enumerate(self.field_entries):
            if field_dict['frame'] == frame_to_remove:
                frame_to_remove.destroy()
                del self.field_entries[i]
                self._rearrange_fields()
                break

    def _rearrange_fields(self):
        for i, field_dict in enumerate(self.field_entries):
            field_dict['frame'].grid(row=i+1, column=0, columnspan=4, sticky="ew", pady=2, padx=5)
        self.current_field_row = len(self.field_entries) + 1
        # add_field_button больше не привязан к grid() в этом месте, он всегда pack()
        # Но мы можем обновить его позицию, если он был бы в grid
        # self.add_field_button.grid(row=self.current_field_row, ...)
        
    def _update_field_labels(self):
        selected_type = self.parsing_type_var.get()
        if selected_type == "API (JSON)":
            for field_dict in self.field_entries:
                field_dict['selector_label'].config(text="Селектор (JSONPath):")
                field_dict['attribute_label'].grid_remove() # Скрываем атрибут для JSON
                field_dict['attribute'].grid_remove() # Скрываем поле ввода атрибута
        else:
            for field_dict in self.field_entries:
                field_dict['selector_label'].config(text="Селектор (CSS):")
                field_dict['attribute_label'].grid() # Показываем атрибут для HTML
                field_dict['attribute'].grid() # Показываем поле ввода атрибута

    def _on_parsing_type_change(self, *args):
        selected_type = self.parsing_type_var.get()

        # Управление видимостью настроек Selenium
        if selected_type == "Selenium (Динамика)":
            self.selenium_options_frame.grid() # Показываем рамку Selenium
            self.browser_menu.config(state="normal")
            self.headless_checkbox.config(state="normal")
        else:
            self.selenium_options_frame.grid_remove() # Скрываем рамку Selenium
            self.browser_menu.config(state="disabled")
            self.headless_checkbox.config(state="disabled")

        # Управление видимостью настроек Source API Headers
        if selected_type == "API (JSON)":
            self.source_api_options_frame.grid() # Показываем рамку Source API
            self.source_api_headers_text.config(state='normal')
        else:
            self.source_api_options_frame.grid_remove() # Скрываем рамку Source API
            self.source_api_headers_text.config(state='disabled')

        # Управление видимостью HTML и JSON секций извлечения данных
        if selected_type == "API (JSON)":
            self.html_extraction_frame.pack_forget() # Скрываем HTML-специфичные поля
            self.json_extraction_frame.pack(fill="x", expand=True) # Показываем JSON-специфичные поля
        else:
            self.json_extraction_frame.pack_forget() # Скрываем JSON-специфичные поля
            self.html_extraction_frame.pack(fill="x", expand=True) # Показываем HTML-специфичные поля

        # Управление состоянием пагинации (только для HTML/Selenium)
        if selected_type == "API (JSON)":
            self.pagination_checkbox.config(state="disabled")
            self.pagination_var.set(False) # Отключаем пагинацию для API
        else:
            self.pagination_checkbox.config(state="normal")
        self._on_pagination_change() # Обновляем состояние полей пагинации

        self._update_field_labels() # Обновить тексты меток полей для извлечения

    def _on_pagination_change(self, *args):
        # Эта функция теперь зависит от типа парсинга
        selected_type = self.parsing_type_var.get()
        if selected_type == "API (JSON)":
            # Если API, всегда отключаем пагинацию
            self.next_page_selector_entry.config(state="disabled")
            self.max_pages_entry.config(state="disabled")
            self.pagination_var.set(False)
        else:
            # Для HTML/Selenium - включаем/отключаем по чекбоксу
            if self.pagination_var.get():
                self.next_page_selector_entry.config(state="normal")
                self.max_pages_entry.config(state="normal")
            else:
                self.next_page_selector_entry.config(state="disabled")
                self.max_pages_entry.config(state="disabled")

    def log_message(self, message):
        self.log_text.config(state='normal')
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.log_text.config(state='disabled')

    def clear_output(self):
        self.log_text.config(state='normal')
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state='disabled')

    def _save_config(self):
        config_data = {
            'url': self.url_entry.get(),
            'parsing_type': self.parsing_type_var.get(),
            'browser': self.browser_var.get(),
            'headless': self.headless_var.get(),
            'main_container_selector': self.main_container_selector_entry.get(),
            'json_root_path': self.json_root_path_entry.get(),
            'source_api_headers': self.source_api_headers_text.get("1.0", tk.END).strip(),
            'fields': [],
            'pagination_enabled': self.pagination_var.get(),
            'next_page_selector': self.next_page_selector_entry.get(),
            'max_pages': self.max_pages_entry.get(),
            'save_csv': self.save_csv_var.get(),
            'save_json': self.save_json_var.get(),
            'enable_api': self.enable_api_var.get(),
            'api_url': self.api_url_entry.get(),
            'api_method': self.api_method_var.get(),
            'api_headers': self.api_headers_text.get("1.0", tk.END).strip(),
            'enable_monitoring': self.enable_monitoring_var.get(),
            'monitoring_interval': self.monitoring_interval_entry.get()
        }
        for field in self.field_entries:
            config_data['fields'].append({
                'name': field['name'].get(),
                'selector': field['selector'].get(),
                'attribute': field['attribute'].get()
            })

        file_path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON files", "*.json")])
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(config_data, f, ensure_ascii=False, indent=4)
                messagebox.showinfo("Сохранение", "Настройки успешно сохранены.")
            except Exception as e:
                messagebox.showerror("Ошибка сохранения", f"Не удалось сохранить настройки: {e}")

    def _load_config(self):
        file_path = filedialog.askopenfilename(filetypes=[("JSON files", "*.json")])
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)

                self.url_entry.delete(0, tk.END)
                self.url_entry.insert(0, config_data.get('url', ''))
                self.parsing_type_var.set(config_data.get('parsing_type', 'Запросы (Статика)'))
                self.browser_var.set(config_data.get('browser', 'Chrome'))
                self.headless_var.set(config_data.get('headless', True))
                
                self.main_container_selector_entry.delete(0, tk.END)
                self.main_container_selector_entry.insert(0, config_data.get('main_container_selector', ''))
                self.json_root_path_entry.delete(0, tk.END)
                self.json_root_path_entry.insert(0, config_data.get('json_root_path', ''))
                self.source_api_headers_text.config(state='normal') # Временно включаем для вставки
                self.source_api_headers_text.delete("1.0", tk.END)
                self.source_api_headers_text.insert(tk.END, config_data.get('source_api_headers', '{}'))


                for field in list(self.field_entries): # Удаляем существующие поля
                    self._remove_field(field['frame'])
                for field_data in config_data.get('fields', []): # Добавляем новые
                    self._add_field(field_name_default=field_data.get('name', ''),
                                    selector_default=field_data.get('selector', ''),
                                    attribute_default=field_data.get('attribute', ''))

                self.pagination_var.set(config_data.get('pagination_enabled', False))
                self.next_page_selector_entry.delete(0, tk.END)
                self.next_page_selector_entry.insert(0, config_data.get('next_page_selector', ''))
                self.max_pages_entry.delete(0, tk.END)
                self.max_pages_entry.insert(0, config_data.get('max_pages', '3'))

                self.save_csv_var.set(config_data.get('save_csv', True))
                self.save_json_var.set(config_data.get('save_json', True))

                self.enable_api_var.set(config_data.get('enable_api', False))
                self.api_url_entry.delete(0, tk.END)
                self.api_url_entry.insert(0, config_data.get('api_url', ''))
                self.api_method_var.set(config_data.get('api_method', 'POST'))
                self.api_headers_text.delete("1.0", tk.END)
                self.api_headers_text.insert(tk.END, config_data.get('api_headers', '{}'))
                
                self.enable_monitoring_var.set(config_data.get('enable_monitoring', False))
                self.monitoring_interval_entry.delete(0, tk.END)
                self.monitoring_interval_entry.insert(0, config_data.get('monitoring_interval', '300'))

                self._on_parsing_type_change() # Важно вызвать для обновления UI после загрузки
                self._on_pagination_change()

                messagebox.showinfo("Загрузка", "Настройки успешно загружены.")
            except Exception as e:
                messagebox.showerror("Ошибка загрузки", f"Не удалось загрузить настройки: {e}")

    def start_single_parsing(self):
        if self.monitoring_timer:
            self._stop_monitoring()
        
        self.log_message(f"Запускаю разовый парсинг...")
        self.start_button.config(state="disabled")

        threading.Thread(target=self._run_parsing_logic, args=(False,)).start()

    def _start_monitoring(self):
        try:
            interval_seconds = int(self.monitoring_interval_entry.get())
            if interval_seconds <= 0:
                messagebox.showerror("Ошибка", "Интервал должен быть положительным числом.")
                return
            
            if not self.enable_api_var.get():
                messagebox.showwarning("Предупреждение", "Отправка по API не включена. Новые элементы будут обнаружены, но не отправлены.")
            
            self.stop_event.clear()
            self.log_message(f"Запускаю мониторинг каждые {interval_seconds} секунд...")
            self.start_monitoring_button.config(state="disabled")
            self.stop_monitoring_button.config(state="normal")
            self.start_button.config(state="disabled")

            self._run_monitoring_cycle()

        except ValueError:
            messagebox.showerror("Ошибка", "Неверный интервал. Введите целое число.")

    def _stop_monitoring(self):
        self.stop_event.set()
        if self.monitoring_timer:
            self.monitoring_timer.cancel()
            self.monitoring_timer = None
        self.log_message("Мониторинг остановлен.")
        self.start_monitoring_button.config(state="normal")
        self.stop_monitoring_button.config(state="disabled")
        self.start_button.config(state="normal")

    def _run_monitoring_cycle(self):
        if self.stop_event.is_set():
            return

        self.log_message("\n--- Выполняю плановую проверку ---")
        threading.Thread(target=self._run_parsing_logic, args=(True,)).start()

    def _run_parsing_logic(self, is_monitoring_cycle=False):
        url = self.url_entry.get()
        parsing_type = self.parsing_type_var.get() # "Запросы (Статика)", "Selenium (Динамика)", "API (JSON)"
        
        main_container_selector = self.main_container_selector_entry.get()
        json_root_path = self.json_root_path_entry.get()
        source_api_headers_str = self.source_api_headers_text.get("1.0", tk.END).strip()

        browser = self.browser_var.get().lower()
        headless = self.headless_var.get()
        pagination_enabled = self.pagination_var.get()
        next_page_selector = self.next_page_selector_entry.get()
        max_pages_str = self.max_pages_entry.get()
        save_csv = self.save_csv_var.get()
        save_json = self.save_json_var.get()
        enable_api = self.enable_api_var.get()
        api_url = self.api_url_entry.get()
        api_method = self.api_method_var.get()
        api_headers_str = self.api_headers_text.get("1.0", tk.END).strip()

        if not url:
            self.log_message("Ошибка: URL не введен.")
            self.master.after(0, lambda: self.start_button.config(state="normal"))
            return

        item_fields_patterns = {}
        for field_dict in self.field_entries:
            field_name = field_dict['name'].get()
            field_selector = field_dict['selector'].get()
            field_attribute = field_dict['attribute'].get() or None # Атрибут используется только для HTML
            if field_name and field_selector:
                item_fields_patterns[field_name] = (field_selector, field_attribute)
            elif field_name or field_selector:
                 self.log_message(f"Предупреждение: Поле '{field_name or field_selector}' не будет использовано, так как отсутствует имя или селектор.")
        
        if not item_fields_patterns:
            self.log_message("Ошибка: Не определены поля для извлечения.")
            self.master.after(0, lambda: self.start_button.config(state="normal"))
            return

        source_api_headers = {}
        if parsing_type == "API (JSON)":
            if not json_root_path:
                self.log_message("Ошибка: 'JSON-путь к списку элементов' обязателен для парсинга API (JSON).")
                self.master.after(0, lambda: self.start_button.config(state="normal"))
                return
            try:
                if source_api_headers_str:
                    source_api_headers = json.loads(source_api_headers_str)
            except json.JSONDecodeError:
                self.log_message("Ошибка: Неверный формат JSON для заголовков API источника. Проверьте синтаксис.")
                self.master.after(0, lambda: self.start_button.config(state="normal"))
                return
        else: # HTML/Selenium specific checks
            if not main_container_selector:
                self.log_message("Ошибка: CSS-селектор контейнера элемента не введен.")
                self.master.after(0, lambda: self.start_button.config(state="normal"))
                return
            if pagination_enabled:
                if not next_page_selector:
                    self.log_message("Ошибка: Селектор 'Следующая страница' для пагинации не введен.")
                    self.master.after(0, lambda: self.start_button.config(state="normal"))
                    return
                try:
                    max_pages = int(max_pages_str)
                    if max_pages <= 0:
                        raise ValueError("Максимальное количество страниц должно быть положительным числом.")
                except ValueError:
                    self.log_message("Ошибка: Неверное значение для 'Макс. страниц'. Введите целое число.")
                    self.master.after(0, lambda: self.start_button.config(state="normal"))
                    return
            else:
                max_pages = 1

        api_headers_for_sending = {}
        if enable_api:
            try:
                if api_headers_str:
                    api_headers_for_sending = json.loads(api_headers_str)
            except json.JSONDecodeError:
                self.log_message("Ошибка: Неверный формат JSON для заголовков API (Целевой API). Проверьте синтаксис.")
                self.master.after(0, lambda: self.start_button.config(state="normal"))
                return

        parser = None
        try:
            # Преобразуем имя типа парсинга для WebParser
            parser_mode_map = {
                "Запросы (Статика)": "requests",
                "Selenium (Динамика)": "selenium",
                "API (JSON)": "api"
            }
            parser_mode = parser_mode_map.get(parsing_type, "requests")

            parser = WebParser(parsing_mode=parser_mode, headless=headless, browser=browser)
            all_extracted_items = []

            if parser_mode == "api":
                json_data = parser.fetch_api_data(url, headers=source_api_headers)
                if json_data:
                    all_extracted_items = parser.extract_multiple_items(json_data, json_root_path, item_fields_patterns, is_json=True)
                else:
                    self.log_message("Не удалось получить или разобрать JSON данные API.")
            elif pagination_enabled: # HTML/Selenium with pagination
                soups = parser.follow_pagination(url, next_page_selector, max_pages=max_pages)
                for i, soup_page in enumerate(soups):
                    page_items = parser.extract_multiple_items(soup_page, main_container_selector, item_fields_patterns, is_json=False)
                    all_extracted_items.extend(page_items)
                    self.log_message(f"Со страницы {i+1} извлечено {len(page_items)} элементов.")
            else: # HTML/Selenium without pagination
                html_content = parser.fetch_html(url)
                if html_content:
                    soup = parser.parse_html(html_content)
                    if soup:
                        all_extracted_items = parser.extract_multiple_items(soup, main_container_selector, item_fields_patterns, is_json=False)
            
            self.log_message(f"Парсинг завершен. Всего извлечено {len(all_extracted_items)} сырых элементов.")

            # --- Логика дедупликации ---
            new_items = self.duplicate_checker.filter_new_items(all_extracted_items)
            
            if new_items:
                self.log_message(f"Найдено {len(new_items)} новых уникальных элементов после проверки дубликатов.")
                
                # --- Логика отправки API ---
                if enable_api:
                    api_sender = ApiSender(api_url, api_headers_for_sending)
                    successfully_sent_items = api_sender.send_data(new_items, api_method)
                    self.log_message(f"Успешно отправлено {len(successfully_sent_items)} новых элементов в API.")
                    self.duplicate_checker.mark_as_processed(successfully_sent_items)
                else:
                    self.log_message("Отправка по API отключена. Новые элементы не будут отправлены.")
                    if is_monitoring_cycle:
                        self.log_message("Отмечены новые элементы как обработанные, даже без отправки через API (режим мониторинга).")
                        self.duplicate_checker.mark_as_processed(new_items)
            else:
                self.log_message("Новых уникальных элементов не найдено.")

            # --- Сохранение в CSV/JSON (только при разовом парсинге) ---
            if not is_monitoring_cycle:
                if all_extracted_items:
                    if save_csv:
                        save_data_to_csv(all_extracted_items, "parsed_data.csv")
                    if save_json:
                        save_data_to_json(all_extracted_items, "parsed_data.json")
                else:
                    self.log_message("Данные не извлечены с помощью предоставленных селекторов.")

        except Exception as e:
            self.log_message(f"Произошла непредвиденная ошибка во время парсинга: {e}")
            import traceback
            self.log_message(traceback.format_exc())
        finally:
            if parser:
                parser.close_driver()
            
            if is_monitoring_cycle and not self.stop_event.is_set():
                try:
                    interval_seconds = int(self.monitoring_interval_entry.get())
                    self.monitoring_timer = threading.Timer(interval_seconds, self._run_monitoring_cycle)
                    self.monitoring_timer.start()
                    self.log_message(f"Следующая проверка запланирована через {interval_seconds} секунд.")
                except ValueError:
                    self.log_message("Ошибка: Неверный интервал для следующего цикла мониторинга. Мониторинг остановлен.")
                    self._stop_monitoring()
            elif not is_monitoring_cycle:
                self.master.after(0, lambda: self.start_button.config(state="normal"))


class TextHandler(logging.Handler):
    def __init__(self, app_instance):
        super().__init__()
        self.app_instance = app_instance
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        self.setFormatter(formatter)
        logging.getLogger().addHandler(self)

    def emit(self, record):
        msg = self.format(record)
        self.app_instance.master.after(0, lambda: self.app_instance.log_message(msg))

if __name__ == "__main__":
    root = tk.Tk()
    app = ParserApp(root)
    root.protocol("WM_DELETE_WINDOW", lambda: on_closing(root, app))
    root.mainloop()

def on_closing(root_window, app_instance):
    if app_instance.monitoring_timer:
        app_instance._stop_monitoring()
    if app_instance.parser and app_instance.parser.driver:
        app_instance.parser.close_driver()
    root_window.destroy()