
from os import environ

API_HASH = environ.get("API_HASH", "8a19a6a007044ff7b41ada4b377cdfba")
API_ID = int(environ.get("API_ID", "27461953"))
BOT_TOKEN = environ.get("BOT_TOKEN", "7530428356:AAEIqnXFYd4yuKTcS12LpmziyPM9phTpQDc")
BOT_OWNER = int(environ.get("BOT_OWNER", "-1001938030055"))
BOT_USERNAME = environ.get("BOT_USERNAME", "Gsiege_sksgwvv_bot")
LOG_CHANNEL = int(environ.get("LOG_CHANNEL", "-1001524622686"))
AUTH_CHANNEL = int(environ.get("AUTH_CHANNEL", "-1001684575211"))
DATABASE_URL = environ.get("DATABASE_URL", "mongodb+srv://soniji:chaloji@cluster0.i5zy74f.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")

# Define default emojis list
EMOJIS = [
    "👍", "🤷‍♂", "❤", "🔥", "🥰", "👏", "😁", "🤔", "🤯", "😱", "🤬", "😢", 
    "🥶", "🤩", "🥳", "😎", "🙏", "👌", "🤣", "😇", "🥱", "🥴", "😍", "🤓", 
    "❤‍🔥", "🌚", "😐", "💯", "🦄", "⚡", "👾", "🏆", "💔", "🤨", "🌟", "😡", 
    "👅", "🆒", "😘", "😈", "😴", "😭", "👻", "🌈", "👨‍💻", "👀", "🎃", "🙄", 
    "🤧", "😨", "🤝", "🤐", "🤗", "🫡", "🤭", "🥸", "🤫", "😶‍🌫", "🤪", "😏"
]
