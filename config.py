# config.py

from os import environ

API_HASH = environ.get("API_HASH", "8a19a6a007044ff7b41ada4b377cdfba")
API_ID = int(environ.get("API_ID", "27461953"))
BOT_TOKEN = environ.get("BOT_TOKEN", "7978391610:AAH8QfTjlDJ9aat58WAAF0a7HwblsxhT7EI")
BOT_OWNER = int(environ.get("BOT_OWNER", "1938030055")) # Make sure this is an integer
BOT_USERNAME = environ.get("BOT_USERNAME", "Auto_Post_React_bot")
LOG_CHANNEL = int(environ.get("LOG_CHANNEL", "-1001524622686"))
AUTH_CHANNEL = int(environ.get("AUTH_CHANNEL", "-1001684575211"))
DATABASE_URL = environ.get("DATABASE_URL", "mongodb+srv://soniji:chaloji@cluster0.i5zy74f.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
UPDATE_CHANNEL = "https://t.me/joinnowearn"

# Positive Telegram reaction emojis only
VALID_EMOJIS = ["👍", "❤️", "🔥", "🎉", "👏", "🥰", "🤩", "👌", "💯"]

# The ARMY_BOT_TOKENS list has been removed from here.
# The army is now managed dynamically via the bot owner commands and stored in the database.
