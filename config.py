from os import environ

API_HASH = environ.get("API_HASH", "")
API_ID = int(environ.get("API_ID", ""))
BOT_TOKEN = environ.get("BOT_TOKEN", "")
BOT_OWNER = int(environ.get("BOT_OWNER", ""))
BOT_USERNAME = environ.get("BOT_USERNAME", "QuickReactRobot")
LOG_CHANNEL = int(environ.get("LOG_CHANNEL", ""))
AUTH_CHANNEL = int(environ.get("AUTH_CHANNEL", ""))
DATABASE_URL = environ.get("DATABASE_URL", "")

# Define default emojis list
EMOJIS = [
    "👍", "🤷‍♂", "❤", "🔥", "🥰", "👏", "😁", "🤔", "🤯", "😱", "🤬", "😢", 
    "🥶", "🤩", "🥳", "😎", "🙏", "👌", "🤣", "😇", "🥱", "🥴", "😍", "🤓", 
    "❤‍🔥", "🌚", "😐", "💯", "🦄", "⚡", "👾", "🏆", "💔", "🤨", "🌟", "😡", 
    "👅", "🆒", "😘", "😈", "😴", "😭", "👻", "🌈", "👨‍💻", "👀", "🎃", "🙄", 
    "🤧", "😨", "🤝", "🤐", "🤗", "🫡", "🤭", "🥸", "🤫", "😶‍🌫", "🤪", "😏"
]
