import re
import asyncio
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from database.requests import update_user_status, get_user, add_media, delete_media_by_category, get_all_users, get_media_by_id, delete_media_by_id, get_media_by_category
from states import AdminStates
from config import ADMIN_IDS
from handlers.menu_handlers import open_menu, show_gallery, send_main_menu, send_file
from keyboards import build_user_management_keyboard, build_manage_media_keyboard

admin_router = Router()

# --- ENTRY POINT ---

@admin_router.message(Command("admin"), F.from_user.id.in_(ADMIN_IDS))
async def admin_command_handler(message: Message, state: FSMContext):
    """Вхід в режим адміністратора."""
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
        '🔧 <b>Режим Адміністратора</b>\n'
        'Навігуйте по меню як звичайний користувач. Коли ви дійдете до кінцевої категорії (Галерея або Каталог), '
        'з\'явиться меню редагування.',
        reply_markup=admin_kb
    )
    # Відкриваємо меню, щоб адмін міг почати навігацію
    await open_menu(message)

# --- ADMIN ACTIONS (Add, View, Clear) ---

@admin_router.callback_query(F.data.startswith("admin_"))
async def admin_actions_handler(callback: CallbackQuery, state: FSMContext):
    data = callback.data.split("|")
    action = data[0]
    category_code = data[1] if len(data) > 1 else None

    if action == "admin_add":
        if not category_code:
            await callback.answer("Помилка коду категорії", show_alert=True)
            return

        await state.update_data(category=category_code)
        await state.set_state(AdminStates.waiting_for_media)
        
        # Визначаємо підказку залежно від типу категорії
        is_doc = any(k in category_code for k in ["PDF", "CATALOG", "PRICE", "SHEETS", "DRAWINGS"])
        prompt = "📄 Надсилайте файли (PDF/DOC)" if is_doc else "📸 Надсилайте фото або відео"
        
        await callback.message.answer(
            f"{prompt} для категорії: <b>{category_code}</b>\n\n"
            f"<i>Можна надсилати декілька файлів поспіль. Натисніть /admin, щоб вийти.</i>"
        )
        await callback.answer()
    
    elif action == "admin_clear":
        await delete_media_by_category(category_code)
        await callback.answer(f"🗑 Категорію {category_code} очищено!", show_alert=True)
        await callback.message.answer(f"✅ Всі файли з категорії <b>{category_code}</b> видалено.")
    
    elif action == "admin_view":
        # Визначаємо, як показувати контент: як галерею чи як список файлів
        doc_keywords = ["PDF", "CATALOG", "DRAWINGS", "SHEETS", "CHECKLIST", "PRICE", "CERT"]
        is_doc = any(keyword in (category_code or "") for keyword in doc_keywords)
        
        if is_doc:
            await send_file(callback.message, category_code, user_id=callback.from_user.id)
        else:
            await show_gallery(callback.message, category_code, parent_path="", page=0, is_edit=False, user_id=callback.from_user.id)
        
        await callback.answer()
    
    elif action == "admin_exit":
        await state.set_state(AdminStates.browsing)
        await callback.message.delete()
        await callback.answer("Меню дій закрито")

# --- MEDIA UPLOAD HANDLER ---

@admin_router.message(AdminStates.waiting_for_media, F.photo | F.video | F.document)
async def media_upload_handler(message: Message, state: FSMContext):
    data = await state.get_data()
    category = data.get("category")
    
    if not category:
        await message.answer("⚠️ Помилка: категорія втрачена. Почніть знову через /admin.")
        await state.set_state(AdminStates.browsing)
        return

    file_id = None
    file_type = None

    # Визначаємо тип і ID файлу
    if message.photo:
        file_id = message.photo[-1].file_id # Беремо найкращу якість
        file_type = "photo"
    elif message.video:
        file_id = message.video.file_id
        file_type = "video"
    elif message.document:
        file_id = message.document.file_id
        file_type = "document"

    if file_id:
        # Зберігаємо в БД
        await add_media(
            category_code=category,
            file_id=file_id,
            file_type=file_type,
            caption=message.caption  # Зберігаємо підпис, якщо є
        )
        await message.reply(f'✅ Збережено у {category}!')
    else:
        await message.reply("❌ Не вдалося отримати ID файлу.")

# --- DELETION HANDLERS ---

