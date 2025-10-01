import os
import logging
from typing import Set

from aiogram.filters import BaseFilter
from aiogram.types import TelegramObject


class AdminOnly(BaseFilter):
    """Фильтр допускает только пользователей из ADMINS.

    Переменная окружения ADMINS может содержать список ID через запятую или пробелы.
    Пример: "123456, 789012 345678".
    """

    def __init__(self) -> None:
        self._admin_ids: Set[int] = self._load_admin_ids()

    def _load_admin_ids(self) -> Set[int]:
        raw = os.getenv("ADMINS", "") or ""
        candidates = [p.strip() for p in raw.replace("\n", " ").replace(",", " ").split(" ")]
        ids: Set[int] = set()
        for chunk in candidates:
            if not chunk:
                continue
            try:
                ids.add(int(chunk))
            except ValueError:
                # Игнорируем некорректные значения
                continue
        return ids

    async def __call__(self, event: TelegramObject) -> bool:
        user = getattr(event, "from_user", None)
        if not user:
            return False
        if not self._admin_ids:
            # Если ADMINS пуст — никого не пускаем
            return False
        return int(user.id) in self._admin_ids


class NonAdminOnly(BaseFilter):
    """Фильтр допускает только пользователей, которые НЕ входят в ADMINS."""

    def __init__(self) -> None:
        # Разделяем с AdminOnly логику парсинга для согласованности
        self._admin_ids: Set[int] = self._load_admin_ids()

    def _load_admin_ids(self) -> Set[int]:
        raw = os.getenv("ADMINS", "") or ""
        candidates = [p.strip() for p in raw.replace("\n", " ").replace(",", " ").split(" ")]
        ids: Set[int] = set()
        for chunk in candidates:
            if not chunk:
                continue
            try:
                ids.add(int(chunk))
            except ValueError:
                continue
        return ids

    async def __call__(self, event: TelegramObject) -> bool:
        user = getattr(event, "from_user", None)
        if not user:
            return True  # если не знаем пользователя — считаем не админом
        if not self._admin_ids:
            # Если список админов пуст, все считаются не-админами
            return True
        return int(user.id) not in self._admin_ids


