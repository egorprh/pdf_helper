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
from handlers import create_invoice_router, plug_router, trade_share_router, create_user_pdf_router


logging.basicConfig(level=logging.INFO)


TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TELEGRAM_TOKEN:
    raise SystemExit("TELEGRAM_BOT_TOKEN не найден в .env")

bot = Bot(token=TELEGRAM_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Подключаем роутеры
dp.include_router(create_invoice_router)  # Основные команды
dp.include_router(trade_share_router)  # Шеринг сделок /okx
dp.include_router(create_user_pdf_router)  # Создание пользовательского PDF
dp.include_router(plug_router)  # Заглушки (подключаем последним)


if __name__ == "__main__":
    async def main():
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    asyncio.run(main())
