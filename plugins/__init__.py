import os
import string
import random
from time import time
from urllib3 import disable_warnings

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery

from cloudscraper import create_scraper
from motor.motor_asyncio import AsyncIOMotorClient
from config import Config, Txt

# =====================================================
# MEMORY (SIMPLE & STABLE)
# =====================================================

verify_dict = {}              # user_id → {token, short_url, generated_at}
last_verify_message = {}      # user_id → last sent time (anti spam)

VERIFY_MESSAGE_COOLDOWN = 5   # seconds
SHORTLINK_REUSE_TIME = 600    # 10 minutes

# =====================================================
# CONFIG
# =====================================================

VERIFY_PHOTO = os.environ.get(
    "VERIFY_PHOTO",
    "https://images8.alphacoders.com/138/1384114.png"
)
SHORTLINK_SITE = os.environ.get("SHORTLINK_SITE", "gplinks.com")
SHORTLINK_API = os.environ.get("SHORTLINK_API", "")
VERIFY_EXPIRE = int(os.environ.get("VERIFY_EXPIRE", 3000))
VERIFY_TUTORIAL = os.environ.get("VERIFY_TUTORIAL", "https://t.me/N4_Society/55")

DATABASE_URL = Config.DB_URL
COLLECTION_NAME = os.environ.get("COLLECTION_NAME", "Token1")
PREMIUM_USERS = list(map(int, os.environ.get("PREMIUM_USERS", "").split())) if os.environ.get("PREMIUM_USERS") else []

# =====================================================
# DATABASE
# =====================================================

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

# =====================================================
# HELPERS
# =====================================================

def get_readable_time(seconds):
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}ʜ{m}ᴍ"
    if m:
        return f"{m}ᴍ"
    return f"{s}s"

async def is_user_verified(user_id):
    if not VERIFY_EXPIRE or user_id in PREMIUM_USERS:
        return True
    last = await verifydb.get_verify_status(user_id)
    return bool(last and (time() - last) < VERIFY_EXPIRE)

# =====================================================
# SHORTLINK
# =====================================================

async def get_short_url(longurl):
    cget = create_scraper().request
    disable_warnings()
    try:
        res = cget(
            "GET",
            f"https://{SHORTLINK_SITE}/api",
            params={"api": SHORTLINK_API, "url": longurl, "format": "text"}
        )
        return res.text if res.status_code == 200 else longurl
    except:
        return longurl

async def get_verify_token(bot, user_id, base):
    data = verify_dict.get(user_id)

    if data and (time() - data["generated_at"] < SHORTLINK_REUSE_TIME):
        return data["short_url"]

    token = "".join(random.choices(string.ascii_letters + string.digits, k=9))
    long_link = f"{base}verify-{user_id}-{token}"
    short_url = await get_short_url(long_link)

    verify_dict[user_id] = {
        "token": token,
        "short_url": short_url,
        "generated_at": time()
    }
    return short_url

# =====================================================
# MARKUPS
# =====================================================

def verify_markup(link):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Tutorial", url=VERIFY_TUTORIAL),
            InlineKeyboardButton("Premium", callback_data="premium_page")
        ],
        [InlineKeyboardButton("Get Token", url=link)]
    ])

def welcome_markup():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("❌ Cancel", callback_data="close_message"),
            InlineKeyboardButton("⭐ Premium", callback_data="premium_page")
        ]
    ])

def premium_markup():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅ Back", callback_data="back_to_welcome")]
    ])

# =====================================================
# CORE VERIFICATION (STABLE)
# =====================================================

async def send_verification(client, message):
    user_id = message.from_user.id

    if await is_user_verified(user_id):
        return

    now = time()
    last = last_verify_message.get(user_id, 0)

    # hard anti-spam
    if now - last < VERIFY_MESSAGE_COOLDOWN:
        return

    bot = await client.get_me()
    link = await get_verify_token(client, user_id, f"https://t.me/{bot.username}?start=")

    text = (
        f"Hi 👋 {message.from_user.mention}\n\n"
        f"To start using this bot, please complete Ads Token verification.\n\n"
        f"Validity: {get_readable_time(VERIFY_EXPIRE)}"
    )

    await client.send_photo(
        chat_id=message.chat.id,
        photo=VERIFY_PHOTO,
        caption=text,
        reply_markup=verify_markup(link)
    )

    last_verify_message[user_id] = now

async def validate_token(client, message, data):
    user_id = message.from_user.id
    stored = verify_dict.get(user_id)

    if await is_user_verified(user_id):
        return await message.reply("Already verified.")

    if not stored:
        return await send_verification(client, message)

    _, uid, token = data.split("-")

    if uid == str(user_id) and token == stored["token"]:
        verify_dict.pop(user_id, None)
        last_verify_message.pop(user_id, None)

        await verifydb.update_verify_status(user_id)

        await client.send_photo(
            chat_id=user_id,
            photo=VERIFY_PHOTO,
            caption=(
                f"<b>Welcome Back 😊\n"
                f"Your token has been successfully verified.\n"
                f"You can now use me for {get_readable_time(VERIFY_EXPIRE)}.\n\n"
                f"Enjoy ❤️</b>"
            ),
            reply_markup=welcome_markup()
        )
    else:
        await send_verification(client, message)

# =====================================================
# CALLBACKS
# =====================================================

@Client.on_callback_query(filters.regex("^premium_page$"))
async def premium_cb(client, query: CallbackQuery):
    await query.message.edit_text(
        Txt.PREMIUM_TXT,
        reply_markup=premium_markup(),
        disable_web_page_preview=True
    )

@Client.on_callback_query(filters.regex("^back_to_welcome$"))
async def back_cb(client, query: CallbackQuery):
    await query.message.edit_caption(
        caption=(
            f"<b>Welcome Back 😊\n"
            f"You can now use me for {get_readable_time(VERIFY_EXPIRE)}.\n\n"
            f"Enjoy ❤️</b>"
        ),
        reply_markup=welcome_markup()
    )

@Client.on_callback_query(filters.regex("^close_message$"))
async def close_cb(client, query: CallbackQuery):
    await query.message.delete()

# =====================================================
# VERIFY COMMAND
# =====================================================

@Client.on_message(filters.private & filters.command("verify"))
async def verify_cmd(client, message):
    if len(message.command) == 2 and message.command[1].startswith("verify"):
        await validate_token(client, message, message.command[1])
    else:
        await send_verification(client, message)
