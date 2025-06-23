# bot.py

import asyncio
import logging
import traceback
from random import choice
from typing import Dict

from pyrogram import Client, filters, enums
from pyrogram.types import (InlineKeyboardMarkup, InlineKeyboardButton, Message,
                            CallbackQuery)
from pyrogram.errors import (FloodWait, ReactionInvalid, UserNotParticipant,
                             ChatAdminRequired, ChannelPrivate, AuthKeyUnregistered)
from database import Database
from config import *

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Global variables
db = Database(DATABASE_URL, "autoreactionbot")
Bot = Client("AutoReactionBot", bot_token=BOT_TOKEN, api_id=API_ID, api_hash=API_HASH)
ARMY_CLIENTS: Dict[int, Client] = {}  # {bot_id: client_instance}
owner_convo_state: Dict[int, str] = {} # {owner_id: "state"}

VALID_EMOJIS = ["👍", "❤️", "🔥", "🎉", "👏", "🥰", "🤩", "👌", "💯"]
UPDATE_CHANNEL = "https://t.me/joinnowearn"

# --- Reaction Manager for Performance ---
class ReactionManager:
    def __init__(self, num_workers: int = 10):
        self.queue = asyncio.Queue()
        self.num_workers = num_workers
        self.workers = []

    async def start_workers(self):
        self.workers = [asyncio.create_task(self.worker()) for _ in range(self.num_workers)]
        logger.info(f"Started {self.num_workers} reaction workers.")

    async def add_reaction(self, client: Client, message: Message):
        await self.queue.put((client, message))

    async def worker(self):
        while True:
            try:
                client, msg = await self.queue.get()
                emoji = choice(VALID_EMOJIS)
                await client.send_reaction(msg.chat.id, msg.id, emoji)
            except FloodWait as e:
                logger.warning(f"Flood wait of {e.value}s for @{client.me.username}. Retrying...")
                await asyncio.sleep(e.value + 1)
                await self.add_reaction(client, msg)
            except (ReactionInvalid, UserNotParticipant, ChatAdminRequired, ChannelPrivate):
                pass
            except Exception as e:
                logger.error(f"Reaction error by @{client.me.username}: {e}")
            finally:
                self.queue.task_done()

reaction_manager = None

# --- Message Texts & Keyboards ---
START_TEXT = """<b>{},

ɪ ᴀᴍ sɪᴍᴘʟᴇ ʙᴜᴛ ᴘᴏᴡᴇʀꜰᴜʟʟ ᴀᴜᴛᴏ ʀᴇᴀᴄᴛɪᴏɴ ʙᴏᴛ.

ᴊᴜsᴛ ᴀᴅᴅ ᴍᴇ ᴀs ᴀ ᴀᴅᴍɪɴ ɪɴ ʏᴏᴜʀ ᴄʜᴀɴɴᴇʟ ᴏʀ ɢʀᴏᴜᴘ ᴛʜᴇɴ sᴇᴇ ᴍʏ ᴘᴏᴡᴇʀ</b>"""

# >>> नया बटन यहाँ जोड़ा गया है <<<
START_BUTTONS_USER = InlineKeyboardMarkup(
    [
        [InlineKeyboardButton(text='💂 हमारी आर्मी', callback_data='show_army_list')],
        [InlineKeyboardButton(text='🔔 ᴜᴩᴅᴀᴛᴇꜱ', url=UPDATE_CHANNEL)]
    ]
)

START_BUTTONS_OWNER = InlineKeyboardMarkup(
    [
        [InlineKeyboardButton(text='💂 ᴍᴀɴᴀɢᴇ ᴍʏ ᴀʀᴍʏ', callback_data='manage_army')],
        [InlineKeyboardButton(text='📊 ʙᴏᴛ sᴛᴀᴛs', callback_data='stats')],
        [InlineKeyboardButton(text='🔔 ᴜᴩᴅᴀᴛᴇꜱ', url=UPDATE_CHANNEL)]
    ]
)

# --- Helper Functions ---
async def check_fsub(message: Message):
    try:
        await Bot.get_chat_member(AUTH_CHANNEL, message.from_user.id)
        return True
    except UserNotParticipant:
        invite_link = (await Bot.get_chat(AUTH_CHANNEL)).invite_link
        await message.reply(
            "<b>👋 To use me, you must join our Updates Channel.</b>\n\n"
            "This helps us provide continuous service. Please join and try again.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔔 Join Updates Channel", url=invite_link)]]),
            disable_web_page_preview=True
        )
        return False
    except Exception as e:
        logger.error(f"FSUB Error: {e}")
        await message.reply("An error occurred. Please try again later.")
        return False

