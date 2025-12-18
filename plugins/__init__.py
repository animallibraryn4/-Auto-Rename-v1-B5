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
from config import Config 

# ================= MEMORY =================
# Enhanced verification tracking
verify_dict = {}
verification_data = {}  # Stores verification message info per user
VERIFICATION_COOLDOWN = 21600  # 6 hours
VERIFICATION_RESEND_COOLDOWN = 300  # 5 minutes - minimal time before sending new message

# ================= PREMIUM TEXTS =================
PREMIUM_TXT = """<b>ᴜᴘɢʀᴀᴅᴇ ᴛᴏ ᴏᴜʀ ᴘʀᴇᴍɪᴜᴍ sᴇʀᴠɪᴄᴇ ᴀɴᴅ ᴇɴJᴏʏ ᴇxᴄʟᴜsɪᴠᴇ ғᴇᴀᴛᴜʀᴇs:
○ ᴜɴʟɪᴍɪᴛᴇᴅ Rᴇɴᴀᴍɪɴɢ: ʀᴇɴᴀᴍᴇ ᴀs ᴍᴀɴʏ ғɪʟᴇs ᴀs ʏᴏᴜ ᴡᴀɴᴛ ᴡɪᴛʜᴏᴜᴛ ᴀɴʏ ʀᴇsᴛʀɪᴄᴛɪᴏɴs.
○ ᴇᴀʀʟʏ Aᴄᴄᴇss: ʙᴇ ᴛʜᴇ ғɪʀsᴛ ᴛᴏ ᴛᴇsᴛ ᴀɴᴅ ᴜsᴇ ᴏᴜʀ ʟᴀᴛᴇsᴛ ғᴇᴀᴛᴜʀᴇs ʙᴇғᴏʀᴇ ᴀɴʏᴏɴᴇ ᴇʟsᴇ.

• ᴜꜱᴇ /plan ᴛᴏ ꜱᴇᴇ ᴀʟʟ ᴏᴜʀ ᴘʟᴀɴꜱ ᴀᴛ ᴏɴᴄᴇ.

➲ ғɪʀsᴛ sᴛᴇᴘ : ᴘᴀʏ ᴛʜᴇ ᴀᴍᴏᴜɴᴛ ᴀᴄᴄᴏʀᴅɪɴɢ ᴛᴏ ʏᴏᴜʀ ғᴀᴠᴏʀɪᴛᴇ ᴘʟᴀɴ ᴛᴏ ᴛʜɪs fam ᴜᴘɪ ɪᴅ.

➲ sᴇᴄᴏɴᴅ sᴛᴇᴘ : ᴛᴀᴋᴇ ᴀ sᴄʀᴇᴇɴsʜᴏᴛ ᴏғ ʏᴏᴜʀ ᴘᴀʏᴍᴇɴᴟ ᴀɴᴅ sʜᴀʀᴇ ɪᴛ ᴅɪʀᴇᴄᴛʟʏ ʜᴇʀᴇ: @ 

➲ ᴀʟᴛᴇʀɴᴀᴛɪᴠᴇ sᴛᴇᴘ : ᴏʀ ᴜᴘʟᴏᴀᴅ ᴛʜᴇ sᴄʀᴇᴇɴsʜᴏᴛ ʜᴇʀᴇ ᴀɴᴅ ʀᴇᴘʟʏ ᴡɪᴛʜ ᴛʜᴇ /bought ᴄᴏᴍᴍᴀɴᴅ.

Your premium plan will be activated after verification.</b>"""

PREPLANS_TXT = """<b><pre>🎖️Available Plans:</pre>

Pricing:
➜ Monthly Premium: ₹109/month
➜ weekly Premium: ₹49/month
➜ Daily Premium: ₹19/day
➜ Contact: @Anime_Library_N4

➲ UPI ID - <code>bbc@</code>

‼️ Upload the payment screenshot here and reply with the /bought command.</b>"""

