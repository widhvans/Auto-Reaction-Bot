# bot.py

import os
import time
import asyncio
import logging
import traceback
from random import choice
from pyrogram import Client, filters
from pyrogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton, Message,
    LinkPreviewOptions, ForceReply
)
from pyrogram.errors import (
    FloodWait, ReactionInvalid, UserNotParticipant, ChatAdminRequired,
    ChannelPrivate, PeerIdInvalid, AuthKeyUnregistered
)
from database import Database
from config import *

# --- Basic Setup ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler("bot.log"), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

db = Database(DATABASE_URL, BOT_USERNAME)

# --- Global Variables ---
# Main bot client
Bot = Client(
    name="MainReactionBot",
    bot_token=BOT_TOKEN,
    api_id=API_ID,
    api_hash=API_HASH,
    in_memory=True
)

# Dictionary to hold running army bot clients, keyed by bot_id for easy management
army_bots = {}
owner_is_adding_bot = {}


# --- Smart Reaction Manager ---
class ReactionManager:
    def __init__(self):
        self.queue = asyncio.Queue()
        self.rate_limit_delay = 0.5  # Delay between reactions to avoid flood waits

    async def add_reaction_task(self, client, message):
        await self.queue.put((client, message))

    async def process_reactions(self):
        while True:
            client, msg = await self.queue.get()
            try:
                emoji = choice(VALID_EMOJIS)
                await client.send_reaction(msg.chat.id, msg.id, emoji)
                logger.info(f"Reaction '{emoji}' sent by @{client.me.username} to message {msg.id} in chat {msg.chat.id}")
            except FloodWait as e:
                logger.warning(f"Flood wait of {e.value}s for @{client.me.username}. Retrying after sleep.")
                await asyncio.sleep(e.value + 2)
                await self.add_reaction_task(client, msg)  # Re-queue the task
            except ReactionInvalid:
                logger.warning(f"Reaction disabled in chat {msg.chat.id}. Skipping.")
            except Exception as e:
                logger.error(f"Error sending reaction from @{client.me.username}: {e}")
            finally:
                self.queue.task_done()
                await asyncio.sleep(self.rate_limit_delay)

reaction_manager = ReactionManager()


# --- Messages & Keyboards ---
START_TEXT = """<b>{},

ɪ ᴀᴍ sɪᴍᴘʟᴇ ʙᴜᴛ ᴘᴏᴡᴇʀꜰᴜʟʟ ᴀᴜᴛᴏ ʀᴇᴀᴄᴛɪᴏɴ ʙᴏᴛ.

ᴊᴜsᴛ ᴀᴅᴅ ᴍᴇ ᴀs ᴀ ᴀᴅᴍɪɴ ɪɴ ʏᴏᴜʀ ᴄʜᴀɴɴᴇʟ ᴏʀ ɢʀᴏᴜᴘ ᴛʜᴇɴ sᴇᴇ ᴍʏ ᴘᴏᴡᴇʀ</b>"""

def get_start_buttons(user_id):
    buttons = [
        [InlineKeyboardButton(text='🔔 ᴜᴩᴅᴀᴛᴇꜱ', url=UPDATE_CHANNEL)],
    ]
    if user_id == BOT_OWNER:
        buttons.insert(0, [InlineKeyboardButton(text='💂 Manage Army', callback_data='manage_army')])
    return InlineKeyboardMarkup(buttons)


# --- Helper Functions ---
async def is_subscribed(bot, message):
    try:
        await bot.get_chat_member(AUTH_CHANNEL, message.from_user.id)
        return True
    except UserNotParticipant:
        channel_link = (await bot.get_chat(AUTH_CHANNEL)).invite_link
        keyboard = [[InlineKeyboardButton("🔔 Join Our Channel", url=channel_link)]]
        await message.reply(
            "<b>To use me, you must join my updates channel.</b>\n\n"
            "<i>After joining, send /start again!</i>",
            reply_markup=InlineKeyboardMarkup(keyboard),
            link_preview_options=LinkPreviewOptions(is_disabled=True)
        )
        return False
    except Exception as e:
        logger.error(f"FSub Error: {e}")
        return False # Assume not subscribed on error

