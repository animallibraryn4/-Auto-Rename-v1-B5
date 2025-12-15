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

# --- NEW TEXTS ---
REPORT_TXT = """<b>ʜɪ 👋 

ɪꜰ ʏᴏᴜ ꜰɪɴᴅ ᴀɴʏ ᴛᴇᴄʜɴɪᴄᴀʟ ɪꜱꜱᴜᴇ ᴏʀ ʙᴜɢ, ᴘʟᴇᴀꜱᴇ ʀᴇᴘᴏʀᴛ ɪᴛ ᴛᴏ ᴛʜᴇ ᴅᴇᴠᴇʟᴏᴘᴇʀ ᴜꜱɪɴɢ ᴛʜᴇ ʙᴜᴛᴛᴏɴ ʙᴇʟᴏᴡ.

ᴡᴇ’ʟʟ ꜰɪx ɪᴛ ᴀꜱ ꜱᴏᴏɴ ᴀꜱ ᴘᴏꜱꜱɪʙʟᴇ ᴛᴏ ᴍᴀᴋᴇ ʏᴏᴜʀ ᴇxᴘᴇʀɪᴇɴᴄᴇ ʙᴇᴛᴛᴇʀ.
</b>"""

VERIFY_SUCCESS_TXT = lambda time_str: f"""<b>ᴡᴇʟᴄᴏᴍᴇ ʙᴀᴄᴋ 😊  

ʏᴏᴜʀ ᴛᴏᴋᴇɴ ʜᴀꜱ ʙᴇᴇɴ ꜱᴜᴄᴄᴇꜱꜱꜰᴜʟʟʏ ᴠᴇʀɪꜰɪᴇᴅ.
ʏᴏᴜ ᴄᴀɴ ɴᴏᴡ ᴜꜱᴇ ᴍᴇ ꜰᴏʀ {time_str}.

ɪꜰ ʏᴏᴜ ꜰɪɴᴅ ᴀɴʏ ᴛᴇᴄʜɴɪᴄᴀʟ ɪꜱꜱᴜᴇ, ᴘʟᴇᴀꜱᴇ ʀᴇᴘᴏʀᴛ ɪᴛ ᴛᴏ ᴜꜱ.
ᴡᴇ’ʟʟ ꜰɪx ɪᴛ ᴀꜱ ꜱᴏᴏɴ ᴀꜱ ᴘᴏꜱꜱɪʙʟᴇ ᴛᴏ ᴍᴀᴋᴇ ʏᴏᴜʀ ᴇxᴘᴇʀɪᴇɴᴄᴇ ʙᴇᴛᴛᴇʀ.

ᴇɴᴊᴏʏ ʏᴏᴜʀ ᴛɪᴍᴇ ❤️</b>"""


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
VERIFY_EXPIRE = os.environ.get('VERIFY_EXPIRE', 300000) # VERIFY EXPIRE TIME IN SECONDS. LIKE:- 0 (ZERO) TO OFF VERIFICATION 
VERIFY_TUTORIAL = os.environ.get('VERIFY_TUTORIAL', 'https://t.me/N4_Society/55') # LINK OF TUTORIAL TO VERIFY 
REPORT_CHANNEL_USERNAME = os.environ.get('REPORT_CHANNEL_USERNAME', 'Anime_Library_N4') # For the Report button link
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
    
def get_report_markup():
    # Report page buttons: Back, Cancel
    return InlineKeyboardMarkup([
        [InlineKeyboardButton('ʙᴀᴄᴋ', callback_data="verify_success_page"),
         InlineKeyboardButton('ᴄᴀɴᴄᴇʟ', callback_data="close_message")]
    ])

def get_success_markup(time_str):
    # New success page buttons: Report, Premium, Cancel
    return InlineKeyboardMarkup([
        [InlineKeyboardButton('ʀᴇᴘᴏʀᴛ', callback_data="report_page"),
         InlineKeyboardButton('ᴘʀᴇᴍɪᴜᴍ', callback_data="premium_page")],
        [InlineKeyboardButton('ᴄᴀɴᴄᴇʟ', callback_data="close_message")]
    ])

# --- NEW CALLBACK QUERY HANDLERS ---

# Handler for 'Report' button (opens Report page)
@Client.on_callback_query(filters.regex("report_page"))
async def report_callback_handler(client, callback_query: CallbackQuery):
    await callback_query.message.edit_caption(
        REPORT_TXT,
        reply_markup=get_report_markup()
    )
    await callback_query.answer()
    