async def get_stats_text():
    total_users = await db.total_users_count()
    total_army = len(ARMY_CLIENTS)
    return (
        f"📊 **Bot Statistics**\n\n"
        f"👥 **Total Users:** `{total_users}`\n"
        f"💂 **Active Army Bots:** `{total_army}`"
    )

# --- Bot Handlers ---
@Bot.on_message(filters.command("start") & filters.private)
async def start_command(client: Client, message: Message):
    if not await check_fsub(message):
        return

    user_id = message.from_user.id
    if not await db.is_user_exist(user_id):
        await db.add_user(user_id)
        await client.send_message(LOG_CHANNEL, f"New User: [{message.from_user.first_name}](tg://user?id={user_id})")
    
    keyboard = START_BUTTONS_OWNER if user_id == BOT_OWNER else START_BUTTONS_USER
    await message.reply_text(
        text=START_TEXT.format(message.from_user.mention),
        reply_markup=keyboard,
        disable_web_page_preview=True
    )

# >>> यूज़र्स के लिए नया हैंडलर <<<
@Bot.on_callback_query(filters.regex("^show_army_list$"))
async def show_army_list_callback(client: Client, query: CallbackQuery):
    await query.answer()

    army_bots_list = await db.get_all_army_bots()

    if not army_bots_list:
        text = "अभी हमारी आर्मी में कोई बॉट उपलब्ध नहीं है। कृपया बाद में प्रयास करें।"
        keyboard = [[InlineKeyboardButton("⬅️ वापस", callback_data="back_to_user_main")]]
    else:
        text = "<b>💂 हमारी रिएक्शन आर्मी</b>\n\n"
        text += "बेहतर और तेज़ रिएक्शन के लिए, नीचे दिए गए सभी बॉट्स को अपने ग्रुप या चैनल में एडमिन बनाएं।\n\n"
        
        keyboard = []
        for bot in army_bots_list:
            text += f"➥ @{bot['username']}\n"
            keyboard.append([
                InlineKeyboardButton(
                    f"➕ @{bot['username']} को जोड़ें", 
                    url=f"https://t.me/{bot['username']}?startgroup=true"
                )
            ])
        
        keyboard.append([InlineKeyboardButton("⬅️ वापस", callback_data="back_to_user_main")])

    await query.message.edit(
        text=text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        disable_web_page_preview=True
    )

@Bot.on_callback_query(filters.regex("^back_to_user_main$"))
async def back_to_user_main_callback(client: Client, query: CallbackQuery):
    await query.answer()
    await query.message.edit(
        text=START_TEXT.format(query.from_user.mention),
        reply_markup=START_BUTTONS_USER,
        disable_web_page_preview=True
    )

@Bot.on_message(filters.command("stats") & filters.user(BOT_OWNER))
async def stats_command(client: Client, message: Message):
    stats_text = await get_stats_text()
    await message.reply(stats_text)

@Bot.on_message((filters.group | filters.channel))
async def main_bot_reaction_handler(client: Client, message: Message):
    if reaction_manager:
        await reaction_manager.add_reaction(client, message)


# --- Owner & Army Management ---
@Bot.on_callback_query(filters.regex("^stats$") & filters.user(BOT_OWNER))
async def stats_callback(client: Client, query: CallbackQuery):
    stats_text = await get_stats_text()
    await query.message.edit(
        stats_text,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="back_to_owner_main")]])
    )
    await query.answer()

async def get_army_management_keyboard():
    army_bots_list = await db.get_all_army_bots()
    keyboard = []
    for bot in army_bots_list:
        keyboard.append([
            InlineKeyboardButton(f"🤖 @{bot['username']}", url=f"https://t.me/{bot['username']}"),
            InlineKeyboardButton("❌ Remove", callback_data=f"remove_army_{bot['bot_id']}")
        ])
    keyboard.append([InlineKeyboardButton("➕ Add New Bot", callback_data="add_army_prompt")])
    keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="back_to_owner_main")])
    return InlineKeyboardMarkup(keyboard)

@Bot.on_callback_query(filters.regex("^manage_army$") & filters.user(BOT_OWNER))
async def manage_army_callback(client: Client, query: CallbackQuery):
    await query.answer()
    keyboard = await get_army_management_keyboard()
    await query.message.edit(
        "💂 **Army Management**\n\nHere you can add or remove your reaction bots.",
        reply_markup=keyboard
    )

@Bot.on_callback_query(filters.regex("^add_army_prompt$") & filters.user(BOT_OWNER))
async def add_army_prompt_callback(client: Client, query: CallbackQuery):
    await query.answer()
    owner_convo_state[query.from_user.id] = "awaiting_token"
    await query.message.edit(
        "**Please send me the bot token of the bot you want to add to the army.**\n\n"
        "To cancel, press the button below.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✖️ Cancel", callback_data="manage_army")]])
    )