# --- Bot Handlers ---

@Bot.on_message(filters.private & filters.command("start"))
async def start_command(bot, message):
    user_id = message.from_user.id
    if not await db.is_user_exist(user_id):
        await db.add_user(user_id)
        await bot.send_message(LOG_CHANNEL, f"New User: [{message.from_user.first_name}](tg://user?id={user_id})")

    if not await is_subscribed(bot, message):
        return

    await message.reply_text(
        text=START_TEXT.format(message.from_user.mention),
        reply_markup=get_start_buttons(user_id),
        link_preview_options=LinkPreviewOptions(is_disabled=True)
    )

# --- Owner-Only Army Management ---

@Bot.on_callback_query(filters.regex("^manage_army$") & filters.user(BOT_OWNER))
async def manage_army_callback(bot, query):
    buttons = [[InlineKeyboardButton("➕ Add New Bot", callback_data="add_army_prompt")]]
    current_army = await db.get_all_army_bots()

    if not current_army:
        text = "Your reaction army is empty. Add a bot to get started."
    else:
        text = "<b>💂 Your Reaction Army:</b>\n\n"
        for army_bot in current_army:
            text += f"🤖 @{army_bot['username']}\n"
            buttons.append([
                InlineKeyboardButton(f"➖ Remove @{army_bot['username']}", callback_data=f"remove_army_{army_bot['bot_id']}")
            ])
    
    buttons.append([InlineKeyboardButton("🔙 Back to Start", callback_data="back_to_start")])
    await query.message.edit(text, reply_markup=InlineKeyboardMarkup(buttons))


@Bot.on_callback_query(filters.regex("^add_army_prompt$") & filters.user(BOT_OWNER))
async def add_army_prompt_callback(bot, query):
    owner_is_adding_bot[query.from_user.id] = True
    await query.message.edit(
        "Please send me the **bot token** of the bot you want to add to the army.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🚫 Cancel", callback_data="manage_army")]])
    )


@Bot.on_message(filters.private & filters.text & filters.user(BOT_OWNER))
async def handle_new_bot_token(bot, message):
    owner_id = message.from_user.id
    if owner_is_adding_bot.get(owner_id):
        token = message.text
        del owner_is_adding_bot[owner_id]
        
        if not re.match(r'^\d{8,10}:[a-zA-Z0-9_-]{35}$', token):
            await message.reply("That doesn't look like a valid bot token. Please try again.")
            return

        processing_msg = await message.reply("🔄 Verifying token and adding bot to the army...")
        
        if await db.get_army_bot_by_token(token):
            await processing_msg.edit("❌ This bot is already in your army.")
            return

        try:
            temp_client = Client(name=f"temp_verify_{token[:10]}", bot_token=token, api_id=API_ID, api_hash=API_HASH, in_memory=True)
            await temp_client.start()
            bot_info = await temp_client.get_me()
            await temp_client.stop()

            # Add to DB
            await db.add_army_bot(token, bot_info.id, bot_info.username)

            # Start the bot and add to the running clients
            new_army_bot_client = Client(name=str(bot_info.id), bot_token=token, api_id=API_ID, api_hash=API_HASH, in_memory=True)
            await new_army_bot_client.start()
            army_bots[bot_info.id] = new_army_bot_client
            
            # Add reaction handler for the new bot
            add_reaction_handler(new_army_bot_client)

            await processing_msg.edit(f"✅ Success! @{bot_info.username} has been added to your army and is now active.")
            await manage_army_callback(bot, processing_msg) # Refresh the army list for the owner

        except AuthKeyUnregistered:
             await processing_msg.edit("❌ Error: The bot token has been revoked. Please generate a new one.")
        except Exception as e:
            await processing_msg.edit(f"❌ An error occurred: `{e}`. Could not add the bot.")
            logger.error(f"Failed to add army bot: {e}")


