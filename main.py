import os
import time
import asyncio
import datetime
import aiofiles
import logging
import traceback
from random import choice
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, LinkPreviewOptions
from pyrogram.errors import FloodWait, ReactionInvalid, UserNotParticipant, ChatAdminRequired, ChannelPrivate, PeerIdInvalid
from database import Database
from config import *

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(pathname)s:%(lineno)d - %(message)s',
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Database initialization
db = Database(DATABASE_URL, "autoreactionbot")
logger.info("Database initialized")

# Bot setup with in-memory storage
Bot = Client(
    name="AutoReactionBot",
    bot_token=BOT_TOKEN,
    api_id=API_ID,
    api_hash=API_HASH,
    in_memory=True
)

# Army bot clients
army_bots = []
valid_army_bots = []
for i, token in enumerate(ARMY_BOT_TOKENS):
    if token:
        army_bot = Client(
            name=f"army_bot_{i+1}",
            bot_token=token,
            api_id=API_ID,
            api_hash=API_HASH,
            in_memory=True
        )
        army_bots.append((army_bot, token))

# Positive Telegram reaction emojis only
VALID_EMOJIS = ["👍", "❤️", "🔥", "🎉", "👏"]

# Define UPDATE_CHANNEL
UPDATE_CHANNEL = "https://t.me/joinnowearn"

# Smart reaction manager
class ReactionManager:
    def __init__(self):
        self.rate_limits = {}
        self.max_reactions_per_second = 20
        self.queue = asyncio.Queue()

    async def add_reaction(self, client, msg):
        chat_id = msg.chat.id
        current_time = time.time()

        if chat_id not in self.rate_limits:
            self.rate_limits[chat_id] = {'count': 0, 'last_reset': current_time}
        
        if current_time - self.rate_limits[chat_id]['last_reset'] > 1:
            self.rate_limits[chat_id] = {'count': 0, 'last_reset': current_time}

        if self.rate_limits[chat_id]['count'] >= self.max_reactions_per_second:
            await asyncio.sleep(1)
            self.rate_limits[chat_id] = {'count': 0, 'last_reset': time.time()}

        await self.queue.put((client, msg))
        self.rate_limits[chat_id]['count'] += 1

    async def process_reactions(self):
        while True:
            client, msg = await self.queue.get()
            try:
                emoji = choice(VALID_EMOJIS)
                await client.send_reaction(msg.chat.id, msg.id, emoji)
                logger.info(f"Reaction {emoji} sent to message {msg.id} in chat {msg.chat.id}")
            except FloodWait as e:
                logger.warning(f"Flood wait of {e.value} seconds for reaction in chat {msg.chat.id}")
                await asyncio.sleep(min(e.value, 5))
                await self.add_reaction(client, msg)
            except ReactionInvalid:
                logger.warning(f"Invalid reaction {emoji} attempted in chat {msg.chat.id}, skipping")
            except Exception as e:
                logger.error(f"Reaction error in chat {msg.chat.id}: {str(e)}")
            finally:
                self.queue.task_done()

reaction_manager = ReactionManager()

# Messages and buttons
START_TEXT = """<b>{},

ɪ ᴀᴍ sɪᴍᴘʟᴇ ʙᴜᴛ ᴘᴏᴡᴇʀꜰᴜʟʟ ᴀᴜᴛᴏ ʀᴇᴀᴄᴛɪᴏɴ ʙᴏᴛ.

ᴊᴜsᴛ ᴀᴅᴅ ᴍᴇ ᴀs ᴀ ᴀᴅᴍɪɴ ɪɴ ʏᴏᴜʀ ᴄʜᴀɴɴᴇʟ ᴏʀ ɢʀᴏᴜᴘ ᴛʜᴇɴ sᴇᴇ ᴍʏ ᴘᴏᴡᴇʀ</b>"""

CLONE_START_TEXT = f"<b>🤖 Parent Bot - @{BOT_USERNAME} 🤖\n\nɪ ᴀᴍ ᴀ ᴄʟᴏɴᴇ ᴏꜰ ᴛʜɪs ᴘᴏᴡᴇʀꜰᴜʟʟ ᴀᴜᴛᴏ ʀᴇᴀᴄᴛɪᴏɴ ʙᴏᴛ.\n\nᴀᴅᴅ ᴍᴇ ᴀs ᴀɴ ᴀᴅᴍɪɴ ɪɴ ʏᴏᴜʀ ᴄʜᴀɴɴᴇʟ ᴏʀ ɢʀᴏᴜᴘ ᴛᴏ sᴇᴇ ᴍʏ ᴘᴏᴡᴇʀ!</b>"