@Bot.on_callback_query(filters.regex(r"^remove_army_(\d+)$") & filters.user(BOT_OWNER))
async def remove_army_callback(client: Client, query: CallbackQuery):
    bot_id_to_remove = int(query.data.split("_")[2])

    if bot_id_to_remove in ARMY_CLIENTS:
        await ARMY_CLIENTS[bot_id_to_remove].stop()
        del ARMY_CLIENTS[bot_id_to_remove]
        logger.info(f"Army bot {bot_id_to_remove} stopped.")

    await db.remove_army_bot(bot_id_to_remove)
    await query.answer("Bot removed successfully!", show_alert=True)
    
    keyboard = await get_army_management_keyboard()
    await query.message.edit(
        "💂 **Army Management**\n\nBot has been removed. Here is the updated list.",
        reply_markup=keyboard
    )

@Bot.on_callback_query(filters.regex("^back_to_owner_main$") & filters.user(BOT_OWNER))
async def back_to_owner_main_callback(client: Client, query: CallbackQuery):
    await query.answer()
    await query.message.edit(
        text=START_TEXT.format(query.from_user.mention),
        reply_markup=START_BUTTONS_OWNER,
        disable_web_page_preview=True
    )

@Bot.on_message(filters.text & filters.private & filters.user(BOT_OWNER))
async def owner_conversation_handler(client: Client, message: Message):
    user_id = message.from_user.id
    if owner_convo_state.get(user_id) == "awaiting_token":
        del owner_convo_state[user_id]
        token = message.text.strip()
        
        if await db.is_army_bot_exist(token=token):
            await message.reply("This bot token is already in the army.")
            return

        processing_msg = await message.reply("⏳ Validating token and adding bot...")
        temp_client = Client("temp_army_add", api_id=API_ID, api_hash=API_HASH, bot_token=token, in_memory=True)
        try:
            await temp_client.start()
            bot_info = await temp_client.get_me()
            await db.add_army_bot(token, bot_info.id, bot_info.username)
            
            await start_single_army_bot(token, bot_info.id, bot_info.username)

            await processing_msg.edit(f"✅ **Success!**\nBot @{bot_info.username} has been added to the army.")
            logger.info(f"Bot @{bot_info.username} (ID: {bot_info.id}) added to army by owner.")
        except AuthKeyUnregistered:
            await processing_msg.edit("❌ **Error:** The provided token has been revoked or is invalid.")
        except Exception as e:
            await processing_msg.edit(f"❌ **An error occurred:** `{e}`")
            logger.error(f"Failed to add new army bot: {e}")
        finally:
            await temp_client.stop()
            keyboard = await get_army_management_keyboard()
            await message.reply("💂 **Army Management**", reply_markup=keyboard)


# --- Army Bot Startup Logic ---
async def army_bot_reaction_handler(client: Client, message: Message):
    if reaction_manager:
        await reaction_manager.add_reaction(client, message)

async def start_single_army_bot(token: str, bot_id: int, username: str):
    from pyrogram.handlers import MessageHandler
    try:
        army_bot_client = Client(
            name=f"army_bot_{bot_id}",
            api_id=API_ID,
            api_hash=API_HASH,
            bot_token=token,
            in_memory=True
        )
        await army_bot_client.start()
        
        army_bot_client.add_handler(
            MessageHandler(army_bot_reaction_handler, (filters.group | filters.channel))
        )
        
        ARMY_CLIENTS[bot_id] = army_bot_client
        logger.info(f"Army bot @{username} started successfully.")
    except Exception as e:
        logger.error(f"Failed to start army bot @{username} (ID: {bot_id}): {e}")
        await db.remove_army_bot(bot_id)
        logger.info(f"Removed faulty army bot @{username} from database.")

async def initialize_army():
    all_army_bots = await db.get_all_army_bots()
    logger.info(f"Found {len(all_army_bots)} bots in the army database. Initializing...")
    tasks = [start_single_army_bot(bot['token'], bot['bot_id'], bot['username']) for bot in all_army_bots]
    await asyncio.gather(*tasks)
    logger.info(f"Army initialization complete. {len(ARMY_CLIENTS)} bots are active.")

# --- Main Execution ---
async def main():
    global reaction_manager
    reaction_manager = ReactionManager()
    await reaction_manager.start_workers()

    logger.info("Starting main bot...")
    await Bot.start()
    bot_info = Bot.me
    logger.info(f"Main bot @{bot_info.username} started!")

    await initialize_army()
    
    logger.info("Bot is now online and listening for updates.")
    await asyncio.Future()

if __name__ == "__main__":
    try:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        logger.info("Bot shutting down...")
    except Exception as e:
        logger.error(f"Bot crashed with an error: {e}")
        logger.error(traceback.format_exc())
