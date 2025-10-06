import time
from collections import defaultdict, deque
from typing import Callable, Dict, Any
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from aiogram import Bot
import logging

logger = logging.getLogger(__name__)


class AntiSpamMiddleware(BaseMiddleware):
    def __init__(self, bot: Bot, limit=5, interval=2, block_duration=30):
        super().__init__()
        self.bot = bot
        self.limit = limit
        self.interval = interval
        self.block_duration = block_duration
        self.user_spam_tracker: Dict[int, deque] = defaultdict(deque)
        self.user_blocked_until: Dict[int, float] = {}

    async def __call__(
            self,
            handler: Callable[[TelegramObject, Dict[str, Any]], Any],
            event: TelegramObject,
            data: Dict[str, Any]
    ) -> Any:
        # На уровне dp.update event может быть типом Update и не содержать from_user.
        # Aiogram добавляет в data ключи event_from_user / event_chat через UserContextMiddleware.
        user = data.get("event_from_user") or getattr(event, "from_user", None)
        if not user:
            return await handler(event, data)

        now = time.time()
        uid = user.id

        if uid in self.user_blocked_until and now < self.user_blocked_until[uid]:
            logger.warning(f"Пользователь {user.full_name} {user.id} заблокирован за спам")
            await self.bot.send_message(uid, "🚫 Пожалуйста, не спамьте. Подождите 30 секунд.")
            return

        timestamps = self.user_spam_tracker[uid]
        timestamps.append(now)

        while timestamps and now - timestamps[0] > self.interval:
            timestamps.popleft()

        if len(timestamps) > self.limit:
            self.user_blocked_until[uid] = now + self.block_duration
            self.user_spam_tracker[uid].clear()
            logger.warning(f"🔒 Пользователь {user.full_name} временно заблокирован за спам")
            await self.bot.send_message(uid, "🚫 Пожалуйста, не спамьте. Подождите 30 секунд.")
            return

        return await handler(event, data)
