import os
import time
import asyncio
import logging
import traceback
from random import choice
from pyrogram import Client, filters, idle
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, LinkPreviewOptions, ForceReply
from pyrogram.errors import FloodWait, ReactionInvalid, UserNotParticipant, ChatAdminRequired, ChannelPrivate, PeerIdInvalid, RPCError, UserIsBlocked, BotMethodInvalid
from pyrogram.raw.functions.messages import GetMessagesViews
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

# Database initialization
db = Database(DATABASE_URL, BOT_USERNAME)

# Main Bot Client
Bot = Client(
    name="AutoReactionBot",
    bot_token=BOT_TOKEN,
    api_id=API_ID,
    api_hash=API_HASH,
    in_memory=True
)

# In-memory storage for army bots and conversation state
army_bots = {}
user_conversations = {}

# Emojis for reactions
VALID_EMOJIS = ["👍", "❤️", "🔥", "�", "👏", "🥰", "🤩", "💯", "👌", "🕊️", "🙏"]

# A semaphore to limit concurrent reactions
REACTION_SEMAPHORE = asyncio.Semaphore(20) # Limit to 20 concurrent reactions to avoid flooding

class ReactionManager:
    """
    Manages the reaction queue and processing to handle high loads gracefully.
    """
    def __init__(self):
        self.queue = asyncio.Queue()

    async def add_reaction_task(self, client, chat_id, message_id):
        """Adds a reaction task to the queue."""
        await self.queue.put((client, chat_id, message_id))

    async def _process_single_reaction(self, client, chat_id, message_id):
        """Sends a single reaction and handles potential errors."""
        async with REACTION_SEMAPHORE:
            try:
                emoji = choice(VALID_EMOJIS)
                await client.send_reaction(chat_id, message_id, emoji)
                logger.info(f"Reaction '{emoji}' sent by {client.me.username} to message {message_id} in chat {chat_id}")
                await asyncio.sleep(1) # Small delay to be gentle on Telegram API
            except FloodWait as e:
                logger.warning(f"Flood wait of {e.value}s for {client.me.username} in chat {chat_id}. Retrying after wait.")
                await asyncio.sleep(e.value + 2)
                await self.add_reaction_task(client, chat_id, message_id) # Re-add to queue
            except (ReactionInvalid, PeerIdInvalid):
                logger.warning(f"Invalid reaction or peer ID for message {message_id} in chat {chat_id}. Skipping.")
            except Exception as e:
                logger.error(f"An unexpected error occurred for {client.me.username} in chat {chat_id}: {e}")

    async def process_reactions(self):
        """Continuously processes reactions from the queue."""
        while True:
            try:
                client, chat_id, message_id = await self.queue.get()
                asyncio.create_task(self._process_single_reaction(client, chat_id, message_id))
                self.queue.task_done()
            except Exception as e:
                logger.error(f"Error in reaction processing loop: {e}")


reaction_manager = ReactionManager()

# --- Bot Owner Commands & Handlers ---

async def get_owner_start_buttons():
    """Returns the start buttons for the bot owner."""
    army_bots_count = await db.get_army_bots_count(BOT_OWNER)
    buttons = [
        [InlineKeyboardButton(text='➕ ᴀᴅᴅ ʙᴏᴛ ᴛᴏ ᴀʀᴍʏ', callback_data='add_army_bot')],
        [InlineKeyboardButton(text=f'💂 ᴍʏ ᴀʀᴍʏ ({army_bots_count})', callback_data='my_army_bots')],
        [InlineKeyboardButton(text='📊 ʙᴏᴛ sᴛᴀᴛs', callback_data='bot_stats')],
        [InlineKeyboardButton(text='📢 ʙʀᴏᴀᴅᴄᴀsᴛ', callback_data='broadcast')],
        [InlineKeyboardButton(text='🔔 ᴜᴩᴅᴀᴛᴇꜱ', url=UPDATE_CHANNEL)]
    ]
    return InlineKeyboardMarkup(buttons)

