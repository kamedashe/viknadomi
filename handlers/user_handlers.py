from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardRemove
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from states import Registration
from keyboards import request_phone_kb, admin_approval_kb
from config import ADMIN_IDS
from database.requests import get_user, add_user

user_router = Router()

@user_router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    # Check admin first
    if message.from_user.id in ADMIN_IDS:
        await message.answer("Ласкаво просимо! Ви успішно авторизовані.", reply_markup=ReplyKeyboardRemove())
        return

    user = await get_user(message.from_user.id)

    if user:
        if user.is_approved:
            await message.answer("Ласкаво просимо! Ви успішно авторизовані.", reply_markup=ReplyKeyboardRemove())
        else:
            await message.answer("Ваша заявка знаходиться на розгляді адміністрації.", reply_markup=ReplyKeyboardRemove())
    else:
        await message.answer(
            "Привіт! Для доступу до бота необхідно підтвердження номера телефону.",
            reply_markup=request_phone_kb()
        )
        await state.set_state(Registration.waiting_for_phone)

@user_router.message(F.contact)
async def process_contact(message: Message, state: FSMContext):
    # Check if user already exists to avoid duplicates
    existing_user = await get_user(message.from_user.id)
    if existing_user:
        await state.clear()
        if existing_user.is_approved or message.from_user.id in ADMIN_IDS:
             await message.answer("Ви вже авторизовані.", reply_markup=ReplyKeyboardRemove())
        else:
             await message.answer("Ваша заявка вже на розгляді.", reply_markup=ReplyKeyboardRemove())
        return

    contact = message.contact
    user_id = message.from_user.id
    username = message.from_user.username
    full_name = message.from_user.full_name
    phone_number = contact.phone_number

    # Save to DB as unapproved
    await add_user(user_id, phone_number, username, full_name)

    await state.clear()
    await message.answer("Ваш запит надіслано адміністратору. Очікуйте підтвердження.", reply_markup=ReplyKeyboardRemove())

    # Notify admins
    text = f"📝 <b>Нова заявка на реєстрацію!</b>\n\nID: {user_id}\nUsername: @{username}\nІм'я: {full_name}\nТелефон: {phone_number}"
    
    for admin_id in ADMIN_IDS:
        try:
            await message.bot.send_message(admin_id, text, reply_markup=admin_approval_kb(user_id))
        except Exception as e:
            print(f"Failed to send message to admin {admin_id}: {e}")
