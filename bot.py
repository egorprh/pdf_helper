import os
import re
import uuid
import logging
import datetime
import html as html_lib
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, FSInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters import Command
from aiogram.filters.state import StateFilter
from aiogram.enums import ParseMode, ChatAction
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.storage.memory import MemoryStorage

import asyncio
from utils.render_pdf import html_to_pdf_playwright
from utils.utils import send_email_with_attachment
from filters.admin_only import AdminOnly, NonAdminOnly


logging.basicConfig(level=logging.INFO)
load_dotenv()

PDF_HTML_PATH = "html/pdf.html"

# Единая карта кодов продуктов к человеческим названиям
PRODUCT_MAP = {
    "product_a": "Торговая группа Dept Space",
    "product_b": "Обучение Dept Space",
    "product_c": "Soft Screener",
}

# Единая карта кодов длительности к названиям
DURATION_MAP = {
    "1m": "1 месяц",
    "3m": "3 месяца",
    "12m": "12 месяцев",
}

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TELEGRAM_TOKEN:
    raise SystemExit("TELEGRAM_BOT_TOKEN не найден в .env")

bot = Bot(token=TELEGRAM_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
storage = MemoryStorage()
dp = Dispatcher(storage=storage)


class Form(StatesGroup):
    email = State()
    product = State()
    duration = State()
    name = State()
    phone = State()
    order_number = State()
    purchase_date = State()
    cost = State()
    confirm = State()
    send_email_confirm = State()

 
def product_kb():
    builder = InlineKeyboardBuilder()
    for code, title in PRODUCT_MAP.items():
        builder.row(InlineKeyboardButton(text=title, callback_data=f"product:{code}"))
    return builder.as_markup()

def duration_kb():
    builder = InlineKeyboardBuilder()
    for code, title in DURATION_MAP.items():
        builder.row(InlineKeyboardButton(text=title, callback_data=f"duration:{code}"))
    return builder.as_markup()

def confirm_kb():
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="Подтвердить", callback_data="confirm:yes"))
    builder.row(InlineKeyboardButton(text="Отменить", callback_data="confirm:no"))
    return builder.as_markup()

def email_confirm_kb():
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="Да", callback_data="sendmail:yes"),
        InlineKeyboardButton(text="Нет", callback_data="sendmail:no")
    )
    return builder.as_markup()


def format_cost(cost_str: str) -> str:
    """Форматирует стоимость, добавляя пробелы после тысяч."""
    try:
        # Убираем все нецифровые символы кроме точки и запятой
        clean_cost = re.sub(r'[^\d.,]', '', cost_str)
        # Заменяем запятую на точку для float
        clean_cost = clean_cost.replace(',', '.')
        cost_value = float(clean_cost)
        # Форматируем с пробелами после тысяч
        formatted = f"{cost_value:,.0f}".replace(',', ' ')
        return formatted
    except (ValueError, TypeError):
        return cost_str

def fill_pdf_html(data: dict, submission_id: str) -> str:
    """Создает временный HTML файл с подстановками и возвращает путь к нему."""
    with open(PDF_HTML_PATH, "r", encoding="utf-8") as f:
        html_text = f.read()

    # Используем общую карту длительностей

    # Обрабатываем order_number: добавляем нули в начало если меньше 6 символов
    order_number = data.get("order_number", "")
    padded_order_number = order_number.zfill(6) if len(order_number) < 6 else order_number
    
    # Создаем short_number без ведущих нулей
    short_number = order_number.lstrip('0') or '0'
    
    # Форматируем стоимость
    formatted_cost = format_cost(data.get('cost', ''))

    # Заменяем шаблоны {{key}} на значения
    replacements = {
        "{{customer_name}}": html_lib.escape(data.get("name", "")),
        "{{order_number}}": html_lib.escape(padded_order_number),
        "{{short_number}}": html_lib.escape(short_number),
        "{{phone}}": html_lib.escape(data.get("phone", "")),
        "{{purchase_date}}": html_lib.escape(data.get("purchase_date", "")),
        "{{product_name}}": html_lib.escape(data.get("product_title") or PRODUCT_MAP.get(data.get("product", ""), "")),
        "{{tariff}}": html_lib.escape(data.get("duration_title") or DURATION_MAP.get(data.get("duration", ""), "")),
        "{{number}}": html_lib.escape("#" + padded_order_number),
        "{{price}}": html_lib.escape(f"{formatted_cost} ₽"),
        "{{generation_time}}": html_lib.escape(datetime.datetime.now().strftime("%d/%m/%Y | %H:%M"))
    }

    for placeholder, value in replacements.items():
        html_text = html_text.replace(placeholder, value)
    
    # Создаем временный HTML файл внутри html/ чтобы относительные пути к ресурсам оставались валидными
    temp_html_path = f"html/temp_invoice_{submission_id}.html"
    with open(temp_html_path, "w", encoding="utf-8") as f:
        f.write(html_text)
    
    return temp_html_path


