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

# In-memory dictionary to store active tokens and shortlinks
verify_dict = {}

# --- PREMIUM TEXTS ---
PREMIUM_TXT = """<b>ᴜᴘɢʀᴀᴅᴇ ᴛᴏ ᴏᴜʀ ᴘʀᴇᴍɪᴜᴍ sᴇʀᴠɪᴄᴇ ᴀɴᴅ ᴇɴJᴏʏ ᴇxᴄʟᴜsɪᴠᴇ ғᴇᴀᴛᴜʀᴇs:
○ ᴜɴʟɪᴍɪᴛᴇᴅ Rᴇɴᴀᴍɪɴɢ
○ ᴇᴀʀʟʏ Aᴄᴄᴇss

• ᴜꜱᴇ /plan ᴛᴏ ꜱᴇᴇ ᴀʟʟ ᴏᴜʀ ᴘʟᴀɴꜱ ᴀᴛ ᴏɴᴄᴇ.</b>"""

PREPLANS_TXT = """<b><pre>🎖️Available Plans:</pre>
➜ Monthly Premium: ₹109/month
➜ weekly Premium: ₹49/month
➜ Daily Premium: ₹19/day
➲ UPI ID - <code>bbc@</code></b>"""

# CONFIG VARIABLES
VERIFY_PHOTO = os.environ.get('VERIFY_PHOTO', 'https://images8.alphacoders.com/138/1384114.png')
SHORTLINK_SITE = os.environ.get('SHORTLINK_SITE', 'gplinks.com')
SHORTLINK_API = os.environ.get('SHORTLINK_API', '596f423cdf22b174e43d0b48a36a8274759ec2a3')
VERIFY_EXPIRE = int(os.environ.get('VERIFY_EXPIRE', 600))
VERIFY_TUTORIAL = os.environ.get('VERIFY_TUTORIAL', 'https://t.me/N4_Society/55')
DATABASE_URL = Config.DB_URL
COLLECTION_NAME = os.environ.get('COLLECTION_NAME', 'Token1')
PREMIUM_USERS = list(map(int, os.environ.get('PREMIUM_USERS', '').split()))

# DATABASE
class VerifyDB():
    def __init__(self):
        try:
            self._dbclient = AsyncIOMotorClient(DATABASE_URL)
            self._db = self._dbclient['verify-db']
            self._verifydb = self._db[COLLECTION_NAME]  
            print('Database Connected ✅')
        except Exception as e:
            print(f'Failed To Connect To Database ❌. Error: {str(e)}')
    
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

# --- MARKUPS ---

def get_verification_markup(verify_token, username):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton('ᴛᴜᴛᴏʀɪᴀʟ', url=VERIFY_TUTORIAL),
            InlineKeyboardButton('ᴘʀᴇᴍɪᴜᴍ', callback_data="premium_page")
        ],
        [
            InlineKeyboardButton('ɢᴇᴛ ᴛᴏᴋᴇɴ', url=verify_token)
        ]
    ])

def get_premium_markup():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton('ʙᴀᴄᴋ', callback_data="home_page"),
         InlineKeyboardButton('ᴘʟᴀɴ', callback_data="plan_page")]
    ])

def get_plan_markup():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton('ʙᴀᴄᴋ', callback_data="premium_page"),
         InlineKeyboardButton('ᴄᴀɴᴄᴇʟ', callback_data="close_message")],
        [InlineKeyboardButton('ʜᴏᴍᴇ', callback_data="home_page")]
    ])

# --- CORE FUNCTIONS (REUSE LOGIC) ---

async def get_short_url(longurl):
    cget = create_scraper().request
    disable_warnings()
    try:
        url = f'https://{SHORTLINK_SITE}/api'
        params = {'api': SHORTLINK_API, 'url': longurl, 'format': 'text'}
        res = cget('GET', url, params=params)
        if res.status_code == 200 and res.text:
            return res.text
        else:
            params['format'] = 'json'
            res = cget('GET', url, params=params).json()
            return res.get('shortenedUrl', longurl)
    except Exception as e:
        print(f"Shortlink Error: {e}")
        return longurl

