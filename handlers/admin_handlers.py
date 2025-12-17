from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from database.requests import update_user_status

admin_router = Router()

@admin_router.callback_query(F.data.startswith("approve_"))
async def approve_user(callback: CallbackQuery):
    user_id = int(callback.data.split("_")[1])
    
    await update_user_status(user_id, True)

    await callback.message.edit_text(f"{callback.message.text}\n\n✅ <b>Схвалено</b>")
    await callback.answer("Користувача схвалено!")
    
    try:
        await callback.bot.send_message(user_id, "✅ Вашу заявку схвалено! Ласкаво просимо.")
    except Exception as e:
        await callback.message.answer(f"Не вдалося надіслати сповіщення користувачу {user_id}: {e}")

@admin_router.callback_query(F.data.startswith("reject_"))
async def reject_user(callback: CallbackQuery):
    user_id = int(callback.data.split("_")[1])
    
    # Optionally: await update_user_status(user_id, False) # Or delete user

    await callback.message.edit_text(f"{callback.message.text}\n\n❌ <b>Відхилено</b>")
    await callback.answer("Користувача відхилено!")
    
    try:
        await callback.bot.send_message(user_id, "❌ Вашу заявку відхилено адміністратором.")
    except Exception as e:
        await callback.message.answer(f"Не вдалося надіслати сповіщення користувачу {user_id}: {e}")
