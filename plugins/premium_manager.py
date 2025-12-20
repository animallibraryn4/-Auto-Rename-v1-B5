from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from helper.database import codeflixbots
from config import Config
import time
from datetime import datetime
import pytz

@Client.on_message(filters.private & filters.command("addpremium") & filters.user(Config.ADMIN))
async def add_premium_user(client, message: Message):
    """Add a user to premium"""
    try:
        # Command format: /addpremium <user_id> <days>
        if len(message.command) < 3:
            await message.reply_text(
                "**Usage:** `/addpremium <user_id> <days>`\n\n"
                "**Example:** `/addpremium 123456789 30`\n"
                "This will add user with ID 123456789 as premium for 30 days."
            )
            return
        
        user_id = int(message.command[1])
        days = int(message.command[2])
        
        if days <= 0:
            await message.reply_text("❌ Days must be greater than 0")
            return
        
        # Add user to premium
        success = await codeflixbots.add_premium_user(user_id, days)
        
        if success:
            expiry_time = time.time() + (days * 24 * 60 * 60)
            expiry_date = datetime.fromtimestamp(expiry_time, tz=pytz.timezone("Asia/Kolkata")).strftime('%Y-%m-%d %H:%M:%S')
            
            await message.reply_text(
                f"✅ **User Added to Premium Successfully!**\n\n"
                f"**User ID:** `{user_id}`\n"
                f"**Plan Duration:** {days} days\n"
                f"**Expiry Date:** {expiry_date}\n"
                f"**Remaining Days:** {days} days"
            )
            
            # Send notification to the user if possible
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
            await message.reply_text("❌ Failed to add user to premium. Please check the user ID.")
            
    except ValueError:
        await message.reply_text("❌ Invalid user ID or days. Please provide valid numbers.")
    except Exception as e:
        await message.reply_text(f"❌ Error: {str(e)}")

@Client.on_message(filters.private & filters.command("removepremium") & filters.user(Config.ADMIN))
async def remove_premium_user(client, message: Message):
    """Remove premium status from a user"""
    try:
        # Command format: /removepremium <user_id>
        if len(message.command) < 2:
            await message.reply_text(
                "**Usage:** `/removepremium <user_id>`\n\n"
                "**Example:** `/removepremium 123456789`"
            )
            return
        
        user_id = int(message.command[1])
        
        # Remove user from premium
        success = await codeflixbots.remove_premium_user(user_id)
        
        if success:
            await message.reply_text(
                f"✅ **Premium Status Removed Successfully!**\n\n"
                f"**User ID:** `{user_id}`\n"
                f"Premium access has been revoked."
            )
            
            # Send notification to the user if possible
            try:
                await client.send_message(
                    user_id,
                    "⚠️ **Your Premium Access Has Ended**\n\n"
                    "Your premium subscription has been removed. "
                    "You can purchase a new plan to continue enjoying premium features."
                )
            except:
                pass
        else:
            await message.reply_text("❌ Failed to remove premium status. User might not exist.")
            
    except ValueError:
        await message.reply_text("❌ Invalid user ID. Please provide a valid number.")
    except Exception as e:
        await message.reply_text(f"❌ Error: {str(e)}")

@Client.on_message(filters.private & filters.command("premiumlist") & filters.user(Config.ADMIN))
async def list_premium_users(client, message: Message):
    """List all premium users"""
    try:
        # Clean up expired users first
        expired_count = await codeflixbots.cleanup_expired_premium()
        if expired_count > 0:
            await message.reply_text(f"🔄 Cleaned up {expired_count} expired premium users.")
        
        # Get all premium users
        premium_users = await codeflixbots.get_all_premium_users()
        
        if not premium_users:
            await message.reply_text("📭 No premium users found.")
            return
        
        # Sort by expiry time (soonest first)
        premium_users.sort(key=lambda x: x["expiry_time"])
        
        # Create the message
        message_text = f"⭐ **Premium Users List** ⭐\n\n"
        message_text += f"**Total Premium Users:** {len(premium_users)}\n\n"
        
        for i, user in enumerate(premium_users[:50], 1):  # Show first 50 users
            user_id = user["user_id"]
            expiry_time = user["expiry_time"]
            days = user["days"]
            days_left = user["days_left"]
            is_expired = user["is_expired"]
            
            # Format expiry date
            expiry_date = datetime.fromtimestamp(expiry_time, tz=pytz.timezone("Asia/Kolkata")).strftime('%Y-%m-%d %H:%M:%S')
            
            status = "✅ Active" if not is_expired and days_left > 0 else "❌ Expired"
            
            message_text += (
                f"**{i}. User ID:** `{user_id}`\n"
                f"   **Plan:** {days} days\n"
                f"   **Days Left:** {days_left}\n"
                f"   **Expiry:** {expiry_date}\n"
                f"   **Status:** {status}\n\n"
            )
        
        if len(premium_users) > 50:
            message_text += f"\n... and {len(premium_users) - 50} more premium users."
        
        await message.reply_text(message_text)
        
    except Exception as e:
        await message.reply_text(f"❌ Error fetching premium users: {str(e)}")

