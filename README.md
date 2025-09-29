## PDF Sender Bot (Telegram + Playwright)

Телеграм‑бот, который собирает данные у пользователя, генерирует PDF‑счёт из HTML через Playwright и отправляет готовый PDF в чат. В проект также входит утилита для самостоятельной конвертации HTML→PDF и модуль отправки писем через Gmail SMTP (опционально).

### Основные возможности
- Генерация PDF из шаблона `html/pdf.html` со стилями из `html/styles.css` и локальными ассетами в `html/assets/`
- Сбор данных в чате Telegram по шагам (email → продукт → срок → имя → телефон → номер заказа → дата → сумма)
- Подтверждение введённых данных и отправка PDF‑файла в чат
- Отдельный скрипт конвертации HTML→PDF (`render_pdf.py`)
- Опциональная отправка PDF по email через SMTP (модуль `utils.py`)

---

## Структура проекта
- `bot.py` — Telegram‑бот на `aiogram`, генерирует PDF и отправляет его пользователю
- `render_pdf.py` — пример самостоятельной конвертации HTML→PDF с настройками под полный A4
- `utils.py` — отправка писем с вложением через Gmail SMTP (опционально)
- `html/pdf.html` — HTML‑шаблон счёта с элементами, заполняемыми по `id`
- `html/styles.css` — стили для PDF‑страницы (A4, шрифты, сетки и пр.)
- `html/assets/` — изображения и иконки, используемые в шаблоне
- `html/fonts/` — локальные шрифты SF Pro Display (woff/woff2)
- `requirements.txt` — базовые зависимости (Playwright)

---

## Требования
- Python 3.10+
- Установленный `playwright` и браузер Chromium
- Токен Telegram‑бота

---

## Установка
1) Клонируйте репозиторий и перейдите в каталог проекта:
```bash
cd /Users/apple/VSCodeProjects/pdf_sender_bot
```

2) Установите зависимости Python:
```bash
pip install -r requirements.txt
# Дополнительно установите недостающие зависимости бота
pip install aiogram python-dotenv
```

3) Установите браузер для Playwright:
```bash
playwright install chromium
```

Примечание: на macOS может понадобиться разрешить запуск браузера при первом старте.

---

## Конфигурация окружения
Создайте файл `.env` в корне проекта или экспортируйте переменные окружения.

Обязательные:
```bash
# Telegram
TELEGRAM_BOT_TOKEN="<ваш_токен_бота>"
```

Опциональные (для `utils.py`, если будете отправлять email):
```bash
# Gmail SMTP
GMAIL_USER="your-email@gmail.com"
GMAIL_APP_PASSWORD="your-app-password"  # пароль приложения
# Опционально
SMTP_HOST="smtp.gmail.com"
SMTP_PORT="465"
```

Советы:
- Для Gmail используйте App Password (нужна 2FA в аккаунте Google).
- В `bot.py` токен читается из `TELEGRAM_BOT_TOKEN` (ключ в .env должен совпадать).

---

## Запуск Telegram‑бота
```bash
python bot.py
```
Диалог в чате:
1. Команда: `/crate` (так указано в коде)
2. Введите email (валидируется по простому regex)
3. Выберите продукт (инлайн‑клавиатура)
4. Выберите продолжительность (инлайн‑клавиатура)
5. Введите имя → телефон → номер заказа → дату покупки → стоимость
6. Подтвердите данные
7. Бот генерирует PDF и отправляет файл в чат

Как это работает внутри:
- `fill_pdf_html(...)` открывает `pdf.html` и подставляет значения в элементы по `id`:
  - `customer_name`, `order_number`, `phone`, `purchase_date`, `product_name`, `tariff`, `number`, `price`, `generation_time`
- `html_to_pdf_playwright(...)` рендерит HTML в PDF (A4) в headless Chromium
- Временный файл `invoice.pdf` отправляется в чат и удаляется

---

## Ручная конвертация HTML→PDF (без бота)
Вы можете сгенерировать PDF напрямую из HTML:
```bash
python render_pdf.py
```
По умолчанию читается `html/pdf.html` и создаётся `html/invoice.pdf`. Скрипт настраивает печать под полный A4 (без внешних отступов, с `print_background=True`).

---

## Кастомизация шаблона PDF
- Редактируйте `html/pdf.html` и `html/styles.css`
- Изображения храните в `html/assets/` и подключайте через `<img src="assets/...">`
- Для корректной замены значений используйте элементы с предсказуемыми `id` (см. список выше)
- Шрифты уже подключены из каталога `html/fonts/`

---

## Отправка PDF по email (опционально)
Пример использования `utils.py`:
```python
from utils import send_email_with_attachment

ok = send_email_with_attachment(
    file_path="/absolute/path/to/html/invoice.pdf",
    body_text="Здравствуйте! Во вложении ваш счёт.",
    recipient_email="client@example.com",
)
print("Отправлено" if ok else "Не отправлено")
```
Требуется корректно настроенный Gmail (App Password) и переменные окружения.

---

## Частые проблемы и решения
- Не создаётся PDF
  - Проверьте, что выполнено `playwright install chromium`
  - Убедитесь, что ресурсы доступны по путям (шрифты, изображения, CSS)
  - Запустите `render_pdf.py` для локальной проверки рендеринга без бота

- В боте нет реакции на команду
  - Проверьте токен и что бот запущен без ошибок
  - Убедитесь, что команда в коде — `/crate` (именно так), либо измените её в `bot.py`

- Неверные данные в PDF
  - Проверьте соответствие `id` в `html/pdf.html` и ключей, которые подставляет `fill_pdf_html`
  - Убедитесь, что даты/стоимость вводятся в ожидаемом формате

- Ошибки с Gmail SMTP
  - Используйте App Password, включите 2FA
  - Проверьте `GMAIL_USER` и `GMAIL_APP_PASSWORD`, порт и хост

---

## Полезные команды
```bash
# Установка зависимостей
pip install -r requirements.txt
pip install aiogram python-dotenv

# Установка браузера
playwright install chromium

# Запуск бота
python bot.py

# Ручная конвертация HTML→PDF
python render_pdf.py
```

---

## Лицензия
Проект предоставляется «как есть». Используйте и адаптируйте под свои задачи.
