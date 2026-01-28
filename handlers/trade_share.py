import shlex
import shutil
import tempfile
from datetime import datetime
from pathlib import Path

from aiogram import Bot, Router, flags
from aiogram.enums import ChatAction
from aiogram.filters import Command
from aiogram.types import FSInputFile, Message
from aiogram.utils.chat_action import ChatActionMiddleware

from filters.admin_only import AdminOnly
from utils.html_to_image import html_to_image

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


def _format_price_with_spaces(value: str) -> str:
    """Форматирует строковое число: добавляет пробелы между тысячами, сохраняет дробную часть и знак.

    Примеры:
      "114962.0" -> "114 962.0"
      "114962"   -> "114 962"
      "114,962.50" -> "114 962.50"
      "114962,50" -> "114 962,50" (сохраняем исходный разделитель дробной части)
      "+15000" -> "+15 000"
      "-15000.50" -> "-15 000.50"
    """
    if not value:
        return value

    original_value = str(value)
    s = original_value.strip()

    if not s:
        return original_value

    # Сохраняем знак в начале
    sign = ""
    if s.startswith(("+", "-")):
        sign = s[0]
        s = s[1:]

    if not s:
        return original_value

    allowed_chars = set("0123456789., ")
    if any(ch not in allowed_chars for ch in s):
        return original_value
    if not any(ch.isdigit() for ch in s):
        return original_value

    # Определяем разделитель дробной части: "." приоритетно, иначе "," если нет точки
    decimal_sep = "." if "." in s else ("," if "," in s else None)

    if decimal_sep:
        integer_part, fractional_part = s.split(decimal_sep, 1)
    else:
        integer_part, fractional_part = s, None

    # Убираем все нецифровые символы из целой части (запятые, пробелы и т.д.)
    integer_digits = "".join(ch for ch in integer_part if ch.isdigit()) or "0"

    # Группируем по тысячам пробелами
    rev = integer_digits[::-1]
    grouped_rev = " ".join(rev[i : i + 3] for i in range(0, len(rev), 3))
    grouped = grouped_rev[::-1]

    return f"{sign}{grouped}{decimal_sep + fractional_part if fractional_part is not None else ''}"


def _parse_key_value_pairs(text: str) -> tuple[dict[str, str], list[str]]:
    """Парсит строку key=value с поддержкой кавычек."""
    lexer = shlex.shlex(text, posix=True)
    lexer.whitespace_split = True
    lexer.commenters = ""
    tokens = list(lexer)

    result: dict[str, str] = {}
    invalid_tokens: list[str] = []

    for token in tokens:
        if "=" not in token:
            invalid_tokens.append(token)
            continue
        key, value = token.split("=", 1)
        key = key.strip().lower()
        if not key:
            invalid_tokens.append(token)
            continue
        result[key] = value.strip()

    return result, invalid_tokens