async def get_verify_token(bot, userid, link):
    # Check if a link already exists in dictionary
    vdict = verify_dict.setdefault(userid, {})
    short_url = vdict.get('short_url')
    
    if not short_url:
        # Generate new link only if none exists
        token = ''.join(random.choices(string.ascii_letters + string.digits, k=9))
        long_link = f"{link}verify-{userid}-{token}"
        short_url = await get_short_url(long_link)
        vdict.update({'token': token, 'short_url': short_url})
    
    return short_url

async def send_verification(client, message, text=None, buttons=None):
    user_id = message.from_user.id
    username = (await client.get_me()).username
    
    # Safety: check if verified
    if await is_user_verified(user_id):
        return

    # REUSE LOGIC: Get existing or new token
    verify_token = await get_verify_token(client, user_id, f"https://telegram.me/{username}?start=")
    buttons = get_verification_markup(verify_token, username)
    isveri = await verifydb.get_verify_status(user_id)

    if not isveri:
        text = f"ʜɪ 👋 {message.from_user.mention},\n\nᴛᴏ ꜱᴛᴀʀᴛ ᴜꜱɪɴɢ ᴛʜɪꜱ ʙᴏᴛ, ᴘʟᴇᴀꜱᴇ ɢᴇɴᴇʀᴀᴛᴇ ᴀ ᴛᴇᴍᴘᴏʀᴀʀʏ ᴀᴅꜱ ᴛᴏᴋᴇɴ.\n\nᴠᴀʟɪᴅɪᴛʏ: {get_readable_time(VERIFY_EXPIRE)}"
    else:
        text = f"ʜɪ 👋 {message.from_user.mention},\n\nʏᴏᴜʀ ᴀᴅꜱ ᴛᴏᴋᴇɴ ʜᴀꜱ ʙᴇᴇɴ ᴇxᴘɪʀᴇᴅ, ᴋɪɴᴅʟʏ ɢᴇᴛ ᴀ ɴᴇᴡ ᴛᴏᴋᴇɴ.\n\nᴠᴀʟɪᴅɪᴛʏ: {get_readable_time(VERIFY_EXPIRE)}"

    msg = message if isinstance(message, Message) else message.message
    await client.send_photo(
        chat_id=msg.chat.id,
        photo=VERIFY_PHOTO,
        caption=text,
        reply_markup=buttons
    )

async def validate_token(client, message, data):
    user_id = message.from_user.id
    vdict = verify_dict.get(user_id, {})
    dict_token = vdict.get('token')

    if await is_user_verified(user_id):
        return await message.reply("<b>Sɪʀ, Yᴏᴜ Aʀᴇ Aʟʀᴇᴀᴅʏ Vᴇʀɪғɪᴇᴅ 🤓</b>")

    if not dict_token:
        return await send_verification(client, message)

    _, uid, token = data.split("-")
    if uid != str(user_id) or dict_token != token:
        return await message.reply("<b>Invalid Token or Token Mismatch!</b>")

    # CLEANUP: Verification Successful
    verify_dict.pop(user_id, None)
    await verifydb.update_verify_status(user_id)
    
    await client.send_photo(
        chat_id=user_id,
        photo=VERIFY_PHOTO,
        caption=f'<b>Wᴇʟᴄᴏᴍᴇ Bᴀᴄᴋ 😁, Nᴏᴡ Yᴏᴜ Cᴀɴ Usᴇ Mᴇ Fᴏʀ {get_readable_time(VERIFY_EXPIRE)}.\n\nEɴᴊᴏʏʏʏ...❤️</b>'
    )

# --- HANDLERS ---

@Client.on_message(filters.private & filters.regex(r'^/verify') & ~filters.bot)
async def verify_command_handler(client, message):
    cmd = message.text.split()
    if len(cmd) == 2 and cmd[1].startswith("verify"):
        await validate_token(client, message, cmd[1])
    else:
        await send_verification(client, message)

@Client.on_callback_query(filters.regex("premium_page"))
async def premium_callback(client, query):
    await query.message.edit_text(PREMIUM_TXT, reply_markup=get_premium_markup())

@Client.on_callback_query(filters.regex("plan_page"))
async def plan_callback(client, query):
    await query.message.edit_text(PREPLANS_TXT, reply_markup=get_plan_markup())

@Client.on_callback_query(filters.regex("home_page"))
async def home_callback(client, query):
    await query.message.delete()
    await send_verification(client, query)

@Client.on_callback_query(filters.regex("close_message"))
async def close_callback(client, query):
    await query.message.delete()

