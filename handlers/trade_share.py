import os
import shutil
import tempfile
from pathlib import Path

from aiogram import Router, Bot
from aiogram.types import Message, FSInputFile
from aiogram.filters import Command
from aiogram.enums import ChatAction

from filters.admin_only import AdminOnly
from utils.html_to_image import html_to_image


# Роутер для шеринга сделок
trade_share_router = Router()


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
async def handle_okx_share(message: Message, bot: Bot):
    """Обработка команды /okx

    Формат (space-separated):
    /okx <pair> <position_type> <leverage>x <profit_pct> <profit_amount> <entry_price> <exit_price>
    Пример: /okx SOLUSDT Шорт 50,00x +25,31 +2531,3 165,90 165,06
    """
    text = message.text or ""

    # Удаляем саму команду
    # Aiogram уже выделяет команду, но надёжнее отрезать вручную
    content = text
    if content.startswith("/okx"):
        content = content[len("/okx"):].strip()

    tokens = _normalize_tokens(content)

    # Ожидаем минимум 7 токенов
    if len(tokens) < 7:
        await message.answer(
            "Неверный формат. Пример: <code>/okx SOLUSDT Шорт 50,00x +25,31 +2531,3 165,90 165,06</code>"
        )
        return

    pair = tokens[0]
    position_type = tokens[1]
    leverage = tokens[2]
    profit_percentage = tokens[3]
    profit_amount = tokens[4]
    entry_price = tokens[5]
    exit_price = tokens[6]

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
        )
        temp_html.write_text(html_text, encoding="utf-8")

        # Рендерим изображение
        output_dir = project_root / "temp"
        output_image_path = output_dir / f"{pair}_{position_lower}.png"

        await bot.send_chat_action(message.chat.id, ChatAction.UPLOAD_PHOTO)

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


