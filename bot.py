import logging
import sys
import asyncio
from pyrogram import Client, filters
from pyrogram.errors import FloodWait
from pyrogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from config import API_ID, API_HASH, BOT_TOKEN, LOG_CHANNEL_ID, POST_CHANNELS, TIMEZONE
from utils.helpers import get_greeting, handle_photo, post_to_channels, log_to_channel
from datetime import datetime
import pytz

# Setup logging to stdout
logging.basicConfig(level=logging.INFO, stream=sys.stdout, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Client("bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# State management
user_state = {}

# Commands
@app.on_message(filters.command("start") & filters.private)
async def start_command(client, message: Message):
    user_id = message.from_user.id
    user_state[user_id] = None  # Clear any active state
    buttons = ReplyKeyboardMarkup(
        [
            [KeyboardButton("/start"), KeyboardButton("/post")],
            [KeyboardButton("/rename"), KeyboardButton("/status")],
            [KeyboardButton("/log")]
        ],
        resize_keyboard=True
    )
    await message.reply(get_greeting(), reply_markup=buttons)

@app.on_message(filters.command("post") & filters.private)
async def post_command(client, message: Message):
    user_id = message.from_user.id
    user_state[user_id] = 'post'  # Set state to 'post'
    await message.reply("Please send the text you want to post.")

@app.on_message(filters.text & filters.private)
async def handle_text(client, message: Message):
    user_id = message.from_user.id
    if user_state.get(user_id) == 'post':
        text = message.text
        if text.strip():  # Check if text is not empty
            try:
                await post_to_channels(client, text)
                await message.reply("Posted to all channels.")
            except FloodWait as e:
                logger.warning(f"FloodWait error: {e} seconds. Retrying after wait.")
                await asyncio.sleep(e.x)
                await post_to_channels(client, text)
                await message.reply("Posted to all channels after waiting.")
            user_state[user_id] = None  # Clear the state after posting
        else:
            await message.reply("The message is empty. Please send valid text.")

@app.on_message(filters.command("rename") & filters.private)
async def rename_command(client, message: Message):
    user_id = message.from_user.id
    user_state[user_id] = 'rename'  # Set state to 'rename'
    await message.reply("Please send the file you want to rename.")

@app.on_message(filters.photo | filters.document | filters.video | filters.audio | filters.sticker & filters.private)
async def handle_media(client, message: Message):
    user_id = message.from_user.id
    if user_state.get(user_id) == 'rename':
        # Implement the file renaming logic here
        await message.reply("File has been renamed.")
        user_state[user_id] = None  # Clear the state after renaming
    elif user_state.get(user_id) == 'post':
        if message.text:
            try:
                await post_to_channels(client, message.text)
                log_message = f"Posted message from {message.from_user.username}: {message.text}"
                await log_to_channel(client, log_message)
            except FloodWait as e:
                logger.warning(f"FloodWait error: {e} seconds. Retrying after wait.")
                await asyncio.sleep(e.x)
                await post_to_channels(client, message.text)
                await log_to_channel(client, log_message)
        else:
            try:
                await post_to_channels(client, "Media posted")
            except FloodWait as e:
                logger.warning(f"FloodWait error: {e} seconds. Retrying after wait.")
                await asyncio.sleep(e.x)
                await post_to_channels(client, "Media posted")
        user_state[user_id] = None  # Clear the state after posting

@app.on_message(filters.command("status") & filters.private)
async def status_command(client, message: Message):
    user_id = message.from_user.id
    user_state[user_id] = None  # Clear any active state
    await message.reply("Bot is running smoothly.")

@app.on_message(filters.command("log") & filters.private)
async def log_command(client, message: Message):
    user_id = message.from_user.id
    user_state[user_id] = None  # Clear any active state
    log_message = "Bot log: " + get_greeting()
    await log_to_channel(client, log_message)
    await message.reply("Logged to the channel.")

async def periodic_tasks():
    while True:
        now = datetime.now(pytz.timezone(TIMEZONE))
        if now.hour == 9 and now.minute == 0:
            await app.send_message(LOG_CHANNEL_ID, "Good morning message")
        if now.hour == 21 and now.minute == 0:
            await app.send_message(LOG_CHANNEL_ID, "Good night message")
        await asyncio.sleep(60)

async def main():
    await app.start()
    await periodic_tasks()

if __name__ == "__main__":
    try:
        app.run(main())
    except Exception as e:
        logger.error(f"An error occurred: {e}")