@admin_router.callback_query(F.data.startswith("delete_media_"))
async def delete_single_media_handler(callback: CallbackQuery):
    """Видалення одного медіа з галереї (Фото/Відео)."""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Недостатньо прав!", show_alert=True)
        return
    
    media_id = int(callback.data.split("_")[2])
    media = await get_media_by_id(media_id)
    
    if not media:
        await callback.answer("Медіа вже видалено!", show_alert=True)
        return
    
    category_code = media.category_code
    await delete_media_by_id(media_id)
    await callback.answer("🗑 Видалено!", show_alert=True)
    
    # Оновлюємо галерею
    remaining_media = await get_media_by_category(category_code)
    if not remaining_media:
        await callback.message.delete()
        await callback.message.answer(f"Галерея {category_code} тепер порожня.")
    else:
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
    """Видалення одного документу (PDF)."""
    media_id = int(callback.data.split("_")[2])
    
    await delete_media_by_id(media_id)
    # await callback.message.delete() # Видалення викликає "пісок"
    try:
        await callback.message.edit_caption(
            caption=f"{callback.message.caption or ''}\n\n❌ <b>Файл видалено адміністратором</b>",
            reply_markup=None
        )
    except:
        await callback.message.delete()
    
    await callback.answer("🗑 Файл видалено!")

# --- USER MANAGEMENT & BROADCASTING ---
# (Залишаються без суттєвих змін, але наведені для повноти файлу)

@admin_router.callback_query(F.data.startswith("approve_"))
async def approve_user(callback: CallbackQuery):
    user_id = int(callback.data.split("_")[1])
    user = await get_user(user_id)
    
    if not user:
        await callback.answer("Користувача не знайдено!", show_alert=True)
        return
    if user.is_approved:
        await callback.answer("Вже схвалено!", show_alert=True)
        return
    
    await update_user_status(user_id, True)
    await callback.message.edit_text(f"{callback.message.text}\n\n✅ <b>Схвалено</b>")
    
    try:
        await callback.bot.send_message(user_id, "✅ Вашу заявку схвалено! Ласкаво просимо.")
        # Можна відразу надіслати меню
        await send_main_menu(callback.bot, user_id)
    except:
        pass

@admin_router.callback_query(F.data.startswith("reject_"))
async def reject_user(callback: CallbackQuery):
    user_id = int(callback.data.split("_")[1])
    user = await get_user(user_id)

    if not user:
        await callback.answer("Користувача не знайдено!", show_alert=True)
        return
        
    await callback.message.edit_text(f"{callback.message.text}\n\n❌ <b>Відхилено</b>")
    try:
        await callback.bot.send_message(user_id, "❌ Вашу заявку відхилено адміністратором.")
    except:
        pass

@admin_router.message(F.text == '📢 Створити розсилку', F.from_user.id.in_(ADMIN_IDS))
async def start_broadcasting(message: Message, state: FSMContext):
    await state.set_state(AdminStates.broadcasting)
    await message.answer(
        'Надішліть повідомлення (текст, фото або відео), яке отримають всі користувачі.',
        reply_markup=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text='❌ Скасувати')]], resize_keyboard=True)
    )

@admin_router.message(AdminStates.broadcasting, F.text == '❌ Скасувати')
async def cancel_broadcasting(message: Message, state: FSMContext):
    await state.set_state(AdminStates.browsing)
    await admin_command_handler(message, state)

@admin_router.message(AdminStates.broadcasting)
async def perform_broadcasting(message: Message, state: FSMContext):
    users = await get_all_users()
    count = 0
    
    status_msg = await message.answer("⏳ Розсилка...")
    
    for user in users:
        try:
            await message.copy_to(user.id)
            count += 1
        except:
            pass
            
    await status_msg.edit_text(f"✅ Розсилку отримали: {count} користувачів.")
    await state.set_state(AdminStates.browsing)
    await admin_command_handler(message, state)

@admin_router.message(F.text == '👥 Користувачі', F.from_user.id.in_(ADMIN_IDS))
async def manage_users_handler(message: Message):
    users = await get_all_users()
    await message.answer("👥 <b>Керування користувачами:</b>", reply_markup=build_user_management_keyboard(users))

@admin_router.message(F.text == '🏠 Головне меню')
async def back_to_main_menu_admin(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Вихід з режиму адміністратора.", reply_markup=ReplyKeyboardRemove())
    await open_menu(message)