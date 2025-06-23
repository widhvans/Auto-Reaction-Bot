import os
import time
import asyncio
import logging
import traceback
from random import choice
from pyrogram import Client, filters, enums
from pyrogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton, Message,
    CallbackQuery  # LinkPreviewOptions removed from here
)
from pyrogram.errors import (
    FloodWait, ReactionInvalid, UserNotParticipant,
    ChatAdminRequired, ChannelPrivate, PeerIdInvalid,
    AuthKeyUnregistered, UserDeactivated, BotMethodInvalid
)
from database import Database
from config import *

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Bot and Database initialization
db = Database(DATABASE_URL, BOT_USERNAME)
Bot = Client(
    name="AutoReactionBot",
    bot_token=BOT_TOKEN,
    api_id=API_ID,
    api_hash=API_HASH
)

# In-memory storage for running army bot clients
army_bots = {} # Dictionary to store client instances {bot_id: client}
owner_conversation_state = {}

# Reaction Emojis
VALID_EMOJIS = ["👍", "❤️", "🔥", "🎉", "👏", "😁", "🤩", "💯", "🙏", "🕊️"]

# Reaction Manager (for handling high load)
class ReactionManager:
    def __init__(self):
        self.queue = asyncio.Queue()
        self.rate_limits = {}
        self.reactions_per_second = 10 # More realistic rate limit

    async def add_reaction_task(self, client, msg):
        await self.queue.put((client, msg))

    async def process_reactions(self):
        while True:
            try:
                client, msg = await self.queue.get()
                chat_id = msg.chat.id
                current_time = time.time()

                # Rate limiting per chat
                if chat_id not in self.rate_limits:
                    self.rate_limits[chat_id] = []
                
                self.rate_limits[chat_id] = [t for t in self.rate_limits[chat_id] if current_time - t < 1]

                if len(self.rate_limits[chat_id]) >= self.reactions_per_second:
                    await asyncio.sleep(1) # Wait if we are exceeding the rate limit

                try:
                    emoji = choice(VALID_EMOJIS)
                    await client.send_reaction(chat_id, msg.id, emoji)
                    logger.info(f"Reaction '{emoji}' by @{client.me.username} in chat {chat_id}")
                    self.rate_limits[chat_id].append(time.time())
                except FloodWait as e:
                    logger.warning(f"Flood wait of {e.value}s for @{client.me.username} in chat {chat_id}.")
                    await asyncio.sleep(e.value + 1)
                    await self.add_reaction_task(client, msg) # Re-add to queue
                except (ReactionInvalid, PeerIdInvalid):
                    logger.warning(f"Invalid reaction or peer in chat {chat_id}. Skipping.")
                except Exception as e:
                    logger.error(f"Error sending reaction in {chat_id}: {e}")
            except Exception as e:
                logger.error(f"Error in reaction processor: {e}")
            finally:
                self.queue.task_done()

reaction_manager = ReactionManager()

# --- Message Texts and Keyboards ---
START_TEXT = """<b>Hi {},

I am a simple but powerful auto-reaction bot.

Just add me as an admin in your channel or group, then see my power!</b>"""

OWNER_START_TEXT = """<b>Welcome, Owner! 👑</b>

You have access to special commands to manage your reaction army."""

# Buttons
START_BUTTONS = InlineKeyboardMarkup(
    [[InlineKeyboardButton(text='🔔 Updates', url=UPDATE_CHANNEL)]]
)
OWNER_START_BUTTONS = InlineKeyboardMarkup(
    [
        [InlineKeyboardButton(text='💂 My Army', callback_data='my_army')],
        [InlineKeyboardButton(text='🔔 Updates', url=UPDATE_CHANNEL)]
    ]
)