CLONE_TEXT = """<b>Clone Your Bot</b>
Create a bot with @BotFather and send me the token here to clone me!"""

START_BUTTONS = InlineKeyboardMarkup(
    [
        [InlineKeyboardButton(text='🤖 ᴄʟᴏɴᴇ ʏᴏᴜʀ ʙᴏᴛ', callback_data='clone_bot'),
         InlineKeyboardButton(text='📋 ᴍʏ ʙᴏᴛs', callback_data='my_bots')],
        [InlineKeyboardButton(text='🔌 ᴅɪsᴄᴏɴɴᴇᴄᴛ ᴀʟʟ ᴄʟᴏɴᴇᴅ', callback_data='disconnect_all')],
        [InlineKeyboardButton(text='🔔 ᴜᴩᴅᴀᴛᴇꜱ', url=UPDATE_CHANNEL)],
        [InlineKeyboardButton(text='💂 ᴍʏ ʀᴇᴀᴄᴛɪᴏɴ ᴀʀᴍʏ', callback_data='reaction_army')]
    ]
)

# Helper functions
async def save_connected_user(user_id):
    if not await db.is_user_exist(user_id):
        await db.add_user(user_id)
        logger.info(f"Connected user {user_id} added to users collection")

async def send_msg(user_id, message):
    try:
        await message.copy(chat_id=user_id)
        logger.info(f"Message sent to user {user_id}")
        return 200, None
    except FloodWait as e:
        logger.warning(f"Flood wait of {e.value} seconds for user {user_id}")
        await asyncio.sleep(e.value)
        return await send_msg(user_id, message)
    except Exception as e:
        logger.error(f"Error sending message to {user_id}: {str(e)}")
        return 500, f"{user_id} : {str(e)}\n"

async def get_fsub(bot, message):
    target_channel_id = AUTH_CHANNEL
    user_id = message.from_user.id
    try:
        await bot.get_chat_member(target_channel_id, user_id)
        logger.info(f"User {user_id} is subscribed to channel {target_channel_id}")
        return True
    except UserNotParticipant:
        channel_link = (await bot.get_chat(target_channel_id)).invite_link
        keyboard = [[InlineKeyboardButton("🔔 Join Our Channel", url=channel_link)]]
        await message.reply(
            f"<b>👋 Hello {message.from_user.mention()}, Welcome!</b>\n\n"
            "📢 <b>Exclusive Access Alert!</b> ✨\n\n"
            "To unlock all the amazing features I offer, please join our updates channel. "
            "This helps us keep you informed and ensures top-notch service just for you! 😊\n\n"
            "<i>🚀 Join now and dive into a world of knowledge and creativity!</i>",
            reply_markup=InlineKeyboardMarkup(keyboard),
            link_preview_options=LinkPreviewOptions(is_disabled=True)
        )
        logger.info(f"User {user_id} not subscribed to channel {target_channel_id}")
        return False
    except Exception as e:
        logger.error(f"Error checking subscription for {user_id}: {str(e)}")
        return False

async def retry_get_me(army_bot, max_retries=3, timeout=30):
    for attempt in range(max_retries):
        try:
            return await asyncio.wait_for(army_bot.get_me(), timeout=timeout)
        except (asyncio.TimeoutError, Exception) as e:
            logger.warning(f"Attempt {attempt+1}/{max_retries} failed for army bot get_me: {str(e)}")
            if attempt + 1 == max_retries:
                logger.error(f"Max retries reached for army bot get_me: {str(e)}")
                return None
            await asyncio.sleep(2)

async def validate_army_bots():
    global valid_army_bots
    valid_army_bots = []
    for army_bot, token in army_bots:
        try:
            await army_bot.start()
            bot_info = await retry_get_me(army_bot)
            if bot_info:
                logger.info(f"Army bot validated: @{bot_info.username}")
                valid_army_bots.append((army_bot, bot_info))
            else:
                logger.error(f"Skipping army bot with token {token[:10]}... due to failed get_me")
                await army_bot.stop()
        except Exception as e:
            logger.error(f"Failed to validate army bot with token {token[:10]}...: {str(e)}")
            await army_bot.stop()

