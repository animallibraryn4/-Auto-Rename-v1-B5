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

# ================= MEMORY =================
verify_dict = {}
verification_last_sent = {}
verification_message_id = {}
VERIFICATION_COOLDOWN = 21600  # 6 hours

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
# Default values provide karo agar environment variable nahi mile
VERIFY_PHOTO = os.environ.get('VERIFY_PHOTO', 'https://images8.alphacoders.com/138/1384114.png')
SHORTLINK_SITE = os.environ.get('SHORTLINK_SITE', 'gplinks.com')
SHORTLINK_API = os.environ.get('SHORTLINK_API', '596f423cdf22b174e43d0b48a36a8274759ec2a3')
VERIFY_EXPIRE = int(os.environ.get('VERIFY_EXPIRE', 7260))
VERIFY_TUTORIAL = os.environ.get('VERIFY_TUTORIAL', 'https://t.me/N4_Society/55')
DATABASE_URL = Config.DB_URL
COLLECTION_NAME = os.environ.get('COLLECTION_NAME', 'Token1')
PREMIUM_USERS = list(map(int, os.environ.get('PREMIUM_USERS', '').split()))

# Debug ke liye print karo ki variables set hain ya nahi
print(f"DEBUG: VERIFY_PHOTO = {VERIFY_PHOTO}")
print(f"DEBUG: SHORTLINK_SITE = {SHORTLINK_SITE}")
print(f"DEBUG: SHORTLINK_API = {SHORTLINK_API}")
print(f"DEBUG: VERIFY_EXPIRE = {VERIFY_EXPIRE}")
print(f"DEBUG: VERIFY_TUTORIAL = {VERIFY_TUTORIAL}")
print(f"DEBUG: COLLECTION_NAME = {COLLECTION_NAME}")

# Required variables check - ab exit nahi karenge, default values use karenge
required_vars = {
    'VERIFY_PHOTO': VERIFY_PHOTO,
    'SHORTLINK_SITE': SHORTLINK_SITE,
    'SHORTLINK_API': SHORTLINK_API,
    'VERIFY_TUTORIAL': VERIFY_TUTORIAL,
    'COLLECTION_NAME': COLLECTION_NAME
}

missing = [k for k, v in required_vars.items() if not v]
if missing:
    print(f"⚠️ WARNING: Missing variables: {', '.join(missing)}")
    print("⚠️ Using default values where available")

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
    vdict = verify_dict.setdefault(userid, {})
    short_url = vdict.get('short_url')
    
    # Check if cooldown expired
    last_sent = verification_last_sent.get(userid, 0)
    if last_sent and (time() - last_sent) > VERIFICATION_COOLDOWN:
        # Clear old data for new token
        verify_dict.pop(userid, None)
        vdict = verify_dict.setdefault(userid, {})
        short_url = None
    
    if not short_url:
        token = ''.join(random.choices(string.ascii_letters + string.digits, k=9))
        long_link = f"{link}verify-{userid}-{token}"
        short_url = await get_short_url(long_link)
        vdict.update({'token': token, 'short_url': short_url})
    return short_url

