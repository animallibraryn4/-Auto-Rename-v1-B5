import os
import sys
import string
import random

from time import time
from urllib3 import disable_warnings
from cloudscraper import create_scraper

from pyrogram import Client, filters
from pyrogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    Message,
    CallbackQuery
)

from motor.motor_asyncio import AsyncIOMotorClient
from config import Config

verify_dict = {}

# ================= PREMIUM TEXT =================

PREMIUM_TXT = """<b>ᴜᴘɢʀᴀᴅᴇ ᴛᴏ ᴏᴜʀ ᴘʀᴇᴍɪᴜᴍ sᴇʀᴠɪᴄᴇ ᴀɴᴅ ᴇɴJᴏʏ ᴇxᴄʟᴜsɪᴠᴇ ғᴇᴀᴛᴜʀᴇs:

○ ᴜɴʟɪᴍɪᴛᴇᴅ Rᴇɴᴀᴍɪɴɢ  
○ ᴇᴀʀʟʏ Aᴄᴄᴇss  
○ ᴘʀɪᴏʀɪᴛʏ sᴜᴘᴘᴏʀᴛ

➲ Use /plan to see all plans.</b>
"""

# ================= CONFIG =================

VERIFY_PHOTO = os.environ.get(
    "VERIFY_PHOTO",
    "https://images8.alphacoders.com/138/1384114.png"
)

VERIFY_EXPIRE = int(os.environ.get("VERIFY_EXPIRE", 0))
DATABASE_URL = Config.DB_URL
COLLECTION_NAME = os.environ.get("COLLECTION_NAME", "Token1")
PREMIUM_USERS = list(map(int, os.environ.get("PREMIUM_USERS", "").split()))

# ================= DATABASE =================

class VerifyDB:
    def __init__(self):
        self.client = AsyncIOMotorClient(DATABASE_URL)
        self.db = self.client["verify-db"]
        self.col = self.db[COLLECTION_NAME]

    async def get_verify_status(self, user_id):
        data = await self.col.find_one({"id": user_id})
        return data.get("verify_status", 0) if data else 0

    async def update_verify_status(self, user_id):
        await self.col.update_one(
            {"id": user_id},
            {"$set": {"verify_status": time()}},
            upsert=True
        )

verifydb = VerifyDB()

# ================= KEYBOARDS =================

def welcome_markup():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("❌ Cancel", callback_data="close_message"),
            InlineKeyboardButton("⭐ Premium", callback_data="premium_page")
        ]
    ])

def premium_markup():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⬅️ Back", callback_data="back_to_welcome")
        ]
    ])

# ================= CALLBACKS =================

@Client.on_callback_query(filters.regex("^premium_page$"))
async def premium_page(client, query: CallbackQuery):
    await query.message.edit_text(
        PREMIUM_TXT,
        reply_markup=premium_markup(),
        disable_web_page_preview=True
    )
    await query.answer()

@Client.on_callback_query(filters.regex("^back_to_welcome$"))
async def back_to_welcome(client, query: CallbackQuery):
    await query.message.edit_caption(
        get_welcome_text(),
        reply_markup=welcome_markup()
    )
    await query.answer()

@Client.on_callback_query(filters.regex("^close_message$"))
async def close_message(client, query: CallbackQuery):
    try:
        await query.message.delete()
    except:
        pass
    await query.answer()

# ================= VERIFY LOGIC =================

async def is_user_verified(user_id):
    if not VERIFY_EXPIRE or user_id in PREMIUM_USERS:
        return True
    last = await verifydb.get_verify_status(user_id)
    return bool(last and (time() - last) < VERIFY_EXPIRE)

async def validate_token(client, message, data):
    user_id = message.from_user.id

    if await is_user_verified(user_id):
        return await message.reply("Already verified.")

    await verifydb.update_verify_status(user_id)

    await client.send_photo(
        chat_id=user_id,
        photo=VERIFY_PHOTO,
        caption=get_welcome_text(),
        reply_markup=welcome_markup()
    )

# ================= WELCOME TEXT (UPDATED) =================

def get_welcome_text():
    return (
        f"<b>ᴡᴇʟᴄᴏᴍᴇ ʙᴀᴄᴋ 😊\n"
        f"ʏᴏᴜʀ ᴛᴏᴋᴇɴ ʜᴀꜱ ʙᴇᴇɴ ꜱᴜᴄᴄᴇꜱꜰᴜʟʟʏ ᴠᴇʀɪꜰɪᴇᴅ.\n"
        f"ʏᴏᴜ ᴄᴀɴ ɴᴏᴡ ᴜꜱᴇ ᴍᴇ ꜰᴏʀ {get_readable_time(VERIFY_EXPIRE)}.\n\n"
        f"ɪꜰ ʏᴏᴜ ꜰɪɴᴅ ᴀɴʏ ᴛᴇᴄʜɴɪᴄᴀʟ ɪꜱꜱᴜᴇ, ᴘʟᴇᴀꜱᴇ ʀᴇᴘᴏʀᴛ ɪᴛ ᴛᴏ ᴜꜱ.\n"
        f"ᴡᴇ’ʟʟ ꜰɪx ɪᴛ ᴀꜱ ꜱᴏᴏɴ ᴀꜱ ᴘᴏꜱꜱɪʙʟᴇ ᴛᴏ ᴍᴀᴋᴇ ʏᴏᴜʀ ᴇxᴘᴇʀɪᴇɴᴄᴇ ʙᴇᴛᴛᴇʀ.\n\n"
        f"ᴇɴᴊᴏʏ ʏᴏᴜʀ ᴛɪᴍᴇ ❤️</b>"
    )

def get_readable_time(seconds):
    if seconds <= 0:
        return "∞"
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}ʜ{m}ᴍ"
    if m:
        return f"{m}ᴍ"
    return f"{s}s"
