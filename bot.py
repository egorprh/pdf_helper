import os
import logging
from dotenv import load_dotenv

# Загружаем .env ПЕРВЫМ, до всех остальных импортов
load_dotenv()

# Создаем директорию для временных файлов при запуске
os.makedirs("temp", exist_ok=True)

from aiogram import Bot, Dispatcher
from aiogram.types import Message, CallbackQuery
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage

import asyncio
from filters.admin_only import AdminOnly, NonAdminOnly
from handlers import (
    create_invoice_router,
    plug_router,
    trade_share_router,
    create_user_pdf_router,
    channel_comments_router,
)
from middlewares.spam_protection import AntiSpamMiddleware


logging.basicConfig(level=logging.INFO)


TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TELEGRAM_TOKEN:
    raise SystemExit("TELEGRAM_BOT_TOKEN не найден в .env")

bot = Bot(token=TELEGRAM_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Глобальный антиспам мидлвар для всех обновлений
dp.update.middleware(AntiSpamMiddleware(bot))


async def send_startup_message():
    """Отправляет сообщение о запуске бота всем администраторам."""
    main_admins = os.getenv("MAIN_ADMINS", "")
    if not main_admins:
        logging.warning("Переменная MAIN_ADMINS не установлена. Сообщение о запуске не отправлено.")
        return
    
    admin_ids = [int(admin_id.strip()) for admin_id in main_admins.split(",") if admin_id.strip()]
    if not admin_ids:
        logging.warning("Список администраторов пуст. Сообщение о запуске не отправлено.")
        return
    
    message_text = "🤖 <b>Бот запущен!</b>\n\n✅ Статус: Работает"
    
    for admin_id in admin_ids:
        try:
            await bot.send_message(admin_id, message_text)
            logging.info(f"Сообщение о запуске отправлено администратору {admin_id}")
        except Exception as e:
            logging.error(f"Не удалось отправить сообщение администратору {admin_id}: {e}")

# Подключаем роутеры
dp.include_router(create_invoice_router)  # Основные команды
dp.include_router(trade_share_router)  # Шеринг сделок /okx
dp.include_router(create_user_pdf_router)  # Создание пользовательского PDF
dp.include_router(channel_comments_router)  # Комментарии к постам каналов
dp.include_router(plug_router)  # Заглушки (подключаем последним)


if __name__ == "__main__":
    async def main():
        # Очищаем все сообщения в чате  
        await bot.delete_webhook(drop_pending_updates=True)
        
        # Отправляем сообщение о запуске администраторам
        await send_startup_message()
        
        await dp.start_polling(bot)
    asyncio.run(main())
