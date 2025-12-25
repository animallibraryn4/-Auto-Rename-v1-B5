import os
import string
import random
from time import time
from urllib3 import disable_warnings

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery

from cloudscraper import create_scraper
from motor.motor_asyncio import AsyncIOMotorClient
from config import Config, Txt
from helper.database import codeflixbots  # Import main database

# =====================================================
# MEMORY (SIMPLE & STABLE)
# =====================================================

verify_dict = {}              # user_id → {token, short_url, generated_at}
last_verify_message = {}      # user_id → last sent time (anti spam)
user_state = {}               # Track user's previous state for back button
verify_message_ids = {}       # user_id → list of message IDs of verification messages

VERIFY_MESSAGE_COOLDOWN = 5   # seconds
SHORTLINK_REUSE_TIME = 600    # 10 minutes

# =====================================================
# CONFIG
# =====================================================

VERIFY_PHOTO = os.environ.get(
    "VERIFY_PHOTO",
    "https://images8.alphacoders.com/138/1384114.png"
)
SHORTLINK_SITE = os.environ.get("SHORTLINK_SITE", "gplinks.com")
SHORTLINK_API = os.environ.get("SHORTLINK_API", "596f423cdf22b174e43d0b48a36a8274759ec2a3")
VERIFY_EXPIRE = int(os.environ.get("VERIFY_EXPIRE", 0))
VERIFY_TUTORIAL = os.environ.get("VERIFY_TUTORIAL", "https://t.me/N4_Society/55")

PREMIUM_USERS = list(map(int, os.environ.get("PREMIUM_USERS", "").split())) if os.environ.get("PREMIUM_USERS") else []

# =====================================================
# HELPERS
# =====================================================

def get_readable_time(seconds):
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}ʜ{m}ᴍ"
    if m:
        return f"{m}ᴍ"
    return f"{s}s"

async def is_user_verified(user_id):
    """Check if user is verified using main database"""
    if not VERIFY_EXPIRE or user_id in PREMIUM_USERS:
        return True
    
    # Get verification status from main database
    last = await codeflixbots.get_verify_status(user_id)
    
    # If last is 0 or None, user is not verified
    if not last:
        return False
    
    # Check if verification is still valid
    return (time() - last) < VERIFY_EXPIRE

async def delete_verification_messages(client, user_id):
    """Delete all verification messages for a user"""
    if user_id in verify_message_ids:
        for msg_id in verify_message_ids[user_id]:
            try:
                await client.delete_messages(user_id, msg_id)
            except:
                pass
        verify_message_ids.pop(user_id, None)

# =====================================================
# SHORTLINK
# =====================================================

async def get_short_url(longurl):
    cget = create_scraper().request
    disable_warnings()
    try:
        res = cget(
            "GET",
            f"https://{SHORTLINK_SITE}/api",
            params={"api": SHORTLINK_API, "url": longurl, "format": "text"}
        )
        return res.text if res.status_code == 200 else longurl
    except:
        return longurl

async def get_verify_token(bot, user_id, base):
    data = verify_dict.get(user_id)

    if data and (time() - data["generated_at"] < SHORTLINK_REUSE_TIME):
        return data["short_url"]

    token = "".join(random.choices(string.ascii_letters + string.digits, k=9))
    long_link = f"{base}verify-{user_id}-{token}"
    short_url = await get_short_url(long_link)

    verify_dict[user_id] = {
        "token": token,
        "short_url": short_url,
        "generated_at": time()
    }
    return short_url

# =====================================================
# MARKUPS
# =====================================================

def verify_markup(link):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Tutorial", url=VERIFY_TUTORIAL),
            InlineKeyboardButton("⭐ Premium", callback_data="premium_page")
        ],
        [InlineKeyboardButton("Get Token", url=link)]
    ])

def welcome_markup():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("ᴄʟᴏsᴇ", callback_data="close_message")]
    ])

def premium_markup():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅ ʙᴀᴄᴋ", callback_data="back_to_welcome")]
    ])

# =====================================================
# CORE VERIFICATION (STABLE)
# =====================================================

async def send_verification(client, message_or_query):
    """Send verification message"""
    if isinstance(message_or_query, CallbackQuery):
        user_id = message_or_query.from_user.id
        chat_id = message_or_query.message.chat.id
        mention = message_or_query.from_user.mention
        message_obj = message_or_query.message
    else:
        user_id = message_or_query.from_user.id
        chat_id = message_or_query.chat.id
        mention = message_or_query.from_user.mention
        message_obj = None

    if await is_user_verified(user_id):
        return

    now = time()
    last = last_verify_message.get(user_id, 0)

    # hard anti-spam
    if now - last < VERIFY_MESSAGE_COOLDOWN:
        return

    bot = await client.get_me()
    link = await get_verify_token(client, user_id, f"https://t.me/{bot.username}?start=")

    text = (
        f"Hi 👋 {mention}\n\n"
        f"To start using this bot, please complete Ads Token verification.\n\n"
        f"Validity: {get_readable_time(VERIFY_EXPIRE)}"
    )

    # Store user state as "verification"
    user_state[user_id] = "verification"
    
    sent_message = None
    
    # If we have a message object (callback query), edit it
    if message_obj:
        try:
            sent_message = await message_obj.edit_media(
                media=VERIFY_PHOTO,
                caption=text,
                reply_markup=verify_markup(link)
            )
        except:
            # If editing fails, send a new message
            await message_obj.delete()
            sent_message = await client.send_photo(
                chat_id=chat_id,
                photo=VERIFY_PHOTO,
                caption=text,
                reply_markup=verify_markup(link)
            )
    else:
        # Send new message
        sent_message = await client.send_photo(
            chat_id=chat_id,
            photo=VERIFY_PHOTO,
            caption=text,
            reply_markup=verify_markup(link)
        )
    
    # Store the message ID for later deletion
    if sent_message:
        if user_id not in verify_message_ids:
            verify_message_ids[user_id] = []
        verify_message_ids[user_id].append(sent_message.id)

    last_verify_message[user_id] = now

