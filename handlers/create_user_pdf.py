import os
import uuid
import logging
from aiogram import Router, Bot
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.filters import Command
from aiogram.filters.state import StateFilter
from aiogram.enums import ChatAction
from aiogram.fsm.context import FSMContext

from states import UserPdfForm
from utils.render_pdf import html_to_pdf_playwright
from filters.admin_only import AdminOnly
from filters.private_only import PrivateOnly
from misc.keyboards import UserPdfKeyboards
from misc.constants import DEFAULT_PDF_PATH
from misc.utils import fill_title_html, merge_pdfs, cleanup_files

# Создаем роутер для создания пользовательского PDF
create_user_pdf_router = Router()

# Создаем экземпляр клавиатур
keyboards = UserPdfKeyboards()


@create_user_pdf_router.message(PrivateOnly(), AdminOnly(), Command("create_user_pdf"))
async def start_create_user_pdf(message: Message, state: FSMContext):
    """Начало создания пользовательского PDF"""
    await state.clear()
    await message.answer(
        "📝 Создание персонального PDF\n\n"
        "Введите имя пользователя, которое будет вставлено в PDF:",
        reply_markup=keyboards.cancel_kb()
    )
    await state.set_state(UserPdfForm.user_name)


@create_user_pdf_router.message(PrivateOnly(), AdminOnly(), StateFilter(UserPdfForm.user_name))
async def process_user_name(message: Message, state: FSMContext):
    """Обработка введенного имени пользователя"""
    user_name = message.text.strip()
    if not user_name:
        await message.answer(
            "Пожалуйста, введите корректное имя:",
            reply_markup=keyboards.cancel_kb()
        )
        return
    
    await state.update_data(user_name=user_name)
    await message.answer(
        f"✅ Имя сохранено: {user_name}\n\n"
        "📁 Теперь загрузите PDF файл или используйте существующий:",
        reply_markup=keyboards.file_choice_kb()
    )
    await state.set_state(UserPdfForm.pdf_file)


@create_user_pdf_router.callback_query(PrivateOnly(), AdminOnly(), StateFilter(UserPdfForm.pdf_file))
async def handle_file_choice(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Обработка выбора файла"""
    data = callback.data
    
    if data == "cancel":
        await callback.message.answer("❌ Создание PDF отменено.")
        await state.clear()
        await callback.answer()
        return
    
    elif data == "use_existing":
        await callback.answer()

        # Используем существующий файл
        if not os.path.exists(DEFAULT_PDF_PATH):
            await callback.message.answer("❌ Существующий PDF файл не найден.")
            await state.clear()
            return
        
        await state.update_data(pdf_path=DEFAULT_PDF_PATH, is_uploaded=False)
        await process_pdf_creation(callback, state, bot)
    


@create_user_pdf_router.message(PrivateOnly(), AdminOnly(), StateFilter(UserPdfForm.pdf_file))
async def handle_uploaded_file(message: Message, state: FSMContext, bot: Bot):
    """Обработка загруженного файла"""
    if not message.document:
        await message.answer(
            "Пожалуйста, загрузите PDF файл или выберите существующий:",
            reply_markup=keyboards.file_choice_kb()
        )
        return
    
    # Проверяем, что это PDF файл
    if not message.document.file_name.lower().endswith('.pdf'):
        await message.answer(
            "❌ Пожалуйста, загрузите PDF файл:",
            reply_markup=keyboards.file_choice_kb()
        )
        return
    
    # Скачиваем файл
    file_id = message.document.file_id
    file = await bot.get_file(file_id)
    
    # Создаем временный файл
    temp_filename = f"temp_uploaded_{uuid.uuid4().hex}.pdf"
    temp_path = f"temp/{temp_filename}"
    
    # Скачиваем файл
    await bot.download_file(file.file_path, temp_path)
    
    await state.update_data(pdf_path=temp_path, is_uploaded=True)
    
    # Обрабатываем создание PDF
    await process_pdf_creation(message, state, bot)


async def process_pdf_creation(message_or_callback, state: FSMContext, bot: Bot):
    """Основная логика создания PDF"""
    data = await state.get_data()
    user_name = data.get("user_name")
    pdf_path = data.get("pdf_path")
    is_uploaded = data.get("is_uploaded", False)
    
    # Получаем объект message и chat_id в зависимости от типа объекта
    if hasattr(message_or_callback, 'message'):  # CallbackQuery
        message = message_or_callback.message
        chat_id = message.chat.id
    else:  # Message
        message = message_or_callback
        chat_id = message.chat.id
    
    if not user_name or not pdf_path:
        await message.answer("❌ Ошибка: не хватает данных для создания PDF.")
        await state.clear()
        return
    
    # Показываем индикатор загрузки
    await bot.send_chat_action(chat_id, ChatAction.TYPING)
    
    try:
        # Создаем титульную страницу
        temp_html_path = fill_title_html(user_name)
        title_pdf_path = f"temp/title_{uuid.uuid4().hex}.pdf"
        
        # Конвертируем HTML в PDF с альбомной ориентацией
        logging.info(f"Начинаю создание титульной страницы: HTML={temp_html_path}, PDF={title_pdf_path}")
        success = await html_to_pdf_playwright(
            html_file_path=temp_html_path,
            output_pdf_path=title_pdf_path,
            landscape=True
        )
        
        if not success:
            logging.error(f"Ошибка при создании титульной страницы: HTML={temp_html_path}, PDF={title_pdf_path}")
            await message.answer("❌ Ошибка при создании титульной страницы.")
            # Очищаем временные файлы
            cleanup_files([temp_html_path])
            await state.clear()
            return
        
        # Объединяем PDF файлы
        final_pdf_path = f"temp/final_{uuid.uuid4().hex}.pdf"
        merge_success = merge_pdfs(title_pdf_path, pdf_path, final_pdf_path)
        
        if not merge_success:
            await message.answer("❌ Ошибка при объединении PDF файлов.")
            # Очищаем временные файлы
            cleanup_files([temp_html_path, title_pdf_path])
            await state.clear()
            return
        
        # Отправляем файл пользователю
        await bot.send_chat_action(chat_id, ChatAction.UPLOAD_DOCUMENT)
        await message.answer_document(
            FSInputFile(final_pdf_path, filename=f"Персональная_программа_{user_name}.pdf")
        )
        
        # Очищаем временные файлы
        files_to_cleanup = [temp_html_path, title_pdf_path, final_pdf_path]
        if is_uploaded:
            files_to_cleanup.append(pdf_path)
        
        cleanup_files(files_to_cleanup)
        
        await message.answer("✅ PDF успешно создан.")
        await state.clear()
        
    except Exception as e:
        logging.error(f"Ошибка при создании PDF: {e}")
        await message.answer("❌ Произошла ошибка при создании PDF. Попробуйте еще раз.")
        await state.clear()


@create_user_pdf_router.callback_query(PrivateOnly(), AdminOnly(), StateFilter(UserPdfForm.user_name))
async def cancel_callback(callback: CallbackQuery, state: FSMContext):
    """Обработчик кнопки отмены"""
    if callback.data == "cancel":
        await callback.message.answer("❌ Создание PDF отменено.")
        await state.clear()
    try:
        await callback.answer()
    except Exception:
        # Игнорируем ошибки callback answer (например, query is too old)
        pass