@trade_share_router.message(AdminOnly(), Command("okx"))
@flags.chat_action(action=ChatAction.UPLOAD_PHOTO)
async def handle_okx_share(message: Message, bot: Bot):
    """Обработка команды /okx

    Формат (space-separated):
    /okx <pair> <position_type> <leverage>x <profit_pct> <profit_amount> <entry_price> <exit_price> <share_date> <share_time>
    Пример: /okx BTCUSDT Лонг 100 -5,53 -3,48 114962.0 114956.0 15.09.2025 20:21:11
    """
    text = message.text or ""

    # Удаляем саму команду
    # Aiogram уже выделяет команду, но надёжнее отрезать вручную
    content = text
    if content.startswith("/okx"):
        content = content[len("/okx") :].strip()

    tokens = _normalize_tokens(content)

    # Ожидаем минимум 7 токенов (без даты/времени). 9 токенов, если дата и время переданы явно
    if len(tokens) < 7:
        await message.answer(
            "Неверный формат. Пример: <code>/okx BTCUSDT Лонг 100 -5,53 -3,48 114962.0 114956.0 15.09.2025 20:21:11</code>"
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

    # Выбор шаблона по знаку процента прибыли: "+" -> long, "-" -> short
    position_lower = position_type.lower()
    profit_sign = (profit_percentage or "").strip()
    template_name = (
        "long.html"
        if profit_sign.startswith("+")
        else "short.html"
        if profit_sign.startswith("-")
        else "long.html"
    )

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

        # Скопируем папку иконок монет рядом, чтобы использовать относительный путь ./icons/PAIR.png
        icons_src = template_path.parent / "icons"
        icons_dst = tmpdir_path / "icons"
        if icons_src.exists():
            shutil.copytree(icons_src, icons_dst)

        # Скопируем локальные шрифты и файл подключения шрифтов, чтобы @font-face работал по file://
        fonts_src = template_path.parent / "fonts"
        fonts_dst = tmpdir_path / "fonts"
        if fonts_src.exists():
            shutil.copytree(fonts_src, fonts_dst)

        fonts_css_src = template_path.parent / "fonts.css"
        fonts_css_dst = tmpdir_path / "fonts.css"
        if fonts_css_src.exists():
            shutil.copyfile(fonts_css_src, fonts_css_dst)

        # Копия HTML
        temp_html = tmpdir_path / template_name
        shutil.copyfile(template_path, temp_html)

        # Подстановки в HTML
        html_text = temp_html.read_text(encoding="utf-8")
        # Определим путь до иконки монеты: ./icons/{PAIR}.png, либо fallback на BTCUSDT.png
        normalized_pair = (pair or "").upper().strip()
        requested_icon_rel = f"./icons/{normalized_pair}.png"
        fallback_icon_rel = "./icons/BTCUSDT.png"
        selected_icon_rel = requested_icon_rel
        try:
            # Проверим существование файла иконки во временной директории
            if not (tmpdir_path / "icons" / f"{normalized_pair}.png").exists():
                selected_icon_rel = fallback_icon_rel
        except Exception:
            selected_icon_rel = fallback_icon_rel
        # Отформатируем цены с пробелами между тысячами
        entry_price_fmt = _format_price_with_spaces(entry_price)
        exit_price_fmt = _format_price_with_spaces(exit_price)
        profit_amount_fmt = _format_price_with_spaces(profit_amount)

        html_text = (
            html_text.replace("{pair}", pair)
            .replace("{position_type}", position_type)
            .replace("{leverage}", leverage)
            .replace("{profit_percentage}", profit_percentage)
            .replace("{profit_amount}", profit_amount_fmt)
            .replace("{entry_price}", entry_price_fmt)
            .replace("{exit_price}", exit_price_fmt)
            .replace("{share_date}", share_date)
            .replace("{share_time}", share_time)
            .replace("{pair_icon_src}", selected_icon_rel)
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


@trade_share_router.message(AdminOnly(), Command("forex"))
@flags.chat_action(action=ChatAction.UPLOAD_PHOTO)
async def handle_forex_share(message: Message, bot: Bot):
    """Обработка команды /forex (key=value)."""
    text = (message.text or "").strip()
    if not text:
        await message.answer("Неверный формат команды /forex.")
        return

    content = text
    if content.startswith("/forex"):
        parts = content.split(" ", 1)
        content = parts[1].strip() if len(parts) > 1 else ""

    data, invalid_tokens = _parse_key_value_pairs(content)

    required_keys = [
        "pair",
        "side",
        "side_price",
        "ticket",
        "desc",
        "open",
        "close",
        "delta",
        "pct",
        "profit",
        "open_dt",
        "close_dt",
        "sl",
        "swap",
        "tp",
        "fee",
    ]
    missing_keys = [k for k in required_keys if not data.get(k)]

    if invalid_tokens or missing_keys:
        await message.answer(
            "Неверный формат. Пример:\n"
            "<code>/forex pair=EURUSD side=buy side_price=1.06 ticket=54814272772 "
            'desc="Euro vs US Dollar" open=1.16540 close=1.16252 delta=521 pct=0.35 '
            'profit=6108.01 open_dt="2026.01.26 10:12:45" close_dt="2026.01.26 10:35:23" '
            "sl=154.335 swap=2.10 tp=153.536 fee=-5.30</code>"
        )
        return

    side = data["side"].strip().lower()
    if side not in {"buy", "sell"}:
        await message.answer("Поле side должно быть buy или sell.")
        return

    pair = data["pair"].strip().upper()
    template_name = "buy-light.html" if side == "buy" else "sell-light.html"

    project_root = Path(__file__).resolve().parents[1]
    template_dir = project_root / "forex_html"
    template_path = template_dir / template_name

    if not template_path.exists():
        await message.answer("Шаблон не найден.")
        return

    numeric_keys = [
        "side_price",
        "open",
        "close",
        "delta",
        "pct",
        "profit",
        "sl",
        "swap",
        "tp",
        "fee",
    ]
    formatted_values = {
        key: _format_price_with_spaces(data[key]) for key in numeric_keys
    }
    profit_raw = data["profit"].strip()
    profit_class = "red" if "-" in profit_raw else "blue"

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        fonts_src = template_dir / "fonts"
        fonts_dst = tmpdir_path / "fonts"
        if fonts_src.exists():
            shutil.copytree(fonts_src, fonts_dst)

        style_src = template_dir / "style.css"
        style_dst = tmpdir_path / "style.css"
        if style_src.exists():
            shutil.copyfile(style_src, style_dst)

        temp_html = tmpdir_path / template_name
        shutil.copyfile(template_path, temp_html)

        html_text = temp_html.read_text(encoding="utf-8")
        html_text = (
            html_text.replace("{pair}", pair)
            .replace("{side}", side)
            .replace("{side_price}", formatted_values["side_price"])
            .replace("{ticket}", data["ticket"])
            .replace("{desc}", data["desc"])
            .replace("{open}", formatted_values["open"])
            .replace("{close}", formatted_values["close"])
            .replace("{delta}", formatted_values["delta"])
            .replace("{pct}", formatted_values["pct"])
            .replace("{profit}", formatted_values["profit"])
            .replace("{profit_class}", profit_class)
            .replace("{open_dt}", data["open_dt"])
            .replace("{close_dt}", data["close_dt"])
            .replace("{sl}", formatted_values["sl"])
            .replace("{swap}", formatted_values["swap"])
            .replace("{tp}", formatted_values["tp"])
            .replace("{fee}", formatted_values["fee"])
        )
        temp_html.write_text(html_text, encoding="utf-8")

        output_dir = project_root / "temp"
        output_image_path = output_dir / f"forex_{pair}_{side}.png"

        image_path = await html_to_image(
            html_file_path=str(temp_html),
            output_path=str(output_image_path),
            selector="#forex_img",
            width=1142,
            height=564,
            device_scale_factor=2,
            scale="device",
        )

        await message.answer_photo(FSInputFile(image_path))
