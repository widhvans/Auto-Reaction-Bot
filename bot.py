# bot.py

import asyncio
import logging
from random import choice
from typing import Dict, Union

from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import SessionPasswordNeeded, PhoneCodeInvalid, PhoneCodeExpired
from pyrogram.handlers import MessageHandler, CallbackQueryHandler

from database import Database
from config import *

# Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Globals
db = Database(DATABASE_URL, "autoreactionbot")
Bot = Client("AutoReactionBot", bot_token=BOT_TOKEN, api_id=API_ID, api_hash=API_HASH)
ARMY_CLIENTS: Dict[int, Client] = {}
CONVERSATION_CACHE: Dict[int, Dict[str, Union[str, Client]]] = {}

VALID_EMOJIS = ["👍", "❤️", "🔥", "🎉", "👏", "🥰", "🤩", "👌", "💯"]

# Reaction Manager (इसमें कोई बदलाव नहीं)
class ReactionManager:
    def __init__(self, num_workers: int = 25):
        self.queue = asyncio.Queue()
        self.workers = []
        for _ in range(num_workers):
            self.workers.append(asyncio.create_task(self.worker()))

    async def add_reaction(self, client: Client, message: Message):
        await self.queue.put((client, message))

    async def worker(self):
        while True:
            try:
                client, msg = await self.queue.get()
                emoji = choice(VALID_EMOJIS)
                await client.send_reaction(msg.chat.id, msg.id, emoji)
            except FloodWait as e:
                await asyncio.sleep(e.value + 1)
                await self.add_reaction(client, msg)
            except (ReactionInvalid, UserNotParticipant, ChatAdminRequired):
                pass
            except Exception as e:
                logger.error(f"Reaction error: {e}")
            finally:
                if not self.queue.empty():
                    self.queue.task_done()

reaction_manager = ReactionManager()

# --- इंटरैक्टिव लॉगिन हैंडलर्स ---

async def interactive_login_handler(client: Client, message: Message):
    chat_id = message.chat.id
    if chat_id not in CONVERSATION_CACHE:
        return

    state = CONVERSATION_CACHE[chat_id].get("state")
    temp_client = CONVERSATION_CACHE[chat_id].get("client")
    phone_number = CONVERSATION_CACHE[chat_id].get("phone")

    try:
        if state == "awaiting_code":
            phone_code = message.text.replace("-", "").strip()
            phone_code_hash = CONVERSATION_CACHE[chat_id].get("phone_code_hash")
            await message.reply("⏳ कोड को सत्यापित किया जा रहा है...")
            await temp_client.sign_in(phone_number, phone_code_hash, phone_code)
            # यह अपने आप 2FA के लिए SessionPasswordNeeded एरर देगा
            me = await temp_client.get_me()
            await finalize_login(message, temp_client, me)

        elif state == "awaiting_password":
            password = message.text.strip()
            await message.reply("⏳ पासवर्ड की जाँच की जा रही है...")
            await temp_client.check_password(password)
            me = await temp_client.get_me()
            await finalize_login(message, temp_client, me)

    except SessionPasswordNeeded:
        CONVERSATION_CACHE[chat_id]["state"] = "awaiting_password"
        await message.reply("यह अकाउंट 2-Step Verification से सुरक्षित है। कृपया अपना पासवर्ड भेजें।")
    except (PhoneCodeInvalid, PhoneCodeExpired):
        await message.reply("❌ भेजा गया कोड गलत या एक्सपायर हो गया है। कृपया फिर से प्रयास करें।")
        del CONVERSATION_CACHE[chat_id]
    except Exception as e:
        await message.reply(f"❌ एक त्रुटि हुई: {e}")
        logger.error(f"Login Error: {e}")
        del CONVERSATION_CACHE[chat_id]
        if temp_client.is_connected:
            await temp_client.disconnect()


async def finalize_login(message: Message, temp_client: Client, me):
    await db.add_army_account(me.id, me.first_name)
    session_file_name = f"army_user_{me.id}"
    
    # Save session file and stop client
    # Pyrogram v2+ automatically saves session on successful login when name is provided
    await temp_client.stop()
    
    # Start the user account to add to running army
    await start_single_army_user(me.id, me.first_name)
    
    await message.reply(f"✅ **सफलता!**\nअकाउंट **{me.first_name}** आर्मी में सफलतापूर्वक जोड़ दिया गया है।")
    del CONVERSATION_CACHE[message.chat.id]


# --- मुख्य बॉट के कमांड्स और बटन्स ---

