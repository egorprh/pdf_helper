from aiogram.filters import BaseFilter
from aiogram.types import TelegramObject


class PrivateOnly(BaseFilter):
    """Пропускает события только из личных чатов."""

    async def __call__(self, event: TelegramObject) -> bool:
        # Для Message / CallbackQuery чат можно получить по-разному,
        # поэтому аккуратно пробуем несколько вариантов.
        chat = getattr(event, "chat", None)

        # Для CallbackQuery чат лежит в event.message.chat
        if chat is None and hasattr(event, "message"):
            message = getattr(event, "message", None)
            chat = getattr(message, "chat", None)

        if chat is None:
            return False

        return getattr(chat, "type", None) == "private"

