from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto, InputMediaVideo, InputMediaDocument
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command
from aiogram.utils.media_group import MediaGroupBuilder
from aiogram.types import FSInputFile

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
    """Відображення галереї фото/відео з пагінацією."""
    db_media = await get_media_by_category(action)
    
    if not db_media:
        # Заглушка, якщо галерея порожня
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
    # Додаємо лічильник до опису
    caption = f"{media_item['caption']}\n[{current_index + 1}/{total}]" if total > 1 else media_item['caption']
    
    # ID медіа передаємо тільки адміну для можливості видалення
    media_id_for_keyboard = media_item.get("id") if user_id and user_id in ADMIN_IDS else None
    
    keyboard = build_gallery_keyboard(action, current_index, total, parent_path, media_id=media_id_for_keyboard)

    # Формуємо об'єкт медіа
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
            # Telegram не дозволяє змінювати тип медіа (наприклад, фото -> документ) через edit_media в усіх випадках.
            # Тому іноді краще видалити і надіслати нове, якщо типи відрізняються, але спробуємо edit.
            await message.edit_media(media=media_object, reply_markup=keyboard)
        else:
            await message.delete()
            await method_answer(media_file, caption=caption, reply_markup=keyboard)
    except Exception as e:
        # Якщо редагування не вдалося (наприклад, старе повідомлення текстове, а нове - фото), видаляємо і шлемо нове
        try:
            await message.delete()
        except:
            pass
        await method_answer(media_file, caption=caption, reply_markup=keyboard)

async def send_file(message: Message, action: str, user_id: int | None = None):
    """Надсилання документів (PDF, каталоги) списком."""
    db_media = await get_media_by_category(action)
    
    if not db_media:
        await message.answer(f"📄 <b>Документи відсутні</b>\nКатегорія: {action}\n(Файли ще не додано адміністратором).")
        return
    
    is_admin = user_id in ADMIN_IDS if user_id else False
    
    # Надсилаємо кожен файл окремим повідомленням
    for m in db_media:
        keyboard = None
        if is_admin:
            keyboard = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="🗑 Видалити файл", callback_data=f"delete_file_{m.id}")
            ]])

        try:
            if m.file_type == "document":
                await message.answer_document(m.file_id, caption=m.caption, reply_markup=keyboard)
            elif m.file_type == "photo":
                await message.answer_photo(m.file_id, caption=m.caption, reply_markup=keyboard)
            elif m.file_type == "video":
                await message.answer_video(m.file_id, caption=m.caption, reply_markup=keyboard)
        except Exception as e:
            await message.answer(f"Помилка надсилання файлу: {e}")

async def send_main_menu(bot, chat_id: int):
    """Відправка головного меню з банером."""
    try:
        await bot.send_photo(
            chat_id=chat_id,
            photo=MAIN_MENU_BANNER,
            caption="<b>📂 ГОЛОВНЕ МЕНЮ</b>\nОберіть категорію:", 
            reply_markup=build_menu_keyboard(MENU_STRUCTURE)
        )
    except Exception as e:
        print(f"Error sending main menu: {e}")
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
    # Дозволяємо доступ, якщо це адмін АБО якщо користувач затверджений
    is_approved = user and user.is_approved

    if not is_admin and not is_approved:
        await message.answer("⛔️ Доступ заборонено. Вашу заявку ще не підтверджено адміністратором.")
        return

    await send_main_menu(message.bot, user_id)