@Bot.on_message(filters.command("start") & filters.private)
async def start_command(client, message):
    # ... (यह फंक्शन पहले जैसा ही रहेगा)
    user_id = message.from_user.id
    # ... (बाकी का कोड)
    
@Bot.on_callback_query(filters.regex("^add_army_prompt$") & filters.user(BOT_OWNER))
async def add_army_prompt(client: Client, query: CallbackQuery):
    chat_id = query.from_user.id
    CONVERSATION_CACHE[chat_id] = {"state": "awaiting_phone"}
    await query.message.edit(
        "**आर्मी में नया यूज़र अकाउंट जोड़ने के लिए, कृपया उस अकाउंट का फ़ोन नंबर कंट्री कोड के साथ भेजें।**\n\n"
        "उदाहरण: `+919876543210`\n\n"
        "कैंसिल करने के लिए /cancel टाइप करें।"
    )

@Bot.on_message(filters.private & filters.user(BOT_OWNER) & filters.text)
async def owner_message_handler(client, message):
    chat_id = message.from_user.id
    if chat_id not in CONVERSATION_CACHE:
        # अगर कोई कन्वर्सेशन नहीं चल रही है तो कुछ न करें
        return

    state = CONVERSATION_CACHE[chat_id].get("state")

    if message.text == "/cancel":
        del CONVERSATION_CACHE[chat_id]
        await message.reply("प्रक्रिया रद्द कर दी गई है।")
        return

    if state == "awaiting_phone":
        phone_number = message.text.strip()
        await message.reply(f"⏳ `{phone_number}` के लिए OTP भेजा जा रहा है...")
        
        # यूनीक नाम के साथ एक अस्थायी क्लाइंट बनाएं
        temp_client = Client(name=f"army_user_{phone_number}", api_id=API_ID, api_hash=API_HASH)
        
        try:
            await temp_client.connect()
            sent_code = await temp_client.send_code(phone_number)
            
            CONVERSATION_CACHE[chat_id].update({
                "state": "awaiting_code",
                "phone": phone_number,
                "client": temp_client,
                "phone_code_hash": sent_code.phone_code_hash
            })
            await message.reply(
                "आपके नंबर पर एक कोड भेजा गया है। कृपया वह कोड भेजें।\n"
                "अगर कोड डैश के साथ आता है, तो उसे वैसे ही भेजें (जैसे `1-2-3-4-5`)।"
            )
        except Exception as e:
            await message.reply(f"❌ फ़ोन नंबर भेजने में त्रुटि: {e}")
            logger.error(f"Send code error: {e}")
            del CONVERSATION_CACHE[chat_id]
            await temp_client.disconnect()
    
    # बाकी के राज्यों को interactive_login_handler हैंडल करेगा
    else:
        await interactive_login_handler(client, message)


# आर्मी मैनेजमेंट के बाकी बटन्स... (get_army_management_keyboard, remove_army_callback, etc.)
# ये फंक्शन पहले जैसे ही रहेंगे, बस bot की जगह account का इस्तेमाल करें

async def start_single_army_user(user_id: int, first_name: str):
    session_name = f"army_user_{user_id}"
    try:
        user_client = Client(name=session_name, api_id=API_ID, api_hash=API_HASH)
        await user_client.start()
        
        user_client.add_handler(MessageHandler(army_user_reaction_handler, filters.group | filters.channel))
        ARMY_CLIENTS[user_id] = user_client
        logger.info(f"Army user account '{first_name}' (ID: {user_id}) started from session file.")
    except Exception as e:
        logger.error(f"Failed to start army user {first_name}: {e}")
        await db.remove_army_account(user_id)

async def initialize_army():
    all_accounts = await db.get_all_army_accounts()
    logger.info(f"Found {len(all_accounts)} user accounts. Initializing...")
    for acc in all_accounts:
        await start_single_army_user(acc['user_id'], acc['first_name'])
    logger.info(f"Army initialization complete. {len(ARMY_CLIENTS)} accounts active.")


async def main():
    await Bot.start()
    logger.info("Main command bot started.")
    
    await initialize_army()
    
    logger.info("Bot is fully online.")
    await asyncio.Future()

if __name__ == "__main__":
    Bot.add_handler(CallbackQueryHandler(add_army_prompt, filters.regex("^add_army_prompt$") & filters.user(BOT_OWNER)))
    # ... बाकी सभी handler यहाँ जोड़ें ...
    
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(main())
        else:
            loop.run_until_complete(main())
    except KeyboardInterrupt:
        logger.info("Bot shutting down...")
    except Exception as e:
        logger.error(f"Bot crashed: {e}", exc_info=True)
