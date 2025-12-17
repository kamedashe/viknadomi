from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

def request_phone_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📱 Поділитися номером телефону", request_contact=True)]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )

def admin_approval_kb(user_id: int):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Підтвердити", callback_data=f"approve_{user_id}"),
                InlineKeyboardButton(text="❌ Відхилити", callback_data=f"reject_{user_id}")
            ]
        ]
    )