# --- Helper Functions ---
async def is_subscribed(bot, message):
    try:
        await bot.get_chat_member(AUTH_CHANNEL, message.from_user.id)
        return True
    except UserNotParticipant:
        invite_link = None
        try:
            # Try to get invite link
            chat = await bot.get_chat(AUTH_CHANNEL)
            if chat.invite_link:
                invite_link = chat.invite_link
            else:
                 # If no invite link, create one
                 invite_link = await bot.export_chat_invite_link(AUTH_CHANNEL)
        except Exception as e:
            logger.error(f"Could not get/create invite link for {AUTH_CHANNEL}: {e}")
            await message.reply("Sorry, there was an error. Please try again later.")
            return False

        buttons = [[InlineKeyboardButton("🔔 Join Channel", url=invite_link)]]
        await message.reply(
            "You must join my updates channel to use me!",
            reply_markup=InlineKeyboardMarkup(buttons),
            disable_web_page_preview=True  # <-- THE FIX IS HERE
        )
        return False
    except Exception as e:
        logger.error(f"Subscription check failed: {e}")
        # Inform user about the issue
        await message.reply("Sorry, I couldn't check if you are a member of the updates channel. Please try again.")
        return False

# --- Bot Owner Commands ---
@Bot.on_message(filters.private & filters.command("start"))
async def start_command(bot, message):
    if not await is_subscribed(bot, message):
        return

    user_id = message.from_user.id
    if not await db.is_user_exist(user_id):
        await db.add_user(user_id)
        await bot.send_message(LOG_CHANNEL, f"New User: [{message.from_user.first_name}](tg://user?id={user_id})")

    if user_id == BOT_OWNER:
        await message.reply_text(OWNER_START_TEXT, reply_markup=OWNER_START_BUTTONS)
    else:
        await message.reply_text(START_TEXT.format(message.from_user.mention), reply_markup=START_BUTTONS)

@Bot.on_callback_query(filters.regex("^my_army$"))
async def my_army_callback(bot, query: CallbackQuery):
    if query.from_user.id != BOT_OWNER:
        return await query.answer("This is for the owner only!", show_alert=True)

    army = await db.get_all_army_bots()
    if not army:
        text = "Your army is empty. Add a bot to get started."
        buttons = [[InlineKeyboardButton("➕ Add Bot", callback_data="add_bot")]]
    else:
        text = "Here is your reaction army:"
        buttons = []
        for bot_info in army:
            buttons.append([
                InlineKeyboardButton(f"@{bot_info['username']}", url=f"https://t.me/{bot_info['username']}"),
                InlineKeyboardButton("➖ Remove", callback_data=f"remove_bot_{bot_info['bot_id']}")
            ])
        buttons.append([InlineKeyboardButton("➕ Add Another Bot", callback_data="add_bot")])

    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))

@Bot.on_callback_query(filters.regex("^add_bot$"))
async def add_bot_callback(bot, query: CallbackQuery):
    if query.from_user.id != BOT_OWNER:
        return await query.answer("This is for the owner only!", show_alert=True)
    
    owner_conversation_state[BOT_OWNER] = "awaiting_token"
    await query.message.edit_text("Please send me the bot token of the bot you want to add to your army.")

@Bot.on_callback_query(filters.regex(r"^remove_bot_(\d+)"))
async def remove_bot_callback(bot, query: CallbackQuery):
    if query.from_user.id != BOT_OWNER:
        return await query.answer("This is for the owner only!", show_alert=True)

    bot_id_to_remove = int(query.matches[0].group(1))

    # Stop the bot client if it's running
    if bot_id_to_remove in army_bots:
        try:
            await army_bots[bot_id_to_remove].stop()
            del army_bots[bot_id_to_remove]
            logger.info(f"Successfully stopped and removed bot client: {bot_id_to_remove}")
        except Exception as e:
            logger.error(f"Could not stop bot {bot_id_to_remove}: {e}")

    # Remove from database
    await db.remove_army_bot(bot_id_to_remove)
    await query.answer("Bot removed from your army.", show_alert=True)
    
    # Refresh the army list
    await my_army_callback(bot, query)