async def promote_army_bots(client, chat_id, reply_func=None):
    try:
        # Define admin privileges (corrected Pyrogram parameters)
        admin_privileges = {
            "can_change_info": True,
            "can_post_messages": True,
            "can_edit_messages": True,
            "can_delete_messages": True,
            "can_invite_users": True,
            "can_restrict_members": True,
            "can_pin_messages": True,
            "can_promote_members": True,
            "can_manage_voice_chats": True,
            "can_manage_topics": True
        }

        # Get army bot IDs
        army_bot_ids = {bot_info.id: bot_info.username for _, bot_info in valid_army_bots}
        if not army_bot_ids:
            logger.error(f"No valid army bots available for promotion in chat {chat_id}")
            if reply_func:
                await reply_func("No valid army bots available. Please check token validity and try again.")
            return

        promoted_count = 0
        failed_count = 0
        not_in_chat = []

        # Scan chat members to find army bots
        try:
            async for member in client.get_chat_members(chat_id):
                user_id = member.user.id
                if user_id in army_bot_ids:
                    username = army_bot_ids[user_id]
                    # Army bot found, attempt promotion
                    for attempt in range(3):
                        try:
                            await client.promote_chat_member(
                                chat_id,
                                user_id,
                                **admin_privileges
                            )
                            logger.info(f"Promoted army bot @{username} to admin in chat {chat_id}")
                            promoted_count += 1
                            break
                        except PeerIdInvalid as e:
                            logger.warning(f"Attempt {attempt+1}/3 failed for promoting @{username} in chat {chat_id}: {str(e)}")
                            if attempt + 1 < 3:
                                await asyncio.sleep(3)
                            else:
                                logger.error(f"Failed to promote @{username} in chat {chat_id} after 3 attempts: {str(e)}")
                                failed_count += 1
                                if reply_func:
                                    await reply_func(f"Failed to promote @{username}. Please send a private /start to @{username} to register it with Telegram, then retry.")
                        except ChatAdminRequired:
                            logger.error(f"Client lacks admin permissions to promote @{username} in chat {chat_id}")
                            failed_count += 1
                            if reply_func:
                                await reply_func(f"Main bot lacks 'Add Admins' permission in chat {chat_id}. Please grant this permission.")
                            break
                        except Exception as e:
                            logger.error(f"Error promoting @{username} in chat {chat_id}: {str(e)}")
                            failed_count += 1
                            break
                    await asyncio.sleep(1)  # Rate limit delay
                await asyncio.sleep(0.5)  # Rate limit delay between members
        except Exception as e:
            logger.error(f"Error scanning members in chat {chat_id}: {str(e)}")
            if reply_func:
                await reply_func(f"Failed to scan members in chat {chat_id}. Ensure the main bot has admin permissions.")

        # Invite missing army bots
        for bot_id, username in army_bot_ids.items():
            try:
                # Check if bot is already in chat
                found = False
                async for member in client.get_chat_members(chat_id):
                    if member.user.id == bot_id:
                        found = True
                        break
                if not found:
                    not_in_chat.append(username)
                    try:
                        await client.add_chat_members(chat_id, bot_id)
                        logger.info(f"Invited army bot @{username} to chat {chat_id}")
                        # Retry promotion after inviting
                        for attempt in range(3):
                            try:
                                await client.promote_chat_member(
                                    chat_id,
                                    bot_id,
                                    **admin_privileges
                                )
                                logger.info(f"Promoted army bot @{username} to admin in chat {chat_id} after inviting")
                                promoted_count += 1
                                break
                            except PeerIdInvalid as e:
                                logger.warning(f"Attempt {attempt+1}/3 failed for promoting @{username} in chat {chat_id}: {str(e)}")
                                if attempt + 1 < 3:
                                    await asyncio.sleep(3)
                                else:
                                    logger.error(f"Failed to promote @{username} in chat {chat_id} after 3 attempts: {str(e)}")
                                    failed_count += 1
                                    if reply_func:
                                        await reply_func(f"Failed to promote @{username} after inviting. Please send a private /start to @{username} to register it with Telegram, then retry.")
                            except ChatAdminRequired:
                                logger.error(f"Client lacks admin permissions to promote @{username} in chat {chat_id}")
                                failed_count += 1
                                if reply_func:
                                    await reply_func(f"Main bot lacks 'Add Admins' permission in chat {chat_id}. Please grant this permission.")
                                break
                            except Exception as e:
                                logger.error(f"Error promoting @{username} in chat {chat_id}: {str(e)}")
                                failed_count += 1
                                break
                        await asyncio.sleep(1)  # Rate limit delay
                    except ChatAdminRequired:
                        logger.error(f"Client lacks permission to invite @{username} to chat {chat_id}")
                        failed_count += 1
                        if reply_func:
                            await reply_func(f"Please manually add @{username} to the chat, as the main bot lacks 'Invite Users' permission.")
                    except Exception as e:
                        logger.error(f"Error inviting @{username} to chat {chat_id}: {str(e)}")
                        failed_count += 1
                        if reply_func:
                            await reply_func(f"Failed to invite @{username} to chat {chat_id}. Please add it manually.")
            except Exception as e:
                logger.error(f"Error checking presence of @{username} in chat {chat_id}: {str(e)}")
                failed_count += 1
            await asyncio.sleep(0.5)  # Rate limit delay

        if reply_func:
            result_text = f"Promotion complete: {promoted_count} army bots promoted, {failed_count} failed.\n"
            if not_in_chat:
                result_text += f"Bots not in chat (please add manually if invite failed): {', '.join(f'@{name}' for name in not_in_chat)}"
            await reply_func(result_text)
        logger.info(f"Army bot promotion in chat {chat_id}: {promoted_count} succeeded, {failed_count} failed")
    except Exception as e:
        logger.error(f"Error during army bot promotion in chat {chat_id}: {str(e)}")
        if reply_func:
            await reply_func("Failed to promote army bots. Ensure the main bot is an admin with 'Add Admins' and 'Invite Users' permissions.")

