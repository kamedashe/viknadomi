from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto, InputMediaVideo, InputMediaDocument, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command
from aiogram.exceptions import TelegramBadRequest
from aiogram.utils.media_group import MediaGroupBuilder

import os
import traceback

from menu_structure import MENU_STRUCTURE
from keyboards import MenuCallback, build_menu_keyboard, GalleryCallback, build_gallery_keyboard, build_admin_actions_keyboard
from database.requests import get_media_by_category, get_user
from states import AdminStates
from config import ADMIN_IDS, MAIN_MENU_BANNER

menu_router = Router()

# --- HELPER FUNCTIONS ---

async def show_gallery(message: Message, action: str, parent_path: str, page: int = 0, is_edit: bool = False, user_id: int | None = None):
    db_media = await get_media_by_category(action)
    
    if not db_media:
        gallery_data = [
            {"type": "photo", "file_id": "https://picsum.photos/800/600?grayscale", "caption": "Розділ в розробці 🛠", "id": None}
        ]
    else:
        gallery_data = [
            {"type": m.file_type, "file_id": m.file_id, "caption": m.caption or "", "id": m.id} for m in db_media
        ]

    total = len(gallery_data)
    current_index = page % total
    media_item = gallery_data[current_index]
    
    media_type = media_item["type"]
    media_file = media_item["file_id"]
    
    caption = f"{media_item['caption']}\n[{current_index + 1}/{total}]" if total > 1 else media_item['caption']
    media_id_for_keyboard = media_item.get("id") if user_id and user_id in ADMIN_IDS else None
    
    keyboard = build_gallery_keyboard(action, current_index, total, parent_path, media_id=media_id_for_keyboard)

    if media_type == "video":
        media_object = InputMediaVideo(media=media_file, caption=caption)
        method_answer = message.answer_video
    elif media_type == "document":
        media_object = InputMediaDocument(media=media_file, caption=caption)
        method_answer = message.answer_document
    else:
        media_object = InputMediaPhoto(media=media_file, caption=caption)
        method_answer = message.answer_photo

    try:
        if is_edit:
            await message.edit_media(media=media_object, reply_markup=keyboard)
        else:
            await message.delete()
            await method_answer(media_file, caption=caption, reply_markup=keyboard)
    except Exception:
        try:
            await message.delete()
        except:
            pass
        await method_answer(media_file, caption=caption, reply_markup=keyboard)

async def delete_previous_messages(message: Message, state: FSMContext):
    data = await state.get_data()
    msg_ids = data.get("cleanup_msg_ids", [])
    if msg_ids:
        for mid in msg_ids:
            try:
                await message.bot.delete_message(chat_id=message.chat.id, message_id=mid)
            except:
                pass
        await state.update_data(cleanup_msg_ids=[])

async def send_file(message: Message, action: str, user_id: int | None = None) -> list[int]:
    """
    Sends files and returns a list of sent message IDs.
    """
    db_media = await get_media_by_category(action)
    sent_ids = []
    
    if not db_media:
        msg = await message.answer(f"📂 <b>Розділ:</b> {action}\n(Матеріали ще не додано адміністратором).")
        sent_ids.append(msg.message_id)
        return sent_ids
    
    is_admin = user_id in ADMIN_IDS if user_id else False
    
    for m in db_media:
        keyboard = None
        if is_admin:
            keyboard = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="🗑 Видалити цей файл", callback_data=f"delete_file_{m.id}")
            ]])

        try:
            sent_msg = None
            if m.file_type == "document":
                sent_msg = await message.answer_document(m.file_id, caption=m.caption, reply_markup=keyboard)
            elif m.file_type == "photo":
                sent_msg = await message.answer_photo(m.file_id, caption=m.caption, reply_markup=keyboard)
            elif m.file_type == "video":
                sent_msg = await message.answer_video(m.file_id, caption=m.caption, reply_markup=keyboard)
            
            if sent_msg:
                sent_ids.append(sent_msg.message_id)
                
        except Exception as e:
            err_msg = await message.answer(f"⚠️ Помилка надсилання файлу: {e}")
            sent_ids.append(err_msg.message_id)

    return sent_ids