@dp.message(AdminOnly(), Command("create_invoice"))
async def start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Введите почту:")
    await state.set_state(Form.email)

@dp.message(AdminOnly(), StateFilter(Form.email))
async def email(message: Message, state: FSMContext):
    if not re.match(r"[^@]+@[^@]+\.[^@]+", message.text):
        await message.answer("Неверная почта, попробуйте снова.")
        return
    await state.update_data(email=message.text)
    await message.answer(
        "Выберите продукт кнопкой ниже или введите название вручную:",
        reply_markup=product_kb()
    )
    await state.set_state(Form.product)

@dp.callback_query(AdminOnly(), StateFilter(Form.product, Form.duration, Form.confirm))
async def callbacks(callback: CallbackQuery, state: FSMContext):
    data = callback.data
    if data.startswith("product:"):
        product_code = data.split(":")[1]
        await state.update_data(product=product_code, product_title=PRODUCT_MAP.get(product_code, product_code))
        await callback.message.answer(
            "Выберите продолжительность кнопкой ниже или введите вручную (например: 1 месяц):",
            reply_markup=duration_kb()
        )
        await state.set_state(Form.duration)
    elif data.startswith("duration:"):
        duration_code = data.split(":")[1]
        await state.update_data(duration=duration_code, duration_title=DURATION_MAP.get(duration_code, duration_code))
        await callback.message.answer("Введите имя:")
        await state.set_state(Form.name)
    elif data.startswith("confirm:"):
        if data.endswith("no"):
            await callback.message.answer("Отменено.")
            await state.clear()
        else:
            d = await state.get_data()
            submission_id = uuid.uuid4().hex
            
            # Обрабатываем order_number для имени файла
            order_number = d.get("order_number", "")
            padded_order_number = order_number.zfill(6) if len(order_number) < 6 else order_number
            
            # Показываем chat action "отправка файла"
            await bot.send_chat_action(callback.message.chat.id, ChatAction.UPLOAD_DOCUMENT)
            
            # Создаем временный HTML файл с подстановками
            temp_html_path = fill_pdf_html(d, submission_id)
            
            # Создаем путь для PDF файла с правильным именем
            temp_pdf_path = f"invoice_{padded_order_number}.pdf"
            
            # Конвертируем HTML в PDF
            success = await html_to_pdf_playwright(
                html_file_path=temp_html_path,
                output_pdf_path=temp_pdf_path,
                css_file_path="html/styles.css"
            )
            
            if success:
                # Отправляем PDF файл
                await callback.message.answer_document(FSInputFile(temp_pdf_path))

                # Сохраним пути во временное состояние для следующего шага
                await state.update_data(temp_html_path=temp_html_path, temp_pdf_path=temp_pdf_path)

                # Предложим отправить файл на почту
                email = d.get("email", "")
                await callback.message.answer(
                    f"Отправляем данный инвойс на указанную почту {email}?",
                    reply_markup=email_confirm_kb()
                )
                await state.set_state(Form.send_email_confirm)
            else:
                await callback.message.answer("Ошибка при генерации PDF. Попробуйте еще раз.")
                # Удаляем временный HTML файл в случае ошибки
                try:
                    os.remove(temp_html_path)
                except OSError:
                    pass
            
            # Не очищаем состояние при успехе до ответа пользователя
    await callback.answer()

@dp.callback_query(AdminOnly(), StateFilter(Form.send_email_confirm))
async def send_email_callbacks(callback: CallbackQuery, state: FSMContext):
    data = callback.data
    if not data.startswith("sendmail:"):
        await callback.answer()
        return

    st = await state.get_data()
    temp_html_path = st.get("temp_html_path")
    temp_pdf_path = st.get("temp_pdf_path")
    email = st.get("email", "")

    if data.endswith("no"):
        # Очистка временных файлов
        try:
            if temp_html_path and os.path.exists(temp_html_path):
                os.remove(temp_html_path)
            if temp_pdf_path and os.path.exists(temp_pdf_path):
                os.remove(temp_pdf_path)
        except OSError as e:
            logging.warning(f"Не удалось удалить временные файлы: {e}")
        await callback.message.answer("Отправка на email отменена.")
        await state.clear()
        await callback.answer()
        return

    # data.endswith("yes")
    if not temp_pdf_path or not os.path.exists(temp_pdf_path):
        await callback.message.answer("Файл для отправки не найден. Попробуйте сгенерировать инвойс заново.")
        await state.clear()
        await callback.answer()
        return

    await bot.send_chat_action(callback.message.chat.id, ChatAction.TYPING)

    ok = send_email_with_attachment(
        file_path=temp_pdf_path,
        body_text="Здравствуйте! Во вложении ваш счёт.",
        recipient_email=email,
    )
    if ok:
        await callback.message.answer("Письмо отправлено на указанную почту.")
    else:
        await callback.message.answer("Не удалось отправить письмо. Проверьте настройки почты и попробуйте снова.")

    # Очистка временных файлов
    try:
        if temp_html_path and os.path.exists(temp_html_path):
            os.remove(temp_html_path)
        if temp_pdf_path and os.path.exists(temp_pdf_path):
            os.remove(temp_pdf_path)
    except OSError as e:
        logging.warning(f"Не удалось удалить временные файлы: {e}")

    await state.clear()
    await callback.answer()

