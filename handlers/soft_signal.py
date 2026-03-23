"""Роутер /soft_signal для форматирования торговых сигналов.

Назначение:
    Принимает многострочное сообщение команды /soft_signal с параметрами сигнала,
    валидирует поля и возвращает красиво отформатированный текст сигнала.

Ожидаемый вход (body после команды):
    PAIR TIMEFRAME

    Short/Long
    Price: <float>
    TP: <float> (или TP1/TP2, если TP не указан)
    SL: <float>

    2026-03-19 15:41:32 (необязательная строка с датой/временем)

Выход:
    Текстовое сообщение с вычисленными метриками: %SL, %TP, RR, плечо.

Формулы:
    % SL = |SL - Price| / Price × 100
    % TP = |TP - Price| / Price × 100
    RR = % TP / % SL (формат 1:X.XX)
    Плечо = floor(40 / %SL), максимум 100
"""

import logging
import math
import re
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.utils.chat_action import ChatActionMiddleware

from filters.admin_only import AdminOnly
from filters.private_only import PrivateOnly


logger = logging.getLogger(__name__)

_TIMEFRAME_PATTERN = re.compile(r"(\d+)([mhd])", re.IGNORECASE)
_DATE_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}")

soft_signal_router = Router()
soft_signal_router.message.middleware(ChatActionMiddleware())


def _format_number(value: float) -> str:
    """Форматирует число с пробелами между тысячами и запятой.
    
    Примеры:
        73330.0 → "73 330"
        69129.8 → "69 129,8"
        70605.5 → "70 605,5"
    """
    if value < 0:
        sign = "-"
        value = abs(value)
    else:
        sign = ""
    
    # Проверяем, есть ли дробная часть
    if value == int(value):
        # Целое число — убираем дробную часть
        formatted_integer = f"{int(value):,}".replace(",", " ")
        return f"{sign}{formatted_integer}"
    else:
        # Есть дробная часть — округляем до 3 знаков и заменяем точку на запятую
        str_value = f"{value:.3f}".rstrip("0").rstrip(".")
        if "." in str_value:
            integer_part, fractional_part = str_value.split(".")
            formatted_integer = f"{int(integer_part):,}".replace(",", " ")
            return f"{sign}{formatted_integer},{fractional_part}"
        else:
            formatted_integer = f"{int(str_value):,}".replace(",", " ")
            return f"{sign}{formatted_integer}"


def _parse_signal_message(text: str) -> dict | None:
    """Парсит входное сообщение сигнала.
    
    Ожидаемый формат:
        BTCUSDT 10m
        
        Short
        Price: 69129.8
        TP: 67741.9
        SL: 70605.5
        
        2026-03-19 15:41:32
    
    Возвращает dict с полями: pair, timeframe, position_type, price, tp, sl
    или None если формат неверный.
    """
    lines = [line.strip() for line in text.strip().split("\n") if line.strip()]
    
    if len(lines) < 5:
        return None
    
    # Первая строка: PAIR и TIMEFRAME
    first_line = lines[0].split()
    if len(first_line) < 2:
        return None
    
    pair = first_line[0].upper()
    timeframe_raw = first_line[1]
    
    # Парсим таймфрейм: 10m → M10, 1h → H1, etc.
    timeframe_match = _TIMEFRAME_PATTERN.fullmatch(timeframe_raw)
    if not timeframe_match:
        return None
    
    tf_value = timeframe_match.group(1)
    tf_unit = timeframe_match.group(2).upper()
    timeframe = f"{tf_unit}{tf_value}"
    
    # Вторая строка: позиция (Short/Long)
    position_raw = lines[1].lower()
    if position_raw not in ("short", "long"):
        return None
    
    position_type = "ШОРТ" if position_raw == "short" else "ЛОНГ"
    
    # Остальные строки: ключ-значение
    data = {"pair": pair, "timeframe": timeframe, "position_type": position_type}
    
    for line in lines[2:]:
        # Пропускаем дату/время в конце
        if _DATE_PATTERN.match(line):
            continue
        
        if ":" not in line:
            continue
        
        key, value = line.split(":", 1)
        key = key.strip().lower()
        value = value.strip()
        
        try:
            value_float = float(value)
            if math.isnan(value_float) or math.isinf(value_float):
                continue
        except ValueError:
            continue
        
        if key == "price":
            data["price"] = value_float
        elif key == "tp":
            data["tp"] = value_float
        elif key.startswith("tp") and "tp" not in data:
            # Фолбэк для TP1/TP2, если TP не указан
            data["tp"] = value_float
        elif key == "sl":
            data["sl"] = value_float
    
    # Проверяем наличие всех обязательных полей
    required = ["pair", "timeframe", "position_type", "price", "tp", "sl"]
    if not all(k in data for k in required):
        return None
    
    return data


