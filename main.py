import os
import time
import asyncio
import datetime
import aiofiles
import logging
from random import choice
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, LinkPreviewOptions
from pyrogram.errors import *
from database import Database
from config import *

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
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

# Valid Telegram reaction emojis
VALID_EMOJIS = ["👍", "👎", "❤", "🔥", "🥳", "👏", "😁", "😢", "😍", "🤯", "😱", "🤬"]

# Smart reaction manager
class ReactionManager:
    def __init__(self):
        self.rate_limits = {}  # Tracks rate limits per chat
        self.max_reactions_per_second = 20  # Telegram's approximate limit
        self.queue = asyncio.Queue()

    async def add_reaction(self, client, msg):
        chat_id = msg.chat.id
        current_time = time.time()

        # Check rate limit for this chat
        if chat_id not in self.rate_limits:
            self.rate_limits[chat_id] = {'count': 0, 'last_reset': current_time}
        
        if current_time - self.rate_limits[chat_id]['last_reset'] > 1:
            self.rate_limits[chat_id] = {'count': 0, 'last_reset': current_time}

        if self.rate_limits[chat_id]['count'] >= self.max_reactions_per_second:
            await asyncio.sleep(1)  # Wait intelligently
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
                await self.add_reaction(client, msg)  # Retry
            except ReactionInvalid:
                logger.warning(f"Invalid reaction attempted in chat {msg.chat.id}, retrying")
                await self.add_reaction(client, msg)
            except Exception as e:
                logger.error(f"Reaction error in chat {msg.chat.id}: {str(e)}")
            finally:
                self.queue.task_done()

reaction_manager = ReactionManager()
asyncio.create_task(reaction_manager.process_reactions())

# Messages and buttons
START_TEXT = """<b>{},

ɪ ᴀᴍ sɪᴍᴘʟᴇ ʙᴜᴛ ᴘᴏᴡᴇʀꜰᴜʟʟ ᴀᴜᴛᴏ ʀᴇᴀᴄᴛɪᴏɴ ʙᴏᴛ.

ᴊᴜsᴛ ᴀᴅᴅ ᴍᴇ ᴀs ᴀ ᴀᴅᴍɪɴ ɪɴ ʏᴏᴜʀ ᴄʜᴀɴɴᴇʟ ᴏʀ ɢʀᴏᴜᴪ ᴛʜᴇɴ sᴇᴇ ᴍʏ ᴘᴏᴡᴇʀ</b>"""

CLONE_START_TEXT = "<b>@{0}\n\nɪ ᴀᴍ ᴀ ᴄʟᴏɴᴇ ᴏꜰ ᴛʜɪs ᴘᴏᴡᴇʀꜰᴜʟʟ ᴀᴜᴛᴏ ʀᴇᴀᴄᴛɪᴏɴ ʙᴏᴛ.\n\nᴀᴅᴅ ᴍᴇ ᴀs ᴀɴ ᴀᴅᴍɪɴ ɪɴ ʏᴏᴜʀ ᴄʜᴀɴɴᴇʟ ᴏʀ ɢʀᴏᴜᴘ ᴛᴏ sᴇᴇ ᴍʏ ᴘᴏᴡᴇʀ!</b>"

CLONE_TEXT = """<b>Clone Your Bot</b>
Send your bot token to create a clone of me!
Your clone will:
- Work exactly like me
- Have an 'Add to Group/Channel' button
- Be manageable from 'My Bots' section"""

MY_BOTS_TEXT = """<b>Your Cloned Bots</b>
Here are all your active bot clones:"""

LOG_TEXT = """<b>#NewUser
    
ID - <code>{}</code>

Name - {}</b>"""

START_BUTTONS = InlineKeyboardMarkup(
    [
        [InlineKeyboardButton(text='⇆ ᴀᴅᴅ ᴍᴇ ᴛᴏ ʏᴏᴜʀ ɢʀᴏᴜᴘs ⇆', url=f'https://telegram.me/{BOT_USERNAME}?startgroup=botstart')],
        [InlineKeyboardButton(text='• ᴜᴩᴅᴀᴛᴇꜱ •', url='https://telegram.me/StreamExplainer'),
         InlineKeyboardButton(text='• ꜱᴜᴩᴩᴏʀᴛ •', url='https://telegram.me/TechifySupport')],
        [InlineKeyboardButton(text='⇆ ᴀᴅᴅ ᴍᴇ ᴛᴏ ʏᴏᴜʀ ᴄʜᴀɴɴᴇʟ ⇆', url=f'https://telegram.me/{BOT_USERNAME}?startchannel=botstart')],
        [InlineKeyboardButton(text='• ᴍʏ ʙᴏᴛs •', callback_data='my_bots'),
         InlineKeyboardButton(text='• ᴄʟᴏɴᴇ ʙᴏᴛ •', callback_data='clone_bot')]
    ]
)