@Client.on_message(filters.private & filters.command("checkpremium") & filters.user(Config.ADMIN))
async def check_premium_status(client, message: Message):
    """Check premium status of a specific user"""
    try:
        # Command format: /checkpremium <user_id>
        if len(message.command) < 2:
            await message.reply_text(
                "**Usage:** `/checkpremium <user_id>`\n\n"
                "**Example:** `/checkpremium 123456789`"
            )
            return
        
        user_id = int(message.command[1])
        
        # Get premium status
        premium_status = await codeflixbots.get_premium_status(user_id)
        
        if premium_status.get("is_premium", False):
            expiry_time = premium_status.get("expiry_time", 0)
            days_left = premium_status.get("days_left", 0)
            added_at = premium_status.get("added_at", 0)
            
            # Format dates
            expiry_date = datetime.fromtimestamp(expiry_time, tz=pytz.timezone("Asia/Kolkata")).strftime('%Y-%m-%d %H:%M:%S')
            added_date = datetime.fromtimestamp(added_at, tz=pytz.timezone("Asia/Kolkata")).strftime('%Y-%m-%d %H:%M:%S')
            
            await message.reply_text(
                f"✅ **User is Premium**\n\n"
                f"**User ID:** `{user_id}`\n"
                f"**Days Left:** {days_left}\n"
                f"**Expiry Date:** {expiry_date}\n"
                f"**Added On:** {added_date}\n"
                f"**Status:** Active ⭐"
            )
        else:
            await message.reply_text(
                f"❌ **User is Not Premium**\n\n"
                f"**User ID:** `{user_id}`\n"
                f"**Status:** Regular User"
            )
            
    except ValueError:
        await message.reply_text("❌ Invalid user ID. Please provide a valid number.")
    except Exception as e:
        await message.reply_text(f"❌ Error: {str(e)}")

@Client.on_message(filters.private & filters.command("myplan"))
async def my_plan_command(client, message: Message):
    """Check user's own premium status"""
    user_id = message.from_user.id
    
    # Get premium status
    premium_status = await codeflixbots.get_premium_status(user_id)
    
    if premium_status.get("is_premium", False):
        days_left = premium_status.get("days_left", 0)
        expiry_time = premium_status.get("expiry_time", 0)
        
        # Format expiry date
        expiry_date = datetime.fromtimestamp(expiry_time, tz=pytz.timezone("Asia/Kolkata")).strftime('%Y-%m-%d %H:%M:%S')
        
        await message.reply_text(
            f"⭐ **Your Premium Plan** ⭐\n\n"
            f"**Status:** Active\n"
            f"**Days Remaining:** {days_left}\n"
            f"**Expiry Date:** {expiry_date}\n\n"
            f"Enjoy premium features! 🚀"
        )
    else:
        # Check verification status
        last = await codeflixbots.get_verify_status(user_id)
        if last:
            from plugins import VERIFY_EXPIRE, get_readable_time
            remaining_time = VERIFY_EXPIRE - (time.time() - last)
            if remaining_time > 0:
                await message.reply_text(
                    f"📱 **Your Current Plan**\n\n"
                    f"**Status:** Verified (Free)\n"
                    f"**Time Remaining:** {get_readable_time(remaining_time)}\n\n"
                    f"Upgrade to premium for unlimited access! /plan"
                )
            else:
                await message.reply_text(
                    f"⚠️ **Your Current Plan**\n\n"
                    f"**Status:** Verification Expired\n"
                    f"**Action Required:** Please verify again\n\n"
                    f"Use /get_token to verify or /plan to upgrade to premium!"
                )
        else:
            await message.reply_text(
                f"🔒 **Your Current Plan**\n\n"
                f"**Status:** Not Verified\n"
                f"**Action Required:** Please verify first\n\n"
                f"Use /get_token to verify or /plan to upgrade to premium!"
            )
