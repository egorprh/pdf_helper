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
    
    # Создаем временный HTML файл внутри invoice_html/ чтобы относительные пути к ресурсам оставались валидными
    temp_html_path = f"invoice_html/temp_invoice_{submission_id}.html"
    with open(temp_html_path, "w", encoding="utf-8") as f:
        f.write(html_text)
    
    return temp_html_path
