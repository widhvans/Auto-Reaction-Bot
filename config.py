import os
from dotenv import load_dotenv

load_dotenv()

# Essential Bot Configuration
# Get these values from my.telegram.org
API_ID = int(os.environ.get("API_ID", "27461953"))
API_HASH = os.environ.get("API_HASH", "8a19a6a007044ff7b41ada4b377cdfba")

# Get this value from @BotFather
BOT_TOKEN = os.environ.get("BOT_TOKEN", "7978391610:AAH8QfTjlDJ9aat58WAAF0a7HwblsxhT7EI")

# The Telegram user ID of the person who owns the bot
BOT_OWNER = int(os.environ.get("BOT_OWNER", "1938030055"))

# Your bot's username, without the '@'
BOT_USERNAME = os.environ.get("BOT_USERNAME", "Auto_Post_React_bot")

# MongoDB Database URL
DATABASE_URL = os.environ.get("DATABASE_URL", "mongodb+srv://soniji:chaloji@cluster0.i5zy74f.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")

# Optional: For logging and updates
LOG_CHANNEL = int(os.environ.get("LOG_CHANNEL", "-1001524622686")) # A channel where the bot will log new users
UPDATE_CHANNEL = os.environ.get("UPDATE_CHANNEL", "https://t.me/joinnowearn") # Your update channel link
