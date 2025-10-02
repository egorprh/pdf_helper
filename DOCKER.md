# 🐳 Запуск PDF Sender Bot в Docker

Этот документ описывает, как запустить Telegram бота для генерации PDF в Docker контейнере.

## 📋 Предварительные требования

- Docker и Docker Compose установлены на вашей системе
- Токен Telegram бота (получить у @BotFather)

## 🚀 Быстрый старт

### 1. Настройка переменных окружения

```bash
# Скопируйте пример файла окружения
cp env.example .env

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
docker-compose logs -f pdf-sender-bot

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
docker-compose run --rm pdf-sender-bot bash

# Просмотр логов в реальном времени
docker-compose logs -f pdf-sender-bot

# Проверка переменных окружения в контейнере
docker-compose exec pdf-sender-bot env
```

## 📁 Структура Docker файлов

- `Dockerfile` - Описание образа с Python, Playwright и всеми зависимостями
- `docker-compose.yml` - Конфигурация сервисов и сетей
- `.dockerignore` - Файлы, исключаемые из контекста сборки
- `env.example` - Пример файла с переменными окружения

## ⚙️ Конфигурация

### Переменные окружения

| Переменная | Обязательная | Описание |
|------------|--------------|----------|
| `TELEGRAM_BOT_TOKEN` | ✅ | Токен Telegram бота |
| `GMAIL_USER` | ❌ | Email для отправки PDF |
| `GMAIL_APP_PASSWORD` | ❌ | Пароль приложения Gmail |
| `SMTP_HOST` | ❌ | SMTP сервер (по умолчанию: smtp.gmail.com) |
| `SMTP_PORT` | ❌ | SMTP порт (по умолчанию: 465) |

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
docker-compose up pdf-sender-bot

# Выполнение команд в контейнере
docker-compose exec pdf-sender-bot python -c "print('Hello from container!')"
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
3. Проверьте логи: `docker-compose logs pdf-sender-bot`

### Ошибки с Playwright

```bash
# Переустановка браузеров в контейнере
docker-compose exec pdf-sender-bot playwright install chromium
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
docker stats pdf-sender-bot

# Информация о контейнере
docker inspect pdf-sender-bot

# Проверка использования памяти во время генерации PDF
docker exec pdf-sender-bot ps aux --sort=-%mem | head -10
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
docker-compose logs --tail=100 pdf-sender-bot

# Логи с временными метками
docker-compose logs -t pdf-sender-bot
```

## 🔒 Безопасность

- Контейнер запускается от непривилегированного пользователя `app`
- Чувствительные данные передаются через переменные окружения
- Файлы монтируются в режиме только для чтения (`:ro`)
- Ограничены ресурсы контейнера

### Масштабирование

Для запуска нескольких экземпляров бота:

```bash
docker-compose up --scale pdf-sender-bot=3
```

**Примечание**: Убедитесь, что ваш бот поддерживает множественные экземпляры.

---

## 🆘 Поддержка

При возникновении проблем:

1. Проверьте логи: `docker-compose logs -f`
2. Убедитесь в корректности `.env` файла
3. Проверьте доступность всех необходимых файлов
4. Убедитесь, что Docker имеет достаточно ресурсов
