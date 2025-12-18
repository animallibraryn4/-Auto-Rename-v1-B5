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

# ================= MEMORY & LOCKS =================
verify_dict = {}
verification_last_sent = {}
verification_message_id = {}
user_locks = {}  # Naya: Multiple files ko handle karne ke liye
VERIFICATION_COOLDOWN = 21600  # 6 hours

# ================= PREMIUM TEXTS =================
PREMIUM_TXT = """<b>ᴜᴘɢʀᴀᴅᴇ ᴛᴏ ᴏᴜʀ ᴘʀᴇᴍɪᴜᴍ sᴇʀᴠɪᴄᴇ ᴀɴᴅ ᴇɴJᴏʏ ᴇxᴄʟᴜsɪᴠᴇ ғᴇᴀᴛᴜʀᴇs:
○ ᴜɴʟɪᴍɪᴛᴇᴅ Rᴇɴᴀᴍɪɴɢ: ʀᴇɴᴀᴍᴇ ᴀs ᴍᴀɴʏ ғɪʟᴇs ᴀs ʏᴏᴜ ᴡᴀɴᴛ ᴡɪᴛʜᴏᴜᴛ ᴀɴʏ ʀᴇsᴛʀɪᴄᴛɪᴏɴs.
○ ᴇᴀʀʟʏ Aᴄᴄᴇss: ʙᴇ ᴛʜᴇ ғɪʀsᴛ ᴛᴏ ᴛᴇsᴛ ᴀɴᴅ ᴜsᴇ ᴏᴜʀ ʟᴀᴛᴇsᴛ ғᴇᴀᴛᴜʀᴇs ʙᴇғᴏʀᴇ ᴀɴʏᴏɴᴇ ᴇʟsᴇ.

• ᴜꜱᴇ /plan ᴛᴏ ꜱᴇᴇ ᴀʟʟ ᴏᴜʀ ᴘʟᴀɴꜱ ᴀᴛ ᴏɴᴄᴇ.

➲ ғɪʀsᴛ sᴛᴇᴘ : ᴘᴀʏ ᴛʜᴇ ᴀᴍᴏᴜɴᴛ ᴀᴄᴄᴏʀᴅɪɴɢ ᴛᴏ ʏᴏᴜʀ ғᴀᴠᴏʀɪᴛᴇ ᴘʟᴀɴ ᴛᴏ ᴛʜɪs fam ᴜᴘɪ ɪᴅ.

➲ sᴇᴄᴏɴᴅ sᴛᴇᴘ : ᴛᴀᴋᴇ ᴀ sᴄʀᴇᴇɴsʜᴏᴛ ᴏғ ʏᴏᴜʀ ᴘᴀʏᴍᴇɴᴛ ᴀɴᴅ sʜᴀʀᴇ ɪᴛ ᴅɪʀᴇᴄᴛʟʏ ʜᴇʀᴇ: @ 

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

# ================= DATABASE =================
class VerifyDB:
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
        await self._verifydb.update_one(
            {'id': user_id},
            {'$set': {'verify_status': time()}},
            upsert=True
        )

verifydb = VerifyDB()

# ================= HELPERS =================
def get_readable_time(seconds):
    if seconds <= 0: return "∞"
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    return f"{h}ʜ{m}ᴍ" if h else (f"{m}ᴍ" if m else f"{s}s")

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
        [InlineKeyboardButton('ᴛᴜᴛᴏʀɪᴀʟ', url=VERIFY_TUTORIAL), InlineKeyboardButton('ɢᴇᴛ ᴛᴏᴋᴇɴ', url=verify_token)],
        [InlineKeyboardButton('ᴘʀᴇᴍɪᴜᴍ', callback_data="premium_page")]
    ])

def get_premium_markup():
    return InlineKeyboardMarkup([[InlineKeyboardButton('ʙᴀᴄᴋ', callback_data="home_page"), InlineKeyboardButton('ᴘʟᴀɴ', callback_data="plan_page")]])

def get_plan_markup():
    return InlineKeyboardMarkup([[InlineKeyboardButton('ʙᴀᴄᴋ', callback_data="premium_page"), InlineKeyboardButton('ᴄᴀɴᴄᴇʟ', callback_data="close_message")], [InlineKeyboardButton('ʜᴏᴍᴇ', callback_data="home_page")]])

# ================= SHORTLINK =================
async def get_short_url(longurl):
    cget = create_scraper().request
    disable_warnings()
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

# ================= CORE VERIFICATION (ANTI-SPAM) =================
async def send_verification(client, message):
    user_id = message.from_user.id
    
    # Lock lagana taaki ek saath 10 messages na jayein
    if user_id not in user_locks:
        user_locks[user_id] = asyncio.Lock()
    
    async with user_locks[user_id]:
        now = time()
        
        # Check if verified
        if await is_user_verified(user_id):
            return

        # Cooldown Logic (6 hours)
        last_sent_time = verification_last_sent.get(user_id, 0)
        if last_sent_time and (now - last_sent_time) > VERIFICATION_COOLDOWN:
            verify_dict.pop(user_id, None)
            verification_message_id.pop(user_id, None)

        username = (await client.get_me()).username
        verify_token = await get_verify_token(client, user_id, f"https://telegram.me/{username}?start=")
        
        isveri = await verifydb.get_verify_status(user_id)
        msg_text = "ʏᴏᴜʀ ᴀᴅꜱ ᴛᴏᴋᴇɴ ʜᴀꜱ ʙᴇᴇɴ ᴇxᴘɪʀᴇᴅ" if isveri else "ᴛᴏ ꜱᴛᴀʀᴛ ᴜꜱɪɴɢ ᴛʜɪꜱ ʙᴏᴛ, ᴘʟᴇᴀꜱᴇ ɢᴇɴᴇʀᴀᴛᴇ ᴀ ᴛᴇᴍᴘᴏʀᴀʀʏ ᴀᴅꜱ ᴛᴏᴋᴇɴ"
        
        text = f"ʜɪ 👋 {message.from_user.mention},\n\n{msg_text}.\n\nᴠᴀʟɪᴅɪᴛʏ: {get_readable_time(VERIFY_EXPIRE)}"
        markup = get_verification_markup(verify_token)
        
        last_msg_id = verification_message_id.get(user_id)
        
        # Purana message edit karne ki koshish karein
        if last_msg_id:
            try:
                await client.edit_message_caption(chat_id=user_id, message_id=last_msg_id, caption=text, reply_markup=markup)
                verification_last_sent[user_id] = now
                return
            except:
                verification_message_id.pop(user_id, None)

        # Naya message bhejein agar purana na mile
        sent = await client.send_photo(chat_id=user_id, photo=VERIFY_PHOTO, caption=text, reply_markup=markup)
        verification_message_id[user_id] = sent.id
        verification_last_sent[user_id] = now

# ================= TOKEN VALIDATION =================
async def validate_token(client, message, data):
    user_id = message.from_user.id
    
    if await is_user_verified(user_id):
        return await message.reply("<b>Sɪʀ, Yᴏᴜ Aʀᴇ Aʟʀᴇᴀᴅʏ Vᴇʀɪғɪᴇᴅ 🤓...</b>")

    vdict = verify_dict.get(user_id, {})
    dict_token = vdict.get('token')
    
    if not dict_token:
        return await send_verification(client, message)
    
    try:
        _, uid, token = data.split("-")
        if uid != str(user_id) or dict_token != token:
            return await message.reply("<b>Iɴᴠᴀʟɪᴅ Oʀ Exᴘɪʀᴇᴅ Tᴏᴋᴇɴ 🔗...</b>")
    except:
        return await message.reply("<b>Invalid Token Format 🔗</b>")
    
    # ✅ SUCCESS: CLEANUP MEMORY
    verify_dict.pop(user_id, None)
    verification_last_sent.pop(user_id, None)
    old_msg_id = verification_message_id.pop(user_id, None)
    
    if old_msg_id:
        try: await client.delete_messages(user_id, old_msg_id)
        except: pass
    
    await verifydb.update_verify_status(user_id)
    await client.send_photo(chat_id=user_id, photo=VERIFY_PHOTO, caption=f'<b>Wᴇʟᴄᴏᴍᴇ Bᴀᴄᴋ 😁, Nᴏᴡ Yᴏᴜ Cᴀɴ Usᴇ Mᴇ Fᴏʀ {get_readable_time(VERIFY_EXPIRE)}.\n\nEɴᴊᴏʏʏʏ...❤️</b>')

# ================= HANDLERS =================
@Client.on_message(filters.private & filters.regex(r'^/verify') & ~filters.bot)
async def verify_command_handler(client, message):
    cmd = message.text.split()
    if len(cmd) == 2 and cmd[1].startswith("verify"):
        await validate_token(client, message, cmd[1])
    else:
        await send_verification(client, message)

@Client.on_callback_query(filters.regex("premium_page"))
async def premium_callback_handler(client, query):
    await query.message.edit_text(PREMIUM_TXT, reply_markup=get_premium_markup(), disable_web_page_preview=True)

@Client.on_callback_query(filters.regex("plan_page"))
async def plan_callback_handler(client, query):
    await query.message.edit_text(PREPLANS_TXT, reply_markup=get_plan_markup(), disable_web_page_preview=True)

@Client.on_callback_query(filters.regex("home_page"))
async def home_callback_handler(client, query):
    user_id = query.from_user.id
    username = (await client.get_me()).username
    verify_token = await get_verify_token(client, user_id, f"https://telegram.me/{username}?start=")
    isveri = await verifydb.get_verify_status(user_id)
    text = f"ʜɪ 👋 {query.from_user.mention},\n\n{'ʏᴏᴜʀ ᴀᴅꜱ ᴛᴏᴋᴇɴ ʜᴀꜱ ʙᴇᴇɴ ᴇxᴘɪʀᴇᴅ' if isveri else 'ᴛᴏ ꜱᴛᴀʀᴛ ᴜꜱɪɴɢ ᴛʜɪꜱ ʙᴏᴛ'}...\n\nᴠᴀʟɪᴅɪᴛʏ: {get_readable_time(VERIFY_EXPIRE)}"
    
    if query.message.photo:
        await query.message.edit_caption(text, reply_markup=get_verification_markup(verify_token))
    else:
        await query.message.edit_text(text, reply_markup=get_verification_markup(verify_token))

@Client.on_callback_query(filters.regex("close_message"))
async def close_callback_handler(client, query):
    await query.message.delete()