@Bot.on_callback_query(filters.regex("add_army_bot") & filters.user(BOT_OWNER))
async def add_army_bot_callback(bot, query):
    """Handles the 'Add Bot to Army' button click."""
    user_id = query.from_user.id
    user_conversations[user_id] = "adding_army_bot"
    await query.message.reply_text(
        "Please send me the bot token of the bot you want to add to your army.",
        reply_markup=ForceReply(placeholder="Enter Bot Token...")
    )
    await query.answer("Please send the bot token.")

@Bot.on_callback_query(filters.regex("my_army_bots") & filters.user(BOT_OWNER))
async def my_army_bots_callback(bot, query):
    """Displays the list of army bots to the owner."""
    army = await db.get_army_bots(BOT_OWNER)
    if not army:
        await query.answer("You haven't added any bots to your army yet.", show_alert=True)
        return

    text = "🛡️ **Your Bot Army:**\n\n"
    buttons = []
    for bot_doc in army:
        text += f"🤖 @{bot_doc['bot_username']}\n"
        buttons.append([InlineKeyboardButton(f"❌ Remove @{bot_doc['bot_username']}", f"remove_army_{bot_doc['bot_id']}")])
    
    buttons.append([InlineKeyboardButton("🔙 Back", "back_to_start")])
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))
    await query.answer()

@Bot.on_callback_query(filters.regex(r"^remove_army_") & filters.user(BOT_OWNER))
async def remove_army_bot_callback(bot, query):
    """Removes a bot from the army."""
    bot_id_to_remove = int(query.data.split("_")[2])
    
    # Stop the bot if it's running
    if bot_id_to_remove in army_bots:
        try:
            await army_bots[bot_id_to_remove].stop()
            del army_bots[bot_id_to_remove]
            logger.info(f"Successfully stopped and removed bot ID {bot_id_to_remove} from running instances.")
        except Exception as e:
            logger.error(f"Error stopping bot ID {bot_id_to_remove}: {e}")

    # Remove from database
    await db.remove_army_bot(BOT_OWNER, bot_id_to_remove)
    
    await query.answer("Bot removed from your army successfully!", show_alert=True)
    
    # Refresh the army list view
    await my_army_bots_callback(bot, query)


# --- General User Commands & Handlers ---

START_TEXT = """<b>{},

ɪ ᴀᴍ sɪᴍᴘʟᴇ ʙᴜᴛ ᴘᴏᴡᴇʀꜰᴜʟʟ ᴀᴜᴛᴏ ʀᴇᴀᴄᴛɪᴏɴ ʙᴏᴛ.

ᴊᴜsᴛ ᴀᴅᴅ ᴍᴇ ᴀs ᴀ ᴀᴅᴍɪɴ ɪɴ ʏᴏᴜʀ ᴄʜᴀɴɴᴇʟ ᴏʀ ɢʀᴏᴜᴘ ᴛʜᴇɴ sᴇᴇ ᴍʏ ᴘᴏᴡᴇʀ</b>"""

START_BUTTONS = InlineKeyboardMarkup(
    [
        [InlineKeyboardButton(text='🔔 ᴜᴩᴅᴀᴛᴇꜱ', url=UPDATE_CHANNEL)],
        [InlineKeyboardButton(text='➕ Add Me To Your Group', url=f"https://t.me/{BOT_USERNAME}?startgroup=true")]
    ]
)

@Bot.on_message(filters.private & filters.command(["start"]))
async def start_command(bot, message):
    """Handles the /start command."""
    user_id = message.from_user.id
    
    if not await db.is_user_exist(user_id):
        await db.add_user(user_id)
        await bot.send_message(LOG_CHANNEL, f"New User: [{message.from_user.first_name}](tg://user?id={user_id})")

    if user_id == BOT_OWNER:
        buttons = await get_owner_start_buttons()
        await message.reply_text(f"Welcome, Owner! Here are your controls:", reply_markup=buttons)
    else:
        await message.reply_text(
            text=START_TEXT.format(message.from_user.mention),
            reply_markup=START_BUTTONS,
            link_preview_options=LinkPreviewOptions(is_disabled=True)
        )

