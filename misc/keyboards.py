from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


class InvoiceKeyboards:
    """Класс для создания инлайн клавиатур для создания инвойсов"""
    
    def __init__(self, product_map: dict, duration_map: dict):
        self.product_map = product_map
        self.duration_map = duration_map
    
    def product_kb(self):
        """Клавиатура выбора продукта"""
        builder = InlineKeyboardBuilder()
        for code, title in self.product_map.items():
            builder.row(InlineKeyboardButton(text=title, callback_data=f"product:{code}"))
        builder.row(InlineKeyboardButton(text="❌ Отменить", callback_data="cancel"))
        return builder.as_markup()
    
    def duration_kb(self):
        """Клавиатура выбора продолжительности"""
        builder = InlineKeyboardBuilder()
        for code, title in self.duration_map.items():
            builder.row(InlineKeyboardButton(text=title, callback_data=f"duration:{code}"))
        builder.row(InlineKeyboardButton(text="❌ Отменить", callback_data="cancel"))
        return builder.as_markup()
    
    def confirm_kb(self):
        """Клавиатура подтверждения данных"""
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="Создать PDF", callback_data="confirm:yes"))
        builder.row(InlineKeyboardButton(text="Отменить", callback_data="confirm:no"))
        return builder.as_markup()
    
    def email_confirm_kb(self):
        """Клавиатура подтверждения отправки на email"""
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(text="Да", callback_data="sendmail:yes"),
            InlineKeyboardButton(text="Нет", callback_data="sendmail:no")
        )
        return builder.as_markup()
    
    def cancel_kb(self):
        """Клавиатура с кнопкой отмены"""
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="❌ Отменить", callback_data="cancel"))
        return builder.as_markup()


class UserPdfKeyboards:
    """Класс для создания инлайн клавиатур для создания пользовательского PDF"""
    
    def file_choice_kb(self):
        """Клавиатура для выбора файла"""
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="📄 Использовать существующий", callback_data="use_existing"))
        builder.row(InlineKeyboardButton(text="❌ Отменить", callback_data="cancel"))
        return builder.as_markup()
    
    def cancel_kb(self):
        """Клавиатура с кнопкой отмены"""
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="❌ Отменить", callback_data="cancel"))
        return builder.as_markup()
