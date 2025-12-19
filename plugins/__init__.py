import os
import string
import random
from time import time
from urllib3 import disable_warnings

from pyrogram import Client, filters
from pyrogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    Message,
    CallbackQuery
)

from cloudscraper import create_scraper
from motor.motor_asyncio import AsyncIOMotorClient
from config import Config, Txt

# =====================================================
# MEMORY
# =====================================================

verify_dict = {}
last_verify_message = {}
verify_message_ids = {}
user_state = {}        # user_id → "verified" / "verification"
user_prev_state = {}   # for back button

VERIFY_MESSAGE_COOLDOWN = 5
SHORTLINK_REUSE_TIME = 600

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

PREMIUM_USERS = (
    list(map(int, os.environ.get("PREMIUM_USERS", "").split()))
    if os.environ.get("PREMIUM_USERS") else []
)

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

async def delete_verification_messages(client, user_id):
    for msg_id in verify_message_ids.get(user_id, []):
        try:
            await client.delete_messages(user_id, msg_id)
        except:
            pass
    verify_message_ids.pop(user_id, None)

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

    if data and time() - data["generated_at"] < SHORTLINK_REUSE_TIME:
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
            InlineKeyboardButton("⭐ Premium", callback_data="premium_page")
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
# CORE FUNCTIONS
# =====================================================

async def send_verification(client, message_or_query):
    if isinstance(message_or_query, CallbackQuery):
        user_id = message_or_query.from_user.id
        chat_id = message_or_query.message.chat.id
        mention = message_or_query.from_user.mention
        message_obj = message_or_query.message
    else:
        user_id = message_or_query.from_user.id
        chat_id = message_or_query.chat.id
        mention = message_or_query.from_user.mention
        message_obj = None

    if await is_user_verified(user_id):
        return

    now = time()
    if now - last_verify_message.get(user_id, 0) < VERIFY_MESSAGE_COOLDOWN:
        return

    bot = await client.get_me()
    link = await get_verify_token(client, user_id, f"https://t.me/{bot.username}?start=")

    user_state[user_id] = "verification"

    text = (
        f"Hi 👋 {mention}\n\n"
        f"Please complete Ads Token verification to continue.\n\n"
        f"Validity: {get_readable_time(VERIFY_EXPIRE)}"
    )

    if message_obj:
        try:
            sent = await message_obj.edit_media(
                media=VERIFY_PHOTO,
                caption=text,
                reply_markup=verify_markup(link)
            )
        except:
            await message_obj.delete()
            sent = await client.send_photo(
                chat_id,
                VERIFY_PHOTO,
                caption=text,
                reply_markup=verify_markup(link)
            )
    else:
        sent = await client.send_photo(
            chat_id,
            VERIFY_PHOTO,
            caption=text,
            reply_markup=verify_markup(link)
        )

    verify_message_ids.setdefault(user_id, []).append(sent.id)
    last_verify_message[user_id] = now

async def send_welcome_message(client, user_id, message_obj=None):
    user_state[user_id] = "verified"

    text = (
        "<b>Welcome Back 😊\n"
        "Your token has been successfully verified.\n"
        f"You can use me for {get_readable_time(VERIFY_EXPIRE)}.\n\n"
        "Enjoy ❤️</b>"
    )

    if message_obj:
        try:
            await message_obj.edit_caption(text, reply_markup=welcome_markup())
        except:
            await message_obj.delete()
            await client.send_photo(
                user_id,
                VERIFY_PHOTO,
                caption=text,
                reply_markup=welcome_markup()
            )
    else:
        await client.send_photo(
            user_id,
            VERIFY_PHOTO,
            caption=text,
            reply_markup=welcome_markup()
        )

async def validate_token(client, message, data):
    user_id = message.from_user.id
    stored = verify_dict.get(user_id)

    if await is_user_verified(user_id):
        return

    if not stored:
        return await send_verification(client, message)

    _, uid, token = data.split("-")

    if uid == str(user_id) and token == stored["token"]:
        verify_dict.pop(user_id, None)
        await verifydb.update_verify_status(user_id)
        await delete_verification_messages(client, user_id)
        await send_welcome_message(client, user_id)
    else:
        await send_verification(client, message)

# =====================================================
# CALLBACKS
# =====================================================

@Client.on_callback_query(filters.regex("^premium_page$"))
async def premium_cb(client, query: CallbackQuery):
    user_id = query.from_user.id
    user_prev_state[user_id] = user_state.get(user_id, "verification")

    await query.message.edit_text(
        Txt.PREMIUM_TXT,
        reply_markup=premium_markup(),
        disable_web_page_preview=True
    )

@Client.on_callback_query(filters.regex("^back_to_welcome$"))
async def back_cb(client, query: CallbackQuery):
    user_id = query.from_user.id
    prev = user_prev_state.get(user_id, "verification")

    if prev == "verified":
        await send_welcome_message(client, user_id, query.message)
    else:
        await send_verification(client, query)

    user_prev_state.pop(user_id, None)

@Client.on_callback_query(filters.regex("^close_message$"))
async def close_cb(client, query: CallbackQuery):
    user_state.pop(query.from_user.id, None)
    await query.message.delete()

# =====================================================
# COMMANDS
# =====================================================

@Client.on_message(filters.private & filters.command("verify"))
async def verify_cmd(client, message):
    if len(message.command) == 2:
        await validate_token(client, message, message.command[1])
    else:
        await send_verification(client, message)

@Client.on_message(filters.private & filters.command("get_token"))
async def get_token_cmd(client, message):
    await send_verification(client, message)