async def background_army_promotion(client):
    while True:
        try:
            # Scan known group chats from database
            all_clones = await db.get_all_clones()
            chat_ids = set()
            for clone in all_clones:
                for chat_id in clone.get('connected_chats', []):
                    try:
                        chat = await client.get_chat(chat_id)
                        if chat.type in ["group", "supergroup"]:  # Only process groups
                            chat_ids.add(chat_id)
                    except ChannelPrivate:
                        logger.info(f"Skipping private chat {chat_id} in background promotion")
                    except Exception as e:
                        logger.error(f"Error checking chat {chat_id} type: {str(e)}")

            for chat_id in chat_ids:
                try:
                    # Verify main bot is in chat and has admin rights
                    await client.get_chat_member(chat_id, "me")
                    await promote_army_bots(client, chat_id)
                except (UserNotParticipant, ChatAdminRequired):
                    logger.info(f"Main bot not admin in chat {chat_id}, skipping background promotion")
                except Exception as e:
                    logger.error(f"Error in background promotion for chat {chat_id}: {str(e)}")
                await asyncio.sleep(2)  # Rate limit delay between chats
        except Exception as e:
            logger.error(f"Error in background army promotion: {str(e)}")
        await asyncio.sleep(300)  # Run every 5 minutes

# Handlers
@Bot.on_message(filters.command("addarmy") & filters.group & filters.user(int(BOT_OWNER)))
async def add_army_command(bot, message):
    chat_id = message.chat.id
    logger.info(f"Add army command received from {message.from_user.id} in chat {chat_id}")
    await promote_army_bots(bot, chat_id, reply_func=message.reply_text)

@Bot.on_message(filters.private & filters.command(["start"]))
async def start(bot, update):
    user_id = update.from_user.id
    await save_connected_user(user_id)
    
    is_subscribed = await get_fsub(bot, update)
    if not is_subscribed:
        return

    await update.reply_text(
        text=START_TEXT.format(update.from_user.mention),
        link_preview_options=LinkPreviewOptions(is_disabled=True),
        reply_markup=START_BUTTONS
    )
    logger.info(f"Start command processed for user {user_id}")

