import os
import time
import asyncio
import datetime
import aiofiles
from random import choice
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, LinkPreviewOptions
from pyrogram.errors import *
from database import Database
from config import *

# Database initialization
db = Database(DATABASE_URL, "autoreactionbot")

# Bot setup with in-memory storage
Bot = Client(
    name="AutoReactionBot",
    bot_token=BOT_TOKEN,
    api_id=API_ID,
    api_hash=API_HASH,
    in_memory=True
)

# Messages and buttons
START_TEXT = """<b>{},

ɪ ᴀᴍ sɪᴍᴘʟᴇ ʙᴜᴛ ᴘᴏᴡᴇʀꜰᴜʟʟ ᴀᴜᴛᴏ ʀᴇᴀᴄᴛɪᴏɴ ʙᴏᴛ.

ᴊᴜsᴛ ᴀᴅᴅ ᴍᴇ ᴀs ᴀ ᴀᴅᴍɪɴ ɪɴ ʏᴏᴜʀ ᴄʜᴀɴɴᴇʟ ᴏʀ ɢʀᴏᴜᴘ ᴛʜᴇɴ sᴇᴇ ᴍʏ ᴘᴏᴡᴇʀ</b>"""

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
        return 200, None
    except FloodWait as e:
        await asyncio.sleep(e.value)
        return await send_msg(user_id, message)
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
            link_preview_options=LinkPreviewOptions(is_disabled=True)
        )
        return False
    else:
        return True

# Smart reaction handler with rate limit handling
async def smart_react(client, msg):
    try:
        await client.react(msg.chat.id, msg.id, choice(EMOJIS))
    except FloodWait as e:
        await asyncio.sleep(e.value)
        await smart_react(client, msg)
    except Exception as e:
        print(f"Reaction error: {str(e)}")

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
        link_preview_options=LinkPreviewOptions(is_disabled=True),
        reply_markup=START_BUTTONS
    )

@Bot.on_message(filters.private & filters.command("users") & filters.user(BOT_OWNER))
async def users(bot, update):
    total_users = await db.total_users_count()
    text = f"Bot Status\n\nTotal Users: {total_users}"
    await update.reply_text(
        text=text,
        quote=True,
        link_preview_options=LinkPreviewOptions(is_disabled=True)
    )

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

# Clone handling
@Bot.on_message(filters.private & filters.text & filters.regex(r'^[A-Za-z0-9]+:[A-Za-z0-9_-]+$'))
async def handle_clone_token(bot, message):
    token = message.text
    processing_msg = await message.reply("⏳ Processing your clone request...")
    
    # Check if token is already cloned
    existing_clone = await db.get_clone(token)
    if existing_clone:
        await processing_msg.edit(f"❌ This bot token is already cloned as @{existing_clone['username']}!")
        return

    try:
        temp_client = Client(name="temp", bot_token=token, api_id=API_ID, api_hash=API_HASH, in_memory=True)
        try:
            await temp_client.start()
        except FloodWait as e:
            await asyncio.sleep(e.value)
            await temp_client.start()
        
        bot_info = await temp_client.get_me()
        await temp_client.stop()

        clone_data = await db.add_clone(message.from_user.id, token, bot_info.username)
        
        clone_buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("Add to Group", url=f"https://telegram.me/{bot_info.username}?startgroup=botstart")],
            [InlineKeyboardButton("Add to Channel", url=f"https://telegram.me/{bot_info.username}?startchannel=botstart")],
            [InlineKeyboardButton("Create Your Own Bot", url=f"https://telegram.me/{BOT_USERNAME}")]
        ])

        await processing_msg.edit(
            f"✅ Bot cloned successfully!\n\nUsername: @{bot_info.username}\nParent: @{BOT_USERNAME}",
            reply_markup=clone_buttons
        )

        clone_bot = Client(name=f"clone_{bot_info.username}", bot_token=token, api_id=API_ID, api_hash=API_HASH, in_memory=True)
        
        @clone_bot.on_message(filters.private & filters.command(["start"]))
        async def clone_start(client, update):
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

        @clone_bot.on_message(filters.group | filters.channel)
        async def clone_reaction(client, msg):
            clone_data = await db.get_clone(token)
            if not clone_data or not clone_data['active']:
                return
            
            try:
                await client.get_chat_member(msg.chat.id, "me")
                asyncio.create_task(smart_react(client, msg))  # Async reaction
                await db.update_connected_chats(clone_data['_id'], msg.chat.id)
            except (UserNotParticipant, ChatAdminRequired):
                await db.toggle_clone(clone_data['_id'], False)
                print(f"Bot @{bot_info.username} disconnected from {msg.chat.id}")
            except Exception as e:
                print(f"Error in reaction for @{bot_info.username}: {str(e)}")
        
        asyncio.create_task(clone_bot.start())

    except FloodWait as e:
        await processing_msg.edit(f"⏳ Please wait {e.value} seconds due to Telegram flood limits and try again.")
    except Exception as e:
        await processing_msg.edit(f"❌ Failed to clone bot: {str(e)}")

