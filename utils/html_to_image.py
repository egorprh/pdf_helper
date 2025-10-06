import asyncio
import os
from pathlib import Path
from playwright.async_api import async_playwright


async def html_to_image(html_file_path: str, output_path: str = None, 
                       selector: str = 'div[id="dept_img_trade"]', width: int = 1200, height: int = None) -> str:
    """
    Конвертирует HTML файл в изображение высокого качества.
    
    Args:
        html_file_path (str): Путь к HTML файлу
        output_path (str, optional): Путь для сохранения изображения. Если не указан, 
                                   сохраняется рядом с HTML файлом с расширением .png
        selector (str): CSS селектор элемента для скриншота (по умолчанию div[id="dept_img_trade"])
        width (int): Ширина viewport браузера (по умолчанию 1200)
        height (int, optional): Высота viewport браузера. Если не указана, подстраивается под контент
    
    Returns:
        str: Путь к сохраненному изображению
        
    Raises:
        FileNotFoundError: Если HTML файл не найден
        Exception: При ошибках рендеринга
    """
    
    # Проверяем существование HTML файла
    html_path = Path(html_file_path)
    if not html_path.exists():
        raise FileNotFoundError(f"HTML файл не найден: {html_file_path}")
    
    # Определяем путь для сохранения изображения
    if output_path is None:
        output_path = html_path.parent / f"{html_path.stem}.png"
    else:
        output_path = Path(output_path)
    
    # Создаем директорию для выходного файла, если она не существует
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Получаем абсолютный путь к HTML файлу
    html_absolute_path = html_path.resolve()
    
    async with async_playwright() as p:
        # Запускаем браузер с теми же настройками, что и в render_pdf.py
        browser = await p.chromium.launch(
            headless=True,
            args=[
                '--disable-web-security',
                '--disable-features=VizDisplayCompositor',
                '--no-sandbox',
                '--disable-setuid-sandbox'
            ]
        )
        context = await browser.new_context(
            viewport={'width': width, 'height': height or 800},
            device_scale_factor=6  # Увеличиваем DPI для лучшего качества
        )
        
        try:
            # Создаем новую страницу
            page = await context.new_page()
            
            # Загружаем HTML файл
            await page.goto(f"file://{html_absolute_path}")
            
            # Ждем загрузки всех ресурсов
            await page.wait_for_load_state('networkidle')
            
            # Ждем больше времени для полной загрузки шрифтов и стилей
            await asyncio.sleep(3)
            
            # Дополнительно ждем загрузки шрифтов
            await page.evaluate("document.fonts.ready")
            
            # Находим элемент по селектору
            element = await page.query_selector(selector)
            if not element:
                raise Exception(f"Элемент с селектором '{selector}' не найден")
            
            # Делаем скриншот элемента
            loc = page.locator(selector)
            box = await loc.bounding_box()
            # может вернуть None до рендера — подождём появления и стабильности
            await loc.wait_for(state="visible")

            # округляем клип так, чтобы не было «щели» справа/снизу
            from math import floor, ceil
            clip = {
                "x": floor(box["x"]),
                "y": floor(box["y"]),
                "width": ceil(box["width"]),
                "height": ceil(box["height"]),
            }

            # фон страницы сделаем тёмным и уберём возможные отступы
            await page.add_style_tag(content="""
                html,body{margin:0;padding:0;background:#000;}
            """)

            await page.screenshot(
                path=str(output_path),
                scale='device',
                type='png',
                clip=clip,
            )
            
            print(f"Изображение успешно сохранено: {output_path}")
            return str(output_path)
            
        except Exception as e:
            print(f"Ошибка при создании скриншота: {e}")
            raise
        finally:
            await browser.close()


# Пример использования
if __name__ == "__main__":
    # Пример асинхронного использования
    async def main():
        html_file = "/Users/apple/VSCodeProjects/pdf_sender_bot/tradehtml/positive.html"
        output_file = "/Users/apple/VSCodeProjects/pdf_sender_bot/output/positive_screenshot.png"
        
        try:
            result = await html_to_image(
                html_file_path=html_file,
                output_path=output_file,
                width=1200
            )
            print(f"Скриншот создан: {result}")
        except Exception as e:
            print(f"Ошибка: {e}")
    
    # Запуск примера
    asyncio.run(main())
