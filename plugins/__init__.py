import os
import sys
import string
import random

from time import time
from urllib.parse import quote
from urllib3 import disable_warnings

from pyrogram import Client, filters 
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery 

from cloudscraper import create_scraper
from motor.motor_asyncio import AsyncIOMotorClient
from config import Config 

# In-memory storage
verify_dict = {}
verification_last_sent = {}
# ✅ STEP 1: Store last verification message_id (per user)
verification_message_id = {}

# Cooldown Configuration
VERIFICATION_COOLDOWN = 21600 # 6 Hours

# CONFIG VARIABLES
VERIFY_PHOTO = os.environ.get('VERIFY_PHOTO', 'https://images8.alphacoders.com/138/1384114.png')
SHORTLINK_SITE = os.environ.get('SHORTLINK_SITE', 'gplinks.com')
SHORTLINK_API = os.environ.get('SHORTLINK_API', '596f423cdf22b174e43d0b48a36a8274759ec2a3')
VERIFY_EXPIRE = int(os.environ.get('VERIFY_EXPIRE', 0))
VERIFY_TUTORIAL = os.environ.get('VERIFY_TUTORIAL', 'https://t.me/N4_Society/55')
DATABASE_URL = Config.DB_URL
COLLECTION_NAME = os.environ.get('COLLECTION_NAME', 'Token1')
PREMIUM_USERS = list(map(int, os.environ.get('PREMIUM_USERS', '').split()))

# DATABASE (VerifyDB class remains same as before)
class VerifyDB():
    def __init__(self):
        try:
            self._dbclient = AsyncIOMotorClient(DATABASE_URL)
            self._db = self._dbclient['verify-db']
            self._verifydb = self._db[COLLECTION_NAME]  
        except Exception as e:
            print(f'DB Error: {str(e)}')
    
    async def get_verify_status(self, user_id):
        if status := await self._verifydb.find_one({'id': user_id}):
            return status.get('verify_status', 0)
        return 0

    async def update_verify_status(self, user_id):
        await self._verifydb.update_one({'id': user_id}, {'$set': {'verify_status': time()}}, upsert=True)

verifydb = VerifyDB()

# --- HELPERS ---

async def is_user_verified(user_id):
    if not VERIFY_EXPIRE or (user_id in PREMIUM_USERS):
        return True
    isveri = await verifydb.get_verify_status(user_id)
    if not isveri or (time() - isveri) >= float(VERIFY_EXPIRE):
        return False
    return True

def get_readable_time(seconds):
    periods = [('ᴅ', 86400), ('ʜ', 3600), ('ᴍ', 60), ('s', 1)]
    result = ''
    for period_name, period_seconds in periods:
        if seconds >= period_seconds:
            period_value, seconds = divmod(seconds, period_seconds)
            result += f'{int(period_value)}{period_name}'
    return result

async def get_short_url(longurl):
    cget = create_scraper().request
    try:
        url = f'https://{SHORTLINK_SITE}/api'
        params = {'api': SHORTLINK_API, 'url': longurl, 'format': 'text'}
        res = cget('GET', url, params=params)
        return res.text if res.status_code == 200 else longurl
    except:
        return longurl

async def get_verify_token(bot, userid, link):
    vdict = verify_dict.setdefault(userid, {})
    short_url = vdict.get('short_url')
    if not short_url:
        token = ''.join(random.choices(string.ascii_letters + string.digits, k=9))
        long_link = f"{link}verify-{userid}-{token}"
        short_url = await get_short_url(long_link)
        vdict.update({'token': token, 'short_url': short_url})
    return short_url

# --- CORE FUNCTION: SEND OR EDIT VERIFICATION ---