# ================= CONFIG VARIABLES =================
VERIFY_PHOTO = os.environ.get('VERIFY_PHOTO', 'https://images8.alphacoders.com/138/1384114.png')
SHORTLINK_SITE = os.environ.get('SHORTLINK_SITE', 'gplinks.com')
SHORTLINK_API = os.environ.get('SHORTLINK_API', '596f423cdf22b174e43d0b48a36a8274759ec2a3')
VERIFY_EXPIRE = int(os.environ.get('VERIFY_EXPIRE', 7260))
VERIFY_TUTORIAL = os.environ.get('VERIFY_TUTORIAL', 'https://t.me/N4_Society/55')
DATABASE_URL = Config.DB_URL
COLLECTION_NAME = os.environ.get('COLLECTION_NAME', 'Token1')
PREMIUM_USERS = list(map(int, os.environ.get('PREMIUM_USERS', '').split()))

print(f"DEBUG: VERIFY_EXPIRE = {VERIFY_EXPIRE}")

# ================= DATABASE =================
class VerifyDB:
    def __init__(self):
        try:
            self._dbclient = AsyncIOMotorClient(DATABASE_URL)
            self._db = self._dbclient['verify-db']
            self._verifydb = self._db[COLLECTION_NAME]
            print('✅ Database Connected')
        except Exception as e:
            print(f'❌ Failed To Connect To Database. \nError: {str(e)}')
    
    async def get_verify_status(self, user_id):
        if status := await self._verifydb.find_one({'id': user_id}):
            return status.get('verify_status', 0)
        return 0

    async def update_verify_status(self, user_id):
        await self._verifydb.update_one(
            {'id': user_id},
            {'$set': {'verify_status': time()}},
            upsert=True
        )

# ================= HELPERS =================
def get_readable_time(seconds):
    if seconds <= 0:
        return "∞"
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    d, h = divmod(h, 24)
    
    if d:
        return f"{d}ᴅ{h}ʜ"
    if h:
        return f"{h}ʜ{m}ᴍ"
    if m:
        return f"{m}ᴍ{s}s"
    return f"{s}s"

async def is_user_verified(user_id):
    if not VERIFY_EXPIRE or (user_id in PREMIUM_USERS):
        return True
    isveri = await verifydb.get_verify_status(user_id)
    if not isveri or (time() - isveri) >= VERIFY_EXPIRE:
        return False
    return True

# ================= MARKUPS =================
def get_verification_markup(verify_token):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton('ᴛᴜᴛᴏʀɪᴀʟ', url=VERIFY_TUTORIAL),
            InlineKeyboardButton('ɢᴇᴛ ᴛᴏᴋᴇɴ', url=verify_token)
        ],
        [
            InlineKeyboardButton('ᴘʀᴇᴍɪᴜᴍ', callback_data="premium_page")
        ]
    ])

def get_premium_markup():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton('ʙᴀᴄᴋ', callback_data="home_page"),
            InlineKeyboardButton('ᴘʟᴀɴ', callback_data="plan_page")
        ]
    ])

def get_plan_markup():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton('ʙᴀᴄᴋ', callback_data="premium_page"),
            InlineKeyboardButton('ᴄᴀɴᴄᴇʟ', callback_data="close_message")
        ],
        [
            InlineKeyboardButton('ʜᴏᴍᴇ', callback_data="home_page")
        ]
    ])

# ================= SHORTLINK =================
async def get_short_url(longurl, shortener_site=SHORTLINK_SITE, shortener_api=SHORTLINK_API):
    if not shortener_api or shortener_api == '':
        print("⚠️ Shortlink API not configured, returning original URL")
        return longurl
    
    cget = create_scraper().request
    disable_warnings()
    try:
        url = f'https://{shortener_site}/api'
        params = {
            'api': shortener_api,
            'url': longurl,
            'format': 'text'
        }
        res = cget('GET', url, params=params)
        if res.status_code == 200 and res.text:
            return res.text
        else:
            params['format'] = 'json'
            res = cget('GET', url, params=params)
            res = res.json()
            if res.status_code == 200:
                return res.get('shortenedUrl', longurl)
    except Exception as e:
        print(f"Shortlink error: {e}")
        return longurl