# Handler for successful verification page from callback
@Client.on_callback_query(filters.regex("verify_success_page"))
async def verify_success_callback_handler(client, callback_query: CallbackQuery):
    time_str = get_readable_time(VERIFY_EXPIRE)
    await callback_query.message.edit_caption(
        VERIFY_SUCCESS_TXT(time_str),
        reply_markup=get_success_markup(time_str)
    )
    await callback_query.answer()

# Handler for 'Premium' button (opens Premium page)
@Client.on_callback_query(filters.regex("premium_page"))
async def premium_callback_handler(client, callback_query: CallbackQuery):
    await callback_query.message.edit_caption(
        PREMIUM_TXT,
        reply_markup=get_premium_markup()
    )
    await callback_query.answer()

# Handler for 'Plan' button (opens Plans page)
@Client.on_callback_query(filters.regex("plan_page"))
async def plan_callback_handler(client, callback_query: CallbackQuery):
    await callback_query.message.edit_caption(
        PREPLANS_TXT,
        reply_markup=get_plan_markup()
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
    if not isveri or (time() - isveri) >= float(VERIFY_EXPIRE): # First time/No record found or expired
        text = f"""ʜɪ 👋 {callback_query.from_user.mention},

ᴛᴏ ꜱᴛᴀʀᴛ ᴜꜱɪɴɢ ᴛʜɪꜱ ʙᴏᴛ, ᴘʟᴇᴀꜱᴇ ɢᴇɴᴇʀᴀᴛᴇ ᴀ ᴛᴇᴍᴘᴏʀᴀʀʏ ᴀᴅꜱ ᴛᴏᴋᴇɴ.

ᴠᴀʟɪᴅɪᴛʏ: {get_readable_time(VERIFY_EXPIRE)}"""
        
        if isveri and (time() - isveri) >= float(VERIFY_EXPIRE): # Token is expired
            text = f"""ʜɪ 👋 {callback_query.from_user.mention},

<blockquote>ʏᴏᴜʀ ᴀᴅꜱ ᴛᴏᴋᴇɴ ʜᴀꜱ ʙᴇᴇɴ ᴇxᴘɪʀᴇᴅ, ᴋɪɴᴅʟʏ ɢᴇᴛ ᴀ ɴᴇᴡ ᴛᴏᴋᴇɴ ᴛᴏ ᴄᴏɴᴛɪɴᴜᴇ ᴜꜱɪɴɢ ᴛʜɪꜱ ʙᴏᴛ.</blockquote>

ᴠᴀʟɪᴅɪᴛʏ: {get_readable_time(VERIFY_EXPIRE)}"""

        # Edit message content (always use edit_caption when photo is present)
        await callback_query.message.edit_caption(
            text,
            reply_markup=get_verification_markup(verify_token, username)
        )
    else: # User is currently verified, redirect to success page
        time_str = get_readable_time(VERIFY_EXPIRE)
        await callback_query.message.edit_caption(
            VERIFY_SUCCESS_TXT(time_str),
            reply_markup=get_success_markup(time_str)
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
        buttons = get_success_markup(get_readable_time(VERIFY_EXPIRE)) # Show success buttons
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

<blockquote>ʏᴏᴜʀ ᴀᴅꜱ ᴛᴏᴋᴇɴ ʜᴀꜱ ʙᴇᴇɴ ᴇxᴘɪʀᴇᴅ, ᴋɪɴᴅʟʏ ɢᴇᴛ ᴀ ɴᴇᴡ ᴛᴏᴋᴇɴ ᴛᴏ ᴄᴏɴᴛɪɴᴜᴇ ᴜꜱɪɴɢ ᴛʜɪꜱ ʙᴏᴛ.</blockquote>

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
                return res.get('shortenedUrl', longurl) # Corrected fallback to longurl
    except Exception as e:
        print(e)
        return longurl

async def validate_token(client, message, data):
    user_id = message.from_user.id
    vdict = verify_dict.setdefault(user_id, {})
    dict_token = vdict.get('token', None)
    time_str = get_readable_time(VERIFY_EXPIRE) # Calculate readable time here

    if await is_user_verified(user_id):
        # Existing verified users see the new success message/buttons
        return await client.send_photo(chat_id=message.from_user.id,
                                photo=VERIFY_PHOTO,
                                caption=VERIFY_SUCCESS_TXT(time_str),
                                reply_markup=get_success_markup(time_str)
                                )
        
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
    
    # Token is valid: update status and send success message with new buttons
    verify_dict.pop(user_id, None)
    await verifydb.update_verify_status(user_id)
    
    # NEW SUCCESS MESSAGE AND BUTTONS
    await client.send_photo(chat_id=message.from_user.id,
                            photo=VERIFY_PHOTO,
                            caption=VERIFY_SUCCESS_TXT(time_str),
                            reply_markup=get_success_markup(time_str)
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
        