# Helper functions
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

# Handlers
@Bot.on_message(filters.private & filters.command(["start"]))
async def start(bot, update):
    if not await db.is_user_exist(update.from_user.id):
        await db.add_user(update.from_user.id)
        await bot.send_message(LOG_CHANNEL, LOG_TEXT.format(update.from_user.id, update.from_user.mention))
        logger.info(f"New user added: {update.from_user.id}")
    
    is_subscribed = await get_fsub(bot, update)
    if not is_subscribed:
        return

    await update.reply_text(
        text=START_TEXT.format(update.from_user.mention),
        link_preview_options=LinkPreviewOptions(is_disabled=True),
        reply_markup=START_BUTTONS
    )
    logger.info(f"Start command processed for user {update.from_user.id}")

@Bot.on_message(filters.private & filters.command("users") & filters.user(BOT_OWNER))
async def users(bot, update):
    total_users = await db.total_users_count()
    text = f"Bot Status\n\nTotal Users: {total_users}"
    await update.reply_text(
        text=text,
        quote=True,
        link_preview_options=LinkPreviewOptions(is_disabled=True)
    )
    logger.info(f"Users command executed by owner: Total users = {total_users}")

@Bot.on_message(filters.private & filters.command("stats") & filters.user(BOT_OWNER))
async def stats(bot, update):
    total_users = await db.total_users_count()
    total_clones = await db.total_clones_count()
    all_clones = await db.get_all_clones()
    total_chats = 0
    for clone in all_clones:
        total_chats += len(clone.get('connected_chats', []))

    text = (
        f"📊 Bot Statistics\n\n"
        f"👥 Total Users: {total_users}\n"
        f"🤖 Total Cloned Bots: {total_clones}\n"
        f"💬 Total Connected Chats: {total_chats}"
    )
    await update.reply_text(
        text=text,
        quote=True,
        link_preview_options=LinkPreviewOptions(is_disabled=True)
    )
    logger.info(f"Stats command executed: Users={total_users}, Clones={total_clones}, Chats={total_chats}")

