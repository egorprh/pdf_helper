import os
import shutil
import tempfile
from pathlib import Path

from aiogram import Router, Bot
from aiogram import flags
from aiogram.types import Message, FSInputFile
from aiogram.filters import Command
from aiogram.enums import ChatAction
from aiogram.utils.chat_action import ChatActionMiddleware

from filters.admin_only import AdminOnly
from utils.html_to_image import html_to_image
from datetime import datetime


# Роутер для шеринга сделок
trade_share_router = Router()
trade_share_router.message.middleware(ChatActionMiddleware())


def _normalize_tokens(text: str) -> list[str]:
    """Возвращает список токенов, разделённых пробелом.

    На вход может прийти строка, где поля разделены вертикальными чертами.
    Мы приводим её к space-separated, затем режем по whitespace.
    """
    # Убираем переносы строк и заменяем вертикальные черты на пробелы
    prepared = (text or "").replace("|", " ").replace("\n", " ").replace("\t", " ")
    # Сжимаем повторяющиеся пробелы
    parts = [p for p in prepared.split(" ") if p]
    return parts


@trade_share_router.message(AdminOnly(), Command("okx"))
@flags.chat_action(action=ChatAction.UPLOAD_PHOTO)
async def handle_okx_share(message: Message, bot: Bot):
    """Обработка команды /okx

    Формат (space-separated):
    /okx <pair> <position_type> <leverage>x <profit_pct> <profit_amount> <entry_price> <exit_price> <share_date> <share_time>
    Пример: /okx SOLUSDT Шорт 50,00x +25,31 +2531,3 165,90 165,06 01.10.2025 15:26:49
    """
    text = message.text or ""

    # Удаляем саму команду
    # Aiogram уже выделяет команду, но надёжнее отрезать вручную
    content = text
    if content.startswith("/okx"):
        content = content[len("/okx"):].strip()

    tokens = _normalize_tokens(content)

    # Ожидаем минимум 7 токенов (без даты/времени). 9 токенов, если дата и время переданы явно
    if len(tokens) < 7:
        await message.answer(
            "Неверный формат. Пример: <code>/okx SOLUSDT Шорт 50,00x +25,31 +2531,3 165,90 165,06 01.10.2025 15:26:49</code>"
        )
        return

    pair = tokens[0]
    position_type = tokens[1]
    leverage = tokens[2]
    profit_percentage = tokens[3]
    profit_amount = tokens[4]
    entry_price = tokens[5]
    exit_price = tokens[6]

    # Дата/время шеринга: если не переданы, подставим текущее локальное время
    share_date: str
    share_time: str
    if len(tokens) >= 9:
        share_date = tokens[7]
        share_time = tokens[8]
    else:
        now = datetime.now()
        share_date = now.strftime("%d.%m.%Y")
        share_time = now.strftime("%H:%M:%S")

    # Выбор шаблона
    position_lower = position_type.lower()
    template_name = "long.html"
    if "шорт" in position_lower or "short" in position_lower:
        template_name = "short.html"

    project_root = Path(__file__).resolve().parents[1]
    template_path = project_root / "tradehtml" / template_name

    if not template_path.exists():
        await message.answer("Шаблон не найден.")
        return

    # Создаём временную копию шаблона и выполняем подстановки
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        # Скопируем всю папку assets рядом, чтобы относительные пути работали
        assets_src = template_path.parent / "assets"
        assets_dst = tmpdir_path / "assets"
        if assets_src.exists():
            shutil.copytree(assets_src, assets_dst)

        # Копия HTML
        temp_html = tmpdir_path / template_name
        shutil.copyfile(template_path, temp_html)

        # Подстановки в HTML
        html_text = temp_html.read_text(encoding="utf-8")
        html_text = (
            html_text
            .replace("{pair}", pair)
            .replace("{position_type}", position_type)
            .replace("{leverage}", leverage)
            .replace("{profit_percentage}", profit_percentage)
            .replace("{profit_amount}", profit_amount)
            .replace("{entry_price}", entry_price)
            .replace("{exit_price}", exit_price)
            .replace("{share_date}", share_date)
            .replace("{share_time}", share_time)
        )
        temp_html.write_text(html_text, encoding="utf-8")

        # Рендерим изображение
        output_dir = project_root / "temp"
        output_image_path = output_dir / f"{pair}_{position_lower}.png"

        image_path = await html_to_image(
            html_file_path=str(temp_html),
            output_path=str(output_image_path),
        )

        # Отправляем изображение
        await message.answer_photo(FSInputFile(image_path))

        # Удаляем сгенерированное изображение после отправки
        try:
            if output_image_path.exists():
                output_image_path.unlink()
        except OSError:
            pass


