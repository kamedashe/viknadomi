from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from states import Registration
from keyboards import request_phone_kb, admin_approval_kb, MenuCallback
from config import ADMIN_IDS
from database.requests import get_user, add_user

user_router = Router()

@user_router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    user_id = message.from_user.id
    print(f"DEBUG: /start from {user_id}")
    
    # Check if admin
    if user_id in ADMIN_IDS:
        await message.answer(
            "Ласкаво просимо! Ви успішно авторизовані (Адмін).", 
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="📂 Відкрити меню", callback_data=MenuCallback(path="").pack())]])
        )
        return

    user = await get_user(user_id)
    if user:
        if user.is_approved:
            await message.answer(
                "Ласкаво просимо! Ви успішно авторизовані.", 
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="📂 Відкрити меню", callback_data=MenuCallback(path="").pack())]])
            )
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
    user_id = message.from_user.id
    contact = message.contact
    
    print(f"DEBUG [Contact]: From {user_id}, Contact ID: {contact.user_id}")
    
    # Security check: ensure the contact shared belongs to the sender (if user_id is provided)
    if contact.user_id is not None and contact.user_id != user_id:
        print(f"DEBUG [Contact]: Security rejection - ID mismatch")
        await message.answer(
            "⚠️ Будь ласка, надішліть саме **ВЛАСНИЙ** контакт через кнопку нижче 👇",
            reply_markup=request_phone_kb()
        )
        return

    # Check if user already exists
    existing_user = await get_user(user_id)
    if existing_user and existing_user.is_approved:
        print(f"DEBUG [Contact]: User {user_id} already approved")
        await state.clear()
        await message.answer("Ви вже авторизовані.", reply_markup=ReplyKeyboardRemove())
        return

    username = message.from_user.username
    full_name = message.from_user.full_name
    phone_number = contact.phone_number

    # Save to DB (or update if exists but not approved)
    await add_user(user_id, phone_number, username, full_name)
    print(f"DEBUG [Contact]: User {user_id} added/updated in DB")

    await state.clear()
    await message.answer("Ваш запит надіслано адміністратору. Очікуйте підтвердження.", reply_markup=ReplyKeyboardRemove())

    # Notify admins
    text = f"📝 <b>Нова заявка на реєстрацію!</b>\n\nID: {user_id}\nUsername: @{username}\nІм'я: {full_name}\nТелефон: {phone_number}"
    
    print(f"DEBUG [Contact]: Notifying admins: {ADMIN_IDS}")
    for admin_id in ADMIN_IDS:
        try:
            await message.bot.send_message(admin_id, text, reply_markup=admin_approval_kb(user_id))
            print(f"DEBUG [Contact]: Notification sent to admin {admin_id}")
        except Exception as e:
            print(f"DEBUG ERROR [Contact]: Failed to notify admin {admin_id}: {e}")

@user_router.message(Registration.waiting_for_phone, F.text.regexp(r'\+?\d{10,15}'))
async def text_phone_handler(message: Message):
    await message.answer(
        "На жаль, я не можу прийняти номер текстом. ⛔️\n\nБудь ласка, натисніть на кнопку **'📱 Поділитися номером телефону'** нижче для безпечної реєстрації 👇",
        reply_markup=request_phone_kb()
    )

@user_router.message(Registration.waiting_for_phone)
async def waiting_for_phone_msg(message: Message):
    await message.answer(
        "Для доступу до функцій бота необхідно поділитися номером телефону. 👇",
        reply_markup=request_phone_kb()
    )

@user_router.message(~F.text.startswith("/"))
async def handle_all_messages(message: Message):
    # CRITICAL: If this is a contact message, ignore it here to let process_contact handle it
    if message.contact:
        return
        
    user_id = message.from_user.id
    user = await get_user(user_id)
    
    is_admin = user_id in ADMIN_IDS
    is_approved = user and user.is_approved
    
    print(f"DEBUG [Msg]: From {user_id}, Admin: {is_admin}, Approved: {is_approved}")

    # File ID helper for admins
    if message.photo and is_admin:
        file_id = message.photo[-1].file_id
        await message.answer(f"<code>{file_id}</code>", parse_mode='HTML')
        return

    # Forward messages from approved users to admins
    if is_approved and not is_admin:
        sender_info = f"📩 Від: {message.from_user.full_name} (@{message.from_user.username}) [ID:{user_id}]"
        
        for admin_id in ADMIN_IDS:
            try:
                await message.bot.send_message(admin_id, sender_info)
                await message.copy_to(admin_id)
            except Exception as e:
                print(f"DEBUG ERROR [Forward]: Admin {admin_id}: {e}")
