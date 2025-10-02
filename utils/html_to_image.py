import asyncio
import os
from pathlib import Path
from playwright.async_api import async_playwright


async def html_to_image(html_file_path: str, output_path: str = None, 
                       selector: str = 'div[data-testid="inLand"]', width: int = 1200, height: int = None) -> str:
    """
    Конвертирует HTML файл в изображение высокого качества.
    
    Args:
        html_file_path (str): Путь к HTML файлу
        output_path (str, optional): Путь для сохранения изображения. Если не указан, 
                                   сохраняется рядом с HTML файлом с расширением .png
        selector (str): CSS селектор элемента для скриншота (по умолчанию div[data-testid="inLand"])
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
        # Запускаем браузер
        browser = await p.chromium.launch(headless=True)
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
            
            # Ждем немного для полной загрузки стилей и изображений
            await asyncio.sleep(2)
            
            # Находим элемент по селектору
            element = await page.query_selector(selector)
            if not element:
                raise Exception(f"Элемент с селектором '{selector}' не найден")
            
            # Делаем скриншот элемента
            await element.screenshot(
                path=str(output_path),
                type='png'
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