@Bot.on_callback_query(filters.regex("clone_bot"))
async def clone_bot_callback(bot, query):
    await query.message.reply(CLONE_TEXT)

@Bot.on_callback_query(filters.regex("my_bots"))
async def my_bots_callback(bot, query):
    clones = await db.get_user_clones(query.from_user.id)
    if not clones:
        current_text = query.message.text or ""
        if current_text != "You haven't cloned any bots yet!":
            await query.message.edit_text("You haven't cloned any bots yet!")
        return

    buttons = []
    seen_usernames = set()
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
            except Exception:
                await db.clones.delete_one({'_id': clone['_id']})
                print(f"Removed deleted bot @{clone['username']} from DB")
                continue

    new_text = MY_BOTS_TEXT if buttons else "No active bots found!"
    current_text = query.message.text or ""
    if current_text != new_text or not buttons:
        await query.message.edit_text(
            new_text,
            reply_markup=InlineKeyboardMarkup(buttons) if buttons else None
        )

@Bot.on_callback_query(filters.regex(r"toggle_(.+)"))
async def toggle_clone_callback(bot, query):
    clone_id = query.data.split("_")[1]
    clone = await db.clones.find_one({'_id': clone_id})
    if clone:
        new_status = not clone['active']
        await db.toggle_clone(clone_id, new_status)
        await query.answer(f"Bot {'activated' if new_status else 'deactivated'}!")
        await my_bots_callback(bot, query)
    else:
        await query.answer("Bot not found!")
        await my_bots_callback(bot, query)

@Bot.on_callback_query(filters.regex(r"delete_(.+)"))
async def delete_clone_callback(bot, query):
    clone_id = query.data.split("_")[1]
    clone = await db.clones.find_one({'_id': clone_id})
    if clone:
        await db.clones.delete_one({'_id': clone_id})
        await query.answer(f"Bot @{clone['username']} deleted successfully!")
        await my_bots_callback(bot, query)
    else:
        await query.answer("Bot not found or already deleted!")
        await my_bots_callback(bot, query)

# Reaction handling for main bot
@Bot.on_message(filters.group | filters.channel)
async def send_reaction(bot, msg: Message):
    asyncio.create_task(smart_react(bot, msg))

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

                @clone_bot.on_message(filters.group | filters.channel)
                async def clone_reaction(client, msg):
                    clone_data = await db.get_clone(clone['token'])
                    if not clone_data or not clone_data['active']:
                        return
                    
                    try:
                        await client.get_chat_member(msg.chat.id, "me")
                        asyncio.create_task(smart_react(client, msg))
                        await db.update_connected_chats(clone['_id'], msg.chat.id)
                    except (UserNotParticipant, ChatAdminRequired):
                        await db.toggle_clone(clone['_id'], False)
                        print(f"Bot @{clone['username']} disconnected from {msg.chat.id}")
                    except Exception as e:
                        print(f"Error in reaction for @{clone['username']}: {str(e)}")
                
                asyncio.create_task(clone_bot.start())
                print(f"Started clone bot: @{clone['username']}")
            except Exception as e:
                print(f"Failed to start clone bot @{clone['username']}: {str(e)}")
                await db.toggle_clone(clone['_id'], False)

async def main():
    await Bot.start()
    print("Main Bot Started!")
    await activate_clones()
    await asyncio.Future()  # Keep the bot running

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