@menu_router.callback_query(GalleryCallback.filter())
async def gallery_navigation_handler(callback: CallbackQuery, callback_data: GalleryCallback):
    """Навігація всередині галереї (Вперед/Назад)."""
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
    """Основний хендлер навігації по меню."""
    
    # 1. Перевірка доступу
    user = await get_user(callback.from_user.id)
    if callback.from_user.id not in ADMIN_IDS and (not user or not user.is_approved):
        await callback.answer("⛔️ Доступ заборонено.", show_alert=True)
        return

    # 2. Обробка повернення в корінь
    if not callback_data.path:
        await callback.message.delete()
        await send_main_menu(callback.bot, callback.from_user.id)
        await callback.answer()
        return

    # 3. Парсинг шляху і пошук поточного вузла в MENU_STRUCTURE
    current_structure = MENU_STRUCTURE
    path_indices = [int(i) for i in callback_data.path.split(":")]
    parent_path_str = ":".join(callback_data.path.split(":")[:-1])
    
    current_node_name = ""
    
    try:
        for idx in path_indices:
            keys = list(current_structure.keys())
            if idx >= len(keys):
                raise ValueError("Index out of bounds")
            key = keys[idx]
            current_node_name = key
            current_structure = current_structure[key]
    except Exception as e:
        print(f"Navigation error: {e}")
        await callback.answer("Помилка навігації. Меню змінено.", show_alert=True)
        await open_menu(callback.message)
        return

    # --- ЛОГІКА ВІДОБРАЖЕННЯ ---

    # ВАРІАНТ А: Це ПІДМЕНЮ (Dictionary)
    if isinstance(current_structure, dict):
        # Якщо попереднє повідомлення було медіа (фото/відео), краще видалити і надіслати нове
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
        await callback.answer()
        return

    # ВАРІАНТ Б: Це ДІЯ (String)
    elif isinstance(current_structure, str):
        action_code = current_structure
        
        # --- ПЕРЕВІРКА РЕЖИМУ АДМІНІСТРАТОРА ---
        # Якщо адмін у режимі редагування і це не просте посилання, перехоплюємо дію
        current_state = await state.get_state()
        editable_prefixes = ("GALLERY_", "PDF_", "ACTION_CONTACTS") # Можна редагувати ці типи
        
        # Перевіряємо, чи це редагована категорія і чи увімкнено режим адміна
        is_editable = any(action_code.startswith(p) for p in editable_prefixes)
        
        if current_state == AdminStates.browsing.state and is_editable and callback.from_user.id in ADMIN_IDS:
             await callback.message.answer(
                 f"⚙️ <b>Адмін-панель:</b> {current_node_name}\n\nКод: <code>{action_code}</code>\nОберіть дію:",
                 reply_markup=build_admin_actions_keyboard(action_code)
             )
             await callback.answer()
             return

        # --- ОБРОБКА КОНКРЕТНИХ ДІЙ ДЛЯ КОРИСТУВАЧА ---

        # 1. URL Посилання
        if action_code.startswith("http"):
            # Видаляємо старе меню, щоб не засмічувати чат, і даємо красиву кнопку
            await callback.message.delete()
            
            link_kb = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text=f"🔗 Відкрити: {current_node_name}", url=action_code)],
                    [
                        InlineKeyboardButton(text="🔙 Назад", callback_data=MenuCallback(path=parent_path_str).pack()),
                        InlineKeyboardButton(text="🏠 На головну", callback_data=MenuCallback(path="").pack())
                    ]
                ]
            )
            await callback.message.answer(
                f"🌐 <b>{current_node_name}</b>\n\nНатисніть кнопку нижче, щоб перейти за посиланням:",
                reply_markup=link_kb
            )
        
        # 2. Контакти
        elif action_code == "ACTION_CONTACTS":
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
            # Для контактів не робимо gallery, просто текст, можна видалити попереднє або едітнути
            await callback.message.delete()
            # Додаємо кнопку назад вручну або через helper, тут спрощено:
            back_kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data=MenuCallback(path=parent_path_str).pack())]
            ])
            await callback.message.answer(contacts_text, reply_markup=back_kb)

        # 3. Документи (PDF, Каталоги)
        elif any(k in action_code for k in ["PDF_", "CATALOG", "DRAWINGS", "SHEETS", "CHECKLIST", "PRICE", "CERT"]):
            await callback.message.delete() # Видаляємо меню, щоб показати файли
            await send_file(callback.message, action_code, user_id=callback.from_user.id)
            # Після надсилання файлів варто показати кнопку "Назад", щоб не тупик
            back_kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Повернутися в меню", callback_data=MenuCallback(path=parent_path_str).pack())]
            ])
            await callback.message.answer("⬆️ Файли вище", reply_markup=back_kb)

        # 4. Галереї (Фото/Відео) за замовчуванням
        else:
            # GALLERY_... або інші кастомні коди
            await show_gallery(
                callback.message, 
                action_code, 
                parent_path=parent_path_str, 
                page=0, 
                is_edit=False, 
                user_id=callback.from_user.id
            )
        
        await callback.answer()

    else:
        # Unknown structure type
        await callback.answer("Невідомий тип меню", show_alert=True)