@Bot.on_callback_query(filters.regex("back_to_start") & filters.user(BOT_OWNER))
async def back_to_start_callback(bot, query):
    """Handles the back button to the owner's start menu."""
    buttons = await get_owner_start_buttons()
    await query.message.edit_text("Welcome, Owner! Here are your controls:", reply_markup=buttons)
    await query.answer()

# --- Message Handlers for Conversation ---

@Bot.on_message(filters.private & filters.text & ~filters.command("start"))
async def private_message_handler(bot, message):
    """Handles incoming text messages in private chat for conversations."""
    user_id = message.from_user.id
    if user_id == BOT_OWNER and user_conversations.get(user_id) == "adding_army_bot":
        await handle_add_army_bot(bot, message)
    elif user_id == BOT_OWNER and user_conversations.get(user_id) == "broadcast":
        await handle_broadcast_message(bot, message)
    else:
        await message.reply_text("I'm a reaction bot. Add me to a group or channel to see me in action!")


async def handle_add_army_bot(bot, message):
    """Logic to handle adding a new army bot."""
    user_id = message.from_user.id
    token = message.text
    processing_msg = await message.reply("Verifying token and adding bot to your army...")

    try:
        temp_client = Client(name=f"temp_army_{token[:10]}", bot_token=token, api_id=API_ID, api_hash=API_HASH, in_memory=True)
        await temp_client.start()
        bot_info = await temp_client.get_me()
        await temp_client.stop()

        bot_id = bot_info.id
        bot_username = bot_info.username

        if await db.is_army_bot_exist(BOT_OWNER, bot_id):
            await processing_msg.edit(f"❌ This bot (@{bot_username}) is already in your army.")
            return

        await db.add_army_bot(BOT_OWNER, bot_id, token, bot_username)
        await processing_msg.edit(f"✅ Success! @{bot_username} has been added to your army.")
        
        # Start the new bot immediately
        await start_single_army_bot({'bot_id': bot_id, 'token': token, 'bot_username': bot_username})

    except (RPCError, BotMethodInvalid) as e:
        await processing_msg.edit(f"❌ Failed to add bot. The provided token is invalid or expired. Please check and try again.\n\n`Error: {e}`")
    except Exception as e:
        await processing_msg.edit(f"❌ An unexpected error occurred: {e}")
        logger.error(f"Failed to add army bot: {e}\n{traceback.format_exc()}")
    finally:
        if user_id in user_conversations:
            del user_conversations[user_id]


# --- Main Reaction Logic ---

@Bot.on_message(filters.group | filters.channel, group=-1)
async def main_bot_reaction(client, message: Message):
    """Main handler for reacting to new messages in groups/channels."""
    # React with the main bot
    await reaction_manager.add_reaction_task(client, message.chat.id, message.id)

    # React with all army bots
    for bot_id, army_client in army_bots.items():
        if army_client.is_connected:
            await reaction_manager.add_reaction_task(army_client, message.chat.id, message.id)


# --- Bot Stats and Broadcast ---

@Bot.on_callback_query(filters.regex("bot_stats") & filters.user(BOT_OWNER))
async def stats_callback(bot, query):
    """Shows bot statistics to the owner."""
    try:
        total_users = await db.total_users_count()
        army_bots_count = await db.get_army_bots_count(BOT_OWNER)
        
        text = (
            f"📊 **Bot Statistics**\n\n"
            f"👥 **Total Users:** `{total_users}`\n"
            f"💂 **Your Army Bots:** `{army_bots_count}`"
        )
        await query.answer(text, show_alert=True)
    except Exception as e:
        logger.error(f"Error in stats_callback: {e}")
        await query.answer("❌ An error occurred while fetching stats.", show_alert=True)


