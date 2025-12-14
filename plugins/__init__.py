import os
import sys
import string
import random

from time import time
from urllib.parse import quote
from urllib3 import disable_warnings

from pyrogram import Client, filters 
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message

from cloudscraper import create_scraper
from motor.motor_asyncio import AsyncIOMotorClient
#from config import DB_URL as DATABASE_URL

verify_dict = {}

# CONFIG VARIABLES 😄
VERIFY_PHOTO = os.environ.get('VERIFY_PHOTO', 'https://images8.alphacoders.com/138/1384114.png')  # YOUR VERIFY PHOTO LINK
SHORTLINK_SITE = os.environ.get('SHORTLINK_SITE', 'gplinks.com') # YOUR SHORTLINK URL LIKE:- site.com
SHORTLINK_API = os.environ.get('SHORTLINK_API', '596f423cdf22b174e43d0b48a36a8274759ec2a3') # YOUR SHORTLINK API LIKE:- ma82owowjd9hw6_js7
VERIFY_EXPIRE = os.environ.get('VERIFY_EXPIRE', 30000) # VERIFY EXPIRE TIME IN SECONDS. LIKE:- 0 (ZERO) TO OFF VERIFICATION 
VERIFY_TUTORIAL = os.environ.get('VERIFY_TUTORIAL', 'https://t.me/N4_Society/55') # LINK OF TUTORIAL TO VERIFY 
DATABASE_URL = os.environ.get('DATABASE_URL', 'mongodb+srv://n4animeedit:u80hdwhlka5NBFfY@cluster0.jowvb.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0') # MONGODB DATABASE URL To Store Verifications 
COLLECTION_NAME = os.environ.get('COLLECTION_NAME', 'Token1')   # Collection Name For MongoDB 
PREMIUM_USERS = list(map(int, os.environ.get('PREMIUM_USERS', '').split()))

missing = [v for v in ["COLLECTION_NAME", "VERIFY_PHOTO", "SHORTLINK_SITE", "SHORTLINK_API", "VERIFY_TUTORIAL"] if not v]; sys.exit(f"Missing: {', '.join(missing)}") if missing else None 

# DATABASE
class VerifyDB():
    def __init__(self):
        try:
            self._dbclient = AsyncIOMotorClient(DATABASE_URL)
            self._db = self._dbclient['verify-db']
            self._verifydb = self._db[COLLECTION_NAME]  
            print('Database Comnected ✅')
        except Exception as e:
            print(f'Failed To Connect To Database ❌. \nError: {str(e)}')
    
    async def get_verify_status(self, user_id):
        if status := await self._verifydb.find_one({'id': user_id}):
            return status.get('verify_status', 0)
        return 0

    async def update_verify_status(self, user_id):
        await self._verifydb.update_one({'id': user_id}, {'$set': {'verify_status': time()}}, upsert=True)

# TOKEN VALIDATION COMMAND HANDLER (New Implementation)
@Client.on_message(filters.private & filters.regex(r'^/verify') & ~filters.bot)
async def verify_command_handler(client, message):
    cmd = message.text.split()
    if len(cmd) == 2:
        data = cmd[1]
        if data.startswith("verify"):
            await validate_token(client, message, data)
    else:
        await send_verification(client, message)
        
# FUNCTIONS
async def is_user_verified(user_id):
    if not VERIFY_EXPIRE or (user_id in PREMIUM_USERS):
        return True
    isveri = await verifydb.get_verify_status(user_id)
    if not isveri or (time() - isveri) >= float(VERIFY_EXPIRE):
        return False
    return True    
    
async def send_verification(client, message, text=None, buttons=None):
    username = (await client.get_me()).username
    if done := await is_user_verified(message.from_user.id):
        text = f'<b>Hi 👋 {message.from_user.mention},\nYou Are Already Verified Enjoy 😄</b>'
    else:
        verify_token = await get_verify_token(client, message.from_user.id, f"https://telegram.me/{username}?start=")
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton('Get Token', url=verify_token)],
            [InlineKeyboardButton('🎬 Tutorial 🎬', url=VERIFY_TUTORIAL)]
        ])
    if not text:
        text = f"""<b>Hi 👋 {message.from_user.mention}, 
<blockquote expandable>\nYour Ads Token Has Been Expired, Kindly Get A New Token To Continue Using This Bot.
         ㅤㅤㅤㅤㅤ   - Thank You 
\nआपका विज्ञापन टोकन समाप्त हो गया है, बॉट को फिर से उपयोग करने के लिए नया टोकन लें!
         ㅤㅤㅤㅤㅤㅤㅤ- धन्यवाद
\nValidity: {get_readable_time(VERIFY_EXPIRE)}
\n#Verification...⌛</blockquote></b>"""
    message = message if isinstance(message, Message) else message.message
    await client.send_photo(
        chat_id=message.chat.id,
        photo=VERIFY_PHOTO,
        caption=text,
        reply_markup=buttons,
        reply_to_message_id=message.id,
    )
 