def _calculate_metrics(price: float, tp: float, sl: float, position_type: str) -> dict | None:
    """Рассчитывает метрики сделки.
    
    Формулы:
        % SL = |SL - Price| / Price × 100
        % TP = |TP - Price| / Price × 100
        RR = % TP / % SL (формат: 1:X.XX)
        Плечо = 40 / % SL (округление вниз, максимум 100)
    """
    if price <= 0 or tp <= 0 or sl <= 0:
        return None
    if any(math.isnan(v) or math.isinf(v) for v in (price, tp, sl)):
        return None

    if position_type == "ЛОНГ":
        if tp <= price or sl >= price:
            return None
    elif position_type == "ШОРТ":
        if tp >= price or sl <= price:
            return None

    sl_pct = abs(sl - price) / price * 100
    tp_pct = abs(tp - price) / price * 100
    if sl_pct <= 0:
        return None
    
    # RR: отношение тейка к стопу
    rr = tp_pct / sl_pct if sl_pct > 0 else 0
    
    # Плечо: 40 / %SL, округление вниз, максимум 100
    leverage_raw = 40 / sl_pct if sl_pct > 0 else 100
    leverage = min(math.floor(leverage_raw), 100)
    
    return {
        "sl_pct": sl_pct,
        "tp_pct": tp_pct,
        "rr": rr,
        "leverage": leverage,
    }


def _format_signal_message(data: dict, metrics: dict) -> str:
    """Формирует итоговое сообщение сигнала."""
    pair = data["pair"]
    position_type = data["position_type"]
    price = data["price"]
    tp = data["tp"]
    sl = data["sl"]
    timeframe = data["timeframe"]
    
    sl_pct = metrics["sl_pct"]
    tp_pct = metrics["tp_pct"]
    rr = metrics["rr"]
    leverage = metrics["leverage"]
    
    # Определяем знаки для процентов
    # Для лонга: TP выше входа (+), SL ниже входа (−)
    # Для шорта: TP ниже входа (+), SL выше входа (−)
    # Но в примере оба процента положительные, просто с разными знаками
    
    # Формируем строки с процентами
    sl_sign = "−" if sl_pct > 0 else ""
    tp_sign = "+" if tp_pct > 0 else ""
    
    # Форматируем RR как 1:X.XX
    rr_str = f"1:{rr:.2f}".rstrip("0").rstrip(".")
    
    message = (
        f"{position_type} | ${pair}\n"
        f"\n"
        f"Вход: {_format_number(price)}\n"
        f"Стоп: {_format_number(sl)}  ({sl_sign}{sl_pct:.2f}%)\n"
        f"Тейк: {_format_number(tp)}  ({tp_sign}{tp_pct:.2f}%)\n"
        f"\n"
        f"RR: {rr_str}\n"
        f"Плечо: x{leverage}\n"
        f"Таймфрейм: {timeframe}\n"
        f"\n"
        f"🏷 #soft | Ростислав"
    )
    
    return message


@soft_signal_router.message(Command("soft_signal"), PrivateOnly(), AdminOnly())
async def handle_soft_signal(message: Message):
    """Обработка команды /soft_signal.
    
    Формат входного сообщения:
        BTCUSDT 10m
        
        Short
        Price: 69129.8
        TP: 67741.9
        SL: 70605.5
        
        2026-03-19 15:41:32
    """
    try:
        # Получаем текст после команды
        text = message.text or ""

        # Удаляем команду и возможные пробелы/переносы после неё, учитываем @botname
        content = re.sub(
            r"^/soft_signal(?:@\w+)?\s*", "", text, flags=re.IGNORECASE
        ).strip()

        if not content:
            await message.answer(
                "Неверный формат. Пример:\n"
                "<code>/soft_signal BTCUSDT 10m\n\n"
                "Short\n"
                "Price: 69129.8\n"
                "TP: 67741.9\n"
                "SL: 70605.5\n\n"
                "2026-03-19 15:41:32</code>"
            )
            return

        # Парсим входное сообщение
        parsed = _parse_signal_message(content)
        if not parsed:
            await message.answer(
                "Не удалось распарсить сообщение. Проверьте формат:\n"
                "<code>PAIR TIMEFRAME\n\n"
                "Short/Long\n"
                "Price: XXX\n"
                "TP: XXX\n"
                "SL: XXX</code>"
            )
            return

        # Рассчитываем метрики
        metrics = _calculate_metrics(
            parsed["price"], parsed["tp"], parsed["sl"], parsed["position_type"]
        )
        if not metrics:
            await message.answer(
                "Некорректные значения Price/TP/SL. "
                "Проверьте, что все значения больше нуля и соблюдают логику позиции."
            )
            return

        # Формируем итоговое сообщение
        result = _format_signal_message(parsed, metrics)

        # Отправляем результат
        await message.answer(result)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Error in handle_soft_signal: %s", exc)
        await message.answer("⚠️ Произошла ошибка при обработке сигнала")
