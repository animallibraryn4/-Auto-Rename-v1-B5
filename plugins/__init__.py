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

verify_dict = {}

# --- PREMIUM TEXTS (Added back for context) ---
PREMIUM_TXT = """<b>ᴜᴘɢʀᴀᴅᴇ ᴛᴏ ᴏᴜʀ ᴘʀᴇᴍɪᴜᴍ sᴇʀᴠɪᴄᴇ ᴀɴᴅ ᴇɴJᴏʏ ᴇxᴄʟᴜsɪᴠᴇ ғᴇᴀᴛᴜʀᴇs:
○ ᴜɴʟɪᴍɪᴛᴇᴅ Rᴇɴᴀᴍɪɴɢ: ʀᴇɴᴀᴍᴇ ᴀs ᴍᴀɴʏ ғɪʟᴇs ᴀs ʏᴏᴜ ᴡᴀɴᴛ ᴡɪᴛʜᴏᴜᴛ ᴀɴʏ ʀᴇsᴛʀɪᴄᴛɪᴏɴs.
○ ᴇᴀʀʟʏ Aᴄᴄᴇss: ʙᴇ ᴛʜᴇ ғɪʀsᴛ ᴛᴏ ᴛᴇsᴛ ᴀɴᴅ ᴜsᴇ ᴏᴜʀ ʟᴀᴛᴇsᴛ ғᴇᴀᴛᴜʀᴇs ʙᴇғᴏʀᴇ ᴀɴʏᴏɴᴇ ᴇʟsᴇ.

• ᴜꜱᴇ /plan ᴛᴏ ꜱᴇᴇ ᴀʟʟ ᴏᴜʀ ᴘʟᴀɴꜱ ᴀᴛ ᴏɴᴄᴇ.

➲ ғɪʀsᴛ sᴛᴇᴘ : ᴘᴀʏ ᴛʜᴇ ᴀᴍᴏᴜɴᴛ ᴀᴄᴄᴏʀᴅɪɴɢ ᴛᴏ ʏᴏᴜʀ ғᴀᴠᴏʀɪᴛᴇ ᴘʟᴀɴ ᴛᴏ ᴛʜɪs fam ᴜᴘɪ ɪᴅ.

➲ sᴇᴄᴏɴᴅ sᴛᴇᴘ : ᴛᴀᴋᴇ ᴀ sᴄʀᴇᴇɴsʜᴏᴛ ᴏғ ʏᴏᴜʀ ᴘᴀʏᴍᴇɴᴛ ᴀɴᴅ sʜᴀʀᴇ ɪᴛ ᴅɪʀᴇᴄᴛʟʏ ʜᴇʀᴇ: @ 

➲ ᴀʟᴛᴇʀɴᴀᴛɪᴠᴇ sᴛᴇᴘ : ᴏʀ ᴜᴘʟᴏᴀᴅ ᴛʜᴇ sᴄʀᴇᴇɴsʜᴏᴛ ʜᴇʀᴇ ᴀɴᴅ ʀᴇᴘʟʏ ᴡɪᴛʜ ᴛʜᴇ /bought ᴄᴏᴍᴍᴀɴᴅ.

Your premium plan will be activated after verification.</b>"""

PREPLANS_TXT = """<b>👋 bro,

🎖️ <u>Available Plans</u> :

Pricing:
➜ Monthly Premium: ₹50/month
➜ Daily Premium: ₹5/day
➜ For bot hosting: contact @Anime_Library_N4

➲ UPI ID - <code>@</code>

‼️ Upload the payment screenshot here and reply with the /bought command.</b>"""

# CONFIG VARIABLES 😄
VERIFY_PHOTO = os.environ.get('VERIFY_PHOTO', 'https://images8.alphacoders.com/138/1384114.png')  # YOUR VERIFY PHOTO LINK
SHORTLINK_SITE = os.environ.get('SHORTLINK_SITE', 'gplinks.com') # YOUR SHORTLINK URL LIKE:- site.com
SHORTLINK_API = os.environ.get('SHORTLINK_API', '596f423cdf22b174e43d0b48a36a8274759ec2a3') # YOUR SHORTLINK API LIKE:- ma82owowjd9hw6_js7
VERIFY_EXPIRE = os.environ.get('VERIFY_EXPIRE', 30000) # VERIFY EXPIRE TIME IN SECONDS. LIKE:- 0 (ZERO) TO OFF VERIFICATION 
VERIFY_TUTORIAL = os.environ.get('VERIFY_TUTORIAL', 'https://t.me/N4_Society/55') # LINK OF TUTORIAL TO VERIFY 

