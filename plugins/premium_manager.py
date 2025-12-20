from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from helper.database import codeflixbots
from config import Config
import time
from datetime import datetime
import pytz
from plugins import VERIFY_EXPIRE, get_readable_time  

@Client.on_message(filters.private & filters.command("addpremium") & filters.user(Config.ADMIN))
async def add_premium_user(client, message: Message):
    """Add a user to premium"""
    try:
        if len(message.command) < 3:
            await message.reply_text(
                "**Usage:** `/addpremium <user_id> <days>`\n\n"
                "**Example:** `/addpremium 123456789 30`"
            )
            return
        
        user_id = int(message.command[1])
        days = int(message.command[2])
        
        if days <= 0:
            await message.reply_text("❌ Days must be greater than 0")
            return
        
        success = await codeflixbots.add_premium_user(user_id, days)
        
        if success:
            expiry_time = time.time() + (days * 24 * 60 * 60)
            expiry_date = datetime.fromtimestamp(expiry_time, tz=pytz.timezone("Asia/Kolkata")).strftime('%Y-%m-%d %H:%M:%S')
            
            await message.reply_text(
                f"✅ **User Added to Premium Successfully!**\n\n"
                f"**User ID:** `{user_id}`\n"
                f"**Plan Duration:** {days} days\n"
                f"**Expiry Date:** {expiry_date}"
            )
            
            try:
                await client.send_message(
                    user_id,
                    f"🎉 **Congratulations! You've been upgraded to Premium!**\n\n"
                    f"**Plan Duration:** {days} days\n"
                    f"**Expiry Date:** {expiry_date}\n\n"
                    f"Enjoy premium features! 🚀"
                )
            except:
                pass
        else:
            await message.reply_text("❌ Failed to add user to premium.")
            
    except ValueError:
        await message.reply_text("❌ Invalid user ID or days.")
    except Exception as e:
        await message.reply_text(f"❌ Error: {str(e)}")

@Client.on_message(filters.private & filters.command("removepremium") & filters.user(Config.ADMIN))
async def remove_premium_user(client, message: Message):
    """Remove premium status from a user"""
    try:
        if len(message.command) < 2:
            await message.reply_text("**Usage:** `/removepremium <user_id>`")
            return
        
        user_id = int(message.command[1])
        success = await codeflixbots.remove_premium_user(user_id)
        
        if success:
            await message.reply_text(f"✅ **Premium Status Removed Successfully!**\n\n**User ID:** `{user_id}`")
            try:
                await client.send_message(user_id, "⚠️ **Your Premium Access Has Ended**")
            except:
                pass
        else:
            await message.reply_text("❌ Failed to remove premium status.")
            
    except ValueError:
        await message.reply_text("❌ Invalid user ID.")
    except Exception as e:
        await message.reply_text(f"❌ Error: {str(e)}")

@Client.on_message(filters.private & filters.command("premiumlist") & filters.user(Config.ADMIN))
async def list_premium_users(client, message: Message):
    """List all premium users"""
    try:
        expired_count = await codeflixbots.cleanup_expired_premium()
        if expired_count > 0:
            await message.reply_text(f"🔄 Cleaned up {expired_count} expired premium users.")
        
        premium_users = await codeflixbots.get_all_premium_users()
        if not premium_users:
            await message.reply_text("📭 No premium users found.")
            return
        
        premium_users.sort(key=lambda x: x["expiry_time"])
        message_text = f"⭐ **Premium Users List** ⭐\n\n"
        for i, user in enumerate(premium_users[:50], 1):
            expiry_date = datetime.fromtimestamp(user["expiry_time"], tz=pytz.timezone("Asia/Kolkata")).strftime('%Y-%m-%d %H:%M:%S')
            message_text += f"**{i}. User ID:** `{user['user_id']}`\n   **Expiry:** {expiry_date}\n\n"
        
        await message.reply_text(message_text)
    except Exception as e:
        await message.reply_text(f"❌ Error: {str(e)}")

@Client.on_message(filters.private & filters.command("checkpremium") & filters.user(Config.ADMIN))
async def check_premium_status(client, message: Message):
    """Check premium status of a specific user"""
    try:
        if len(message.command) < 2:
            await message.reply_text("**Usage:** `/checkpremium <user_id>`")
            return
        
        user_id = int(message.command[1])
        premium_status = await codeflixbots.get_premium_status(user_id)
        
        if premium_status.get("is_premium", False):
            expiry_date = datetime.fromtimestamp(premium_status.get("expiry_time", 0), tz=pytz.timezone("Asia/Kolkata")).strftime('%Y-%m-%d %H:%M:%S')
            await message.reply_text(f"✅ **User is Premium**\n\n**User ID:** `{user_id}`\n**Expiry Date:** {expiry_date}")
        else:
            await message.reply_text(f"❌ **User is Not Premium**")
    except Exception as e:
        await message.reply_text(f"❌ Error: {str(e)}")

@Client.on_message(filters.private & filters.command("myplan"))
async def my_plan_command(client, message: Message):
    """Check user's own premium status"""
    user_id = message.from_user.id
    premium_status = await codeflixbots.get_premium_status(user_id)
    
    if premium_status.get("is_premium", False):
        expiry_date = datetime.fromtimestamp(premium_status.get("expiry_time", 0), tz=pytz.timezone("Asia/Kolkata")).strftime('%Y-%m-%d %H:%M:%S')
        await message.reply_text(f"⭐ **Your Premium Plan** ⭐\n\n**Status:** Active\n**Expiry Date:** {expiry_date}")
    else:
        last = await codeflixbots.get_verify_status(user_id)
        if last:
            remaining_time = VERIFY_EXPIRE - (time.time() - last)
            if remaining_time > 0:
                await message.reply_text(f"📱 **Your Plan**\n\n**Status:** Verified (Free)\n**Time Remaining:** {get_readable_time(remaining_time)}")
            else:
                await message.reply_text("⚠️ **Verification Expired**. Use /get_token.")
        else:
            await message.reply_text("🔒 **Not Verified**. Use /get_token.")
            