async def get_verify_token(bot, userid, link):
    now = time()
    
    # Check if we have existing data
    if userid in verification_data:
        data = verification_data[userid]
        # Check if cooldown expired (6 hours)
        if now - data.get('created_at', 0) < VERIFICATION_COOLDOWN:
            # Return existing shortlink if still valid
            return data.get('short_url')
        else:
            # Cooldown expired, clear old data
            verification_data.pop(userid, None)
            verify_dict.pop(userid, None)
    
    # Generate new token and shortlink
    token = ''.join(random.choices(string.ascii_letters + string.digits, k=9))
    long_link = f"{link}verify-{userid}-{token}"
    short_url = await get_short_url(long_link)
    
    # Store new data
    verification_data[userid] = {
        'token': token,
        'short_url': short_url,
        'created_at': now,
        'last_used': now
    }
    verify_dict[userid] = {'token': token, 'short_url': short_url}
    
    return short_url

# ================= VERIFICATION MESSAGE MANAGER =================
async def get_or_create_verification_message(client, user_id, force_new=False):
    """
    Get existing verification message or create a new one.
    Returns (message_id, is_new)
    """
    now = time()
    
    # Check if user has an existing verification message
    if user_id in verification_data and not force_new:
        data = verification_data[user_id]
        
        # Check if we should send a new message
        if 'message_id' in data:
            last_used = data.get('last_message_time', 0)
            # Don't send new message if last one was sent recently
            if now - last_used < VERIFICATION_RESEND_COOLDOWN:
                return data['message_id'], False
        
        # Check if cooldown expired
        if now - data.get('created_at', 0) < VERIFICATION_COOLDOWN:
            return data.get('message_id'), False
    
    # Need to create or get verification content
    username = (await client.get_me()).username
    verify_token = await get_verify_token(client, user_id, f"https://telegram.me/{username}?start=")
    
    # Get verification status for text
    isveri = await verifydb.get_verify_status(user_id)
    if not isveri:
        text = f"""ʜɪ 👋 {user_id},

ᴛᴏ ꜱᴛᴀʀᴛ ᴜꜱɪɴɢ ᴛʜɪꜱ ʙᴏᴛ, ᴘʟᴇᴀꜱᴇ ɢᴇɴᴇʀᴀᴛᴇ ᴀ ᴛᴇᴍᴘᴏʀᴀʀʏ ᴀᴅꜱ ᴛᴏᴋᴇɴ.

ᴠᴀʟɪᴅɪᴛʏ: {get_readable_time(VERIFY_EXPIRE)}"""
    else:
        text = f"""ʜɪ 👋 {user_id},

ʏᴏᴜʀ ᴀᴅꜱ ᴛᴏᴋᴇɴ ʜᴀꜱ ʙᴇᴇɴ ᴇxᴘɪʀᴇᴅ, ᴋɪɴᴅʟʏ ɢᴇᴛ ᴀ ɴᴇᴡ ᴛᴏᴋᴇɴ ᴛᴏ ᴄᴏɴᴛɪɴᴜᴇ ᴜꜱɪɴɢ ᴛʜɪꜱ ʙᴏᴛ.

ᴠᴀʟɪᴅɪᴛʏ: {get_readable_time(VERIFY_EXPIRE)}"""
    
    markup = get_verification_markup(verify_token)
    
    # Try to edit existing message first
    if user_id in verification_data and 'message_id' in verification_data[user_id]:
        try:
            message_id = verification_data[user_id]['message_id']
            # Try to edit the existing message
            await client.edit_message_caption(
                chat_id=user_id,
                message_id=message_id,
                caption=text,
                reply_markup=markup
            )
            verification_data[user_id]['last_message_time'] = now
            verification_data[user_id]['last_used'] = now
            return message_id, False
        except Exception as e:
            print(f"Edit failed: {e}")
            # Message not found or can't be edited, will create new
    
    # Send new message
    sent = await client.send_photo(
        chat_id=user_id,
        photo=VERIFY_PHOTO,
        caption=text,
        reply_markup=markup
    )
    
    # Update verification data
    if user_id not in verification_data:
        verification_data[user_id] = {}
    
    verification_data[user_id].update({
        'message_id': sent.id,
        'last_message_time': now,
        'last_used': now
    })
    
    return sent.id, True

