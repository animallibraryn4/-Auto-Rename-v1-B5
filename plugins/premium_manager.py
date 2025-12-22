import time
from helper.database import codeflixbots
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# Plan durations in days
PLAN_DURATIONS = {
    "free": 0.042,  # 1 hour (1/24 ≈ 0.0417)
    "basic": 7,
    "lite": 15,
    "standard": 30,
    "pro": 50,
    "ultra": 0  # Coming soon
}

async def activate_premium_plan(user_id, plan_type, duration_days):
    """Activate premium plan for user"""
    if duration_days > 0:
        expiry_time = time.time() + (duration_days * 86400)  # Convert days to seconds
    else:
        expiry_time = 0
    
    # Set verification expiry (extends verification)
    await codeflixbots.set_verify_status(user_id, int(expiry_time) if expiry_time else int(time.time()))
    
    # Store plan type for tracking
    await codeflixbots.col.update_one(
        {"_id": int(user_id)},
        {"$set": {
            "premium_plan": plan_type,
            "premium_expiry": expiry_time,
            "premium_activated": True
        }},
        upsert=True
    )
    return True

async def check_premium_status(user_id):
    """Check if user has active premium"""
    try:
        user = await codeflixbots.col.find_one({"_id": int(user_id)})
        
        if not user:
            return False
        
        # Check if premium is activated
        if not user.get("premium_activated", False):
            return False
        
        # Check premium expiry
        expiry = user.get("premium_expiry", 0)
        if expiry and time.time() < expiry:
            return True
        
        # If expired, reset premium status
        await codeflixbots.col.update_one(
            {"_id": int(user_id)},
            {"$set": {
                "premium_activated": False,
                "premium_plan": "expired"
            }}
        )
        return False
        
    except Exception as e:
        print(f"[PREMIUM ERROR] User {user_id}: {e}")
        return False

async def get_remaining_days(user_id):
    """Get remaining days of premium"""
    user = await codeflixbots.col.find_one({"_id": int(user_id)})
    
    if not user or not user.get("premium_activated", False):
        return 0
    
    expiry = user.get("premium_expiry", 0)
    if expiry and time.time() < expiry:
        return int((expiry - time.time()) / 86400)
    
    return 0

async def get_user_plan(user_id):
    """Get user's current plan"""
    user = await codeflixbots.col.find_one({"_id": int(user_id)})
    
    if not user:
        return {"type": "none", "remaining": 0, "active": False}
    
    if user.get("premium_activated", False):
        expiry = user.get("premium_expiry", 0)
        if expiry and time.time() < expiry:
            remaining = int((expiry - time.time()) / 86400)
            return {
                "type": user.get("premium_plan", "premium"),
                "remaining": remaining,
                "active": True
            }
    
    # Check free verification
    verify_status = await codeflixbots.get_verify_status(user_id)
    if verify_status:
        remaining_seconds = 3020 - (time.time() - verify_status)
        if remaining_seconds > 0:
            return {
                "type": "free_token",
                "remaining": int(remaining_seconds / 3600),  # hours
                "active": True
            }
    
    return {"type": "none", "remaining": 0, "active": False}

@Client.on_message(filters.command("myplan") & filters.private)
async def my_plan_command(client, message):
    user_id = message.from_user.id
    plan_info = await get_user_plan(user_id)
    
    if plan_info["active"]:
        if plan_info["type"] == "free_token":
            await message.reply_text(
                f"🆓 **Free Token Active**\n\n"
                f"⏰ **Hours Remaining:** {plan_info['remaining']}\n"
                f"⚠️ **Limitations:** Queue system active\n\n"
                f"💎 Upgrade for unlimited access: /plan"
            )
        else:
            await message.reply_text(
                f"✅ **Active Plan:** {plan_info['type'].replace('_', ' ').title()}\n\n"
                f"📅 **Days Remaining:** {plan_info['remaining']}\n"
                f"🚀 **Benefits:** Unlimited renaming\n"
                f"🎯 **Priority:** High\n\n"
                f"Use /plan to view other plans"
            )
    else:
        await message.reply_text(
            "❌ **No Active Plan**\n\n"
            "You don't have an active plan. Choose an option:\n\n"
            "🆓 **Free:** /get_token (1 hour access)\n"
            "💎 **Premium:** /plan (7 to 50 days)\n\n"
            "Premium features:\n"
            "• No verification needed\n"
            "• Unlimited file processing\n"
            "• Priority queue\n"
            "• All quality thumbnails"
        )

# Admin command to manually activate plans
@Client.on_message(filters.command("grant") & filters.user(Config.ADMIN))
async def grant_premium(client, message):
    if len(message.command) < 3:
        await message.reply_text(
            "Usage: `/grant <user_id> <plan_type> <days>`\n\n"
            "Plan types: free, basic, lite, standard, pro\n"
            "Example: `/grant 123456789 basic 7`"
        )
        return
    
    try:
        target_id = int(message.command[1])
        plan_type = message.command[2].lower()
        days = int(message.command[3]) if len(message.command) > 3 else PLAN_DURATIONS.get(plan_type, 7)
        
        if plan_type not in PLAN_DURATIONS:
            await message.reply_text(
                f"Invalid plan type. Choose from: {', '.join(PLAN_DURATIONS.keys())}"
            )
            return
        
        await activate_premium_plan(target_id, plan_type, days)
        
        # Notify admin
        await message.reply_text(
            f"✅ **Plan Activated!**\n\n"
            f"**User ID:** `{target_id}`\n"
            f"**Plan:** {plan_type.title()}\n"
            f"**Duration:** {days} days\n\n"
            f"User has been notified."
        )
        
        # Notify user
        try:
            await client.send_message(
                target_id,
                f"🎉 **Congratulations!**\n\n"
                f"Admin has activated **{plan_type.title()} Plan** for you!\n"
                f"✅ **Duration:** {days} days\n"
                f"🚀 **Benefits:** Unlimited renaming, no verification needed\n\n"
                f"Use `/myplan` to check your status."
            )
        except:
            pass
            
    except ValueError:
        await message.reply_text("Invalid user ID or days format.")
    except Exception as e:
        await message.reply_text(f"Error: {str(e)}")
