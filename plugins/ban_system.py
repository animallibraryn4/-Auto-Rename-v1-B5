# ban_system.py
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from helper.database import codeflixbots
from config import Config
import datetime

@Client.on_message(filters.command("ban") & filters.user(Config.ADMIN))
async def ban_user(client: Client, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("**Usage:** `/ban user_id reason`\n**Example:** `/ban 12345678 Spamming`")
    
    try:
        user_id = int(message.command[1])
        reason = " ".join(message.command[2:]) if len(message.command) > 2 else "No reason provided"
        
        # Check if user exists
        if not await codeflixbots.is_user_exist(user_id):
            return await message.reply_text(f"❌ User `{user_id}` not found in database.")
        
        # Update ban status
        ban_data = {
            "is_banned": True,
            "ban_duration": 0,  # 0 means permanent
            "banned_on": datetime.date.today().isoformat(),
            "ban_reason": reason
        }
        
        await codeflixbots.col.update_one(
            {"_id": user_id},
            {"$set": {"ban_status": ban_data}}
        )
        
        # Notify in log channel
        admin = message.from_user
        log_text = f"""
🚫 **User Banned**
        
👤 **User ID:** `{user_id}`
🛠 **Banned By:** {admin.mention}
📅 **Date:** {datetime.date.today().isoformat()}
📝 **Reason:** {reason}
        """
        
        if Config.LOG_CHANNEL:
            await client.send_message(Config.LOG_CHANNEL, log_text)
        
        # Try to notify user
        try:
            await client.send_message(
                user_id,
                f"🚫 **You have been banned from using this bot.**\n\n📝 **Reason:** {reason}\n\nIf you think this is a mistake, please contact @Anime_Library_N4"
            )
        except:
            pass
        
        await message.reply_text(f"✅ User `{user_id}` has been banned successfully.")
        
    except ValueError:
        await message.reply_text("❌ Invalid user ID. Please provide a numeric ID.")
    except Exception as e:
        await message.reply_text(f"❌ Error: {str(e)}")

@Client.on_message(filters.command("unban") & filters.user(Config.ADMIN))
async def unban_user(client: Client, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("**Usage:** `/unban user_id`\n**Example:** `/unban 12345678`")
    
    try:
        user_id = int(message.command[1])
        
        # Update ban status
        ban_data = {
            "is_banned": False,
            "ban_duration": 0,
            "banned_on": datetime.date.today().isoformat(),
            "ban_reason": ''
        }
        
        await codeflixbots.col.update_one(
            {"_id": user_id},
            {"$set": {"ban_status": ban_data}}
        )
        
        # Notify in log channel
        admin = message.from_user
        log_text = f"""
✅ **User Unbanned**
        
👤 **User ID:** `{user_id}`
🛠 **Unbanned By:** {admin.mention}
📅 **Date:** {datetime.date.today().isoformat()}
        """
        
        if Config.LOG_CHANNEL:
            await client.send_message(Config.LOG_CHANNEL, log_text)
        
        # Try to notify user
        try:
            await client.send_message(
                user_id,
                "✅ **Your ban has been lifted. You can now use the bot again.**"
            )
        except:
            pass
        
        await message.reply_text(f"✅ User `{user_id}` has been unbanned successfully.")
        
    except ValueError:
        await message.reply_text("❌ Invalid user ID. Please provide a numeric ID.")
    except Exception as e:
        await message.reply_text(f"❌ Error: {str(e)}")

@Client.on_message(filters.command("banned") & filters.user(Config.ADMIN))
async def list_banned_users(client: Client, message: Message):
    try:
        banned_users = []
        async for user in codeflixbots.col.find({"ban_status.is_banned": True}):
            banned_users.append(f"`{user['_id']}` - {user['ban_status'].get('ban_reason', 'No reason')}")
        
        if banned_users:
            text = "🚫 **Banned Users:**\n\n" + "\n".join(banned_users)
            await message.reply_text(text)
        else:
            await message.reply_text("✅ No users are currently banned.")
    except Exception as e:
        await message.reply_text(f"❌ Error: {str(e)}")

# बैन चेक करने वाला middleware
async def check_ban_status(_, __, message):
    user_id = message.from_user.id
    try:
        user = await codeflixbots.col.find_one({"_id": user_id})
        if user and user.get("ban_status", {}).get("is_banned", False):
            return False  # बैन यूज़र को कमांड नहीं चलाने दें
        return True
    except:
        return True

# Force Subs के बाद बैन चेक जोड़ें
from pyrogram.errors import UserNotParticipant

async def check_user_access(_, __, message):
    # पहले force sub चेक करें
    for channel in Config.FORCE_SUB_CHANNELS:
        try:
            await message._client.get_chat_member(channel, message.from_user.id)
        except UserNotParticipant:
            return True  # Force sub नहीं किया है
    
    # फिर बैन स्टेटस चेक करें
    user_id = message.from_user.id
    user = await codeflixbots.col.find_one({"_id": user_id})
    if user and user.get("ban_status", {}).get("is_banned", False):
        reason = user["ban_status"].get("ban_reason", "No reason provided")
        try:
            await message.reply_text(
                f"🚫 **You are banned from using this bot.**\n\n📝 **Reason:** {reason}\n\nIf you think this is a mistake, please contact @Anime_Library_N4"
            )
        except:
            pass
        return False
    return True

# सभी कमांड्स के लिए बैन चेक लागू करें
@Client.on_message(filters.private & filters.create(check_user_access))
async def handle_all_messages(client, message):
    # यहाँ कोई एक्शन नहीं, सिर्फ बैन चेक के लिए
    pass