# ================= CORE VERIFICATION (ANTI-SPAM) =================
async def send_verification(client, message):
    user_id = message.from_user.id
    now = time()
    
    if await is_user_verified(user_id):
        text = f'<b>Hi 👋 {message.from_user.mention},\nYou Are Already Verified Enjoy 😄</b>'
        await client.send_message(user_id, text)
        return
    
    # Get last message info
    last_msg_id = verification_message_id.get(user_id)
    last_sent_time = verification_last_sent.get(user_id, 0)
    
    # 6 hours passed? Generate new token
    if last_sent_time and (now - last_sent_time) > VERIFICATION_COOLDOWN:
        verify_dict.pop(user_id, None)
        last_msg_id = None
    
    username = (await client.get_me()).username
    verify_token = await get_verify_token(client, user_id, f"https://telegram.me/{username}?start=")
    
    # Check verification status for text
    isveri = await verifydb.get_verify_status(user_id)
    if not isveri:
        text = f"""ʜɪ 👋 {message.from_user.mention},

ᴛᴏ ꜱᴛᴀʀᴛ ᴜꜱɪɴɢ ᴛʜɪꜱ ʙᴏᴛ, ᴘʟᴇᴀꜱᴇ ɢᴇɴᴇʀᴀᴛᴇ ᴀ ᴛᴇᴍᴘᴏʀᴀʀʏ ᴀᴅꜱ ᴛᴏᴋᴇɴ.

ᴠᴀʟɪᴅɪᴛʏ: {get_readable_time(VERIFY_EXPIRE)}"""
    else:
        text = f"""ʜɪ 👋 {message.from_user.mention},

ʏᴏᴜʀ ᴀᴅꜱ ᴛᴏᴋᴇɴ ʜᴀꜱ ʙᴇᴇɴ ᴇxᴘɪʀᴇᴅ, ᴋɪɴᴅʟʏ ɢᴇᴛ ᴀ ɴᴇᴡ ᴛᴏᴋᴇɴ ᴛᴏ ᴄᴏɴᴛɪɴᴜᴇ ᴜꜱɪɴɢ ᴛʜɪꜱ ʙᴏᴛ.

ᴠᴀʟɪᴅɪᴛʏ: {get_readable_time(VERIFY_EXPIRE)}"""
    
    markup = get_verification_markup(verify_token)
    
    # Try to EDIT existing message first (NO SPAM)
    if last_msg_id:
        try:
            # Always use edit_message_caption for photo messages
            await client.edit_message_caption(
                chat_id=user_id,
                message_id=last_msg_id,
                caption=text,
                reply_markup=markup
            )
            verification_last_sent[user_id] = now
            return
        except Exception as e:
            print(f"Edit failed: {e}")
            # Message not found, clear and send new
            verification_message_id.pop(user_id, None)
    
    # Send NEW message only if no existing message
    sent = await client.send_photo(
        chat_id=user_id,
        photo=VERIFY_PHOTO,
        caption=text,
        reply_markup=markup
    )
    
    verification_message_id[user_id] = sent.id
    verification_last_sent[user_id] = now

# ================= TOKEN VALIDATION =================
async def validate_token(client, message, data):
    user_id = message.from_user.id
    vdict = verify_dict.setdefault(user_id, {})
    dict_token = vdict.get('token', None)
    
    if await is_user_verified(user_id):
        return await message.reply("<b>Sɪʀ, Yᴏᴜ Aʀᴇ Aʟʀᴇᴀᴅʏ Vᴇʀɪғɪᴇᴅ 🤓...</b>")
    
    if not dict_token:
        return await send_verification(client, message)
    
    try:
        _, uid, token = data.split("-")
    except ValueError:
        return await message.reply("<b>Invalid token format</b>")
    
    if uid != str(user_id):
        return await send_verification(client, message)
    elif dict_token != token:
        return await message.reply("<b>Iɴᴠᴀʟɪᴅ Oʀ Exᴘɪʀᴇᴅ Tᴏᴋᴇɴ 🔗...</b>")
    
    # ✅ VALID TOKEN - VERIFY USER
    verify_dict.pop(user_id, None)
    verification_last_sent.pop(user_id, None)
    verification_message_id.pop(user_id, None)
    
    await verifydb.update_verify_status(user_id)
    
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
        await send_verification(client, message)

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
        # Try to send new message if edit fails
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
    await send_verification(client, message)

# ================= INITIALIZE =================
verifydb = VerifyDB()
print("✅ Verification system initialized")
print(f"✅ Verification expire time: {get_readable_time(VERIFY_EXPIRE)}")
print(f"✅ Cooldown time: {get_readable_time(VERIFICATION_COOLDOWN)}")
