import os
import sys
import string
import random

from time import time
from urllib3 import disable_warnings
from cloudscraper import create_scraper

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery

from motor.motor_asyncio import AsyncIOMotorClient
from config import Config

# ================= MEMORY =================

verify_dict = {}
verification_last_sent = {}
verification_message_id = {}

VERIFICATION_COOLDOWN = 21600  # 6 hours

# ================= CONFIG =================

VERIFY_PHOTO = os.environ.get(
    'VERIFY_PHOTO',
    'https://images8.alphacoders.com/138/1384114.png'
)

SHORTLINK_SITE = os.environ.get('SHORTLINK_SITE', 'gplinks.com')
SHORTLINK_API = os.environ.get('SHORTLINK_API', '596f423cdf22b174e43d0b48a36a8274759ec2a3')
VERIFY_EXPIRE = int(os.environ.get('VERIFY_EXPIRE', 7260))
VERIFY_TUTORIAL = os.environ.get('VERIFY_TUTORIAL', 'https://t.me/N4_Society/55')

DATABASE_URL = Config.DB_URL
COLLECTION_NAME = os.environ.get('COLLECTION_NAME', 'Token1')
PREMIUM_USERS = list(map(int, os.environ.get('PREMIUM_USERS', '').split()))

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

# ================= HELPERS =================

async def is_user_verified(user_id):
    if not VERIFY_EXPIRE or user_id in PREMIUM_USERS:
        return True
    last = await verifydb.get_verify_status(user_id)
    return bool(last and (time() - last) < VERIFY_EXPIRE)

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

# ================= MARKUP =================

def get_verification_markup(link):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("ᴛᴜᴛᴏʀɪᴀʟ", url=VERIFY_TUTORIAL),
            InlineKeyboardButton("ɢᴇᴛ ᴛᴏᴋᴇɴ", url=link)
        ]
    ])

# ================= SHORTLINK =================

async def get_short_url(longurl):
    cget = create_scraper().request
    disable_warnings()
    try:
        url = f"https://{SHORTLINK_SITE}/api"
        res = cget("GET", url, params={
            "api": SHORTLINK_API,
            "url": longurl,
            "format": "text"
        })
        return res.text if res.status_code == 200 else longurl
    except:
        return longurl

async def get_verify_token(bot, user_id, base):
    v = verify_dict.setdefault(user_id, {})
    if "short_url" not in v:
        token = ''.join(random.choices(string.ascii_letters + string.digits, k=9))
        long = f"{base}verify-{user_id}-{token}"
        v["token"] = token
        v["short_url"] = await get_short_url(long)
    return v["short_url"]

# ================= CORE (ANTI-SPAM VERIFIED) =================

async def send_verification(client, message):
    user_id = message.from_user.id
    now = time()

    if await is_user_verified(user_id):
        return

    last = verification_last_sent.get(user_id, 0)
    msg_id = verification_message_id.get(user_id)

    # ⏳ 6 hours crossed → fresh start
    if last and (now - last) > VERIFICATION_COOLDOWN:
        verify_dict.pop(user_id, None)
        verification_message_id.pop(user_id, None)
        last = 0
        msg_id = None

    username = (await client.get_me()).username
    link = await get_verify_token(
        client,
        user_id,
        f"https://telegram.me/{username}?start="
    )

    caption = (
        f"<b>ʜɪ 👋 {message.from_user.mention}\n\n"
        f"ᴛᴏ ꜱᴛᴀʀᴛ ᴜꜱɪɴɢ ᴛʜɪꜱ ʙᴏᴛ,\n"
        f"ᴘʟᴇᴀꜱᴇ ᴠᴇʀɪꜰʏ ʏᴏᴜʀ ᴀᴅꜱ ᴛᴏᴋᴇɴ.\n\n"
        f"ᴠᴀʟɪᴅɪᴛʏ: {get_readable_time(VERIFY_EXPIRE)}</b>"
    )

    # 🔁 EDIT existing message (NO SPAM)
    if msg_id:
        try:
            await client.edit_message_caption(
                chat_id=message.chat.id,
                message_id=msg_id,
                caption=caption,
                reply_markup=get_verification_markup(link)
            )
            return
        except:
            verification_message_id.pop(user_id, None)

    # 🆕 SEND only if not exists
    sent = await client.send_photo(
        chat_id=message.chat.id,
        photo=VERIFY_PHOTO,
        caption=caption,
        reply_markup=get_verification_markup(link)
    )

    verification_last_sent[user_id] = now
    verification_message_id[user_id] = sent.id

# ================= VERIFY =================

async def validate_token(client, message, data):
    user_id = message.from_user.id
    v = verify_dict.get(user_id)

    if await is_user_verified(user_id):
        return await message.reply("Already verified.")

    if not v:
        return await send_verification(client, message)

    _, uid, token = data.split("-")

    if uid == str(user_id) and token == v.get("token"):
        verify_dict.pop(user_id, None)
        verification_last_sent.pop(user_id, None)
        verification_message_id.pop(user_id, None)

        await verifydb.update_verify_status(user_id)

        await client.send_photo(
            chat_id=user_id,
            photo=VERIFY_PHOTO,
            caption=f"<b>Verified Successfully!\nEnjoy for {get_readable_time(VERIFY_EXPIRE)} ❤️</b>"
        )
    else:
        await message.reply("Invalid or expired token.")

# ================= HANDLERS =================

@Client.on_message(filters.private & filters.regex(r"^/verify") & ~filters.bot)
async def verify_handler(c, m):
    parts = m.text.split()
    if len(parts) == 2 and parts[1].startswith("verify"):
        await validate_token(c, m, parts[1])
    else:
        await send_verification(c, m)