async def send_verification(client, message, text=None, buttons=None):
    user_id = message.from_user.id
    now = time()

    if await is_user_verified(user_id):
        return

    last_time = verification_last_sent.get(user_id, 0)
    msg_id = verification_message_id.get(user_id)

    # ✅ Rule: Agar cooldown ke andar hai, toh naya message mat bhejo, purana edit karo
    if last_time and (now - last_time) < VERIFICATION_COOLDOWN:
        if msg_id:
            try:
                # Sirf caption edit karenge, photo wahi rahegi
                await client.edit_message_caption(
                    chat_id=message.chat.id,
                    message_id=msg_id,
                    caption=f"ʜɪ 👋 {message.from_user.mention},\n\nᴛᴏ ꜱᴛᴀʀᴛ ᴜꜱɪɴɢ ᴛʜɪꜱ ʙᴏᴛ, ᴘʟᴇᴀꜱᴇ ᴠᴇʀɪꜰʏ ʏᴏᴜʀ ᴀᴅꜱ ᴛᴏᴋᴇɴ.\n\nᴠᴀʟɪᴅɪᴛʏ: {get_readable_time(VERIFY_EXPIRE)}",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton('ᴛᴜᴛᴏʀɪᴀʟ', url=VERIFY_TUTORIAL),
                         InlineKeyboardButton('ᴘʀᴇᴍɪᴜᴍ', callback_data="premium_page")],
                        [InlineKeyboardButton('ɢᴇᴛ ᴛᴏᴋᴇɴ', url=verify_dict[user_id]["short_url"])]
                    ])
                )
            except:
                pass # Agar user ne message delete kar diya ho toh error na aaye
        return

    # ⏳ 6 Hours Gap check: Reset state
    if last_time and (now - last_time) > VERIFICATION_COOLDOWN:
        verify_dict.pop(user_id, None)
        verification_message_id.pop(user_id, None)

    # Naya message bhejna (First time ya 6hr baad)
    username = (await client.get_me()).username
    verify_token = await get_verify_token(client, user_id, f"https://telegram.me/{username}?start=")
    
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton('ᴛᴜᴛᴏʀɪᴀʟ', url=VERIFY_TUTORIAL),
         InlineKeyboardButton('ᴘʀᴇᴍɪᴜᴍ', callback_data="premium_page")],
        [InlineKeyboardButton('ɢᴇᴛ ᴛᴏᴋᴇɴ', url=verify_token)]
    ])

    sent = await client.send_photo(
        chat_id=message.chat.id,
        photo=VERIFY_PHOTO,
        caption=f"ʜɪ 👋 {message.from_user.mention},\n\nᴛᴏ ꜱᴛᴀʀᴛ ᴜꜱɪɴɢ ᴛʜɪꜱ ʙᴏᴛ, ᴘʟᴇᴀꜱᴇ ᴠᴇʀɪꜰʏ ʏᴏᴜʀ ᴀᴅꜱ ᴛᴏᴋᴇɴ.\n\nᴠᴀʟɪᴅɪᴛʏ: {get_readable_time(VERIFY_EXPIRE)}",
        reply_markup=markup
    )

    # 🧠 STATE SAVE
    verification_last_sent[user_id] = now
    verification_message_id[user_id] = sent.id

# --- CLEANUP ON VALIDATION ---

async def validate_token(client, message, data):
    user_id = message.from_user.id
    vdict = verify_dict.get(user_id, {})
    dict_token = vdict.get('token')

    if await is_user_verified(user_id):
        return await message.reply("<b>Sɪʀ, Yᴏᴜ Aʀᴇ Aʟʀᴇᴀᴅʏ Vᴇʀɪғɪᴇᴅ 🤓</b>")

    if not dict_token:
        return await send_verification(client, message)

    _, uid, token = data.split("-")
    if uid == str(user_id) and dict_token == token:
        # ✅ RESET ALL FLAGS
        verify_dict.pop(user_id, None)
        verification_last_sent.pop(user_id, None)
        verification_message_id.pop(user_id, None)
        
        await verifydb.update_verify_status(user_id)
        await client.send_photo(
            chat_id=user_id,
            photo=VERIFY_PHOTO,
            caption=f"<b>Verified! Enjoy for {get_readable_time(VERIFY_EXPIRE)}.</b>"
        )
    else:
        await message.reply("<b>Invalid Token!</b>")

# (Handlers like @Client.on_message remain the same)