# ================= CORE VERIFICATION (ANTI-SPAM) =================
async def send_verification(client, message):
    """Send verification message with anti-spam protection"""
    user_id = message.from_user.id
    
    if await is_user_verified(user_id):
        text = f'<b>Hi 👋 {message.from_user.mention},\nYou Are Already Verified Enjoy 😄</b>'
        await client.send_message(user_id, text)
        return
    
    # Get or create verification message (with anti-spam logic)
    await get_or_create_verification_message(client, user_id)

# ================= FILE HANDLER WRAPPER =================
# This should be integrated with your file renaming handler
def require_verification(func):
    """
    Decorator to check verification before processing files
    """
    async def wrapper(client, message):
        user_id = message.from_user.id
        
        # Check if user is verified
        if not await is_user_verified(user_id):
            # Send verification message (only one per user)
            await get_or_create_verification_message(client, user_id)
            # Don't process the file
            return
        
        # User is verified, process the file
        await func(client, message)
    
    return wrapper

# ================= TOKEN VALIDATION =================
async def validate_token(client, message, data):
    user_id = message.from_user.id
    
    if await is_user_verified(user_id):
        return await message.reply("<b>Sɪʀ, Yᴏᴜ Aʀᴇ Aʟʀᴇᴀᴅʏ Vᴇʀɪғɪᴇᴅ 🤓...</b>")
    
    # Get stored token data
    stored_data = verification_data.get(user_id, {})
    dict_token = stored_data.get('token')
    
    if not dict_token:
        stored_data = verify_dict.get(user_id, {})
        dict_token = stored_data.get('token')
    
    if not dict_token:
        return await get_or_create_verification_message(client, user_id, force_new=True)
    
    try:
        _, uid, token = data.split("-")
    except ValueError:
        return await message.reply("<b>Invalid token format</b>")
    
    if uid != str(user_id):
        return await get_or_create_verification_message(client, user_id, force_new=True)
    elif dict_token != token:
        return await message.reply("<b>Iɴᴠᴀʟɪᴅ Oʀ Exᴘɪʀᴇᴅ Tᴏᴋᴇɴ 🔗...</b>")
    
    # ✅ VALID TOKEN - VERIFY USER
    # Clean up verification data
    verification_data.pop(user_id, None)
    verify_dict.pop(user_id, None)
    
    # Update verification status in database
    await verifydb.update_verify_status(user_id)
    
    # Send success message
    await client.send_photo(
        chat_id=user_id,
        photo=VERIFY_PHOTO,
        caption=f'<b>Wᴇʟᴄᴏᴍᴇ Bᴀᴄᴋ 😁, Nᴏᴡ Yᴏᴜ Cᴀɴ Usᴇ Mᴇ Fᴏʀ {get_readable_time(VERIFY_EXPIRE)}.\n\n\nEɴᴊᴏʏʏʏ...❤️</b>'
    )

# ================= HANDLERS =================
@Client.on_message(filters.private & filters.regex(r'^/verify') & ~filters.bot)
async def verify_command_handler(client, message):
    cmd = message.text.split()
    if len(cmd) == 2:
        data = cmd[1]
        if data.startswith("verify"):
            await validate_token(client, message, data)
    else:
        await get_or_create_verification_message(client, message.from_user.id)

@Client.on_callback_query(filters.regex("premium_page"))
async def premium_callback_handler(client, callback_query: CallbackQuery):
    await callback_query.message.edit_text(
        PREMIUM_TXT,
        reply_markup=get_premium_markup(),
        disable_web_page_preview=True
    )
    await callback_query.answer()

@Client.on_callback_query(filters.regex("plan_page"))
async def plan_callback_handler(client, callback_query: CallbackQuery):
    await callback_query.message.edit_text(
        PREPLANS_TXT,
        reply_markup=get_plan_markup(),
        disable_web_page_preview=True
    )
    await callback_query.answer()

