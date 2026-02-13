from aiogram import Router
from aiogram.types import CallbackQuery, Message

from filters.admin_only import AdminOnly, NonAdminOnly
from filters.private_only import PrivateOnly

# Создаем роутер для заглушек
plug_router = Router()


@plug_router.message(PrivateOnly(), AdminOnly())
async def admin_hint(message: Message):
    """Catch-all для админов: подсказка по использованию"""
    await message.answer(
        "Доступные команды:\n"
        "/create_invoice — создать PDF счёт и отправить на почту\n"
        "/create_user_pdf — сгенерировать персональный PDF\n"
        "/okx — сгенерировать изображение торговой сделки на OKX\n"
        "/forex — сгенерировать карточку сделки Forex\n"
        "/add_comment_channel — добавить канал в список для комментариев\n"
        "/rm_channel — удалить канал из списка для комментариев\n"
        "/set_comment — изменить текст комментария для канала\n"
        "/get_raw_html — получить HTML выбранного сообщения (в ответ на сообщение)\n\n"
        "Пример OKX: <code>/okx BTCUSDT Лонг 100 -5,53 -3,48 114962.0 114956.0 15.09.2025 20:21:11</code>\n"
        "Пример Forex: <code>/forex pair=EURUSD side=buy side_price=1.06 ticket=54814272772 "
        'desc="Euro vs US Dollar" open=1.16540 close=1.16252 delta=521 pct=0.35 '
        'profit=6108.01 open_dt="2026.01.26 10:12:45" close_dt="2026.01.26 10:35:23" '
        "sl=154.335 swap=2.10 tp=153.536 fee=-5.30</code>"
    )


@plug_router.message(PrivateOnly(), NonAdminOnly())
async def not_allowed_message(message: Message):
    """Catch-all для не-админов: отказ в доступе"""
    await message.answer(
        "Вы не можете пользоваться этим ботом. Обратитесь к разработчику для предоставления доступа."
    )


@plug_router.callback_query(PrivateOnly(), NonAdminOnly())
async def not_allowed_callback(callback: CallbackQuery):
    """Catch-all для не-админов: отказ в доступе для callback"""
    await callback.message.answer(
        "Вы не можете пользоваться этим ботом. Обратитесь к разработчику для предоставления доступа."
    )
    try:
        await callback.answer()
    except Exception:
        # Игнорируем ошибки callback answer (например, query is too old)
        pass
