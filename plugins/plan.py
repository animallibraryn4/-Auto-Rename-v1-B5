import asyncio
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import Txt, Config

# Plan Command Handler
@Client.on_message(filters.command("plan"))
async def premium(bot, message):
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("sᴇɴᴅ ss", url="https://t.me/Anime_library_n4"), InlineKeyboardButton("ᴄʟᴏsᴇ", callback_data="close")]
    ])
    yt = await message.reply_photo(
        photo='https://graph.org/file/8b50e21db819f296661b7.jpg', 
        caption=Txt.PREPLANS_TXT, 
        reply_markup=buttons
    )
    await asyncio.sleep(300)
    await yt.delete()
    await message.delete()

