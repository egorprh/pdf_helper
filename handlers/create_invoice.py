import os
import re
import uuid
import logging
import datetime
from aiogram import Router, Bot
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.filters import Command
from aiogram.filters.state import StateFilter
from aiogram.enums import ChatAction
from aiogram.fsm.context import FSMContext

from states import Form
from misc import InvoiceKeyboards, format_cost, fill_pdf_html, PDF_HTML_PATH, PRODUCT_MAP, DURATION_MAP
from misc.utils import cleanup_files
from utils.render_pdf import html_to_pdf_playwright
from utils.utils import send_email_with_attachment
from filters.admin_only import AdminOnly, NonAdminOnly

# Создаем роутер для создания инвойсов
create_invoice_router = Router()

# Создаем экземпляр клавиатур
keyboards = InvoiceKeyboards(PRODUCT_MAP, DURATION_MAP)



@create_invoice_router.message(AdminOnly(), Command("create_invoice"))
async def start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Введите почту:", reply_markup=keyboards.cancel_kb())
    await state.set_state(Form.email)


@create_invoice_router.message(AdminOnly(), StateFilter(Form.email))
async def email(message: Message, state: FSMContext):
    if not re.match(r"[^@]+@[^@]+\.[^@]+", message.text):
        await message.answer("Неверная почта, попробуйте снова.", reply_markup=keyboards.cancel_kb())
        return
    await state.update_data(email=message.text)
    await message.answer(
        "Выберите продукт кнопкой ниже или введите название вручную:",
        reply_markup=keyboards.product_kb()
    )
    await state.set_state(Form.product)


@create_invoice_router.callback_query(AdminOnly(), StateFilter(Form.product, Form.duration, Form.confirm))
async def callbacks(callback: CallbackQuery, state: FSMContext, bot: Bot):
    data = callback.data
    if data == "cancel":
        await callback.message.answer("❌ Создание инвойса отменено.")
        await state.clear()
        await callback.answer()
        return
    elif data.startswith("product:"):
        product_code = data.split(":")[1]
        await state.update_data(product=product_code, product_title=PRODUCT_MAP.get(product_code, product_code))
        await callback.message.answer(
            "Выберите продолжительность кнопкой ниже или введите вручную (например: 1 месяц):",
            reply_markup=keyboards.duration_kb()
        )
        await state.set_state(Form.duration)
    elif data.startswith("duration:"):
        duration_code = data.split(":")[1]
        await state.update_data(duration=duration_code, duration_title=DURATION_MAP.get(duration_code, duration_code))
        await callback.message.answer("Введите имя:", reply_markup=keyboards.cancel_kb())
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
            temp_html_path = fill_pdf_html(d, submission_id, PDF_HTML_PATH)
            
            # Создаем путь для PDF файла с правильным именем в той же временной директории
            temp_pdf_path = os.path.join(os.path.dirname(temp_html_path), f"invoice_{padded_order_number}.pdf")
            
            # Конвертируем HTML в PDF
            logging.info(f"Начинаю генерацию PDF: HTML={temp_html_path}, PDF={temp_pdf_path}")
            # CSS файл уже скопирован в временную директорию вместе с HTML
            css_file_path = os.path.join(os.path.dirname(temp_html_path), "styles.css")
            success = await html_to_pdf_playwright(
                html_file_path=temp_html_path,
                output_pdf_path=temp_pdf_path,
                css_file_path=css_file_path
            )
            
            if success:
                logging.info(f"PDF успешно создан: {temp_pdf_path}")
                # Отправляем PDF файл
                await callback.message.answer_document(FSInputFile(temp_pdf_path))

                # Сохраним пути во временное состояние для следующего шага
                await state.update_data(temp_html_path=temp_html_path, temp_pdf_path=temp_pdf_path)

                # Предложим отправить файл на почту
                email = d.get("email", "")
                await callback.message.answer(
                    f"Отправляем данный инвойс на указанную почту {email}?",
                    reply_markup=keyboards.email_confirm_kb()
                )
                await state.set_state(Form.send_email_confirm)
            else:
                logging.error(f"Ошибка при генерации PDF: HTML={temp_html_path}, PDF={temp_pdf_path}")
                await callback.message.answer("Ошибка при генерации PDF. Попробуйте еще раз.")
                # Очищаем всю папку temp
                cleanup_files(["temp"])
            
            # Не очищаем состояние при успехе до ответа пользователя
    try:
        await callback.answer()
    except Exception:
        # Игнорируем ошибки callback answer (например, query is too old)
        pass


