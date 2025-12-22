import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.types import BotCommand, BotCommandScopeDefault, BotCommandScopeChat
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.bot import DefaultBotProperties
from aiogram.enums import ParseMode

from config import BOT_TOKEN, ADMIN_IDS
from handlers.user_handlers import user_router
from handlers.admin_handlers import admin_router
from handlers.menu_handlers import menu_router

from database.setup import async_main

async def main():
    logging.basicConfig(level=logging.INFO)
    
    await async_main()

    if not BOT_TOKEN:
        print("Error: BOT_TOKEN is not set in .env file")
        return

    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())

    dp.include_router(admin_router)
    dp.include_router(menu_router)
    dp.include_router(user_router)

    try:
        await bot.delete_webhook(drop_pending_updates=True)

        # Public commands (for all users)
        await bot.set_my_commands([
            BotCommand(command="menu", description="📂 Головне меню"),
            BotCommand(command="start", description="🔄 Перезапуск бота")
        ], scope=BotCommandScopeDefault())

        # Admin commands (only for admins)
        admin_commands = [
            BotCommand(command="menu", description="📂 Головне меню"),
            BotCommand(command="admin", description="⚙️ Адмін-панель"),
            BotCommand(command="start", description="🔄 Перезапуск бота")
        ]
        for admin_id in ADMIN_IDS:
            await bot.set_my_commands(admin_commands, scope=BotCommandScopeChat(chat_id=admin_id))

        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot stopped!")
