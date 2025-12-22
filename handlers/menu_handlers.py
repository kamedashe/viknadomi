from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command

from menu_structure import MENU_STRUCTURE
from aiogram.types import InputMediaPhoto, InputMediaVideo
from keyboards import MenuCallback, build_menu_keyboard, GalleryCallback, build_gallery_keyboard, build_admin_actions_keyboard
from database.requests import get_media_by_category, get_user
from states import AdminStates
from config import ADMIN_IDS



menu_router = Router()

async def show_gallery(message: Message, action: str, parent_path: str, page: int = 0, is_edit: bool = False, user_id: int | None = None):
    db_media = await get_media_by_category(action)
    
    if not db_media:
        # Fallback for empty categories
        gallery_data = [
            {"type": "photo", "file_id": "https://picsum.photos/800/600?grayscale", "caption": "Розділ в розробці 🛠"}
        ]
    else:
        # specific format for gallery, including db id for admin deletion
        gallery_data = [
            {"type": m.file_type, "file_id": m.file_id, "caption": m.caption or "", "id": m.id} for m in db_media
        ]

    total = len(gallery_data)
    
    # Circular navigation logic is handled by (page % total)
    current_index = page % total
    media_item = gallery_data[current_index]
    
    media_type = media_item["type"]
    media_file = media_item["file_id"] # Can be URL or file_id
    # Add page counter to caption
    caption = f"{media_item['caption']} [{current_index + 1}/{total}]"
    
    # Pass media_id to keyboard only if user is admin
    media_id_for_keyboard = media_item.get("id") if user_id and user_id in ADMIN_IDS else None
    keyboard = build_gallery_keyboard(action, current_index, total, parent_path, media_id=media_id_for_keyboard)

    # Prepare InputMedia object
    if media_type == "video":
        media_object = InputMediaVideo(media=media_file, caption=caption)
        method_answer = message.answer_video
    elif media_type == "document":
        # Note: editing media to a different type (like photo -> document) 
        # might not work in all Telegram clients, but here we usually delete/send new for non-edit
        from aiogram.types import InputMediaDocument
        media_object = InputMediaDocument(media=media_file, caption=caption)
        method_answer = message.answer_document
    else:
        media_object = InputMediaPhoto(media=media_file, caption=caption)
        method_answer = message.answer_photo

    try:
        if is_edit:
            await message.edit_media(
                media=media_object,
                reply_markup=keyboard
            )
        else:
            await message.delete()
            await method_answer(
                media_file,
                caption=caption,
                reply_markup=keyboard
            )
    except Exception as e:
        print(f"Error showing gallery: {e}")
        if not is_edit:
             await method_answer(media_file, caption=caption, reply_markup=keyboard)

async def send_file(message: Message, action: str, user_id: int | None = None):
    db_media = await get_media_by_category(action)
    if not db_media:
        await message.answer(f"📄 <b>Документ:</b> {action}\n\n(Файл ще не додано. Скористайтесь адмін-панеллю.)")
        return
    
    is_admin = user_id in ADMIN_IDS if user_id else False
    
    for m in db_media:
        keyboard = None
        if is_admin:
            keyboard = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="🗑 Видалити", callback_data=f"delete_file_{m.id}")
            ]])

        if m.file_type == "document":
            await message.answer_document(m.file_id, caption=m.caption, reply_markup=keyboard)
        elif m.file_type == "photo":
            await message.answer_photo(m.file_id, caption=m.caption, reply_markup=keyboard)
        elif m.file_type == "video":
            await message.answer_video(m.file_id, caption=m.caption, reply_markup=keyboard)