@Bot.on_message(filters.private & filters.command("broadcast") & filters.user(BOT_OWNER) & filters.reply)
async def broadcast(bot, update):
    broadcast_ids = {}
    all_users = await db.get_all_users()
    broadcast_msg = update.reply_to_message
    out = await update.reply_text(text="Broadcast Started!")
    start_time = time.time()
    total_users = await db.total_users_count()
    done = 0
    failed = 0
    success = 0
    broadcast_ids["broadcast"] = {"total": total_users, "current": done, "failed": failed, "success": success}

    all_clones = await db.get_all_clones()
    clone_clients = []
    for clone in all_clones:
        if clone['active']:
            clone_client = Client(name=f"clone_{clone['username']}", bot_token=clone['token'], api_id=API_ID, api_hash=API_HASH, in_memory=True)
            await clone_client.start()
            clone_clients.append(clone_client)
            logger.info(f"Broadcast clone client started: @{clone['username']}")

    async with aiofiles.open('broadcast.txt', 'w') as broadcast_log_file:
        async for user in all_users:
            sts, msg = await send_msg(user_id=int(user['id']), message=broadcast_msg)
            if msg is not None:
                await broadcast_log_file.write(msg)
            if sts == 200:
                success += 1
            else:
                failed += 1
            if sts == 400:
                await db.delete_user(user['id'])
            done += 1
            broadcast_ids["broadcast"].update({"current": done, "failed": failed, "success": success})

        for clone_client in clone_clients:
            async for dialog in clone_client.get_dialogs():
                if dialog.chat.type in ['private']:
                    sts, msg = await send_msg(user_id=dialog.chat.id, message=broadcast_msg)
                    if msg is not None:
                        await broadcast_log_file.write(msg)
                    if sts == 200:
                        success += 1
                    else:
                        failed += 1
                    done += 1
                    broadcast_ids["broadcast"].update({"current": done, "failed": failed, "success": success})
            await clone_client.stop()
            logger.info(f"Broadcast clone client stopped: {clone_client.name}")

    completed_in = datetime.timedelta(seconds=int(time.time() - start_time))
    await asyncio.sleep(3)
    await out.delete()
    if failed == 0:
        await update.reply_text(
            text=f"Broadcast completed in `{completed_in}`\n\nTotal users {total_users + done}.\nDone: {done}, Success: {success}, Failed: {failed}",
            quote=True
        )
    else:
        await update.reply_document(
            document='broadcast.txt',
            caption=f"Broadcast completed in `{completed_in}`\n\nTotal users {total_users + done}.\nDone: {done}, Success: {success}, Failed: {failed}"
        )
    os.remove('broadcast.txt')
    logger.info(f"Broadcast completed: Done={done}, Success={success}, Failed={failed}")

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
            [InlineKeyboardButton("Add to Group", url=f"https://telegram.me/{bot_info.username}?startgroup=botstart")],
            [InlineKeyboardButton("Add to Channel", url=f"https://telegram.me/{bot_info.username}?startchannel=botstart")],
            [InlineKeyboardButton("Create Your Own Bot", url=f"https://telegram.me/{BOT_USERNAME}")]
        ])

        await processing_msg.edit(
            f"✅ Bot cloned successfully!\n\nUsername: @{bot_info.username}",
            reply_markup=clone_buttons
        )
        logger.info(f"Bot cloned successfully: @{bot_info.username}")

        clone_bot = Client(name=f"clone_{bot_info.username}", bot_token=token, api_id=API_ID, api_hash=API_HASH, in_memory=True)
        
        @clone_bot.on_message(filters.private & filters.command(["start"]))
        async def clone_start(client, update):
            if hasattr(client, '_start_handled'):  # Prevent duplicate replies
                return
            client._start_handled = True
            
            clone_buttons = InlineKeyboardMarkup([
                [InlineKeyboardButton("Add to Group", url=f"https://telegram.me/{bot_info.username}?startgroup=botstart")],
                [InlineKeyboardButton("Add to Channel", url=f"https://telegram.me/{bot_info.username}?startchannel=botstart")],
                [InlineKeyboardButton("Create Your Own Bot", url=f"https://telegram.me/{BOT_USERNAME}")]
            ])
            await update.reply_text(
                text=CLONE_START_TEXT.format(BOT_USERNAME),
                link_preview_options=LinkPreviewOptions(is_disabled=True),
                reply_markup=clone_buttons
            )
            logger.info(f"Start command processed for clone @{bot_info.username} by user {update.from_user.id}")
            await asyncio.sleep(1)  # Reset after a short delay
            client._start_handled = False

        @clone_bot.on_message(filters.group | filters.channel)
        async def clone_reaction(client, msg):
            clone_data = await db.get_clone(token)
            if not clone_data or not clone_data['active']:
                logger.warning(f"Clone @{bot_info.username} is inactive or not found")
                return
            
            try:
                await client.get_chat_member(msg.chat.id, "me")
                await reaction_manager.add_reaction(client, msg)
                await db.update_connected_chats(clone_data['_id'], msg.chat.id)
            except (UserNotParticipant, ChatAdminRequired):
                await db.toggle_clone(clone_data['_id'], False)
                logger.info(f"Bot @{bot_info.username} disconnected from {msg.chat.id}")
            except Exception as e:
                logger.error(f"Error in reaction for @{bot_info.username}: {str(e)}")
        
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
    # Fetch fresh data from database every time
    clones = await db.get_user_clones(query.from_user.id)
    logger.info(f"Fetched clones for user {query.from_user.id}: {len(clones)} found")

    if not clones:
        await query.message.edit_text("You haven't cloned any bots yet!")
        logger.info(f"No clones found for user {query.from_user.id}")
        return

    buttons = []
    seen_usernames = set()
    active_bots = []
    for clone in clones:
        if clone['username'] not in seen_usernames:
            try:
                temp_client = Client(name=f"check_{clone['username']}", bot_token=clone['token'], api_id=API_ID, api_hash=API_HASH, in_memory=True)
                await temp_client.start()
                await temp_client.get_me()
                await temp_client.stop()
                
                status = "✅" if clone['active'] else "❌"
                buttons.append([
                    InlineKeyboardButton(f"{status} @{clone['username']}", callback_data=f"toggle_{clone['_id']}"),
                    InlineKeyboardButton("Delete", callback_data=f"delete_{clone['_id']}")
                ])
                seen_usernames.add(clone['username'])
                active_bots.append(clone)
            except Exception:
                logger.warning(f"Bot @{clone['username']} is invalid or deleted, skipping")
                continue

    if not buttons:
        await query.message.edit_text("No active bots found!")
        logger.info(f"No active bots found for user {query.from_user.id}")
    else:
        await query.message.edit_text(
            MY_BOTS_TEXT,
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        logger.info(f"My bots list updated for user {query.from_user.id}: {len(active_bots)} active bots")

@Bot.on_callback_query(filters.regex(r"toggle_(.+)"))
async def toggle_clone_callback(bot, query):
    clone_id = query.data.split("_")[1]
    clone = await db.clones.find_one({'_id': clone_id})
    if clone:
        new_status = not clone['active']
        await db.toggle_clone(clone_id, new_status)
        await query.answer(f"Bot {'activated' if new_status else 'deactivated'}!")
        await my_bots_callback(bot, query)
        logger.info(f"Bot @{clone['username']} toggled to {'active' if new_status else 'inactive'} by {query.from_user.id}")
    else:
        await query.answer("Bot not found!")
        await my_bots_callback(bot, query)
        logger.warning(f"Toggle attempt on non-existent bot ID: {clone_id}")

@Bot.on_callback_query(filters.regex(r"delete_(.+)"))
async def delete_clone_callback(bot, query):
    clone_id = query.data.split("_")[1]
    clone = await db.clones.find_one({'_id': clone_id})
    if clone:
        # Immediately remove from list (frontend)
        await query.answer(f"Bot @{clone['username']} deleted!")
        await my_bots_callback(bot, query)  # Instant list update
        
        # Perform actual deletion in background
        async def delete_in_background():
            try:
                result = await db.clones.delete_one({'_id': clone_id})
                if result.deleted_count == 1:
                    logger.info(f"Bot @{clone['username']} successfully removed from database by {query.from_user.id}")
                else:
                    logger.warning(f"Failed to remove bot @{clone['username']} from database")
            except Exception as e:
                logger.error(f"Error deleting bot @{clone['username']} from database: {str(e)}")

        asyncio.create_task(delete_in_background())
    else:
        await query.answer("Bot not found or already deleted!")
        await my_bots_callback(bot, query)
        logger.warning(f"Delete attempt on non-existent bot ID: {clone_id}")

# Reaction handling for main bot
@Bot.on_message(filters.group | filters.channel)
async def send_reaction(bot, msg: Message):
    await reaction_manager.add_reaction(bot, msg)

# Activate clones on startup
async def activate_clones():
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
                
                @clone_bot.on_message(filters.private & filters.command(["start"]))
                async def clone_start(client, update):
                    if hasattr(client, '_start_handled'):  # Prevent duplicate replies
                        return
                    client._start_handled = True
                    
                    clone_buttons = InlineKeyboardMarkup([
                        [InlineKeyboardButton("Add to Group", url=f"https://telegram.me/{clone['username']}?startgroup=botstart")],
                        [InlineKeyboardButton("Add to Channel", url=f"https://telegram.me/{clone['username']}?startchannel=botstart")],
                        [InlineKeyboardButton("Create Your Own Bot", url=f"https://telegram.me/{BOT_USERNAME}")]
                    ])
                    await update.reply_text(
                        text=CLONE_START_TEXT.format(BOT_USERNAME),
                        link_preview_options=LinkPreviewOptions(is_disabled=True),
                        reply_markup=clone_buttons
                    )
                    logger.info(f"Start command processed for clone @{clone['username']} by {update.from_user.id}")
                    await asyncio.sleep(1)  # Reset after a short delay
                    client._start_handled = False

                @clone_bot.on_message(filters.group | filters.channel)
                async def clone_reaction(client, msg):
                    clone_data = await db.get_clone(clone['token'])
                    if not clone_data or not clone_data['active']:
                        logger.warning(f"Clone @{clone['username']} is inactive or not found")
                        return
                    
                    try:
                        await client.get_chat_member(msg.chat.id, "me")
                        await reaction_manager.add_reaction(client, msg)
                        await db.update_connected_chats(clone['_id'], msg.chat.id)
                    except (UserNotParticipant, ChatAdminRequired):
                        await db.toggle_clone(clone['_id'], False)
                        logger.info(f"Bot @{clone['username']} disconnected from {msg.chat.id}")
                    except Exception as e:
                        logger.error(f"Error in reaction for @{clone['username']}: {str(e)}")
                
                asyncio.create_task(clone_bot.start())
                logger.info(f"Clone bot started: @{clone['username']}")
            except Exception as e:
                logger.error(f"Failed to start clone bot @{clone['username']}: {str(e)}")
                await db.toggle_clone(clone['_id'], False)

async def main():
    await Bot.start()
    logger.info("Main Bot Started!")
    await activate_clones()
    await asyncio.Future()  # Keep the bot running

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
