import re
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from database.requests import update_user_status, get_user, add_media, delete_media_by_category, get_all_users, get_media_by_id, delete_media_by_id
from states import AdminStates
from config import ADMIN_IDS
from handlers.menu_handlers import open_menu, show_gallery
from keyboards import build_user_management_keyboard

admin_router = Router()

@admin_router.message(Command("admin"), F.from_user.id.in_(ADMIN_IDS))
async def admin_command_handler(message: Message, state: FSMContext):

    await state.set_state(AdminStates.browsing)
    
    admin_kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text='📢 Створити розсилку')],
            [KeyboardButton(text='👥 Користувачі')],
            [KeyboardButton(text='🏠 Головне меню')]
        ],
        resize_keyboard=True
    )
    
    await message.answer(
        '🔧 Режим Адміністратора увімкнено.\nНавігуйте по меню, щоб обрати категорію для редагування.',
        reply_markup=admin_kb
    )
    await open_menu(message)

# Handle Admin Actions (Callbacks starting with admin_)
@admin_router.callback_query(F.data.startswith("admin_"))
async def admin_actions_handler(callback: CallbackQuery, state: FSMContext):
    data = callback.data.split("|")
    action = data[0]
    category_code = data[1] if len(data) > 1 else None

    if action == "admin_add":
        await state.update_data(category=category_code)
        await state.set_state(AdminStates.waiting_for_media)
        
        prompt = "📄 Надсилайте файли (PDF), фото або відео" if "PDF" in (category_code or "") else "📸 Надсилайте фото або відео"
        await callback.message.answer(f"{prompt} для категорії: <b>{category_code}</b>")
    
    elif action == "admin_clear":
        await delete_media_by_category(category_code)
        await callback.answer(f"🗑 Категорію {category_code} очищено!", show_alert=True)
    
    elif action == "admin_view":
        # Check if it's a document category to decide which view to show
        doc_keywords = ["PDF", "CATALOG", "DRAWINGS", "SHEETS", "CHECKLIST", "PRICE", "CERT"]
        if any(keyword in category_code for keyword in doc_keywords):
            from handlers.menu_handlers import send_file
            await send_file(callback.message, category_code, user_id=callback.from_user.id)
        else:
            await show_gallery(callback.message, category_code, parent_path="", page=0, is_edit=False)
        await callback.answer()
    
    elif action == "admin_exit":
        await state.clear()
        await callback.message.answer("👋 Режим Адміністратора вимкнено.")
        await callback.answer()

# Handler for single media deletion
@admin_router.callback_query(F.data.startswith("delete_media_"))
async def delete_single_media_handler(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Недостатньо прав!", show_alert=True)
        return
    
    # Extract media ID from callback data
    media_id = int(callback.data.split("_")[2])
    
    # Get the media to know its category for refreshing
    media = await get_media_by_id(media_id)
    if not media:
        await callback.answer("Медіа не знайдено!", show_alert=True)
        return
    
    category_code = media.category_code
    
    # Delete the media
    await delete_media_by_id(media_id)
    await callback.answer("🗑 Видалено!", show_alert=True)
    
    # Refresh gallery - get remaining media count
    from database.requests import get_media_by_category
    remaining_media = await get_media_by_category(category_code)
    
    if not remaining_media:
        # No more media, go back to menu
        await callback.message.delete()
        await callback.message.answer("Галерея порожня. Повернення до меню.")
    else:
        # Refresh the gallery at page 0
        await show_gallery(
            message=callback.message,
            action=category_code,
            parent_path="",
            page=0,
            is_edit=True,
            user_id=callback.from_user.id
        )

@admin_router.callback_query(F.data.startswith("delete_file_"), F.from_user.id.in_(ADMIN_IDS))
async def delete_file_handler(callback: CallbackQuery):
    # Extract media ID from callback data
    media_id = int(callback.data.split("_")[2])
    
    # Delete the media entry from DB
    await delete_media_by_id(media_id)
    
    # Delete the message in Telegram
    try:
        await callback.message.delete()
    except Exception as e:
        print(f"Error deleting file message: {e}")
        
    await callback.answer("🗑 Файл видалено!")

# Handle Media Upload
@admin_router.message(AdminStates.waiting_for_media, F.photo | F.video | F.document)
async def media_upload_handler(message: Message, state: FSMContext):
    data = await state.get_data()
    category = data.get("category")
    
    if not category:
        await message.answer("Помилка: категорію не знайдено. Спробуйте ще раз через меню.")
        return

    file_id = None
    file_type = None

    if message.photo:
        file_id = message.photo[-1].file_id
        file_type = "photo"
    elif message.video:
        file_id = message.video.file_id
        file_type = "video"
    elif message.document:
        # Check if it's a PDF or something we support as 'document' action
        file_id = message.document.file_id
        file_type = "document"

    if file_id:
        await add_media(
            category_code=category,
            file_id=file_id,
            file_type=file_type,
            caption=message.caption
        )
        await message.reply('✅ Збережено! (Надішліть ще або натисніть /menu)')

@admin_router.callback_query(F.data.startswith("approve_"))
async def approve_user(callback: CallbackQuery):
    user_id = int(callback.data.split("_")[1])
    
    # Check current status
    user = await get_user(user_id)
    
    if not user:
        await callback.message.edit_text(f"{callback.message.text}\n\n⚠️ <b>Користувач не знайдений</b>")
        await callback.answer("Користувача не знайдено в базі!", show_alert=True)
        return

    if user.is_approved:
        await callback.message.edit_text(f"{callback.message.text}\n\n⚠️ <b>Вже схвалено іншим адміном</b>")
        await callback.answer("⚠️ Користувач вже схвалений іншим адміном!", show_alert=True)
        return
    
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
    
    # Check status
    user = await get_user(user_id)

    if not user:
        await callback.message.edit_text(f"{callback.message.text}\n\n⚠️ <b>Користувач не знайдений</b>")
        await callback.answer("Користувача не знайдено!", show_alert=True)
        return

    if user.is_approved:
        await callback.message.edit_text(f"{callback.message.text}\n\n⚠️ <b>Вже схвалено іншим адміном</b>")
        await callback.answer("⚠️ Користувач вже схвалений іншим адміном! Неможливо відхилити.", show_alert=True)
        return
    
    # Optionally: await update_user_status(user_id, False) # Or delete user

    await callback.message.edit_text(f"{callback.message.text}\n\n❌ <b>Відхилено</b>")
    await callback.answer("Користувача відхилено!")
    
    try:
        await callback.bot.send_message(user_id, "❌ Вашу заявку відхилено адміністратором.")
    except Exception as e:
        await callback.message.answer(f"Не вдалося надіслати сповіщення користувачу {user_id}: {e}")

# Broadcasting Handlers
@admin_router.message(F.text == '🏠 Головне меню')
async def back_to_main_menu(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Ви повернулися до звичайного режиму.", reply_markup=ReplyKeyboardRemove())
    await open_menu(message)

@admin_router.message(F.text == '📢 Створити розсилку', F.from_user.id.in_(ADMIN_IDS))
async def start_broadcasting(message: Message, state: FSMContext):
    
    await state.set_state(AdminStates.broadcasting)
    await message.answer(
        'Надішліть повідомлення (текст, фото або відео), яке отримають всі користувачі.',
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text='❌ Скасувати')]],
            resize_keyboard=True
        )
    )

