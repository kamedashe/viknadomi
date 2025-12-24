import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
# Admin IDs should be a comma-separated string in .env: ADMIN_IDS=12345678,87654321
ADMIN_IDS = [int(id_str) for id_str in os.getenv("ADMIN_IDS", "").split(",") if id_str.strip()]

# Correct menu banner file_id (Red premium banner)
MAIN_MENU_BANNER = "AgACAgIAAxkBAAIHGGlJq9kHC3vqbQIS8-DFl_sfX2p1AALcC2sbB6dQSu5fa4MNZcXnAQADAgADdwADNgQ"