@Bot.on_message(filters.private & filters.command("stats"))
async def stats(bot, update):
    user_id = str(update.from_user.id)
    bot_owner_str = str(BOT_OWNER)
    
    logger.info(f"Stats command received - User ID: {user_id}, Type: {type(user_id)}")
    logger.info(f"BOT_OWNER: {bot_owner_str}, Type: {type(bot_owner_str)}")
    
    if user_id != bot_owner_str:
        logger.warning(f"Unauthorized stats attempt - User: {user_id}, Expected: {bot_owner_str}")
        await update.reply_text("❌ You are not authorized to use this command!")
        return
    
    try:
        logger.info(f"Processing stats command for authorized user: {user_id}")
        total_users = await db.total_users_count()
        total_clones = await db.total_clones_count()
        all_clones = await db.get_all_clones()
        connected_users = set()
        
        for clone in all_clones:
            connected_users.update(clone.get('connected_users', []))
        
        text = (
            f"📊 Bot Statistics\n\n"
            f"👥 Total Users: {total_users}\n"
            f"🤖 Total Cloned Bots: {total_clones}\n"
            f"🔗 Total Connected Users: {len(connected_users)}"
        )
        await update.reply_text(
            text=text,
            quote=True,
            link_preview_options=LinkPreviewOptions(is_disabled=True)
        )
        logger.info(f"Stats command completed successfully: Users={total_users}, Clones={total_clones}")
        
    except Exception as e:
        error_msg = f"Error in stats command: {str(e)}\n{traceback.format_exc()}"
        logger.error(error_msg)
        await update.reply_text("❌ An error occurred while fetching stats!")

@Bot.on_message(filters.private & filters.command("broadcast"))
async def broadcast(bot, update):
    user_id = str(update.from_user.id)
    bot_owner_str = str(BOT_OWNER)
    
    logger.info(f"Broadcast command received - User ID: {user_id}, Type: {type(user_id)}")
    logger.info(f"BOT_OWNER: {bot_owner_str}, Type: {type(bot_owner_str)}")
    
    if user_id != bot_owner_str:
        logger.warning(f"Unauthorized broadcast attempt - User: {user_id}, Expected: {bot_owner_str}")
        await update.reply_text("❌ You are not authorized to use this command!")
        return

    try:
        logger.info(f"Processing broadcast command for authorized user: {user_id}")
        
        if not update.reply_to_message:
            logger.info("No message to broadcast - user didn't reply to a message")
            await update.reply_text("Please reply to a message to broadcast!")
            return

        broadcast_msg = update.reply_to_message
        all_users = await db.get_all_connected_users()
        total_users = len(all_users)
        
        logger.info(f"Total users to broadcast to: {total_users}")
        
        if total_users == 0:
            logger.info("No users available for broadcast")
            await update.reply_text("No users to broadcast to!")
            return

        processing_msg = await update.reply_text(f"Starting broadcast to {total_users} users...")
        success_count = 0
        failed_count = 0
        
        for user_id in all_users:
            try:
                logger.info(f"Attempting to broadcast to user: {user_id}")
                status, error = await send_msg(user_id, broadcast_msg)
                if status == 200:
                    success_count += 1
                    logger.info(f"Successfully broadcast to user: {user_id}")
                else:
                    failed_count += 1
                    logger.info(f"Failed to broadcast to user: {user_id} - Error: {error}")
                await asyncio.sleep(0.5)
            except Exception as e:
                failed_count += 1
                logger.error(f"Broadcast failed for user {user_id}: {str(e)}")

        result_text = (
            f"📢 Broadcast Completed!\n\n"
            f"✅ Successfully sent to: {success_count} users\n"
            f"❌ Failed to send to: {failed_count} users\n"
            f"👥 Total users: {total_users}"
        )
        await processing_msg.edit(result_text)
        logger.info(f"Broadcast completed: Success={success_count}, Failed={failed_count}")
        
    except Exception as e:
        error_msg = f"Error in broadcast command: {str(e)}\n{traceback.format_exc()}"
        logger.error(error_msg)
        await update.reply_text("❌ An error occurred during broadcast!")

