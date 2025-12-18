import os
import sys
import string
import random
import asyncio
from time import time
from urllib.parse import quote
from urllib3 import disable_warnings

from pyrogram import Client, filters 
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery 

from cloudscraper import create_scraper
from motor.motor_asyncio import AsyncIOMotorClient
from config import Config, Txt 

# --- DATA TRACKING ---
verify_dict = {}
verification_messages = {}
verification_in_progress = {}

# --- CONFIG VARIABLES ---
VERIFY_PHOTO = os.environ.get('VERIFY_PHOTO', 'https://images8.alphacoders.com/138/1384114.png')
SHORTLINK_SITE = os.environ.get('SHORTLINK_SITE', 'gplinks.com')
SHORTLINK_API = os.environ.get('SHORTLINK_API', '596f423cdf22b174e43d0b48a36a8274759ec2a3')
VERIFY_EXPIRE = int(os.environ.get('VERIFY_EXPIRE', 7260))
VERIFY_TUTORIAL = os.environ.get('VERIFY_TUTORIAL', 'https://t.me/N4_Society/55')
DATABASE_URL = Config.DB_URL
COLLECTION_NAME = os.environ.get('COLLECTION_NAME', 'Token1')
PREMIUM_USERS = list(map(int, os.environ.get('PREMIUM_USERS', '').split())) if os.environ.get('PREMIUM_USERS') else []

# --- DATABASE CLASS ---
class VerifyDB():
    def __init__(self):
        try:
            self._dbclient = AsyncIOMotorClient(DATABASE_URL)
            self._db = self._dbclient['verify-db']
            self._verifydb = self._db[COLLECTION_NAME]  
            print('Database Connected ✅')
        except Exception as e:
            print(f'Failed To Connect To Database ❌. \nError: {str(e)}')
    
    async def get_verify_status(self, user_id):
        if status := await self._verifydb.find_one({'id': user_id}):
            return status.get('verify_status', 0)
        return 0

    async def update_verify_status(self, user_id):
        await self._verifydb.update_one({'id': user_id}, {'$set': {'verify_status': time()}}, upsert=True)

verifydb = VerifyDB()

# --- UTILITIES ---
def get_readable_time(seconds):
    periods = [('ᴅ', 86400), ('ʜ', 3600), ('ᴍ', 60), ('s', 1)]
    result = ''
    for period_name, period_seconds in periods:
        if seconds >= period_seconds:
            period_value, seconds = divmod(seconds, period_seconds)
            result += f'{int(period_value)}{period_name}'
    return result or "0s"

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
    vdict = verify_dict.get(userid, {})
    if vdict and (time() - vdict.get('generated_at', 0) < 600):
        return vdict['short_url']
    
    token = ''.join(random.choices(string.ascii_letters + string.digits, k=9))
    long_link = f"{link}verify-{userid}-{token}"
    short_url = await get_short_url(long_link)
    verify_dict[userid] = {'token': token, 'short_url': short_url, 'generated_at': time()}
    return short_url

# --- CORE VERIFICATION LOGIC ---
async def is_user_verified(user_id):
    if not VERIFY_EXPIRE or (user_id in PREMIUM_USERS):
        return True
    isveri = await verifydb.get_verify_status(user_id)
    if not isveri or (time() - isveri) >= float(VERIFY_EXPIRE):
        return False
    return True

async def send_verification(client, message):
    user_id = message.from_user.id
    if await is_user_verified(user_id):
        return
    
    if user_id in verification_in_progress:
        return
    
    verification_in_progress[user_id] = True
    try:
        current_time = time()
        if user_id in verification_messages:
            if current_time - verification_messages[user_id].get("sent_at", 0) < 5:
                return
        
        bot_obj = await client.get_me()
        username = bot_obj.username
        isveri = await verifydb.get_verify_status(user_id)
        verify_token = await get_verify_token(client, user_id, f"https://telegram.me/{username}?start=")
        
        text = f"ʜɪ 👋 {message.from_user.mention},\n\n"
        if not isveri:
            text += "ᴛᴏ ꜱᴛᴀʀᴛ ᴜꜱɪɴɢ ᴛʜɪꜱ ʙᴏᴛ, ᴘʟᴇᴀꜱᴇ ɢᴇɴᴇʀᴀᴛᴇ ᴀ ᴛᴇᴍᴘᴏʀᴀʀʏ ᴀᴅꜱ ᴛᴏᴋᴇɴ."
        else:
            text += "ʏᴏᴜʀ ᴀᴅꜱ ᴛᴏᴋᴇɴ ʜᴀꜱ ʙᴇᴇɴ ᴇxᴘɪʀᴇᴅ, ᴋɪɴᴅʟʏ ɢᴇᴛ ᴀ ɴᴇᴡ ᴛᴏᴋᴇɴ ᴛᴏ ᴄᴏɴᴛɪɴᴜᴇ."
        
        text += f"\n\nᴠᴀʟɪᴅɪᴛʏ: {get_readable_time(VERIFY_EXPIRE)}"
        
        buttons = get_verification_markup(verify_token, username)
        msg_to_use = message if isinstance(message, Message) else message.message
        
        sent_msg = await client.send_photo(
            chat_id=msg_to_use.chat.id,
            photo=VERIFY_PHOTO,
            caption=text,
            reply_markup=buttons
        )
        verification_messages[user_id] = {"message_id": sent_msg.id, "sent_at": current_time}
    finally:
        await asyncio.sleep(0.1)
        verification_in_progress.pop(user_id, None)

