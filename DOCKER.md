# 🐳 Запуск PDF Sender Bot в Docker

Этот документ описывает, как запустить Telegram бота для генерации PDF в Docker контейнере.

**Версия образа**: `mcr.microsoft.com/playwright/python:v1.55.0-jammy`

## 📋 Предварительные требования

- Docker и Docker Compose установлены на вашей системе
- Токен Telegram бота (получить у @BotFather)

## 🚀 Быстрый старт

### 1. Настройка переменных окружения

```bash
# Скопируйте пример файла окружения
cp .env-example .env

# Отредактируйте .env файл и добавьте ваш токен бота
nano .env
```

Обязательно заполните:
```bash
TELEGRAM_BOT_TOKEN=your_actual_bot_token_here
```

### 2. Запуск бота

```bash
# Сборка и запуск в фоновом режиме
docker-compose up -d

# Просмотр логов
docker-compose logs -f helper-bot

# Остановка
docker-compose down
```

## 🔧 Управление контейнером

### Основные команды

```bash
# Запуск
docker-compose up -d

# Остановка
docker-compose down

# Перезапуск
docker-compose restart

# Просмотр логов
docker-compose logs -f

# Просмотр статуса
docker-compose ps

# Пересборка образа
docker-compose build --no-cache
```

### Отладка

```bash
# Запуск в интерактивном режиме
docker-compose run --rm helper-bot bash

# Просмотр логов в реальном времени
docker-compose logs -f helper-bot

# Проверка переменных окружения в контейнере
docker-compose exec helper-bot env
```

## 📁 Структура Docker файлов

- `Dockerfile` - Описание образа с Python, Playwright v1.55.0 и всеми зависимостями
- `docker-compose.yml` - Конфигурация сервисов и сетей
- `.dockerignore` - Файлы, исключаемые из контекста сборки
- `.env-example` - Пример файла с переменными окружения

## ⚙️ Конфигурация

### Основные зависимости

- **Playwright v1.55.0** - автоматизация браузеров для генерации PDF
- **aiogram 3.22** - Telegram Bot API
- **PyPDF2 3.0+** - работа с PDF файлами
- **python-dotenv 1.0.1** - управление переменными окружения
- **certifi 2025.8.3** - SSL сертификаты

### Шрифты SF Pro Display

Dockerfile автоматически устанавливает шрифты SF Pro Display:
- Копирует `.woff2` и `.woff` файлы из `invoice_html/fonts/`
- Устанавливает в `/usr/share/fonts/truetype/sf-pro-display/`
- Обновляет кэш шрифтов через `fc-cache -fv`

### Переменные окружения

| Переменная | Обязательная | Описание |
|------------|--------------|----------|
| `TELEGRAM_BOT_TOKEN` | ✅ | Токен Telegram бота |
| `GMAIL_USER` | ❌ | Email для отправки PDF |
| `GMAIL_APP_PASSWORD` | ❌ | Пароль приложения Gmail |
| `SMTP_HOST` | ❌ | SMTP сервер (по умолчанию: smtp.gmail.com) |
| `SMTP_PORT` | ❌ | SMTP порт (по умолчанию: 465) |
| `ADMINS` | ❌ | Список ID администраторов (через запятую) |
| `MAIN_ADMINS` | ❌ | Список ID главных администраторов (через запятую) |

### Docker Compose конфигурация

**Переменные окружения в docker-compose.yml:**
- `TELEGRAM_BOT_TOKEN` - токен бота (обязательно)
- `GMAIL_USER`, `GMAIL_APP_PASSWORD` - настройки Gmail SMTP
- `SMTP_HOST`, `SMTP_PORT` - параметры SMTP сервера
- `DISPLAY=:99` - настройка дисплея для Playwright
- `PLAYWRIGHT_BROWSERS_PATH=/ms-playwright` - путь к браузерам
- `ADMINS`, `MAIN_ADMINS` - списки администраторов

### Volumes (тома)

- `.:/app:ro` - Весь проект монтируется в режиме только для чтения
- `temp_files:/app/temp` - Временные файлы (отдельный volume для производительности)

**Использование временных файлов:**
- **`create_invoice.py`**: `temp/invoice_*.pdf`, `temp/temp_invoice_*.html`
- **`create_user_pdf.py`**: `temp/temp_uploaded_*.pdf`, `temp/title_*.pdf`, `temp/final_*.pdf`, `temp/temp_title_*.html`
- **`trade_share.py`**: `temp/*.png` (изображения торговых сделок)