@Client.on_callback_query(filters.regex("home_page"))
async def home_callback_handler(client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    username = (await client.get_me()).username
    verify_token = await get_verify_token(client, user_id, f"https://telegram.me/{username}?start=")

    isveri = await verifydb.get_verify_status(user_id)
    
    if not isveri:
        text = f"""ʜɪ 👋 {callback_query.from_user.mention},

ᴛᴏ ꜱᴛᴀʀᴛ ᴜꜱɪɴɢ ᴛʜɪꜱ ʙᴏᴛ, ᴘʟᴇᴀꜱᴇ ɢᴇɴᴇʀᴀᴛᴇ ᴀ ᴛᴇᴍᴘᴏʀᴀʀʏ ᴀᴅꜱ ᴛᴏᴋᴇɴ.

ᴠᴀʟɪᴅɪᴛʏ: {get_readable_time(VERIFY_EXPIRE)}"""
    else:
        text = f"""ʜɪ 👋 {callback_query.from_user.mention},

ʏᴏᴜʀ ᴀᴅꜱ ᴛᴏᴋᴇɴ ʜᴀꜱ ʙᴇᴇɴ ᴇxᴘɪʀᴇᴅ, ᴋɪɴᴅʟʏ ɢᴇᴛ ᴀ ɴᴇᴡ ᴛᴏᴋᴇɴ ᴛᴏ ᴄᴏɴᴛɪɴᴜᴇ ᴜꜱɪɴɢ ᴛʜɪꜱ ʙᴏᴛ.

ᴠᴀʟɪᴅɪᴛʏ: {get_readable_time(VERIFY_EXPIRE)}"""
    
    try:
        if callback_query.message.photo:
            await callback_query.message.edit_caption(
                text,
                reply_markup=get_verification_markup(verify_token)
            )
        else:
            await callback_query.message.edit_text(
                text,
                reply_markup=get_verification_markup(verify_token)
            )
    except Exception as e:
        print(f"Edit error in callback: {e}")
        await callback_query.message.reply_photo(
            photo=VERIFY_PHOTO,
            caption=text,
            reply_markup=get_verification_markup(verify_token)
        )
    
    await callback_query.answer()

@Client.on_callback_query(filters.regex("close_message"))
async def close_callback_handler(client, callback_query: CallbackQuery):
    try:
        await callback_query.message.delete()
        await callback_query.answer("Closed the window.")
    except Exception:
        await callback_query.answer("Closed the window.", show_alert=True)

# ================= AUTO VERIFICATION FOR NEW USERS =================
@Client.on_message(filters.private & filters.command("start") & ~filters.bot)
async def start_handler(client, message):
    user_id = message.from_user.id
    
    # Check if user sent a verification token
    if len(message.command) > 1 and message.command[1].startswith("verify"):
        await validate_token(client, message, message.command[1])
        return
    
    # Check if user is already verified
    if await is_user_verified(user_id):
        await message.reply(f"<b>Welcome back {message.from_user.mention}! You're already verified. 😊</b>")
        return
    
    # Send verification for unverified users
    await get_or_create_verification_message(client, user_id)

# ================= BULK FILE UPLOAD HANDLER (EXAMPLE) =================
# This is an example of how to integrate with your file renaming handler
@Client.on_message(filters.private & filters.document & ~filters.bot)
async def file_handler(client, message):
    """Example file handler with verification check"""
    user_id = message.from_user.id
    
    # Check verification status
    if not await is_user_verified(user_id):
        # Send only ONE verification message regardless of how many files
        await get_or_create_verification_message(client, user_id)
        return  # Don't process the file
    
    # User is verified, process the file
    # ... your file renaming logic here ...
    await message.reply(f"Processing your file...")

# ================= INITIALIZE =================
verifydb = VerifyDB()
print("✅ Verification system initialized")
print(f"✅ Verification expire time: {get_readable_time(VERIFY_EXPIRE)}")
print(f"✅ Cooldown time: {get_readable_time(VERIFICATION_COOLDOWN)}")
print(f"✅ Anti-spam resend cooldown: {get_readable_time(VERIFICATION_RESEND_COOLDOWN)}")
