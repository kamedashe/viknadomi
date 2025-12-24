import re
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters.callback_data import CallbackData

class MenuCallback(CallbackData, prefix="m", sep="_"):
    path: str
    action: str = ""

class GalleryCallback(CallbackData, prefix="gallery", sep="|"):
    action: str
    page: int
    parent_path: str

class ManageMediaCallback(CallbackData, prefix="manage", sep="|"):
    action: str  # 'prev', 'next', 'delete', 'close'
    index: int

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

def build_admin_actions_keyboard(category_code: str):
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="➕ Додати медіа", callback_data=f"admin_add|{category_code}"))
    builder.row(InlineKeyboardButton(text="🗑 Очистити категорію", callback_data=f"admin_clear|{category_code}"))
    builder.row(InlineKeyboardButton(text="👀 Подивитися як є", callback_data=f"admin_view|{category_code}"))
    builder.row(InlineKeyboardButton(text="❌ Вийти з адмінки", callback_data="admin_exit"))
    return builder.as_markup()

def build_gallery_keyboard(action: str, page: int, total: int, parent_path: str, media_id: int | None = None) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    
    # Calculate prev/next pages (circular)
    prev_page = (page - 1) % total
    next_page = (page + 1) % total
    
    # Navigation row
    builder.row(
        InlineKeyboardButton(text="⬅️", callback_data=GalleryCallback(action=action, page=prev_page, parent_path=parent_path).pack()),
        InlineKeyboardButton(text=f"{page + 1}/{total}", callback_data="noop"), # No-op button for counter
        InlineKeyboardButton(text="➡️", callback_data=GalleryCallback(action=action, page=next_page, parent_path=parent_path).pack())
    )
    
    # Delete button for admins (if media_id is provided)
    if media_id is not None:
        builder.row(InlineKeyboardButton(text="🗑 Видалити це фото", callback_data=f"delete_media_{media_id}"))
    
    # Back button to Menu and Home button side-by-side
    builder.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data=MenuCallback(path=parent_path).pack()),
        InlineKeyboardButton(text="🏠 На головну", callback_data=MenuCallback(path="").pack())
    )
    
    return builder.as_markup()

def build_menu_keyboard(current_structure: dict, current_path: str = "") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    
    # Add buttons from structure
    for idx, (text, value) in enumerate(current_structure.items()):
        # Clean text
        text = re.sub(r'^[-•\d\w]{1,2}\.\s*|^-\s*', '', text)

        # Calculate new path
        new_path = f"{current_path}:{idx}" if current_path else str(idx)
        # Check if value is dict (submenu) or string (action)
        # We store just the path. The handler figures out if it's an action.
        
        callback = MenuCallback(path=new_path).pack()
        builder.button(text=text, callback_data=callback)
    
    # Adjust layout - 1 column
    builder.adjust(1)

    # Navigation buttons
    nav_buttons = []
    
    # Calculate depth
    depth = len(current_path.split(':')) if current_path else 0

    # Add Back button if we are deep in menu
    if current_path:
        # Calculate parent path by removing last segment
        if ":" in current_path:
            parent_path = current_path.rsplit(":", 1)[0]
        else:
            parent_path = "" # Back to root
            
        nav_buttons.append(InlineKeyboardButton(text="🔙 Назад", callback_data=MenuCallback(path=parent_path).pack()))

    if depth >= 1:
        nav_buttons.append(InlineKeyboardButton(text="🏠 На головну", callback_data=MenuCallback(path="").pack()))
        
    if nav_buttons:
        builder.row(*nav_buttons)
        
    return builder.as_markup()

def build_user_management_keyboard(users: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    
    for user in users:
        # Display name or ID
        name = user.full_name or user.username or f"ID: {user.id}"
        display_text = f"{name} ({user.phone_number})"
        
        # Action button based on status
        if user.is_approved:
            btn_text = "⛔️ Block"
            callback_data = f"block_user_{user.id}"
        else:
            btn_text = "✅ Unblock"
            callback_data = f"unblock_user_{user.id}"
            
        builder.row(
            InlineKeyboardButton(text=display_text, callback_data="noop"),
            InlineKeyboardButton(text=btn_text, callback_data=callback_data)
        )
    
    return builder.as_markup()

def build_manage_media_keyboard(index: int, total: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    
    # Navigation row
    prev_idx = (index - 1) % total
    next_idx = (index + 1) % total
    
    builder.row(
        InlineKeyboardButton(text="⬅️ Попереднє", callback_data=ManageMediaCallback(action="prev", index=prev_idx).pack()),
        InlineKeyboardButton(text=f"{index + 1}/{total}", callback_data="noop"),
        InlineKeyboardButton(text="Наступне ➡️", callback_data=ManageMediaCallback(action="next", index=next_idx).pack())
    )
    
    # Action row
    builder.row(
        InlineKeyboardButton(text="🗑 Видалити файл", callback_data=ManageMediaCallback(action="delete", index=index).pack())
    )
    
    # Close row
    builder.row(
        InlineKeyboardButton(text="❌ Закрити", callback_data=ManageMediaCallback(action="close", index=index).pack())
    )
    
    return builder.as_markup()