**Управление временными файлами:**
- Директория `temp/` создается автоматически при запуске бота
- Временные файлы удаляются после использования через `cleanup_files()`
- Директория остается пустой после очистки файлов

### Ограничения ресурсов

- **Память**: максимум 2GB, минимум 1GB
- **CPU**: максимум 1.0 ядро, минимум 0.5 ядра

**Обоснование увеличенных ресурсов:**
- **Playwright + Chromium**: требует ~800MB-1.2GB памяти
- **PDF генерация**: высокое качество рендеринга (`device_scale_factor=2`)
- **Изображения**: создание скриншотов с `device_scale_factor=6`
- **PyPDF2**: обработка и объединение PDF файлов
- **Пиковая нагрузка**: несколько одновременных запросов на генерацию

## 🛠️ Разработка

### Локальная разработка с Docker

```bash
# Запуск с пересборкой
docker-compose up --build

# Запуск только сервиса бота
docker-compose up helper-bot

# Выполнение команд в контейнере
docker-compose exec helper-bot python -c "print('Hello from container!')"
```

### Обновление зависимостей

```bash
# Обновить requirements.txt, затем:
docker-compose build --no-cache
docker-compose up -d
```

## 🐛 Решение проблем

### Бот не запускается

1. Проверьте токен в `.env` файле
2. Убедитесь, что Docker запущен
3. Проверьте логи: `docker-compose logs helper-bot`

### Ошибки с Playwright

```bash
# Переустановка браузеров в контейнере
docker-compose exec helper-bot playwright install chromium

# Проверка установленных браузеров
docker-compose exec helper-bot playwright --version
```

### Проблемы со шрифтами

```bash
# Проверка установленных шрифтов
docker-compose exec helper-bot fc-list | grep -i "sf pro"

# Переустановка шрифтов (если необходимо)
docker-compose build --no-cache
```

### Проблемы с правами доступа

```bash
# Проверка прав на файлы
ls -la invoice_html/
ls -la pdf_title/
ls -la tradehtml/
```

### Очистка Docker

```bash
# Удаление неиспользуемых образов
docker system prune -a

# Удаление всех контейнеров и сетей
docker-compose down --volumes --remove-orphans
```

## 📊 Мониторинг

### Просмотр ресурсов

```bash
# Использование ресурсов контейнером (в реальном времени)
docker stats helper-bot

# Информация о контейнере
docker inspect helper-bot

# Проверка использования памяти во время генерации PDF
docker exec helper-bot ps aux --sort=-%mem | head -10
```

### Критические метрики

**⚠️ Следите за:**
- **Память > 1.5GB** - может указывать на утечки памяти
- **CPU > 80%** длительное время - возможны проблемы с производительностью
- **Время генерации PDF > 30 секунд** - может потребоваться оптимизация

**💡 Рекомендации:**
- При высокой нагрузке рассмотрите увеличение лимитов до 3GB RAM
- Для продакшена добавьте мониторинг (Prometheus + Grafana)
- Настройте алерты при превышении лимитов

### Логи

```bash
# Последние 100 строк логов
docker-compose logs --tail=100 helper-bot

# Логи с временными метками
docker-compose logs -t helper-bot
```

## 🔒 Безопасность

### Пользователь и права доступа

- **Пользователь**: `app` (непривилегированный)
- **Рабочая директория**: `/app` с правами `755`
- **Временная директория**: `/app/temp` с правами `777`
- **Шрифты**: установлены с правами `644`

### Меры безопасности

- Контейнер запускается от непривилегированного пользователя `app`
- Чувствительные данные передаются через переменные окружения
- Файлы монтируются в режиме только для чтения (`:ro`)
- Ограничены ресурсы контейнера
- Изолированная сеть `bot-network`

### Масштабирование

Для запуска нескольких экземпляров бота:

```bash
docker-compose up --scale helper-bot=3
```

**Примечание**: Убедитесь, что ваш бот поддерживает множественные экземпляры.

---

## 🆘 Поддержка

При возникновении проблем:

1. Проверьте логи: `docker-compose logs -f`
2. Убедитесь в корректности `.env` файла
3. Проверьте доступность всех необходимых файлов
4. Убедитесь, что Docker имеет достаточно ресурсов
