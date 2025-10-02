import logging
from aiogram import Router
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from filters.admin_only import AdminOnly, NonAdminOnly

# Создаем роутер для заглушек
plug_router = Router()


@plug_router.message(AdminOnly())
async def admin_hint(message: Message):
    """Catch-all для админов: подсказка по использованию"""
    await message.answer("Воспользуйтесь командами /create_invoice и /okx.<br>Пример: <code>/okx SOLUSDT Шорт 50,00x +25,31 +2531,3 165,90 165,06</code>")


@plug_router.message(NonAdminOnly())
async def not_allowed_message(message: Message):
    """Catch-all для не-админов: отказ в доступе"""
    await message.answer("Вы не можете пользоваться этим ботом. Обратитесь к разработчику для предоставления доступа.")


@plug_router.callback_query(NonAdminOnly())
async def not_allowed_callback(callback: CallbackQuery):
    """Catch-all для не-админов: отказ в доступе для callback"""
    await callback.message.answer("Вы не можете пользоваться этим ботом. Обратитесь к разработчику для предоставления доступа.")
    await callback.answer()
