# Используем официальный Playwright образ с Python
FROM mcr.microsoft.com/playwright/python:v1.55.0-jammy

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем файл зависимостей
COPY requirements.txt .

# Устанавливаем Python зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Браузеры уже установлены в официальном Playwright образе

# Устанавливаем системные шрифты SF Pro Display
RUN mkdir -p /usr/share/fonts/truetype/sf-pro-display

# Копируем шрифты SF Pro Display в системную директорию
COPY invoice_html/fonts/*.woff2 /usr/share/fonts/truetype/sf-pro-display/
COPY invoice_html/fonts/*.woff /usr/share/fonts/truetype/sf-pro-display/

# Устанавливаем права доступа для шрифтов
RUN chmod 644 /usr/share/fonts/truetype/sf-pro-display/*

# Обновляем кэш шрифтов
RUN fc-cache -fv

# Создаем пользователя для безопасности
RUN useradd --create-home --shell /bin/bash app

# Копируем весь проект
COPY . .

# Устанавливаем правильные права доступа для всех файлов и директорий
RUN chown -R app:app /app \
    && chmod -R 755 /app \
    && mkdir -p /app/temp \
    && chmod 777 /app/temp

USER app

# Команда запуска
CMD ["python", "bot.py"]