async def send_welcome_message(client, user_id, message_obj=None):
    """Send welcome message to verified users"""
    # Store user state as "verified"
    user_state[user_id] = "verified"
    
    text = (
        f"<b>ᴡᴇʟᴄᴏᴍᴇ ʙᴀᴄᴋ 😊\n\n"
        f"ʏᴏᴜʀ ᴛᴏᴋᴇɴ ʜᴀꜱ ʙᴇᴇɴ ꜱᴜᴄᴄᴇꜱꜱꜰᴜʟʟʏ ᴠᴇʀɪꜰɪᴇᴅ.\n"
        f"ʏᴏᴜ ᴄᴀɴ ɴᴏᴡ ᴜꜱᴇ ᴍᴇ ꜰᴏʀ {get_readable_time(VERIFY_EXPIRE)}.\n\n"
        f"ᴇɴᴊᴏʏ ʏᴏᴜʀ ᴛɪᴍᴇ ❤️</b>"
    )
    
    # If we have a message object, edit it
    if message_obj:
        try:
            await message_obj.edit_caption(
                caption=text,
                reply_markup=welcome_markup()
            )
        except:
            # If editing fails, send a new message
            await message_obj.delete()
            await client.send_photo(
                chat_id=user_id,
                photo=VERIFY_PHOTO,
                caption=text,
                reply_markup=welcome_markup()
            )
    else:
        # Send new message
        await client.send_photo(
            chat_id=user_id,
            photo=VERIFY_PHOTO,
            caption=text,
            reply_markup=welcome_markup()
        )

async def validate_token(client, message, data):
    """Validate the verification token and update user status"""
    user_id = message.from_user.id
    
    # Check if already verified
    if await is_user_verified(user_id):
        await message.reply("✅ You are already verified!")
        return

    stored = verify_dict.get(user_id)

    if not stored:
        # No active token found, send new verification
        return await send_verification(client, message)

    try:
        # Parse the data: verify-user_id-token
        _, uid, token = data.split("-")
        
        if uid == str(user_id) and token == stored["token"]:
            # Token is valid
            verify_dict.pop(user_id, None)
            last_verify_message.pop(user_id, None)

            # Save verification status in main database
            await codeflixbots.set_verify_status(user_id, int(time()))
            
            # Delete all previous verification messages
            await delete_verification_messages(client, user_id)
            
            # Send welcome message
            await send_welcome_message(client, user_id)
            
            print(f"[VERIFY SUCCESS] User {user_id} verified successfully")
        else:
            # Token mismatch
            print(f"[VERIFY FAIL] Token mismatch for user {user_id}")
            await send_verification(client, message)
            
    except Exception as e:
        print(f"[VERIFY ERROR] {e}")
        await send_verification(client, message)

# =====================================================
# CALLBACKS
# =====================================================

@Client.on_callback_query(filters.regex("^premium_page$"))
async def premium_cb(client, query: CallbackQuery):
    user_id = query.from_user.id
    # Store current state before going to premium
    if user_id not in user_state:
        user_state[user_id] = "verification"
    
    # Edit the current message to show premium page
    await query.message.edit_text(
        Txt.PREMIUM_TXT,
        reply_markup=premium_markup(),
        disable_web_page_preview=True
    )

@Client.on_callback_query(filters.regex("^back_to_welcome$"))
async def back_cb(client, query: CallbackQuery):
    user_id = query.from_user.id
    
    # Check user's previous state
    state = user_state.get(user_id, "verification")
    
    if state == "verified":
        # User was already verified, show welcome message
        await send_welcome_message(client, user_id, query.message)
    else:
        # User was in verification flow, show verification message
        await send_verification(client, query)

@Client.on_callback_query(filters.regex("^close_message$"))
async def close_cb(client, query: CallbackQuery):
    user_id = query.from_user.id
    # Clear user state when closing
    user_state.pop(user_id, None)
    await query.message.delete()

# =====================================================
# VERIFY COMMAND
# =====================================================

@Client.on_message(filters.private & filters.command("verify"))
async def verify_cmd(client, message):
    if len(message.command) == 2 and message.command[1].startswith("verify"):
        await validate_token(client, message, message.command[1])
    else:
        await send_verification(client, message)

# =====================================================
# GET_TOKEN COMMAND
# =====================================================

@Client.on_message(filters.private & filters.command("get_token"))
async def get_token_cmd(client, message):
    """New command to get verification token"""
    await send_verification(client, message)

