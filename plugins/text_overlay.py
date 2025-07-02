
from pyrogram import Client, filters
from pyrogram.types import Message
from helper.database import codeflixbots
from config import Config, Txt

@Client.on_message(filters.private & filters.command("settext") & filters.user(Config.ADMIN))
async def set_custom_text(client, message):
    if len(message.command) == 1:
        return await message.reply_text(
            "**Please provide the text you want to display\n\n"
            "Example:** `/settext Visit @Animelibraryn4 for more content`"
        )
    
    text = message.text.split(" ", 1)[1]
    await codeflixbots.set_custom_text(message.from_user.id, text)
    await message.reply_text("✅ Custom text saved successfully!")

@Client.on_message(filters.private & filters.command("settexttime") & filters.user(Config.ADMIN))
async def set_text_timing(client, message):
    if len(message.command) < 3:
        return await message.reply_text(
            "**Please provide interval and duration in seconds\n\n"
            "Example:** `/settexttime 600 30` (shows text every 10 minutes for 30 seconds)"
        )
    
    try:
        interval = int(message.command[1])
        duration = int(message.command[2])
        await codeflixbots.set_text_timing(message.from_user.id, interval, duration)
        await message.reply_text(
            f"✅ Timing set successfully!\n"
            f"Text will appear every {interval} seconds for {duration} seconds"
        )
    except ValueError:
        await message.reply_text("Please provide valid numbers for interval and duration")

@Client.on_message(filters.private & filters.command("viewtext"))
async def view_custom_text(client, message):
    text = await codeflixbots.get_custom_text(message.from_user.id)
    interval, duration = await codeflixbots.get_text_timing(message.from_user.id)
    
    if text:
        response = (
            f"**Current text overlay settings (Admin Only):**\n\n"
            f"📝 Text: `{text}`\n"
            f"⏱ Interval: Every `{interval}` seconds\n"
            f"⏳ Duration: `{duration}` seconds"
        )
    else:
        response = "❌ No custom text overlay is currently set by admin"
    
    await message.reply_text(response)
