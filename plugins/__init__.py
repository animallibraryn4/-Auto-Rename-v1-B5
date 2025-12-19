# ===================== IMPORTS =====================
import os
import string
import random
from time import time
from urllib3 import disable_warnings

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from cloudscraper import create_scraper
from motor.motor_asyncio import AsyncIOMotorClient

from config import Config, Txt

# ===================== CONFIG =====================
VERIFY_PHOTO = os.environ.get("VERIFY_PHOTO", "https://images8.alphacoders.com/138/1384114.png")
VERIFY_EXPIRE = int(os.environ.get("VERIFY_EXPIRE", 3020))
VERIFY_TUTORIAL = os.environ.get("VERIFY_TUTORIAL", "https://t.me/N4_Society/55")

SHORTLINK_SITE = os.environ.get("SHORTLINK_SITE", "gplinks.com")
SHORTLINK_API = os.environ.get("SHORTLINK_API", "")

DATABASE_URL = Config.DB_URL
COLLECTION_NAME = "Token1"

# ===================== MEMORY =====================
verify_cache = {}

# ===================== DATABASE =====================
class VerifyDB:
    def __init__(self):
        self.client = AsyncIOMotorClient(DATABASE_URL)
        self.col = self.client["verify-db"][COLLECTION_NAME]

    async def get(self, uid):
        x = await self.col.find_one({"id": uid})
        return x["time"] if x else 0

    async def set(self, uid):
        await self.col.update_one(
            {"id": uid},
            {"$set": {"time": time()}},
            upsert=True
        )

db = VerifyDB()

# ===================== HELPERS =====================
def readable(t):
    m, s = divmod(t, 60)
    h, m = divmod(m, 60)
    return f"{h}ʜ{m}ᴍ" if h else f"{m}ᴍ"

async def is_verified(uid):
    last = await db.get(uid)
    return last and (time() - last) < VERIFY_EXPIRE

async def short(url):
    try:
        disable_warnings()
        r = create_scraper().get(
            f"https://{SHORTLINK_SITE}/api",
            params={"api": SHORTLINK_API, "url": url, "format": "text"}
        )
        return r.text
    except:
        return url

# ===================== MARKUPS =====================
def verify_buttons(link):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Tutorial", url=VERIFY_TUTORIAL),
            InlineKeyboardButton("⭐ Premium", callback_data="premium_verify")
        ],
        [InlineKeyboardButton("Get Token", url=link)]
    ])

def verify_back():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅ Back", callback_data="back_verify")]
    ])

def welcome_buttons():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⭐ Premium", callback_data="premium_welcome")]
    ])

def welcome_back():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅ Back", callback_data="back_welcome")]
    ])

# ===================== CORE =====================
async def send_verify(client, chat_id, user):
    bot = await client.get_me()
    token = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
    link = await short(f"https://t.me/{bot.username}?start=verify-{user.id}-{token}")

    verify_cache[user.id] = token

    await client.send_photo(
        chat_id,
        VERIFY_PHOTO,
        caption=f"Hi 👋 {user.mention}\n\nPlease verify to continue.\nValidity: {readable(VERIFY_EXPIRE)}",
        reply_markup=verify_buttons(link)
    )

async def send_welcome(client, chat_id):
    await client.send_photo(
        chat_id,
        VERIFY_PHOTO,
        caption=f"<b>Welcome Back 😊\nVerified for {readable(VERIFY_EXPIRE)}</b>",
        reply_markup=welcome_buttons()
    )

# ===================== CALLBACKS =====================
@Client.on_callback_query(filters.regex("^premium_verify$"))
async def premium_verify(_, q: CallbackQuery):
    await q.message.edit_text(
        Txt.PREMIUM_TXT,
        reply_markup=verify_back(),
        disable_web_page_preview=True
    )

@Client.on_callback_query(filters.regex("^premium_welcome$"))
async def premium_welcome(_, q: CallbackQuery):
    await q.message.edit_text(
        Txt.PREMIUM_TXT,
        reply_markup=welcome_back(),
        disable_web_page_preview=True
    )

@Client.on_callback_query(filters.regex("^back_verify$"))
async def back_verify(client, q: CallbackQuery):
    await send_verify(client, q.message.chat.id, q.from_user)

@Client.on_callback_query(filters.regex("^back_welcome$"))
async def back_welcome(client, q: CallbackQuery):
    await send_welcome(client, q.message.chat.id)

# ===================== START / VERIFY =====================
@Client.on_message(filters.private & filters.command("start"))
async def start(client, m):
    if len(m.command) == 2 and m.command[1].startswith("verify"):
        _, uid, token = m.command[1].split("-")
        if uid == str(m.from_user.id) and verify_cache.get(m.from_user.id) == token:
            await db.set(m.from_user.id)
            await send_welcome(client, m.chat.id)
            return
    if await is_verified(m.from_user.id):
        await send_welcome(client, m.chat.id)
    else:
        await send_verify(client, m.chat.id, m.from_user)