@dp.message(AdminOnly(), StateFilter(Form.product))
async def product_text_input(message: Message, state: FSMContext):
    title = (message.text or "").strip()
    if not title:
        await message.answer("Пожалуйста, введите название продукта или выберите кнопку ниже.")
        return
    await state.update_data(product="custom", product_title=title)
    await message.answer(
        "Выберите продолжительность кнопкой ниже или введите вручную (например: 6 месяцев):",
        reply_markup=duration_kb()
    )
    await state.set_state(Form.duration)

@dp.message(AdminOnly(), StateFilter(Form.duration))
async def duration_text_input(message: Message, state: FSMContext):
    title = (message.text or "").strip()
    if not title:
        await message.answer("Пожалуйста, введите продолжительность или выберите кнопку ниже.")
        return
    await state.update_data(duration="custom", duration_title=title)
    await message.answer("Введите имя:")
    await state.set_state(Form.name)

@dp.message(AdminOnly(), StateFilter(Form.name))
async def name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Введите телефон:")
    await state.set_state(Form.phone)

@dp.message(AdminOnly(), StateFilter(Form.phone))
async def phone(message: Message, state: FSMContext):
    await state.update_data(phone=message.text)
    await message.answer("Введите номер заказа:")
    await state.set_state(Form.order_number)

@dp.message(AdminOnly(), StateFilter(Form.order_number))
async def order(message: Message, state: FSMContext):
    await state.update_data(order_number=message.text)
    await message.answer("Введите дату покупки (ДД/ММ/ГГГГ):")
    await state.set_state(Form.purchase_date)

@dp.message(AdminOnly(), StateFilter(Form.purchase_date))
async def date(message: Message, state: FSMContext):
    # Валидация формата даты ДД/ММ/ГГГГ
    date_pattern = r'^\d{2}/\d{2}/\d{4}$'
    if not re.match(date_pattern, message.text):
        await message.answer("Неверный формат даты. Введите дату в формате ДД/ММ/ГГГГ (например: 25/12/2023):")
        return
    
    # Дополнительная проверка корректности даты
    try:
        day, month, year = message.text.split('/')
        datetime.datetime(int(year), int(month), int(day))
    except ValueError:
        await message.answer("Неверная дата. Проверьте правильность введенной даты:")
        return
    
    await state.update_data(purchase_date=message.text)
    await message.answer("Введите стоимость:")
    await state.set_state(Form.cost)

@dp.message(AdminOnly(), StateFilter(Form.cost))
async def cost(message: Message, state: FSMContext):
    await state.update_data(cost=message.text)
    data = await state.get_data()
    # Читаемые названия продукта и длительности
    product_title = data.get('product_title') or PRODUCT_MAP.get(data.get('product', ''), data.get('product', ''))
    duration_title = data.get('duration_title') or DURATION_MAP.get(data.get('duration', ''), data.get('duration', ''))
    await message.answer(
        f"Подтвердите данные:\n"
        f"Email: {data.get('email')}\n"
        f"Продукт: {product_title}\n"
        f"Продолжительность: {duration_title}\n"
        f"Имя: {data.get('name')}\n"
        f"Телефон: {data.get('phone')}\n"
        f"Заказ: {data.get('order_number')}\n"
        f"Дата: {data.get('purchase_date')}\n"
        f"Сумма: {data.get('cost')} руб.",
        reply_markup=confirm_kb()
    )
    await state.set_state(Form.confirm)


if __name__ == "__main__":
    async def main():
        # Catch-all для админов: подсказка по использованию
        @dp.message(AdminOnly())
        async def admin_hint(message: Message):
            await message.answer("Воспользуйтесь командами /create_invoice")

        # Catch-all для не-админов: отказ в доступе
        @dp.message(NonAdminOnly())
        async def not_allowed_message(message: Message):
            await message.answer("Вы не можете пользоваться этим ботом. Обратитесь к разработчику для предоставления доступа.")

        @dp.callback_query(NonAdminOnly())
        async def not_allowed_callback(callback: CallbackQuery):
            await callback.message.answer("Вы не можете пользоваться этим ботом. Обратитесь к разработчику для предоставления доступа.")
            await callback.answer()
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    asyncio.run(main())