# --- NEW VARIABLE ADDED FOR SUCCESS MESSAGE VIDEO ---
VERIFY_SUCCESS_VIDEO = os.environ.get('VERIFY_SUCCESS_VIDEO', 'https://files.catbox.moe/um3zgp.mp4')
# ----------------------------------------------------

# DATABASE_URL now uses Config.DB_URL
DATABASE_URL = Config.DB_URL
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
        # Returns the verification timestamp or 0 if not found
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

# --- INLINE KEYBOARD MARKUPS ---

def get_verification_markup(verify_token, username):
    # CHANGED: Get Token is now the first button in the first row
    return InlineKeyboardMarkup([
    [
        InlineKeyboardButton('ᴛᴜᴛᴏʀɪᴀʟ', url='https://t.me/N4_Society/55'),
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

# --- NEW CALLBACK QUERY HANDLERS ---

# Handler for 'Premium' button (opens Premium page)
@Client.on_callback_query(filters.regex("premium_page"))
async def premium_callback_handler(client, callback_query: CallbackQuery):
    await callback_query.message.edit_text(
        PREMIUM_TXT,
        reply_markup=get_premium_markup(),
        disable_web_page_preview=True
    )
    await callback_query.answer()

# Handler for 'Plan' button (opens Plans page)
@Client.on_callback_query(filters.regex("plan_page"))
async def plan_callback_handler(client, callback_query: CallbackQuery):
    await callback_query.message.edit_text(
        PREPLANS_TXT,
        reply_markup=get_plan_markup(),
        disable_web_page_preview=True
    )
    await callback_query.answer()

# Handler for 'Back' and 'Home' buttons (returns to Verification page)
@Client.on_callback_query(filters.regex("home_page"))
async def home_callback_handler(client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    username = (await client.get_me()).username
    verify_token = await get_verify_token(client, user_id, f"https://telegram.me/{username}?start=")

    isveri = await verifydb.get_verify_status(user_id)
    
    # NEW FORMAT AND FONT
    if not isveri: # First time/No record found
        text = f"""ʜɪ 👋 {callback_query.from_user.mention},

ᴛᴏ ꜱᴛᴀʀᴛ ᴜꜱɪɴɢ ᴛʜɪꜱ ʙᴏᴛ, ᴘʟᴇᴀꜱᴇ ɢᴇɴᴇʀᴀᴛᴇ ᴀ ᴛᴇᴍᴘᴏʀᴀʀʏ ᴀᴅꜱ ᴛᴏᴋᴇɴ.

ᴠᴀʟɪᴅɪᴛʏ: {get_readable_time(VERIFY_EXPIRE)}"""
    else: # Subsequent visit, token is likely expired since we are showing the verification
        text = f"""ʜɪ 👋 {callback_query.from_user.mention},

<u>ʏᴏᴜʀ ᴀᴅꜱ ᴛᴏᴋᴇɴ ʜᴀꜱ ʙᴇᴇɴ ᴇxᴘɪʀᴇᴅ, ᴋɪɴᴅʟʏ ɢᴇᴛ ᴀ ɴᴇᴡ ᴛᴏᴋᴇɴ ᴛᴏ ᴄᴏɴᴛɪɴᴜᴇ ᴜꜱɪɴɢ ᴛʜɪꜱ ʙᴏᴛ.</u>

ᴠᴀʟɪᴅɪᴛʏ: {get_readable_time(VERIFY_EXPIRE)}"""
        
    # Edit message content
    if callback_query.message.photo:
        await callback_query.message.edit_caption(
            text,
            reply_markup=get_verification_markup(verify_token, username)
        )
    else:
        await callback_query.message.edit_text(
            text,
            reply_markup=get_verification_markup(verify_token, username)
        )

    await callback_query.answer()

# Handler for 'Cancel' button (closes the message or sends an alert)
@Client.on_callback_query(filters.regex("close_message"))
async def close_callback_handler(client, callback_query: CallbackQuery):
    try:
        await callback_query.message.delete()
        await callback_query.answer("Closed the window.")
    except Exception:
        await callback_query.answer("Closed the window.", show_alert=True)


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
    user_id = message.from_user.id
    
    isveri = await verifydb.get_verify_status(user_id)

    if done := await is_user_verified(user_id):
        text = f'<b>Hi 👋 {message.from_user.mention},\nYou Are Already Verified Enjoy 😄</b>'
    else:
        verify_token = await get_verify_token(client, user_id, f"https://telegram.me/{username}?start=")
        buttons = get_verification_markup(verify_token, username)
        
        # NEW FORMAT AND FONT
        if not isveri:
            # Verification message for first-time users
            text = f"""ʜɪ 👋 {message.from_user.mention},

ᴛᴏ ꜱᴛᴀʀᴛ ᴜꜱɪɴɢ ᴛʜɪꜱ ʙᴏᴛ, ᴘʟᴇᴀꜱᴇ ɢᴇɴᴇʀᴀᴛᴇ ᴀ ᴛᴇᴍᴘᴏʀᴀʀʏ ᴀᴅꜱ ᴛᴏᴋᴇɴ.

ᴠᴀʟɪᴅɪᴛʏ: {get_readable_time(VERIFY_EXPIRE)}"""
        # ELSE: User record exists but token is expired
        else:
            # Verification message for expired token
            text = f"""ʜɪ 👋 {message.from_user.mention},

<u>ʏᴏᴜʀ ᴀᴅꜱ ᴛᴏᴋᴇɴ ʜᴀꜱ ʙᴇᴇɴ ᴇxᴘɪʀᴇᴅ, ᴋɪɴᴅʟʏ ɢᴇᴛ ᴀ ɴᴇᴡ ᴛᴏᴋᴇɴ ᴛᴏ ᴄᴏɴᴛɪɴᴜᴇ ᴜꜱɪɴɢ ᴛʜɪꜱ ʙᴏᴛ.</u>

ᴠᴀʟɪᴅɪᴛʏ: {get_readable_time(VERIFY_EXPIRE)}"""

    if not text:
        # Fallback to the expired message
        text = f"""ʜɪ 👋 {message.from_user.mention},

ʏᴏᴜʀ ᴀᴅꜱ ᴛᴏᴋᴇɴ ʜᴀꜱ ʙᴇᴇɴ ᴇxᴘɪʀᴇᴅ, ᴋɪɴᴅʟʏ ɢᴇᴛ ᴀ ɴᴇᴡ ᴛᴏᴋᴇɴ ᴛᴏ ᴄᴏɴᴛɪɴᴜᴇ ᴜꜱɪɴɢ ᴛʜɪꜱ ʙᴏᴛ.

ᴠᴀʟɪᴅɪᴛʏ: {get_readable_time(VERIFY_EXPIRE)}"""

    message = message if isinstance(message, Message) else message.message
    await client.send_photo(
        chat_id=message.chat.id,
        photo=VERIFY_PHOTO,
        caption=text,
        reply_markup=buttons,
        # reply_to_message_id=message.id, IS REMOVED
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
        # The verification will be sent without replying to the file message
        return await send_verification(client, message, text="<b>Tʜᴀᴛ's Nᴏᴛ Yᴏᴜʀ Vᴇʀɪғʏ Tᴏᴋᴇɴ 🥲...\n\n\nTᴀᴘ Oɴ Vᴇʀɪғʏ Tᴏ Gᴇɴᴇʀᴀᴛᴇ Yᴏᴜʀs...</b>")  
    _, uid, token = data.split("-")
    if uid != str(user_id):
        # The verification will be sent without replying to the file message
        return await send_verification(client, message, text="<b>Vᴇʀɪғʏ Tᴏᴋᴇɴ Dɪᴅ Nᴏᴛ Mᴀᴛᴄʜᴇᴅ 😕...\n\n\nTᴀᴘ Oɴ Vᴇʀɪғʏ Tᴏ Gᴇɴᴇʀᴀᴛᴇ Aɢᴀɪɴ...</b>")
    elif dict_token != token:
        # The verification will be sent without replying to the file message
        return await send_verification(client, message, text="<b>Iɴᴠᴀʟɪᴅ Oʀ Exᴘɪʀᴇᴅ Tᴏᴋᴇɴ 🔗...</b>")
    verify_dict.pop(user_id, None)
    await verifydb.update_verify_status(user_id)
    
    # --- MODIFIED: Using send_video with the new variable for success message ---
    await client.send_video(
        chat_id=message.from_user.id,
        video=VERIFY_SUCCESS_VIDEO, # This uses the video link: https://files.catbox.moe/um3zgp.mp4
        caption=f'<b>Wᴇʟᴄᴏᴍᴇ Bᴀᴄᴋ 😁, Nᴏᴡ Yᴏᴜ Cᴀɴ Usᴇ Mᴇ Fᴏʀ {get_readable_time(VERIFY_EXPIRE)}.\n\n\nEɴᴊᴏʏʏʏ...❤️</b>',
        # reply_to_message_id=message.id, IS REMOVED
    )
    # --------------------------------------------------------------------------
    
def get_readable_time(seconds):
    periods = [('ᴅ', 86400), ('ʜ', 3600), ('ᴍ', 60), ('s', 1)]
    result = ''
    for period_name, period_seconds in periods:
        if seconds >= period_seconds:
            period_value, seconds = divmod(seconds, period_seconds)
            result += f'{int(period_value)}{period_name}'
    return result

verifydb = VerifyDB()
                                           