@Bot.on_callback_query(filters.regex(r"^remove_army_(\d+)$") & filters.user(BOT_OWNER))
async def remove_army_callback(bot, query):
    bot_id_to_remove = int(query.data.split("_")[2])
    
    bot_data = await db.get_army_bot_by_id(bot_id_to_remove)
    if not bot_data:
        await query.answer("Bot not found in the database.", show_alert=True)
        return

    # Stop the running client
    if bot_id_to_remove in army_bots:
        try:
            await army_bots[bot_id_to_remove].stop()
            del army_bots[bot_id_to_remove]
            logger.info(f"Stopped and removed running client for bot ID {bot_id_to_remove}")
        except Exception as e:
            logger.error(f"Could not stop bot client {bot_id_to_remove}: {e}")

    # Remove from DB
    await db.remove_army_bot(bot_id_to_remove)
    
    await query.answer(f"@{bot_data['username']} has been removed from your army.", show_alert=True)
    
    # Refresh the list
    await manage_army_callback(bot, query)


@Bot.on_callback_query(filters.regex("^back_to_start$") & filters.user(BOT_OWNER))
async def back_to_start_callback(bot, query):
    await query.message.edit(
        text=START_TEXT.format(query.from_user.mention),
        reply_markup=get_start_buttons(query.from_user.id),
        link_preview_options=LinkPreviewOptions(is_disabled=True)
    )

# --- Reaction Logic ---

def add_reaction_handler(client):
    @client.on_message(filters.group | filters.channel, group=1)
    async def reaction_sender(c, m: Message):
        try:
            # A simple check to see if the bot is in the chat.
            # get_chat_member is heavy, a lighter check might be better if performance is an issue.
            # For now, this ensures it doesn't try to react where it's not present.
            await c.get_chat_member(m.chat.id, "me")
            await reaction_manager.add_reaction_task(c, m)
        except (UserNotParticipant, ChannelPrivate):
            # If bot is removed from a chat, we can optionally handle it here.
            # For now, just log and skip.
            logger.warning(f"@{c.me.username} not in chat {m.chat.id}. Skipping reaction.")
        except Exception as e:
            logger.error(f"Error in reaction handler for @{c.me.username} in chat {m.chat.id}: {e}")

# --- Startup Sequence ---

async def activate_all_bots():
    logger.info("Starting activation sequence for all bots...")
    
    # 1. Start Main Bot
    await Bot.start()
    bot_info = await Bot.get_me()
    logger.info(f"Main Bot @{bot_info.username} started.")
    add_reaction_handler(Bot)

    # 2. Start Army Bots from DB
    army_bots_from_db = await db.get_all_army_bots()
    if not army_bots_from_db:
        logger.warning("No army bots found in the database to activate.")
        return

    logger.info(f"Found {len(army_bots_from_db)} army bots in the database. Activating them...")

    start_tasks = []
    for bot_data in army_bots_from_db:
        try:
            client = Client(
                name=str(bot_data['bot_id']), # Use bot_id as session name
                bot_token=bot_data['token'],
                api_id=API_ID,
                api_hash=API_HASH,
                in_memory=True
            )
            start_tasks.append(client.start())
            army_bots[bot_data['bot_id']] = client # Add to dict before starting
            add_reaction_handler(client)
        except Exception as e:
            logger.error(f"Failed to initialize client for bot @{bot_data['username']}: {e}")
    
    # Start all bots concurrently
    if start_tasks:
        await asyncio.gather(*start_tasks, return_exceptions=True)
        logger.info(f"Successfully started {len(army_bots)} army bots.")

async def main():
    # Start the reaction processing queue in the background
    asyncio.create_task(reaction_manager.process_reactions())
    
    # Activate main bot and all army bots from DB
    await activate_all_bots()
    
    # Keep the bot running
    logger.info("Bot is now online and listening for messages.")
    await asyncio.Future()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot shutting down...")
    except Exception as e:
        logger.critical(f"Bot crashed with a critical error: {e}", exc_info=True)
