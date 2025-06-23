from os import environ

API_HASH = environ.get("API_HASH", "8a19a6a007044ff7b41ada4b377cdfba")
API_ID = int(environ.get("API_ID", "27461953"))
BOT_TOKEN = environ.get("BOT_TOKEN", "7978391610:AAE_H6GUjs3kFpwkwitKLnLq2s34EW7fzho")
BOT_OWNER = int(environ.get("BOT_OWNER", "1938030055"))
BOT_USERNAME = environ.get("BOT_USERNAME", "Auto_Post_React_bot")
LOG_CHANNEL = int(environ.get("LOG_CHANNEL", "-1001524622686"))
AUTH_CHANNEL = int(environ.get("AUTH_CHANNEL", "-1001684575211"))
DATABASE_URL = environ.get("DATABASE_URL", "mongodb+srv://soniji:chaloji@cluster0.i5zy74f.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
UPDATE_CHANNEL = environ.get("UPDATE_CHANNEL", "https://t.me/joinnowearn")

# This is no longer needed, as army bots are stored in the database.
# ARMY_BOT_TOKENS = []