async def send_main_menu(bot, chat_id: int):
    try:
        await bot.send_photo(
            chat_id=chat_id,
            photo=MAIN_MENU_BANNER,
            caption="<b>📂 ГОЛОВНЕ МЕНЮ</b>\nОберіть категорію:", 
            reply_markup=build_menu_keyboard(MENU_STRUCTURE)
        )
    except Exception:
        await bot.send_message(
            chat_id=chat_id,
            text="<b>📂 ГОЛОВНЕ МЕНЮ</b>\nОберіть категорію:", 
            reply_markup=build_menu_keyboard(MENU_STRUCTURE)
        )

# --- HANDLERS ---

@menu_router.message(Command("menu"))
async def open_menu(message: Message):
    user_id = message.from_user.id
    user = await get_user(user_id)
    is_admin = user_id in ADMIN_IDS
    is_approved = user and user.is_approved

    if not is_admin and not is_approved:
        await message.answer("⛔️ Доступ заборонено. Очікуйте підтвердження адміністратором.")
        return

    await send_main_menu(message.bot, user_id)

@menu_router.callback_query(GalleryCallback.filter())
async def gallery_navigation_handler(callback: CallbackQuery, callback_data: GalleryCallback):
    await show_gallery(
        message=callback.message,
        action=callback_data.action,
        parent_path=callback_data.parent_path,
        page=callback_data.page,
        is_edit=True,
        user_id=callback.from_user.id
    )
    await callback.answer()

