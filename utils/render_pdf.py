#!/usr/bin/env python3
"""
Пример Playwright с идеальными настройками для полного использования A4.
Убирает все возможные отступы и использует полную площадь страницы.
"""

import asyncio
from playwright.async_api import async_playwright
import os
from pathlib import Path

async def html_to_pdf_playwright(html_file_path: str, output_pdf_path: str, css_file_path: str = None) -> bool:
    """Преобразовать HTML файл в PDF с максимальным использованием A4.
    
    Аргументы:
        html_file_path: Путь к HTML файлу для преобразования.
        output_pdf_path: Путь для сохранения результирующего PDF файла.
        css_file_path: Опциональный путь к CSS файлу для стилизации.
    
    Возвращает:
        True, если PDF успешно создан; False, если произошла ошибка.
    """
    
    try:
        # Валидация входных параметров
        html_path = Path(html_file_path).expanduser().resolve()
        if not html_path.exists() or not html_path.is_file():
            print(f"❌ HTML файл не найден: {html_path}")
            return False

        output_path = Path(output_pdf_path).expanduser().resolve()
        
        # Создадим директорию для выходного файла, если она не существует
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Проверим CSS файл, если он указан
        if css_file_path:
            css_path = Path(css_file_path).expanduser().resolve()
            if not css_path.exists() or not css_path.is_file():
                print(f"⚠️ CSS файл не найден: {css_path}. Будет использован HTML без внешних стилей.")
                css_file_path = None

        print(f"🔄 Начинаю конвертацию HTML в PDF с максимальным использованием A4...")
        print(f"📄 HTML файл: {html_path}")
        if css_file_path:
            print(f"🎨 CSS файл: {css_path}")
        print(f"📋 Выходной PDF: {output_path}")
        
        async with async_playwright() as p:
            # Запускаем браузер в headless режиме
            browser = await p.chromium.launch(headless=True)
            # Используем контекст с повышенной плотностью рендеринга
            context = await browser.new_context(device_scale_factor=2)
            page = await context.new_page()
            
            # Загружаем HTML файл
            await page.goto(f"file://{html_path}")
            
            # Ждем загрузки всех ресурсов
            await page.wait_for_load_state('networkidle')
            
            # Настройки для максимального использования A4 с улучшенным качеством
            pdf_options = {
                'path': str(output_path),
                'format': 'A4',
                'margin': {
                    'top': '0',
                    'right': '0',
                    'bottom': '0',
                    'left': '0'
                },
                'print_background': True,  # Включаем фоновые цвета и изображения
                'prefer_css_page_size': False,  # Используем стандартные размеры A4
                'scale': 1.3348,  # Чтобы полностью заполнить A4
                'display_header_footer': False,  # Отключаем заголовки и футеры браузера
                'header_template': '',  # Пустой заголовок
                'footer_template': '',  # Пустой футер
            }
            
            # Генерируем PDF
            await page.pdf(**pdf_options)
            
            await context.close()
            await browser.close()
        
        print(f"✅ PDF успешно создан: {output_path}")
        return True

    except Exception as e:
        print(f"❌ Ошибка при конвертации HTML в PDF: {str(e)}")
        return False


async def main():
    """Основная функция для демонстрации."""
    
    # Пути к файлам
    html_file = "invoice_html/pdf.html"
    css_file = "invoice_html/styles.css"
    output_pdf = "invoice_html/invoice.pdf"
    
    # Получаем абсолютные пути
    current_dir = os.path.dirname(os.path.abspath(__file__))
    html_path = os.path.join(current_dir, html_file)
    css_path = os.path.join(current_dir, css_file)
    pdf_path = os.path.join(current_dir, output_pdf)
    
    print("🚀 Демонстрация Playwright с максимальным использованием A4")
    print("=" * 60)
    
    # Вызываем функцию конвертации
    success = await html_to_pdf_playwright(
        html_file_path=html_path,
        output_pdf_path=pdf_path,
        css_file_path=css_path
    )
    
    if success:
        print("\n🎉 Конвертация завершена успешно!")
        print(f"📁 Проверьте файл: {pdf_path}")
        print("\n💡 Настройки для максимального использования A4:")
        print("   - format: 'A4'")
        print("   - margin: 0 (без отступов)")
        print("   - prefer_css_page_size: False")
        print("   - scale: 1.3348 (100%)")
        print("   - display_header_footer: False")
        print("   - CSS: .container { width: 100%; height: 100%; padding: 42px 33px; }")
        print("   - CSS: .page { width: 210mm; height: 297mm; }")
    else:
        print("\n❌ Конвертация не удалась")


if __name__ == "__main__":
    asyncio.run(main())
