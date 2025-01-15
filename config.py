import os

API_HASH = os.getenv("API_HASH", "")
API_ID = int(os.getenv("API_ID", ""))
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
BOT_OWNER = int(os.getenv("BOT_OWNER", ""))
BOT_USERNAME = os.getenv("BOT_USERNAME", "QuickReactRobot")
LOG_CHANNEL = int(os.getenv("LOG_CHANNEL", ""))
AUTH_CHANNEL = int(os.getenv("AUTH_CHANNEL", ""))
DATABASE_URL = os.getenv("DATABASE_URL", "")
# Define default emojis list
EMOJIS = [
    "👍", "🤷‍♂", "❤", "🔥", "🥰", "👏", "😁", "🤔", "🤯", "😱", "🤬", "😢", 
    "🥶", "🤩", "🥳", "😎", "🙏", "👌", "🤣", "😇", "🥱", "🥴", "😍", "🤓", 
    "❤‍🔥", "🌚", "😐", "💯", "🦄", "⚡", "👾", "🏆", "💔", "🤨", "🌟", "😡", 
    "👅", "🆒", "😘", "😈", "😴", "😭", "👻", "🌈", "👨‍💻", "👀", "🎃", "🙄", 
    "🤧", "😨", "🤝", "🤐", "🤗", "🫡", "🤭", "🥸", "🤫", "😶‍🌫", "🤪", "😏"
]