@Bot.on_callback_query(filters.regex("reaction_army"))
async def reaction_army_callback(bot, query):
    army_text = (
        "<b>💂 My Reaction Army</b>\n\n"
        "1. Add the main bot (@{main_bot}) to your group and make it an admin with full permissions, including 'Add Admins' and 'Invite Users'.\n"
        "2. Add the army bots below to the group using the buttons or manually.\n"
        "3. Send a private /start to each army bot to register it with Telegram.\n"
        "4. The main bot will automatically detect and promote existing army bots to admins in groups. Use /addarmy to force immediate promotion.\n\n"
        "<b>Army Bots:</b>\n"
    ).format(main_bot=BOT_USERNAME)

    army_buttons = []
    for _, bot_info in valid_army_bots:
        army_text += f"- @{bot_info.username}\n"
        army_buttons.append([
            InlineKeyboardButton(text=f"👥 Add @{bot_info.username} to Group", url=f"https://telegram.me/{bot_info.username}?startgroup=botstart"),
            InlineKeyboardButton(text=f"📺 Add @{bot_info.username} to Channel", url=f"https://telegram.me/{bot_info.username}?startchannel=botstart")
        ])

    if not army_buttons:
        army_text += "No valid army bots available. Please check token validity and try again."

    await query.message.reply_text(
        text=army_text,
        reply_markup=InlineKeyboardMarkup(army_buttons),
        link_preview_options=LinkPreviewOptions(is_disabled=True)
    )
    logger.info(f"Reaction army list requested by {query.from_user.id}")

# Clone handling
@Bot.on_message(filters.private & filters.text & filters.regex(r'^[A-Za-z0-9]+:[A-Za-z0-9_-]+$'))
async def handle_clone_token(bot, message):
    token = message.text
    processing_msg = await message.reply("Processing your clone request...")
    logger.info(f"Clone request received for token: {token[:10]}...")

    existing_clone = await db.get_clone(token)
    if existing_clone:
        await processing_msg.edit(f"❌ This bot token is already cloned as @{existing_clone['username']}!")
        logger.warning(f"Duplicate clone attempt with token: {token[:10]}...")
        return

    try:
        temp_client = Client(name="temp", bot_token=token, api_id=API_ID, api_hash=API_HASH, in_memory=True)
        try:
            await temp_client.start()
        except FloodWait as e:
            logger.warning(f"Flood wait of {e.value} seconds for cloning with token: {token[:10]}...")
            await asyncio.sleep(e.value)
            await temp_client.start()
        
        bot_info = await temp_client.get_me()
        await temp_client.stop()
        logger.info(f"Bot info retrieved: @{bot_info.username}")

        clone_data = await db.add_clone(message.from_user.id, token, bot_info.username)
        
        clone_buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton(text="👥 ᴀᴅᴅ ᴛᴏ ɢʀᴏᴜᴘ", url=f"https://telegram.me/{bot_info.username}?startgroup=botstart")],
            [InlineKeyboardButton(text="📺 ᴀᴅᴅ ᴛᴏ ᴄʜᴀɴɴᴇʟ", url=f"https://telegram.me/{bot_info.username}?startchannel=botstart")],
            [InlineKeyboardButton(text="🤖 ᴄʀᴇᴀᴛᴇ ʏᴏᴜʀ ᴏᴡɴ ʙᴏᴛ", url=f"https://telegram.me/{BOT_USERNAME}")]
        ])

        await processing_msg.edit(
            f"✅ Bot cloned successfully!\n\nUsername: @{bot_info.username}",
            reply_markup=clone_buttons
        )
        logger.info(f"Bot cloned successfully: @{bot_info.username} with buttons using username @{bot_info.username}")

        clone_bot = Client(name=f"clone_{bot_info.username}", bot_token=token, api_id=API_ID, api_hash=API_HASH, in_memory=True)
        
        @clone_bot.on_message(filters.private & filters.command(["start"]) & ~filters.me)
        async def clone_start(client, update):
            clone_data = await db.get_clone(token)
            if not clone_data or not clone_data['active']:
                logger.warning(f"Clone @{bot_info.username} is inactive or not found")
                return
            
            user_id = update.from_user.id
            await save_connected_user(user_id)
            await db.update_connected_users(clone_data['_id'], user_id)

            clone_buttons = InlineKeyboardMarkup([
                [InlineKeyboardButton(text="👥 ᴀᴅᴅ ᴛᴏ ɢʀᴏᴜᴘ", url=f"https://telegram.me/{bot_info.username}?startgroup=botstart")],
                [InlineKeyboardButton(text="📺 ᴀᴅᴅ ᴛᴏ ᴄʜᴀɴɴᴇʟ", url=f"https://telegram.me/{bot_info.username}?startchannel=botstart")],
                [InlineKeyboardButton(text="🤖 ᴄʀᴇᴀᴛᴇ ʏᴏᴜʀ ᴏᴡɴ ʙᴏᴛ", url=f"https://telegram.me/{BOT_USERNAME}")]
            ])
            await update.reply_text(
                text=CLONE_START_TEXT,
                link_preview_options=LinkPreviewOptions(is_disabled=True),
                reply_markup=clone_buttons
            )
            logger.info(f"Start command processed for clone @{bot_info.username} by user {update.from_user.id} with buttons using username @{bot_info.username}")

        @clone_bot.on_message(filters.private & ~filters.command(["start"]) & ~filters.me)
        async def clone_reply(client, update):
            clone_data = await db.get_clone(token)
            if not clone_data or not clone_data['active']:
                logger.warning(f"Clone @{bot_info.username} is inactive or not found")
                return
            
            user_id = update.from_user.id
            await save_connected_user(user_id)
            await db.update_connected_users(clone_data['_id'], user_id)
            await reaction_manager.add_reaction(client, update)

        @clone_bot.on_message(filters.group | filters.channel)
        async def clone_reaction(client, msg):
            clone_data = await db.get_clone(token)
            if not clone_data or not clone_data['active']:
                logger.warning(f"Clone @{clone['username']} is inactive or not found")
                return
            
            try:
                await client.get_chat_member(msg.chat.id, "me")
                await reaction_manager.add_reaction(client, msg)
                await db.update_connected_chats(clone_data['_id'], msg.chat.id)
            except (UserNotParticipant, ChatAdminRequired, ChannelPrivate):
                await db.clones.delete_one({'_id': clone_data['_id']})
                logger.info(f"Bot @{clone['username']} disconnected and removed from database due to lack of access in {msg.chat.id}")
            except Exception as e:
                logger.error(f"Error in reaction for @{clone['username']}: {str(e)}")
        
        asyncio.create_task(clone_bot.start())
        logger.info(f"Clone bot started: @{bot_info.username}")

    except FloodWait as e:
        await processing_msg.edit(f"⏳ Please wait {e.value} seconds due to Telegram flood limits and try again.")
        logger.warning(f"Flood wait error during cloning: {e.value} seconds")
    except Exception as e:
        await processing_msg.edit(f"❌ Failed to clone bot: {str(e)}")
        logger.error(f"Failed to clone bot with token {token[:10]}...: {str(e)}")