@menu_router.callback_query(MenuCallback.filter())
async def menu_navigation_handler(callback: CallbackQuery, callback_data: MenuCallback, state: FSMContext):
    user = await get_user(callback.from_user.id)
    if callback.from_user.id not in ADMIN_IDS and (not user or not user.is_approved):
        await callback.answer("⛔️ Доступ заборонено.", show_alert=True)
        return

    
    # Cleaning up previous media batch if exists
    await delete_previous_messages(callback.message, state)

    if not callback_data.path:
        # Back to Main Menu
        if callback.message.photo or callback.message.video or callback.message.document:
            await callback.message.delete()
            await send_main_menu(callback.bot, callback.from_user.id)
        else:
            try:
                await callback.message.edit_text(
                    "<b>📂 ГОЛОВНЕ МЕНЮ</b>\nОберіть категорію:",
                    reply_markup=build_menu_keyboard(MENU_STRUCTURE)
                )
            except TelegramBadRequest:
                try:
                    await callback.message.delete()
                except:
                    pass
                await send_main_menu(callback.bot, callback.from_user.id)
        await callback.answer()
        return

    current_structure = MENU_STRUCTURE
    parent_path_str = ""
    if ":" in callback_data.path:
        parent_path_str = ":".join(callback_data.path.split(":")[:-1])
    
    try:
        indices = [int(i) for i in callback_data.path.split(":")]
        for idx in indices:
            keys = list(current_structure.keys())
            node_name = keys[idx]
            current_structure = current_structure[node_name]
    except Exception:
        await callback.answer("Помилка навігації.", show_alert=True)
        await open_menu(callback.message)
        return

    # ВАРІАНТ 1: Це підменю (dict)
    if isinstance(current_structure, dict):
        if callback.message.photo or callback.message.video or callback.message.document:
            await callback.message.delete()
            await callback.message.answer(f"📂 <b>{node_name}</b>:", reply_markup=build_menu_keyboard(current_structure, callback_data.path))
        else:
            try:
                await callback.message.edit_text(f"📂 <b>{node_name}</b>:", reply_markup=build_menu_keyboard(current_structure, callback_data.path))
            except TelegramBadRequest:
                try:
                    await callback.message.delete()
                except:
                    pass
                await callback.message.answer(f"📂 <b>{node_name}</b>:", reply_markup=build_menu_keyboard(current_structure, callback_data.path))
        await callback.answer()

    # ВАРІАНТ 2: Це кінцева дія (str)
    elif isinstance(current_structure, str):
        action_code = current_structure
        current_state = await state.get_state()
        
        # Перевірка для адмінки
        editable_prefixes = ("GALLERY_", "PDF_", "CATALOG_", "ACTION_CONTACTS", "DRAWINGS", "SHEETS", "CHECKLIST", "PRICE", "CERT")
        is_editable = any(action_code.startswith(p) for p in editable_prefixes)

        if current_state == AdminStates.browsing.state and is_editable and callback.from_user.id in ADMIN_IDS:
             # Admin edit menu - new message or edit?
             # For admin panel we usually send a new message or edit.
             # Let's keep existing behavior or optimize.
             # Existing: answer -> new message.
             await callback.message.answer(
                 f"⚙️ <b>Адмін-панель</b>\nРозділ: {node_name}\nКод: <code>{action_code}</code>",
                 reply_markup=build_admin_actions_keyboard(action_code)
             )
             await callback.answer()
             return

        # A. ПОСИЛАННЯ (http)
        if action_code.startswith("http"):
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=f"🔗 Переглянути", url=action_code)],
                [
                    InlineKeyboardButton(text="🔙 Назад", callback_data=MenuCallback(path=parent_path_str).pack()),
                    InlineKeyboardButton(text="🏠 На головну", callback_data=MenuCallback(path="").pack())
                ]
            ])
            text = f"🌐 <b>{node_name}</b>"
            
            if callback.message.photo or callback.message.video or callback.message.document:
                await callback.message.delete()
                await callback.message.answer(text, reply_markup=kb)
            else:
                 try:
                    await callback.message.edit_text(text, reply_markup=kb)
                 except TelegramBadRequest:
                    try:
                        await callback.message.delete()
                    except:
                        pass
                    await callback.message.answer(text, reply_markup=kb)
        
        # B. КОНТАКТИ
        elif action_code == "ACTION_CONTACTS":
            contacts_text = (
                "<b>Контактна інформація</b>\n"
                "📍 Чернівці, пров. Маланчука, 14\n"
                "📧 hello@viknadomi.com.ua\n\n"
                "<b>Call-центр</b>\n"
                "📞 Менеджери по роботі з партнерами:\n"
                "+380 96 766 9166 (🇮🇹🇪🇸)\n"
                "+380 96 051 0901 (Решта 🇪🇺)\n\n"
                "📞 Технічний відділ\n"
                "(рекламації, допомога у замірах та монтажу)\n"
                "+380 66 983 4921\n\n"
                "📞 Відділ логістики\n"
                "+380 75 110 4018\n\n"
                "🕐 <b>Графік роботи:</b>\n"
                "Пн–Пт: 10:00 – 19:00\n"
                "Пт: 9:00 – 17:00\n"
                "Сб: 10:00 – 14:00 (черговий менеджер)\n"
                "Нд: вихідний"
            )
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="🔙 Назад", callback_data=MenuCallback(path=parent_path_str).pack()),
                    InlineKeyboardButton(text="🏠 На головну", callback_data=MenuCallback(path="").pack())
                ]
            ])
            
            if callback.message.photo or callback.message.video or callback.message.document:
                await callback.message.delete()
                await callback.message.answer(contacts_text, reply_markup=kb)
            else:
                try:
                    await callback.message.edit_text(contacts_text, reply_markup=kb)
                except TelegramBadRequest:
                    try:
                        await callback.message.delete()
                    except:
                        pass
                    await callback.message.answer(contacts_text, reply_markup=kb)

        # C. СПИСКИ ФАЙЛІВ (Каталоги, PDF, і т.д.)
        elif any(k in action_code for k in ["CATALOG", "PDF_", "DRAWINGS", "SHEETS", "CHECKLIST", "PRICE", "CERT"]):
            try:
                await callback.message.delete()
            except:
                pass
            
            # Відправляємо файли
            sent_msgs_ids = await send_file(callback.message, action_code, user_id=callback.from_user.id)
            
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="🔙 Назад", callback_data=MenuCallback(path=parent_path_str).pack()),
                    InlineKeyboardButton(text="🏠 На головну", callback_data=MenuCallback(path="").pack())
                ]
            ])
            
            # Send navigation message ("Materials above")
            nav_msg = await callback.message.answer("⬆️ Матеріали вище", reply_markup=kb)
            sent_msgs_ids.append(nav_msg.message_id)

            # Store IDs to clean up later
            await state.update_data(cleanup_msg_ids=sent_msgs_ids)
        
        # D. ГАЛЕРЕЯ (Фото-слайдер)
        else:
            # show_gallery вже має правильну кнопку "На головну" всередині keyboards.py
            await show_gallery(callback.message, action_code, parent_path=parent_path_str, page=0, is_edit=False, user_id=callback.from_user.id)
        
        await callback.answer()