@Bot.on_message(filters.private & filters.text & ~filters.command("start"))
async def private_message_handler(bot, message):
    user_id = message.from_user.id
    if user_id == BOT_OWNER and owner_conversation_state.get(user_id) == "awaiting_token":
        token = message.text.strip()
        del owner_conversation_state[user_id]
        
        processing_msg = await message.reply("Validating token and adding bot...")

        try:
            # Check if bot exists with this token already
            temp_client = Client(name=f"temp_{token[:10]}", bot_token=token, api_id=API_ID, api_hash=API_HASH, in_memory=True)
            await temp_client.start()
            
            bot_info = await temp_client.get_me()
            bot_id = bot_info.id
            username = bot_info.username

            if await db.is_army_bot_exist(bot_id):
                await processing_msg.edit(f"❌ This bot (@{username}) is already in your army.")
                await temp_client.stop()
                return

            # Add to DB and start the bot
            await db.add_army_bot(token, bot_id, username)
            army_bots[bot_id] = temp_client
            register_army_bot_handlers(temp_client, username) # Register handlers for the new bot
            
            await processing_msg.edit(f"✅ Success! @{username} has been added to your army and is now active.")
            logger.info(f"Owner added new army bot: @{username} (ID: {bot_id})")

        except (AuthKeyUnregistered, UserDeactivated):
            await processing_msg.edit("❌ Invalid Token: The provided bot token has been revoked or deleted.")
        except Exception as e:
            await processing_msg.edit(f"❌ An error occurred: {e}")
            logger.error(f"Failed to add army bot: {e}")
    else:
        # Handle other private messages or forward to owner if desired
        await bot.send_message(
            chat_id=message.chat.id,
            text="Add me to a channel or group as admin to get reactions."
        )


# --- Universal Reaction Handler ---
async def reaction_sender(client, message: Message):
    try:
        await reaction_manager.add_reaction_task(client, message)
    except (ChatAdminRequired, ChannelPrivate):
        logger.warning(f"Bot @{client.me.username} is not an admin in {message.chat.id}, can't react.")
    except Exception as e:
        if "RIGHT_FORBIDDEN" in str(e): 
             logger.warning(f"Bot @{client.me.username} lacks permission in {message.chat.id}.")
        else:
             logger.error(f"Reaction error for @{client.me.username} in {message.chat.id}: {e}")

# Register handler for the main bot
@Bot.on_message((filters.group | filters.channel) & filters.incoming & ~filters.service)
async def main_bot_react(client, message: Message):
    await reaction_sender(client, message)

# Function to register handlers for army bots
def register_army_bot_handlers(client, username):
    @client.on_message((filters.group | filters.channel) & filters.incoming & ~filters.service)
    async def army_bot_react(_, message: Message):
        await reaction_sender(client, message)
    
    logger.info(f"Handlers registered for army bot @{username}")


# --- Bot Startup ---
async def start_all_bots():
    # Start the main bot
    await Bot.start()
    bot_info = await Bot.get_me()
    logger.info(f"Main bot @{bot_info.username} started!")

    # Start all army bots from the database
    all_army_bots = await db.get_all_army_bots()
    for bot_data in all_army_bots:
        bot_id = bot_data['bot_id']
        token = bot_data['token']
        username = bot_data['username']
        try:
            client = Client(name=f"army_bot_{bot_id}", bot_token=token, api_id=API_ID, api_hash=API_HASH, in_memory=True)
            await client.start()
            army_bots[bot_id] = client
            register_army_bot_handlers(client, username)
            logger.info(f"Army bot @{username} started successfully.")
        except (AuthKeyUnregistered, UserDeactivated):
             logger.error(f"Failed to start army bot @{username} due to invalid token. Removing from DB.")
             await db.remove_army_bot(bot_id)
        except Exception as e:
            logger.error(f"Failed to start army bot @{username} (ID: {bot_id}). Error: {e}")
            
async def main():
    logger.info("Starting Auto Reaction Bot service...")
    # Start the reaction processing queue in the background
    asyncio.create_task(reaction_manager.process_reactions())
    
    # Start the main bot and all saved army bots
    await start_all_bots()
    
    logger.info("All bots are running. Bot is now online.")
    await asyncio.Future() # Keep the script running

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Service stopped by user.")
    except Exception as e:
        logger.critical(f"Critical error in main loop: {e}", exc_info=True)