@Bot.on_callback_query(filters.regex("clone_bot"))
async def clone_bot_callback(bot, query):
    await query.message.reply(CLONE_TEXT)
    logger.info(f"Clone bot callback triggered by {query.from_user.id}")

@Bot.on_callback_query(filters.regex("my_bots"))
async def my_bots_callback(bot, query):
    user_id = query.from_user.id
    all_clones = await db.get_user_clones(user_id)
    
    if not all_clones:
        await query.message.reply("You have no active cloned bots!")
        logger.info(f"No active bots found for user {user_id}")
        return
    
    bot_list = "\n".join([f"@{clone['username']}" for clone in all_clones if clone['active']])
    await query.message.reply(f"Your Active Cloned Bots:\n{bot_list}")
    logger.info(f"My bots list requested by {user_id}: {len(all_clones)} active bots")

@Bot.on_callback_query(filters.regex("disconnect_all"))
async def disconnect_all_callback(bot, query):
    user_id = query.from_user.id
    all_clones = await db.get_user_clones(user_id)
    disconnected_count = 0
    
    result = await db.clones.delete_many({'user_id': user_id})
    disconnected_count = result.deleted_count
    
    for clone in all_clones:
        logger.info(f"Bot @{clone['username']} disconnected and removed from database by {user_id}")

    await query.message.reply(f"Disconnected {disconnected_count} of your bots successfully!")
    logger.info(f"All bots disconnected by {user_id}: {disconnected_count} bots affected")

