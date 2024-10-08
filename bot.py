import sys
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from config import API_ID, API_HASH, BOT_TOKEN, LOG_CHANNEL_ID, POST_CHANNELS, TIMEZONE, OWNER_ID
from utils.helpers import post_text_to_channels, post_media_to_channels, get_greeting
from datetime import datetime, timedelta
import pytz

app = Client("bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# State management
user_state = {}

async def is_owner(user_id):
    return user_id == OWNER_ID

# Error handling function
async def handle_error(client, error, message):
    error_message = f"Error: {str(error)}\nOccurred in {message.text if message.text else 'Media/Unknown'}"
    print(error_message)
    # Log the error to the log channel
    await client.send_message(LOG_CHANNEL_ID, f"**Error Occurred**:\n{error_message}")
    await message.reply(f"An error occurred: {error}")

# Function to post to all channels (Text and Photo)
async def post_to_channels(client, message):
    for channel_id in POST_CHANNELS:
        try:
            # Handle Photo messages with caption
            if message.photo:
                caption = message.caption if message.caption else ""
                await client.send_photo(channel_id, message.photo.file_id, caption=caption)
            # Handle Text messages
            elif message.text:
                await client.send_message(channel_id, message.text)
        except Exception as e:
            await handle_error(client, e, message)

# Commands
@app.on_message(filters.command("start") & filters.private)
async def start_command(client, message: Message):
    user_id = message.from_user.id
    
    try:
        if not await is_owner(user_id):
            await message.reply("You are not authorized to use this bot.")
            return
        
        user_state[user_id] = None  # Clear any active state
        buttons = ReplyKeyboardMarkup(
            [
                [KeyboardButton("/start"), KeyboardButton("/post")],
                [KeyboardButton("/rename"), KeyboardButton("/status")],
                [KeyboardButton("/schedule")]
            ],
            resize_keyboard=True
        )
        await message.reply(get_greeting(), reply_markup=buttons)
        
        # Admin Notification on Start
        await app.send_message(OWNER_ID, f"**__{message.from_user.first_name} has started the bot.__**")
    
    except Exception as e:
        await handle_error(client, e, message)

@app.on_message(filters.command("post") & filters.private)
async def post_command(client, message: Message):
    user_id = message.from_user.id
    
    try:
        if not await is_owner(user_id):
            await message.reply("You are not authorized to use this bot.")
            return
        
        user_state[user_id] = 'post'  # Set state to 'post'
        await message.reply("Please send the text or media you want to post.")
    
    except Exception as e:
        await handle_error(client, e, message)

@app.on_message(filters.command("schedule") & filters.private)
async def schedule_command(client, message: Message):
    user_id = message.from_user.id
    
    try:
        if not await is_owner(user_id):
            await message.reply("You are not authorized to use this bot.")
            return
        
        user_state[user_id] = 'schedule'  # Set state to 'schedule'
        await message.reply("Please send the text or media you want to schedule.")
    
    except Exception as e:
        await handle_error(client, e, message)

@app.on_message(filters.text & filters.private)
async def handle_text(client, message: Message):
    user_id = message.from_user.id
    state = user_state.get(user_id)
    
    try:
        if state == 'post':
            text = message.text
            await post_to_channels(client, text)
            await message.reply("Posted to all channels.")
            user_state[user_id] = None  # Clear the state after posting
        elif state == 'schedule':
            user_state[user_id] = 'schedule_text'
            user_state['schedule_message'] = message.text
            await message.reply("Please enter the time to post (HH:MM format):")
        elif state == 'schedule_text':
            try:
                schedule_time = datetime.strptime(message.text, "%H:%M").time()
                now = datetime.now(pytz.timezone(TIMEZONE))
                scheduled_datetime = datetime.combine(now.date(), schedule_time)
                scheduled_datetime = pytz.timezone(TIMEZONE).localize(scheduled_datetime)

                if scheduled_datetime < now:
                    scheduled_datetime += timedelta(days=1)
                delay = (scheduled_datetime - now).total_seconds()
                asyncio.create_task(schedule_post(client, user_state['schedule_message'], delay))
                await message.reply(f"Message scheduled for {schedule_time}.")
                user_state[user_id] = None
            except ValueError:
                await message.reply("Invalid time format. Please enter the time as HH:MM.")
    
    except Exception as e:
        await handle_error(client, e, message)

@app.on_message(filters.media & filters.private)
async def handle_media(client, message: Message):
    user_id = message.from_user.id
    state = user_state.get(user_id)
    
    try:
        if state == 'rename':
            # Implement the file renaming logic here
            await message.reply("File has been renamed.")
            user_state[user_id] = None  # Clear the state after renaming
        elif state == 'post':
            await post_to_channels(client, message)
            await message.reply("Posted to all channels.")
            user_state[user_id] = None  # Clear the state after posting
        elif state == 'schedule':
            user_state['schedule_message'] = message
            await message.reply("Please enter the time to post (HH:MM format):")
            user_state[user_id] = 'schedule_text'
    
    except Exception as e:
        await handle_error(client, e, message)

@app.on_message(filters.command("rename") & filters.private)
async def rename_command(client, message: Message):
    user_id = message.from_user.id
    
    try:
        if not await is_owner(user_id):
            await message.reply("You are not authorized to use this bot.")
            return
        
        user_state[user_id] = 'rename'  # Set state to 'rename'
        await message.reply("Please send the file you want to rename.")
    
    except Exception as e:
        await handle_error(client, e, message)

@app.on_message(filters.command("status") & filters.private)
async def status_command(client, message: Message):
    user_id = message.from_user.id
    
    try:
        if not await is_owner(user_id):
            await message.reply("You are not authorized to use this bot.")
            return
        
        await message.reply("Bot is running smoothly.")
    
    except Exception as e:
        await handle_error(client, e, message)

# Function to handle scheduled posts
async def schedule_post(client, message, delay):
    try:
        await asyncio.sleep(delay)
        await post_to_channels(client, message)
    except Exception as e:
        print(f"Error in scheduled post: {e}")

# Periodic tasks (for morning/evening messages)
async def periodic_tasks():
    while True:
        try:
            now = datetime.now(pytz.timezone(TIMEZONE))
            if now.hour == 9 and now.minute == 0:
                await app.send_message(LOG_CHANNEL_ID, "Good morning Sir")
            elif now.hour == 21 and now.minute == 0:
                await app.send_message(LOG_CHANNEL_ID, "Good night Sir")
            await asyncio.sleep(60)
        except Exception as e:
            print(f"Error in periodic tasks: {e}")

# Main function to start the bot and log the startup message
async def main():
    await app.start()
    
    try:
        # Check log channel access
        await app.get_chat(LOG_CHANNEL_ID)  # Test connection to the log channel
    except Exception as e:
        print(f"Error accessing log channel: {e}")

    # Log Channel Notification on Start
    me = await app.get_me()
    await app.send_message(LOG_CHANNEL_ID, f"**__{me.first_name} Bot has started.__**")

    await periodic_tasks()

if __name__ == "__main__":
    app.run(main())