async def get_verify_token(bot, userid, link):
    vdict = verify_dict.setdefault(userid, {})
    short_url = vdict.get('short_url')
    if not short_url:
        token = ''.join(random.choices(string.ascii_letters + string.digits, k=9))
        long_link = f"{link}verify-{userid}-{token}"
        short_url = await get_short_url(long_link)
        vdict.update({'token': token, 'short_url': short_url})
    return short_url

async def get_short_url(longurl, shortener_site = SHORTLINK_SITE, shortener_api = SHORTLINK_API):
    cget = create_scraper().request
    disable_warnings()
    try:
        url = f'https://{shortener_site}/api'
        params = {'api': shortener_api,
                  'url': longurl,
                  'format': 'text',
                 }
        res = cget('GET', url, params=params)
        if res.status_code == 200 and res.text:
            return res.text
        else:
            params['format'] = 'json'
            res = cget('GET', url, params=params)
            res = res.json()
            if res.status_code == 200:
                return res.get('shortenedUrl', long_url)
    except Exception as e:
        print(e)
        return longurl

async def validate_token(client, message, data):
    user_id = message.from_user.id
    vdict = verify_dict.setdefault(user_id, {})
    dict_token = vdict.get('token', None)
    if await is_user_verified(user_id):
        return await message.reply("<b>Sɪʀ, Yᴏᴜ Aʀᴇ Aʟʀᴇᴀᴅʏ Vᴇʀɪғɪᴇᴅ 🤓...</b>")
    if not dict_token:
        return await send_verification(client, message, text="<b>Tʜᴀᴛ's Nᴏᴛ Yᴏᴜʀ Vᴇʀɪғʏ Tᴏᴋᴇɴ 🥲...\n\n\nTᴀᴘ Oɴ Vᴇʀɪғʏ Tᴏ Gᴇɴᴇʀᴀᴛᴇ Yᴏᴜʀs...</b>")  
    _, uid, token = data.split("-")
    if uid != str(user_id):
        return await send_verification(client, message, text="<b>Vᴇʀɪғʏ Tᴏᴋᴇɴ Dɪᴅ Nᴏᴛ Mᴀᴛᴄʜᴇᴅ 😕...\n\n\nTᴀᴘ Oɴ Vᴇʀɪғʏ Tᴏ Gᴇɴᴇʀᴀᴛᴇ Aɢᴀɪɴ...</b>")
    elif dict_token != token:
        return await send_verification(client, message, text="<b>Iɴᴠᴀʟɪᴅ Oʀ Exᴘɪʀᴇᴅ Tᴏᴋᴇɴ 🔗...</b>")
    verify_dict.pop(user_id, None)
    await verifydb.update_verify_status(user_id)
    await client.send_photo(chat_id=message.from_user.id,
                            photo=VERIFY_PHOTO,
                            caption=f'<b>Wᴇʟᴄᴏᴍᴇ Bᴀᴄᴋ 😁, Nᴏᴡ Yᴏᴜ Cᴀɴ Usᴇ Mᴇ Fᴏʀ {get_readable_time(VERIFY_EXPIRE)}.\n\n\nEɴᴊᴏʏʏʏ...❤️</b>',
                            reply_to_message_id=message.id,
                            )
    
def get_readable_time(seconds):
    periods = [('ᴅ', 86400), ('ʜ', 3600), ('ᴍ', 60), ('s', 1)]
    result = ''
    for period_name, period_seconds in periods:
        if seconds >= period_seconds:
            period_value, seconds = divmod(seconds, period_seconds)
            result += f'{int(period_value)}{period_name}'
    return result

verifydb = VerifyDB()
    