# Reaction handling for main bot
@Bot.on_message(filters.group | filters.channel)
async def send_reaction(bot, msg: Message):
    try:
        await bot.get_chat_member(msg.chat.id, "me")
        await reaction_manager.add_reaction(bot, msg)
    except (UserNotParticipant, ChatAdminRequired, ChannelPrivate):
        logger.info(f"Main bot not admin in chat {msg.chat.id}, skipping reaction")
    except Exception as e:
        logger.error(f"Error in main bot reaction for chat {msg.chat.id}: {str(e)}")

async def activate_clones_and_army():
    await validate_army_bots()
    # Start clones
    all_clones = await db.get_all_clones()
    for clone in all_clones:
        if clone['active']:
            try:
                clone_bot = Client(
                    name=f"clone_{clone['username']}",
                    bot_token=clone['token'],
                    api_id=API_ID,
                    api_hash=API_HASH,
                    in_memory=True
                )
                
                @clone_bot.on_message(filters.private & filters.command(["start"]) & ~filters.me)
                async def clone_start(client, update):
                    clone_data = await db.get_clone(clone['token'])
                    if not clone_data or not clone_data['active']:
                        logger.warning(f"Clone @{clone['username']} is inactive or not found")
                        return
                    
                    user_id = update.from_user.id
                    await save_connected_user(user_id)
                    await db.update_connected_users(clone_data['_id'], user_id)

                    clone_buttons = InlineKeyboardMarkup([
                        [InlineKeyboardButton(text="👥 ᴀᴅᴅ ᴛᴏ ɢʀᴏᴜᴘ", url=f"https://telegram.me/{clone['username']}?startgroup=botstart")],
                        [InlineKeyboardButton(text="📺 ᴀᴅᴅ ᴛᴏ ᴄʜᴀɴɴᴇʟ", url=f"https://telegram.me/{clone['username']}?startchannel=botstart")],
                        [InlineKeyboardButton(text="🤖 ᴄʀᴇᴀᴛᴇ ʏᴏᴜʀ ᴏᴡɴ ʙᴏᴛ", url=f"https://telegram.me/{BOT_USERNAME}")]
                    ])
                    await update.reply_text(
                        text=CLONE_START_TEXT,
                        link_preview_options=LinkPreviewOptions(is_disabled=True),
                        reply_markup=clone_buttons
                    )
                    logger.info(f"Start command processed for clone @{clone['username']} by user {update.from_user.id} with buttons using username @{clone['username']}")

                @clone_bot.on_message(filters.private & ~filters.command(["start"]) & ~filters.me)
                async def clone_reply(client, update):
                    clone_data = await db.get_clone(clone['token'])
                    if not clone_data or not clone_data['active']:
                        logger.warning(f"Clone @{clone['username']} is inactive or not found")
                        return
                    
                    user_id = update.from_user.id
                    await save_connected_user(user_id)
                    await db.update_connected_users(clone_data['_id'], user_id)
                    await reaction_manager.add_reaction(client, update)

                @clone_bot.on_message(filters.group | filters.channel)
                async def clone_reaction(client, msg):
                    clone_data = await db.get_clone(clone['token'])
                    if not clone_data or not clone_data['active']:
                        logger.warning(f"Clone @{clone['username']} is inactive or not found")
                        return
                    
                    try:
                        await client.get_chat_member(msg.chat.id, "me")
                        await reaction_manager.add_reaction(client, msg)
                        await db.update_connected_chats(clone_data['_id'], msg.chat.id)
                    except (UserNotParticipant, ChatAdminRequired, ChannelPrivate):
                        await db.clones.delete_one({'_id': clone_data['_id']})
                        logger.info(f"Bot @{clone['username']} disconnected and removed from database due to lack of access in {msg.chat.id}")
                    except Exception as e:
                        logger.error(f"Error in reaction for @{clone['username']}: {str(e)}")
                
                asyncio.create_task(clone_bot.start())
                logger.info(f"Clone bot started: @{clone['username']}")
            except Exception as e:
                logger.error(f"Failed to start clone bot @{clone['username']}: {str(e)}")
                await db.clones.delete_one({'_id': clone['_id']})

async def main():
    await Bot.start()
    logger.info("Main Bot Started!")
    asyncio.create_task(reaction_manager.process_reactions())
    asyncio.create_task(background_army_promotion(Bot))
    await activate_clones_and_army()
    await asyncio.Future()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
