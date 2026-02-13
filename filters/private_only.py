from aiogram.filters import BaseFilter
from aiogram.types import TelegramObject
from aiogram.enums import ChatType


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

        chat_type = getattr(chat, "type", None)

        # aiogram can return either raw string or ChatType enum
        if isinstance(chat_type, ChatType):
            return chat_type == ChatType.PRIVATE

        return str(chat_type) == "private"