# Entry point for menu
@menu_router.message(Command("menu"))
async def open_menu(message: Message):
    user_id = message.from_user.id
    user = await get_user(user_id)
    is_admin = user_id in ADMIN_IDS
    is_approved = user and user.is_approved

    if not is_admin and not is_approved:
        await message.answer("⛔️ Доступ заборонено. Будь ласка, спочатку пройдіть реєстрацію через /start")
        return

    # Use the correct file_id for the banner
    banner_url = "AgACAgIAAxkBAAIBamlFLcvAqErGCPv74YeSW_dkoPmNAALlEWsb0Y8pSqCU0_ibd7sFAQADAgADdwADNgQ"
    try:
        await message.answer_photo(
            photo=banner_url,
            caption="<b>📂 ГОЛОВНЕ МЕНЮ</b>", 
            reply_markup=build_menu_keyboard(MENU_STRUCTURE)
        )
    except Exception as e:
        print(f"Error sending banner: {e}")
        await message.answer(
            "<b>📂 ГОЛОВНЕ МЕНЮ</b>", 
            reply_markup=build_menu_keyboard(MENU_STRUCTURE)
        )

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
    # Security Check
    user = await get_user(callback.from_user.id)
    if callback.from_user.id not in ADMIN_IDS and (not user or not user.is_approved):
        await callback.answer("⛔️ Доступ заборонено. Очікуйте підтвердження.", show_alert=True)
        return

    current_structure = MENU_STRUCTURE
    
    # Empty path means root
    if not callback_data.path:
        # Always delete the old message and send a fresh one with photo for consistency when going to root
        await callback.message.delete()
        banner_url = "AgACAgIAAxkBAAIBamlFLcvAqErGCPv74YeSW_dkoPmNAALlEWsb0Y8pSqCU0_ibd7sFAQADAgADdwADNgQ"
        try:
            await callback.message.answer_photo(
                photo=banner_url,
                caption="<b>📂 ГОЛОВНЕ МЕНЮ</b>", 
                reply_markup=build_menu_keyboard(MENU_STRUCTURE)
            )
        except Exception as e:
            print(f"Error sending banner in callback: {e}")
            await callback.message.answer(
                "<b>📂 ГОЛОВНЕ МЕНЮ</b>", 
                reply_markup=build_menu_keyboard(MENU_STRUCTURE)
            )
        
        await callback.answer()
        return

    # Navigate to the target node
    path_indices = [int(i) for i in callback_data.path.split(":")]
    
    try:
        current_node_name = ""
        for idx in path_indices:
            # Get key by index
            keys = list(current_structure.keys())
            if idx >= len(keys):
                raise ValueError("Index out of bounds")
            
            key = keys[idx]
            current_node_name = key
            current_structure = current_structure[key]

        # Check node type
        if isinstance(current_structure, dict):
            # If coming from Gallery/Files (User clicked Back), we need to send new message instead of edit
            # because we cannot turn Media (Photo/Video/Doc) back into Text easily via edit_text.
            if callback.message.photo or callback.message.video or callback.message.document:
                await callback.message.delete()
                await callback.message.answer(
                    f"📂 <b>{current_node_name}</b>:",
                    reply_markup=build_menu_keyboard(current_structure, callback_data.path)
                )
            else:
                 await callback.message.edit_text(
                    f"📂 <b>{current_node_name}</b>:",
                    reply_markup=build_menu_keyboard(current_structure, callback_data.path)
                )
        elif isinstance(current_structure, str):
            # It's an action -> Trigger action
            action = current_structure
            
            # ADMIN MODE CHECK
            current_state = await state.get_state()
            editable_prefixes = ("GALLERY_", "PDF_", "ACTION_GALLERY", "ACTION_SEND_PDF")
            if current_state == AdminStates.browsing.state and any(action.startswith(p) for p in editable_prefixes):
                 await callback.message.answer(
                     f"⚙️ Адмін-панель: {current_node_name}\nОберіть дію:",
                     reply_markup=build_admin_actions_keyboard(action)
                 )
                 await callback.answer()
                 return

            if action.startswith("http"):
                 # It's a URL - send distinct message with link button + navigation
                 parent_path = ":".join(callback_data.path.split(":")[:-1])
                 link_kb = InlineKeyboardMarkup(
                     inline_keyboard=[
                         [InlineKeyboardButton(text="🔗 Відкрити посилання", url=action)],
                         [
                             InlineKeyboardButton(text="🔙 Назад", callback_data=MenuCallback(path=parent_path).pack()),
                             InlineKeyboardButton(text="🏠 На головну", callback_data=MenuCallback(path="").pack())
                         ]
                     ]
                 )
                 await callback.message.answer(
                     "<b>Перейдіть за посиланням👇</b>",
                     reply_markup=link_kb
                 )
            
            elif action == "ACTION_CONTACTS":
                contacts_text = (
                    "<b>📞 КОНТАКТИ</b>\n\n"
                    "📍 <b>Адреса:</b> Чернівці, пров. Маланчука, 14\n"
                    "📧 <b>Email:</b> hello@viknadomi.com.ua\n\n"
                    "📞 <b>Партнери (🇮🇹🇪🇸):</b> +380 96 766 9166\n"
                    "📞 <b>Партнери (🇪🇺):</b> +380 96 051 0901\n"
                    "🛠 <b>Тех. відділ:</b> +380 66 983 4921\n"
                    "🚚 <b>Логістика:</b> +380 75 110 4018\n\n"
                    "🕐 <b>Графік роботи:</b>\n"
                    "Пн–Пт: 10:00 – 19:00\n"
                    "Сб: 10:00 – 14:00\n"
                    "Нд: Вихідний"
                )
                await callback.message.answer(contacts_text)
                await callback.answer()
                return

            else:
                # Keywords determining if it is a document/file
                doc_keywords = ["PDF", "CATALOG", "DRAWINGS", "SHEETS", "CHECKLIST", "PRICE", "CERT"]
                
                if any(keyword in action for keyword in doc_keywords):
                     await send_file(callback.message, action, user_id=callback.from_user.id)
                else:
                    # Default to gallery for everything else (Photos, Videos, Handles, etc.)
                    # Pass parent path so we can return
                    # Parent path is current path MINUS last index (the action itself)
                    parent_path = ":".join(callback_data.path.split(":")[:-1])
                    await show_gallery(callback.message, action, parent_path=parent_path, page=0, is_edit=False, user_id=callback.from_user.id)
            
            # Avoid loading animation
    except Exception as e:
        import traceback
        traceback.print_exc() 
        print(f"Navigation error details: {e}, Path: {callback_data.path}")
        await callback.answer(f"Помилка: {str(e)[:50]}", show_alert=True)
        return

    await callback.answer()