@Bot.on_callback_query(filters.regex("broadcast") & filters.user(BOT_OWNER))
async def broadcast_callback(bot, query):
    """Initiates the broadcast process."""
    user_id = query.from_user.id
    user_conversations[user_id] = "broadcast"
    await query.message.reply_text(
        "Please send the message you want to broadcast to all users.",
        reply_markup=ForceReply(placeholder="Enter broadcast message...")
    )
    await query.answer("Please send the message to broadcast.")

async def handle_broadcast_message(bot, message):
    """Handles the actual broadcast logic."""
    user_id = message.from_user.id
    processing_msg = await message.reply_text("Broadcasting... this may take a while.")
    
    all_users = await db.get_all_users()
    total_users = await db.total_users_count()
    success_count = 0
    failed_count = 0
    start_time = time.time()

    for user in all_users:
        try:
            await message.copy(chat_id=user['id'])
            success_count += 1
            await asyncio.sleep(0.1) # 10 messages per second
        except FloodWait as e:
            await asyncio.sleep(e.value)
            await message.copy(chat_id=user['id']) # Retry
            success_count += 1
        except UserIsBlocked:
            failed_count += 1
        except Exception:
            failed_count += 1
    
    end_time = time.time()
    duration = round(end_time - start_time)
    
    result_text = (
        f"📢 **Broadcast Complete!**\n\n"
        f"✅ **Sent to:** `{success_count}` users\n"
        f"❌ **Failed for:** `{failed_count}` users\n"
        f"👥 **Total users:** `{total_users}`\n"
        f"⏱️ **Duration:** `{duration}` seconds"
    )
    await processing_msg.edit(result_text)
    
    if user_id in user_conversations:
        del user_conversations[user_id]


# --- Army Bot Management ---

async def army_bot_reaction_handler(client, message: Message):
    """Common reaction handler for all army bots."""
    try:
        # A simple check to see if the bot is a member.
        # This reduces API calls compared to get_chat_member on every message.
        await client.send_chat_action(message.chat.id, "typing")
        await reaction_manager.add_reaction_task(client, message.chat.id, message.id)
    except (UserNotParticipant, ChannelPrivate):
        logger.info(f"Army bot @{client.me.username} left or was removed from {message.chat.id}. No longer reacting.")
        # Optionally, you can add logic here to remove the bot from the DB if it's kicked.
    except Exception as e:
        logger.error(f"Error in army bot @{client.me.username} reaction: {e}")

async def start_single_army_bot(bot_doc):
    """Starts and configures a single army bot."""
    bot_id = bot_doc['bot_id']
    token = bot_doc['token']
    username = bot_doc['bot_username']
    
    if bot_id in army_bots:
        logger.info(f"Bot @{username} is already running.")
        return

    try:
        army_client = Client(name=f"army_{username}", bot_token=token, api_id=API_ID, api_hash=API_HASH, in_memory=True)
        await army_client.start()
        army_client.add_handler(MessageHandler(army_bot_reaction_handler, filters.group | filters.channel))
        army_bots[bot_id] = army_client
        logger.info(f"✅ Army bot started successfully: @{username}")
    except Exception as e:
        logger.error(f"❌ Failed to start army bot @{username}: {e}. Removing from DB.")
        await db.remove_army_bot(BOT_OWNER, bot_id)

async def activate_all_army_bots():
    """Starts all army bots from the database on main bot startup."""
    logger.info("Activating all bots from the Bot Army...")
    army = await db.get_army_bots(BOT_OWNER)
    for bot_doc in army:
        await start_single_army_bot(bot_doc)
    logger.info("All army bots have been activated.")


async def main():
    """The main function to start the bot and all its components."""
    await Bot.start()
    logger.info("Main Bot has started!")
    
    asyncio.create_task(reaction_manager.process_reactions())
    logger.info("Reaction processing task has started.")
    
    await activate_all_army_bots()
    
    logger.info("Bot is now fully operational. Press Ctrl+C to stop.")
    await idle()
    
    # Stop all bots on shutdown
    await Bot.stop()
    for client in army_bots.values():
        await client.stop()
    logger.info("All bots have been stopped.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot shutdown requested.")
�
