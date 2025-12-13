import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from helper.database import codeflixbots
from config import Config, Txt

# ===== BAN CHECK =====

async def is_banned(message):
    if message.from_user.id in Config.ADMIN:
        return False
    return await codeflixbots.is_banned(message.from_user.id)

# ===== START =====

@Client.on_message(filters.private & filters.command("start"))
async def start(client, message: Message):

    if await is_banned(message):
        await message.reply_text("🚫 You are banned.")
        return

    # ADD USER IN BACKGROUND (NO CRASH)
    asyncio.create_task(
        codeflixbots.add_user(client, message)
    )

    await message.reply_text(
        Txt.START_TXT.format(message.from_user.mention),
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("HELP", callback_data="help")]
        ])
    )
