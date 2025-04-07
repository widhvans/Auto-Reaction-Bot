import os
import time
import asyncio
import datetime
import aiofiles
from random import choice
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from pyrogram.errors import *
from database import Database
from config import *

# Database initialization
db = Database(DATABASE_URL, "autoreactionbot")

# Bot setup
Bot = Client(
    "Auto Reaction Bot",
    bot_token=BOT_TOKEN,
    api_id=API_ID,
    api_hash=API_HASH,
)

# Messages and buttons
START_TEXT = """<b>{},

ɪ ᴀᴍ sɪᴍᴘʟᴇ ʙᴜᴛ ᴘᴏᴡᴇʀꜰᴜʟʟ ᴀᴜᴛᴏ ʀᴇᴀᴄᴛɪᴏɴ ʙᴏᴛ.

ᴊᴜsᴛ ᴀᴅᴅ ᴍᴇ ᴀs ᴀ ᴀᴅᴍɪɴ ɪɴ ʏᴏᴜʀ ᴄʜᴀɴɴᴇʟ ᴏʀ ɢʀᴏᴜᴘ ᴛʜᴇɴ sᴇᴇ ᴍʏ ᴘᴏᴡᴇʀ

<blockquote>ᴍᴀɪɴᴛᴀɪɴᴇᴅ ʙʏ : <a href='https://telegram.me/CallOwnerBot'>ʀᴀʜᴜʟ</a></blockquote></b>"""

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
        return 200, None
    except FloodWait as e:
        await asyncio.sleep(e.value)
        return send_msg(user_id, message)
    except (InputUserDeactivated, UserIsBlocked):
        return 400, f"{user_id} : error\n"
    except Exception as e:
        return 500, f"{user_id} : {str(e)}\n"

async def get_fsub(bot, message):
    target_channel_id = AUTH_CHANNEL
    user_id = message.from_user.id
    try:
        await bot.get_chat_member(target_channel_id, user_id)
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
        )
        return False
    else:
        return True

# Handlers
@Bot.on_message(filters.private & filters.command(["start"]))
async def start(bot, update):
    if not await db.is_user_exist(update.from_user.id):
        await db.add_user(update.from_user.id)
        await bot.send_message(LOG_CHANNEL, LOG_TEXT.format(update.from_user.id, update.from_user.mention))
    
    is_subscribed = await get_fsub(bot, update)
    if not is_subscribed:
        return

    await update.reply_text(
        text=START_TEXT.format(update.from_user.mention),
        disable_web_page_preview=True,
        reply_markup=START_BUTTONS
    )

@Bot.on_message(filters.private & filters.command("users") & filters.user(BOT_OWNER))
async def users(bot, update):
    total_users = await db.total_users_count()
    text = f"Bot Status\n\nTotal Users: {total_users}"
    await update.reply_text(
        text=text,
        quote=True,
        disable_web_page_preview=True
    )

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

    completed_in = datetime.timedelta(seconds=int(time.time() - start_time))
    await asyncio.sleep(3)
    await out.delete()
    if failed == 0:
        await update.reply_text(
            text=f"Broadcast completed in `{completed_in}`\n\nTotal users {total_users}.\nDone: {done}, Success: {success}, Failed: {failed}",
            quote=True
        )
    else:
        await update.reply_document(
            document='broadcast.txt',
            caption=f"Broadcast completed in `{completed_in}`\n\nTotal users {total_users}.\nDone: {done}, Success: {success}, Failed: {failed}"
        )
    os.remove('broadcast.txt')

# Clone handling
@Bot.on_message(filters.private & filters.text & filters.regex(r'^[A-Za-z0-9]+:[A-Za-z0-9_-]+$'))
async def handle_clone_token(bot, message):
    token = message.text
    try:
        # Verify token by creating temporary client
        temp_client = Client("temp", bot_token=token, api_id=API_ID, api_hash=API_HASH)
        await temp_client.start()
        bot_info = await temp_client.get_me()
        await temp_client.stop()

        # Add clone to database
        clone_data = await db.add_clone(message.from_user.id, token, bot_info.username)
        
        # Create clone buttons
        clone_buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("Add to Group", url=f"https://telegram.me/{bot_info.username}?startgroup=botstart")],
            [InlineKeyboardButton("Add to Channel", url=f"https://telegram.me/{bot_info.username}?startchannel=botstart")],
            [InlineKeyboardButton("Parent Bot", url=f"https://telegram.me/{BOT_USERNAME}")]
        ])

        await message.reply(
            f"✅ Bot cloned successfully!\n\nUsername: @{bot_info.username}\nParent: @{BOT_USERNAME}",
            reply_markup=clone_buttons
        )

        # Start the cloned bot instance
        clone_bot = Client(f"clone_{bot_info.username}", bot_token=token, api_id=API_ID, api_hash=API_HASH)
        @clone_bot.on_message(filters.all)
        async def clone_reaction(client, msg):
            try:
                await msg.react(choice(EMOJIS))
            except:
                pass
        asyncio.create_task(clone_bot.start())

    except Exception as e:
        await message.reply(f"❌ Failed to clone bot: {str(e)}")

@Bot.on_callback_query(filters.regex("clone_bot"))
async def clone_bot_callback(bot, query):
    await query.message.reply(CLONE_TEXT)

@Bot.on_callback_query(filters.regex("my_bots"))
async def my_bots_callback(bot, query):
    clones = await db.get_user_clones(query.from_user.id)
    if not clones:
        await query.message.reply("You haven't cloned any bots yet!")
        return

    buttons = []
    for clone in clones:
        status = "✅" if clone['active'] else "❌"
        buttons.append([
            InlineKeyboardButton(f"{status} @{clone['username']}", callback_data=f"toggle_{clone['_id']}"),
            InlineKeyboardButton("Delete", callback_data=f"delete_{clone['_id']}")
        ])

    await query.message.reply(
        MY_BOTS_TEXT,
        reply_markup=InlineKeyboardMarkup(buttons)
    )

@Bot.on_callback_query(filters.regex(r"toggle_(.+)"))
async def toggle_clone_callback(bot, query):
    clone_id = query.data.split("_")[1]
    clone = await db.clones.find_one({'_id': clone_id})
    new_status = not clone['active']
    await db.toggle_clone(clone_id, new_status)
    await query.answer(f"Bot {'activated' if new_status else 'deactivated'}!")
    await my_bots_callback(bot, query)

@Bot.on_callback_query(filters.regex(r"delete_(.+)"))
async def delete_clone_callback(bot, query):
    clone_id = query.data.split("_")[1]
    await db.clones.delete_one({'_id': clone_id})
    await query.answer("Bot deleted!")
    await my_bots_callback(bot, query)

# Reaction handling
@Bot.on_message(filters.all)
async def send_reaction(_, msg: Message):
    try:
        await msg.react(choice(EMOJIS))
    except:
        pass

# Start bot
Bot.run()
