from __future__ import annotations

import os

"""
Утилиты для отправки писем через Gmail SMTP.

Функция ниже отправляет письмо с вложением на указанный адрес, используя
учётные данные, взятые из переменных окружения. Реализация максимально
простая, читаемая и тщательно прокомментированная.

Ожидаемые переменные окружения:
- GMAIL_USER: адрес Gmail отправителя (например, example@gmail.com)
- GMAIL_APP_PASSWORD: пароль приложения (App Password) для Gmail
  (рекомендуется для повышения безопасности; для обычного пароля может
   потребоваться дополнительная настройка аккаунта)

Необязательные переменные окружения:
- SMTP_HOST: SMTP‑хост (по умолчанию "smtp.gmail.com")
- SMTP_PORT: порт SMTP SSL (по умолчанию 465)

Пример использования:
    from utils import send_email_with_attachment
    ok = send_email_with_attachment(
        file_path="/absolute/path/to/report.pdf",
        body_text="Здравствуйте! Отправляю вам документ во вложении.",
        recipient_email="recipient@example.com",
    )
    print("Отправлено" if ok else "Не отправлено")
"""

import logging
import mimetypes
import os
import smtplib
import ssl
import certifi
from email.message import EmailMessage
from pathlib import Path
from typing import Optional


# Базовая настройка логгера: выводим время, уровень и сообщение.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)



def send_email_with_attachment(file_path: str, body_text: str, recipient_email: str) -> bool:
    """Отправить письмо с вложением на указанный email через Gmail SMTP.

    Аргументы:
        file_path: Абсолютный или относительный путь к файлу для вложения.
        body_text: Текст письма (plain text).
        recipient_email: Email получателя.

    Возвращает:
        True, если письмо отправлено успешно; False, если произошла ошибка.

    Обработка ошибок:
        - Проверка наличия и доступности файла.
        - Валидация входных данных.
        - Проверка наличия обязательных переменных окружения.
        - Перехват и логирование исключений при подключении/аутентификации/отправке.
    """

    # Валидация входных параметров на базовом уровне
    try:
        if not recipient_email or "@" not in recipient_email:
            logging.error("Некорректный email получателя: %r", recipient_email)
            return False

        if not body_text:
            logging.error("Текст письма пуст. Укажите body_text.")
            return False

        # Проверим файл
        file_path_obj = Path(file_path).expanduser().resolve(strict=False)
        if not file_path_obj.exists() or not file_path_obj.is_file():
            logging.error("Файл для вложения не найден: %s", file_path_obj)
            return False

        # Прочитаем конфигурацию из окружения
        gmail_user = os.getenv("GMAIL_USER")
        gmail_app_password = os.getenv("GMAIL_APP_PASSWORD")
        smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
        # Порт по умолчанию для SSL
        smtp_port_str = os.getenv("SMTP_PORT", "465")

        if not gmail_user or not gmail_app_password:
            logging.error(
                "Не заданы GMAIL_USER и/или GMAIL_APP_PASSWORD в переменных окружения."
            )
            return False

        try:
            smtp_port = int(smtp_port_str)  # может вызвать ValueError, обработаем ниже
        except Exception:
            logging.error("Некорректный SMTP_PORT: %r", smtp_port_str)
            return False

        # Сформируем письмо
        message = EmailMessage()
        message["From"] = gmail_user
        message["To"] = recipient_email
        # В качестве темы возьмём имя файла; при желании можно изменить
        message["Subject"] = f"Документ: {file_path_obj.name}"
        message.set_content(body_text)

        # Определим MIME‑тип вложения (если не удалось — используем бинарный)
        guessed_mime, _ = mimetypes.guess_type(str(file_path_obj))
        if guessed_mime:
            maintype, subtype = guessed_mime.split("/", 1)
        else:
            maintype, subtype = "application", "octet-stream"

        # Прочитаем файл как байты и добавим во вложение
        try:
            with open(file_path_obj, "rb") as f:
                file_bytes = f.read()
        except Exception as file_err:
            logging.exception("Ошибка чтения файла для вложения: %s", file_path_obj)
            return False

        message.add_attachment(
            file_bytes,
            maintype=maintype,
            subtype=subtype,
            filename=file_path_obj.name,
        )

        # Настроим защищённое SSL‑подключение и отправим письмо.
        # Явно используем сертификаты из certifi для надёжной валидации на macOS/Python.
        ssl_context = ssl.create_default_context(cafile=certifi.where())
        try:
            with smtplib.SMTP_SSL(host=smtp_host, port=smtp_port, context=ssl_context) as smtp:
                smtp.login(gmail_user, gmail_app_password)
                smtp.send_message(message)
            logging.info("Письмо успешно отправлено на %s", recipient_email)
            return True
        except smtplib.SMTPAuthenticationError:
            logging.exception(
                "Ошибка аутентификации SMTP. Проверьте GMAIL_USER и GMAIL_APP_PASSWORD."
            )
            return False
        except smtplib.SMTPConnectError:
            logging.exception("Не удалось подключиться к SMTP‑серверу: %s:%s", smtp_host, smtp_port)
            return False
        except smtplib.SMTPRecipientsRefused:
            logging.exception("SMTP отклонил адрес получателя: %s", recipient_email)
            return False
        except smtplib.SMTPException:
            logging.exception("Ошибка при отправке письма через SMTP")
            return False

    except Exception:
        # Любая непредвиденная ошибка: логируем стек для диагностики и возвращаем False
        logging.exception("Непредвиденная ошибка при подготовке/отправке письма")
        return False


__all__ = ["send_email_with_attachment"]


