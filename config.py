from os import environ

API_HASH = environ.get("API_HASH", "8a19a6a007044ff7b41ada4b377cdfba")
API_ID = int(environ.get("API_ID", "27461953"))
BOT_TOKEN = environ.get("BOT_TOKEN", "7978391610:AAH8QfTjlDJ9aat58WAAF0a7HwblsxhT7EI")
# Ensure BOT_OWNER is always an integer, even from environment
BOT_OWNER = int(environ.get("BOT_OWNER", "-1001938030055"))  # Removed quotes from default value
BOT_USERNAME = environ.get("BOT_USERNAME", "Auto_Post_React_bot")
LOG_CHANNEL = int(environ.get("LOG_CHANNEL", "-1001524622686"))
AUTH_CHANNEL = int(environ.get("AUTH_CHANNEL", "-1001684575211"))
DATABASE_URL = environ.get("DATABASE_URL", "mongodb+srv://soniji:chaloji@cluster0.i5zy74f.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