@create_invoice_router.callback_query(AdminOnly(), StateFilter(Form.send_email_confirm))
async def send_email_callbacks(callback: CallbackQuery, state: FSMContext, bot: Bot):
    data = callback.data
    if not data.startswith("sendmail:"):
        await callback.answer()
        return

    st = await state.get_data()
    temp_html_path = st.get("temp_html_path")
    temp_pdf_path = st.get("temp_pdf_path")
    email = st.get("email", "")

    if data.endswith("no"):
        # Очищаем всю папку temp
        cleanup_files(["temp"])
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

    # Очищаем всю папку temp
    cleanup_files(["temp"])

    await state.clear()
    try:
        await callback.answer()
    except Exception:
        # Игнорируем ошибки callback answer (например, query is too old)
        pass


@create_invoice_router.callback_query(AdminOnly(), StateFilter(Form.email, Form.name, Form.phone, Form.order_number, Form.purchase_date, Form.cost))
async def cancel_callback(callback: CallbackQuery, state: FSMContext):
    """Обработчик кнопки отмены для всех состояний ввода данных"""
    if callback.data == "cancel":
        await callback.message.answer("❌ Создание инвойса отменено.")
        await state.clear()
    await callback.answer()


@create_invoice_router.message(AdminOnly(), StateFilter(Form.product))
async def product_text_input(message: Message, state: FSMContext):
    title = (message.text or "").strip()
    if not title:
        await message.answer("Пожалуйста, введите название продукта или выберите кнопку ниже.", reply_markup=keyboards.product_kb())
        return
    await state.update_data(product="custom", product_title=title)
    await message.answer(
        "Выберите продолжительность кнопкой ниже или введите вручную (например: 6 месяцев):",
        reply_markup=keyboards.duration_kb()
    )
    await state.set_state(Form.duration)


@create_invoice_router.message(AdminOnly(), StateFilter(Form.duration))
async def duration_text_input(message: Message, state: FSMContext):
    title = (message.text or "").strip()
    if not title:
        await message.answer("Пожалуйста, введите продолжительность или выберите кнопку ниже.", reply_markup=keyboards.duration_kb())
        return
    await state.update_data(duration="custom", duration_title=title)
    await message.answer("Введите имя:", reply_markup=keyboards.cancel_kb())
    await state.set_state(Form.name)


@create_invoice_router.message(AdminOnly(), StateFilter(Form.name))
async def name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Введите телефон:", reply_markup=keyboards.cancel_kb())
    await state.set_state(Form.phone)


@create_invoice_router.message(AdminOnly(), StateFilter(Form.phone))
async def phone(message: Message, state: FSMContext):
    await state.update_data(phone=message.text)
    await message.answer("Введите номер заказа:", reply_markup=keyboards.cancel_kb())
    await state.set_state(Form.order_number)


@create_invoice_router.message(AdminOnly(), StateFilter(Form.order_number))
async def order(message: Message, state: FSMContext):
    await state.update_data(order_number=message.text)
    await message.answer("Введите дату покупки (ДД/ММ/ГГГГ):", reply_markup=keyboards.cancel_kb())
    await state.set_state(Form.purchase_date)


@create_invoice_router.message(AdminOnly(), StateFilter(Form.purchase_date))
async def date(message: Message, state: FSMContext):
    # Валидация формата даты ДД/ММ/ГГГГ
    date_pattern = r'^\d{2}/\d{2}/\d{4}$'
    if not re.match(date_pattern, message.text):
        await message.answer("Неверный формат даты. Введите дату в формате ДД/ММ/ГГГГ (например: 25/12/2023):", reply_markup=keyboards.cancel_kb())
        return
    
    # Дополнительная проверка корректности даты
    try:
        day, month, year = message.text.split('/')
        datetime.datetime(int(year), int(month), int(day))
    except ValueError:
        await message.answer("Неверная дата. Проверьте правильность введенной даты:", reply_markup=keyboards.cancel_kb())
        return
    
    await state.update_data(purchase_date=message.text)
    await message.answer("Введите стоимость:", reply_markup=keyboards.cancel_kb())
    await state.set_state(Form.cost)


@create_invoice_router.message(AdminOnly(), StateFilter(Form.cost))
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
        reply_markup=keyboards.confirm_kb()
    )
    await state.set_state(Form.confirm)