async def validate_token(client, message, data):
    user_id = message.from_user.id
    vdict = verify_dict.get(user_id, {})
    
    if await is_user_verified(user_id):
        return await message.reply("<b>Sɪʀ, Yᴏᴜ Aʀᴇ Aʟʀᴇᴀᴅʏ Vᴇʀɪғɪᴇᴅ 🤓...</b>")
    
    try:
        _, uid, token = data.split("-")
        if uid != str(user_id) or vdict.get('token') != token:
            return await send_verification(client, message)
        
        verify_dict.pop(user_id, None)
        await verifydb.update_verify_status(user_id)
        
        await client.send_photo(
            chat_id=user_id,
            photo=VERIFY_PHOTO,
            caption=f'<b>Wᴇʟᴄᴏᴍᴇ Bᴀᴄᴋ 😁, Nᴏᴡ Yᴏᴜ Cᴀɴ Usᴇ Mᴇ Fᴏʀ {get_readable_time(VERIFY_EXPIRE)}.\n\nEɴᴊᴏʏʏʏ...❤️</b>',
            reply_markup=get_welcome_markup()
        )
    except:
        await send_verification(client, message)

# --- KEYBOARDS ---
def get_verification_markup(verify_token, username):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton('ᴛᴜᴛᴏʀɪᴀʟ', url=VERIFY_TUTORIAL), InlineKeyboardButton('ᴘʀᴇᴍɪᴜᴍ', callback_data="premium_page")],
        [InlineKeyboardButton('ɢᴇᴛ ᴛᴏᴋᴇɴ', url=verify_token)]
    ])

def get_welcome_markup():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton('❌ Close', callback_data="close_message"), InlineKeyboardButton('🌟 Premium', callback_data="premium_page")],
        [InlineKeyboardButton('🔙 Back', callback_data="home_page")]
    ])

def get_premium_markup(is_verified=False):
    # If user is verified, Back button goes to Welcome screen. Otherwise, to Token screen.
    back_callback = "back_to_welcome" if is_verified else "home_page"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton('🔙 Back', callback_data=back_callback), InlineKeyboardButton('❌ Close', callback_data="close_message")]
    ])

# --- HANDLERS ---
@Client.on_callback_query(filters.regex("premium_page"))
async def premium_cb(client, query):
    user_id = query.from_user.id
    verified = await is_user_verified(user_id)
    markup = get_premium_markup(is_verified=verified)
    try:
        await query.message.edit_caption(caption=Txt.PREMIUM_TXT, reply_markup=markup)
    except Exception:
        await query.message.edit_text(Txt.PREMIUM_TXT, reply_markup=markup, disable_web_page_preview=True)

@Client.on_callback_query(filters.regex("back_to_welcome"))
async def back_to_welcome_cb(client, query):
    user_id = query.from_user.id
    if await is_user_verified(user_id):
        text = f'<b>Wᴇʟᴄᴏᴍᴇ Bᴀᴄᴋ 😁, Nᴏᴡ Yᴏᴜ Cᴀɴ Usᴇ Mᴇ Fᴏʀ {get_readable_time(VERIFY_EXPIRE)}.\n\nEɴᴊᴏʏʏʏ...❤️</b>'
        try:
            await query.message.edit_caption(caption=text, reply_markup=get_welcome_markup())
        except Exception:
            await query.message.edit_text(text, reply_markup=get_welcome_markup())
    else:
        # If verification expired while they were on the premium page
        await query.answer("Your token has expired!", show_alert=True)
        await home_cb(client, query)

@Client.on_callback_query(filters.regex("home_page"))
async def home_cb(client, query):
    await query.message.delete()
    await send_verification(client, query)

@Client.on_callback_query(filters.regex("close_message"))
async def close_cb(client, query):
    await query.message.delete()

@Client.on_callback_query(filters.regex("plan_command"))
async def plan_command_cb(client, query):
    await client.send_message(chat_id=query.message.chat.id, text="/plan")
    await query.message.delete()
    
