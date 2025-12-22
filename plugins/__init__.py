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
from helper.database import codeflixbots
from plugins.premium_manager import check_premium_status, get_user_plan

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
VERIFY_EXPIRE = int(os.environ.get("VERIFY_EXPIRE", 3020))
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
    """Check if user is verified or has premium"""
    # 1. Check if user is admin
    if user_id in Config.ADMIN:
        return True
    
    # 2. Check premium status first (bypasses verification)
    if await check_premium_status(user_id):
        return True
    
    # 3. Check if user is in premium users list
    if user_id in PREMIUM_USERS:
        return True
    
    # 4. Check free verification
    if not VERIFY_EXPIRE:
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
            InlineKeyboardButton("Premium Plans", callback_data="premium_plans")
        ],
        [InlineKeyboardButton("Get Token", url=link)],
        [InlineKeyboardButton("Check My Plan", callback_data="check_my_plan")]
    ])

def welcome_markup():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Close", callback_data="close_message")]
    ])

def premium_plans_markup():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("View All Plans", callback_data="main_plan")],
        [InlineKeyboardButton("⬅ Back", callback_data="back_to_welcome")]
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

    # Check if already verified or premium
    if await is_user_verified(user_id):
        if message_obj:
            await send_welcome_message(client, user_id, message_obj)
        return

    now = time()
    last = last_verify_message.get(user_id, 0)

    # hard anti-spam
    if now - last < VERIFY_MESSAGE_COOLDOWN:
        return

    bot = await client.get_me()
    link = await get_verify_token(client, user_id, f"https://t.me/{bot.username}?start=")

    # Get user's plan info
    plan_info = await get_user_plan(user_id)
    
    if plan_info["type"] == "free_token" and plan_info["active"]:
        # User has active free token
        remaining_hours = plan_info["remaining"]
        text = (
            f"Hi 👋 {mention}\n\n"
            f"You have an active free token! 🎉\n"
            f"⏰ **Remaining:** {remaining_hours} hours\n\n"
            f"You can continue using the bot, or upgrade for more benefits!"
        )
        
        # Store user state as "verified"
        user_state[user_id] = "verified"
        
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("💎 View Premium Plans", callback_data="main_plan")],
            [InlineKeyboardButton("❌ Close", callback_data="close_message")]
        ])
    else:
        # No active plan/token
        text = (
            f"Hi 👋 {mention}\n\n"
            f"To start using this bot, please complete Ads Token verification.\n\n"
            f"🆓 **Free Access:** {get_readable_time(VERIFY_EXPIRE)}\n"
            f"💎 **Premium:** Unlimited access (no verification needed)\n\n"
            f"Choose an option below:"
        )
        
        # Store user state as "verification"
        user_state[user_id] = "verification"
        buttons = verify_markup(link)

    sent_message = None
    
    # If we have a message object (callback query), edit it
    if message_obj:
        try:
            sent_message = await message_obj.edit_media(
                media=VERIFY_PHOTO,
                caption=text,
                reply_markup=buttons
            )
        except:
            # If editing fails, send a new message
            await message_obj.delete()
            sent_message = await client.send_photo(
                chat_id=chat_id,
                photo=VERIFY_PHOTO,
                caption=text,
                reply_markup=buttons
            )
    else:
        # Send new message
        sent_message = await client.send_photo(
            chat_id=chat_id,
            photo=VERIFY_PHOTO,
            caption=text,
            reply_markup=buttons
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
    
    # Get user's plan info
    plan_info = await get_user_plan(user_id)
    
    if plan_info["type"] == "free_token" and plan_info["active"]:
        text = (
            f"<b>Welcome Back 😊\n\n"
            f"Your free token is active!\n"
            f"⏰ **Remaining:** {plan_info['remaining']} hours\n\n"
            f"Enjoy your free access! 🎉</b>"
        )
    elif plan_info["active"]:
        text = (
            f"<b>Welcome Back Premium User! 🎉\n\n"
            f"✅ **Active Plan:** {plan_info['type'].replace('_', ' ').title()}\n"
            f"📅 **Days Remaining:** {plan_info['remaining']}\n\n"
            f"Enjoy unlimited renaming! 🚀</b>"
        )
    else:
        text = (
            f"<b>Welcome Back 😊\n"
            f"Your token has been successfully verified.\n"
            f"You can now use me for {get_readable_time(VERIFY_EXPIRE)}.\n\n"
            f"Enjoy ❤️</b>"
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

@Client.on_callback_query(filters.regex("^premium_plans$"))
async def premium_plans_cb(client, query: CallbackQuery):
    user_id = query.from_user.id
    # Store current state before going to premium
    if user_id not in user_state:
        user_state[user_id] = "verification"
    
    # Edit the current message to show premium page
    await query.message.edit_text(
        Txt.PREMIUM_TXT,
        reply_markup=premium_plans_markup(),
        disable_web_page_preview=True
    )

@Client.on_callback_query(filters.regex("^main_plan$"))
async def main_plan_cb(client, query: CallbackQuery):
    user_id = query.from_user.id
    from plugins.plan_system import plan_menu
    
    # We need to call the plan menu function
    # Since it expects a message, we'll simulate one
    class SimulatedMessage:
        def __init__(self, from_user, chat):
            self.from_user = from_user
            self.chat = chat
            self.id = query.message.id
    
    simulated_message = SimulatedMessage(
        from_user=query.from_user,
        chat=query.message.chat
    )
    
    await plan_menu(client, simulated_message)

@Client.on_callback_query(filters.regex("^check_my_plan$"))
async def check_my_plan_cb(client, query: CallbackQuery):
    user_id = query.from_user.id
    from plugins.premium_manager import get_user_plan, my_plan_command
    
    plan_info = await get_user_plan(user_id)
    
    if plan_info["active"]:
        if plan_info["type"] == "free_token":
            text = f"🆓 **Free Token Active**\n⏰ **Hours Remaining:** {plan_info['remaining']}"
        else:
            text = f"✅ **Active Plan:** {plan_info['type'].replace('_', ' ').title()}\n📅 **Days Remaining:** {plan_info['remaining']}"
        
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("💎 View All Plans", callback_data="main_plan")],
            [InlineKeyboardButton("❌ Close", callback_data="close_message")]
        ])
    else:
        text = "❌ **No Active Plan**\n\nYou don't have an active plan."
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("🆓 Get Free Token", callback_data="back_to_welcome")],
            [InlineKeyboardButton("💎 View Premium Plans", callback_data="main_plan")],
            [InlineKeyboardButton("❌ Close", callback_data="close_message")]
        ])
    
    await query.message.edit_caption(
        caption=text,
        reply_markup=buttons
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
