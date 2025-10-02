from aiogram.fsm.state import StatesGroup, State


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


class UserPdfForm(StatesGroup):
    user_name = State()
    pdf_file = State()


