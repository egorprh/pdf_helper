import re
import datetime
import html as html_lib
from .constants import PRODUCT_MAP, DURATION_MAP


def format_cost(cost_str: str) -> str:
    """Форматирует стоимость, добавляя пробелы после тысяч."""
    try:
        # Убираем все нецифровые символы кроме точки и запятой
        clean_cost = re.sub(r'[^\d.,]', '', cost_str)
        # Заменяем запятую на точку для float
        clean_cost = clean_cost.replace(',', '.')
        cost_value = float(clean_cost)
        # Форматируем с пробелами после тысяч
        formatted = f"{cost_value:,.0f}".replace(',', ' ')
        return formatted
    except (ValueError, TypeError):
        return cost_str


def fill_pdf_html(data: dict, submission_id: str, pdf_html_path: str) -> str:
    """Создает временный HTML файл с подстановками и возвращает путь к нему."""
    with open(pdf_html_path, "r", encoding="utf-8") as f:
        html_text = f.read()

    # Обрабатываем order_number: добавляем нули в начало если меньше 6 символов
    order_number = data.get("order_number", "")
    padded_order_number = order_number.zfill(6) if len(order_number) < 6 else order_number
    
    # Создаем short_number без ведущих нулей
    short_number = order_number.lstrip('0') or '0'
    
    # Форматируем стоимость
    formatted_cost = format_cost(data.get('cost', ''))

    # Заменяем шаблоны {{key}} на значения
    replacements = {
        "{{customer_name}}": html_lib.escape(data.get("name", "")),
        "{{order_number}}": html_lib.escape(padded_order_number),
        "{{short_number}}": html_lib.escape(short_number),
        "{{phone}}": html_lib.escape(data.get("phone", "")),
        "{{purchase_date}}": html_lib.escape(data.get("purchase_date", "")),
        "{{product_name}}": html_lib.escape(data.get("product_title") or PRODUCT_MAP.get(data.get("product", ""), "")),
        "{{tariff}}": html_lib.escape(data.get("duration_title") or DURATION_MAP.get(data.get("duration", ""), "")),
        "{{number}}": html_lib.escape("#" + padded_order_number),
        "{{price}}": html_lib.escape(f"{formatted_cost} ₽"),
        "{{generation_time}}": html_lib.escape(datetime.datetime.now().strftime("%d/%m/%Y | %H:%M"))
    }

    for placeholder, value in replacements.items():
        html_text = html_text.replace(placeholder, value)
    
    # Создаем временный HTML файл в temp/ директории
    temp_html_path = f"temp/temp_invoice_{submission_id}.html"
    with open(temp_html_path, "w", encoding="utf-8") as f:
        f.write(html_text)
    
    return temp_html_path


def fill_title_html(user_name: str) -> str:
    """Создает временный HTML файл с подстановкой имени пользователя"""
    import uuid
    import datetime
    from .constants import TITLE_HTML_PATH
    
    with open(TITLE_HTML_PATH, "r", encoding="utf-8") as f:
        html_text = f.read()

    # Заменяем шаблоны
    replacements = {
        "{{course_title}}": "Персональная программа обучения D-Space",
        "{{customer_name}}": user_name,
        "{{creation_date}}": datetime.datetime.now().strftime("%d.%m.%Y")
    }

    for placeholder, value in replacements.items():
        html_text = html_text.replace(placeholder, value)
    
    # Создаем временный HTML файл
    temp_html_path = f"temp/temp_title_{uuid.uuid4().hex}.html"
    with open(temp_html_path, "w", encoding="utf-8") as f:
        f.write(html_text)
    
    return temp_html_path


def merge_pdfs(title_pdf_path: str, main_pdf_path: str, output_path: str) -> bool:
    """Объединяет титульную страницу с основным PDF"""
    import logging
    import PyPDF2
    
    try:
        with open(title_pdf_path, 'rb') as title_file, open(main_pdf_path, 'rb') as main_file:
            title_reader = PyPDF2.PdfReader(title_file)
            main_reader = PyPDF2.PdfReader(main_file)
            writer = PyPDF2.PdfWriter()

            # Добавляем титульную страницу
            if title_reader.pages:
                writer.add_page(title_reader.pages[0])

            # Добавляем все страницы основного PDF
            for page in main_reader.pages:
                writer.add_page(page)

            # Сохраняем объединенный PDF
            with open(output_path, 'wb') as output_file:
                writer.write(output_file)
        
        return True
    except Exception as e:
        logging.error(f"Ошибка при объединении PDF: {e}")
        return False


def cleanup_files(file_paths: list):
    """Удаляет временные файлы"""
    import os
    import logging
    
    for file_path in file_paths:
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except OSError as e:
            logging.warning(f"Не удалось удалить файл {file_path}: {e}")