@admin_router.message(AdminStates.broadcasting, F.text == '❌ Скасувати')
async def cancel_broadcasting(message: Message, state: FSMContext):
    await state.set_state(AdminStates.browsing)
    await admin_command_handler(message, state)

@admin_router.message(AdminStates.broadcasting)
async def perform_broadcasting(message: Message, state: FSMContext):
    users = await get_all_users()
    success = 0
    failed = 0
    
    report_message = await message.answer(f"⏳ Розсилка розпочата... (Всього користувачів: {len(users)})")
    
    for user in users:
        try:
            await message.copy_to(user.id)
            success += 1
        except Exception:
            failed += 1
            
    await report_message.edit_text(
        f"✅ Розсилка завершена.\n\nОтримано: <b>{success}</b>\nБлок: <b>{failed}</b>"
    )
    
    await state.set_state(AdminStates.browsing)
    await admin_command_handler(message, state)

@admin_router.message(F.text == '👥 Користувачі', F.from_user.id.in_(ADMIN_IDS))
async def manage_users_handler(message: Message):
    
    users = await get_all_users()
    if not users:
        await message.answer("Користувачів поки немає.")
        return
        
    await message.answer(
        "👥 <b>Керування користувачами:</b>",
        reply_markup=build_user_management_keyboard(users)
    )

@admin_router.callback_query(F.data.startswith("block_user_"))
async def block_user_callback(callback: CallbackQuery):
    user_id = int(callback.data.split("_")[2])
    await update_user_status(user_id, False)
    await callback.answer("Користувача заблоковано.")
    
    # Refresh the list
    users = await get_all_users()
    await callback.message.edit_reply_markup(reply_markup=build_user_management_keyboard(users))

@admin_router.callback_query(F.data.startswith("unblock_user_"))
async def unblock_user_callback(callback: CallbackQuery):
    user_id = int(callback.data.split("_")[2])
    await update_user_status(user_id, True)
    await callback.answer("Користувача розблоковано.")
    
    # Refresh the list
    users = await get_all_users()
    await callback.message.edit_reply_markup(reply_markup=build_user_management_keyboard(users))

@admin_router.message(F.reply_to_message, F.from_user.id.in_(ADMIN_IDS))
async def admin_reply_handler(message: Message):
    
    # Get the text of the message being replied to
    reply_text = message.reply_to_message.text or message.reply_to_message.caption or ""
    
    # Extract user ID using regex
    match = re.search(r'\[ID:(\d+)\]', reply_text)
    
    if not match:
        await message.answer("⚠️ Не вдалося знайти ID користувача. Відповідайте на повідомлення з заголовком [ID:...]")
        return
    
    user_id = int(match.group(1))
    
    try:
        await message.copy_to(user_id)
        await message.answer("✅ Відповідь надіслано!")
    except Exception as e:
        await message.answer(f"❌ Не вдалося надіслати: {e}")

