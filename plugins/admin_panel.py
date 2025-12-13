from config import Config, Txt
from helper.database import codeflixbots
from pyrogram.types import Message
from pyrogram import Client, filters
from pyrogram.errors import FloodWait, InputUserDeactivated, UserIsBlocked, PeerIdInvalid
import os, sys, time, asyncio, logging, datetime
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
ADMIN_USER_ID = Config.ADMIN

# Flag to indicate if the bot is restarting
is_restarting = False

@Client.on_message(filters.private & filters.command("restart") & filters.user(ADMIN_USER_ID))
async def restart_bot(b, m):
    global is_restarting
    if not is_restarting:
        is_restarting = True
        await m.reply_text("**Restarting.....**")

        # Gracefully stop the bot's event loop
        b.stop()
        time.sleep(2)  # Adjust the delay duration based on your bot's shutdown time

        # Restart the bot process
        os.execl(sys.executable, sys.executable, *sys.argv)


@Client.on_message(filters.private & filters.command("tutorial"))
async def tutorial(bot: Client, message: Message):
    user_id = message.from_user.id
    format_template = await codeflixbots.get_format_template(user_id)
    await message.reply_text(
        text=Txt.FILE_NAME_TXT.format(format_template=format_template),
        disable_web_page_preview=True,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(" ᴏᴡɴᴇʀ", url="https://t.me/Anime_library_n4"),
             InlineKeyboardButton(" ᴛᴜᴛᴏʀɪᴀʟ", url="https://t.me/Animelibraryn4")]
        ])
    )


@Client.on_message(filters.command(["stats", "status"]) & filters.user(Config.ADMIN))
async def get_stats(bot, message):
    total_users = await codeflixbots.total_users_count()
    uptime = time.strftime("%Hh%Mm%Ss", time.gmtime(time.time() - bot.uptime))    
    start_t = time.time()
    st = await message.reply('**Accessing The Details.....**')    
    end_t = time.time()
    time_taken_s = (end_t - start_t) * 1000
    await st.edit(text=f"**--Bot Status--** \n\n**⌚️ Bot Uptime :** {uptime} \n**🐌 Current Ping :** `{time_taken_s:.3f} ms` \n**👭 Total Users :** `{total_users}`")

@Client.on_message(filters.command("broadcast") & filters.user(Config.ADMIN) & filters.reply)
async def broadcast_handler(bot: Client, m: Message):
    await bot.send_message(Config.LOG_CHANNEL, f"{m.from_user.mention} or {m.from_user.id} Is Started The Broadcast......")
    all_users = await codeflixbots.get_all_users()
    broadcast_msg = m.reply_to_message
    sts_msg = await m.reply_text("Broadcast Started..!") 
    done = 0
    failed = 0
    success = 0
    start_time = time.time()
    total_users = await codeflixbots.total_users_count()
    async for user in all_users:
        sts = await send_msg(user['_id'], broadcast_msg)
        if sts == 200:
           success += 1
        else:
           failed += 1
        if sts == 400:
           await codeflixbots.delete_user(user['_id'])
        done += 1
        if not done % 20:
           await sts_msg.edit(f"Broadcast In Progress: \n\nTotal Users {total_users} \nCompleted : {done} / {total_users}\nSuccess : {success}\nFailed : {failed}")
    completed_in = datetime.timedelta(seconds=int(time.time() - start_time))
    await sts_msg.edit(f"Bʀᴏᴀᴅᴄᴀꜱᴛ Cᴏᴍᴩʟᴇᴛᴇᴅ: \nCᴏᴍᴩʟᴇᴛᴇᴅ Iɴ `{completed_in}`.\n\nTotal Users {total_users}\nCompleted: {done} / {total_users}\nSuccess: {success}\nFailed: {failed}")
           
async def send_msg(user_id, message):
    try:
        await message.copy(chat_id=int(user_id))
        return 200
    except FloodWait as e:
        await asyncio.sleep(e.value)
        return send_msg(user_id, message)
    except InputUserDeactivated:
        logger.info(f"{user_id} : Deactivated")
        return 400
    except UserIsBlocked:
        logger.info(f"{user_id} : Blocked The Bot")
        return 400
    except PeerIdInvalid:
        logger.info(f"{user_id} : User ID Invalid")
        return 400
    except Exception as e:
        logger.error(f"{user_id} : {e}")
        return 500

# ========== BAN COMMANDS FOR ADMINS ==========

@Client.on_message(filters.private & filters.command("ban") & filters.user(Config.ADMIN))
async def ban_user_command(bot: Client, message: Message):
    try:
        # Check if command has user ID
        if len(message.command) < 2:
            await message.reply_text(
                "**Usage:** `/ban <user_id> [reason]`\n\n"
                "**Example:** `/ban 123456789 Spamming the bot`\n"
                "**Example:** `/ban 123456789` (no reason)"
            )
            return
        
        user_id = int(message.command[1])
        ban_reason = " ".join(message.command[2:]) if len(message.command) > 2 else "No reason provided"
        
        # Don't allow admins to ban themselves or other admins
        if user_id in Config.ADMIN:
            await message.reply_text("❌ You cannot ban another admin!")
            return
        
        # Check if user exists in database
        if not await codeflixbots.is_user_exist(user_id):
            await message.reply_text(f"⚠️ User with ID `{user_id}` not found in database.\n\nThey will still be blocked if they try to use the bot.")
        
        # Check if user is already banned
        is_banned = await codeflixbots.is_banned(user_id)
        if is_banned:
            await message.reply_text(f"⚠️ User `{user_id}` is already banned.")
            return
        
        # Ban the user
        success = await codeflixbots.ban_user(user_id, ban_reason)
        
        if success:
            # Try to notify the user
            try:
                await bot.send_message(
                    chat_id=user_id,
                    text=f"🚫 **You have been banned from using this bot.**\n\n"
                         f"**Reason:** {ban_reason}\n\n"
                         "If you believe this is a mistake, contact @Anime_Library_N4"
                )
            except Exception as e:
                logger.info(f"Could not notify banned user {user_id}: {e}")
            
            # Log to admin channel
            await bot.send_message(
                Config.LOG_CHANNEL,
                f"🚨 **User Banned**\n\n"
                f"👤 User ID: `{user_id}`\n"
                f"📝 Reason: {ban_reason}\n"
                f"🛡️ Banned by: {message.from_user.mention}\n"
                f"🆔 Admin ID: `{message.from_user.id}`"
            )
            
            await message.reply_text(
                f"✅ **Successfully banned user** `{user_id}`\n\n"
                f"**Reason:** {ban_reason}"
            )
        else:
            await message.reply_text(f"❌ Failed to ban user `{user_id}`.")
            
    except ValueError:
        await message.reply_text("❌ Invalid user ID. Please provide a numeric ID.")
    except Exception as e:
        logger.error(f"Error in ban command: {e}")
        await message.reply_text(f"❌ Error: {str(e)}")

@Client.on_message(filters.private & filters.command("unban") & filters.user(Config.ADMIN))
async def unban_user_command(bot: Client, message: Message):
    try:
        # Check if command has user ID
        if len(message.command) < 2:
            await message.reply_text(
                "**Usage:** `/unban <user_id>`\n\n"
                "**Example:** `/unban 123456789`"
            )
            return
        
        user_id = int(message.command[1])
        
        # Check if user is actually banned
        is_banned = await codeflixbots.is_banned(user_id)
        if not is_banned:
            await message.reply_text(f"ℹ️ User `{user_id}` is not currently banned.")
            return
        
        # Unban the user
        success = await codeflixbots.unban_user(user_id)
        
        if success:
            # Try to notify the user
            try:
                await bot.send_message(
                    chat_id=user_id,
                    text="✅ **Your ban has been lifted!**\n\n"
                         "You can now use the bot again."
                )
            except Exception as e:
                logger.info(f"Could not notify unbanned user {user_id}: {e}")
            
            # Log to admin channel
            await bot.send_message(
                Config.LOG_CHANNEL,
                f"✅ **User Unbanned**\n\n"
                f"👤 User ID: `{user_id}`\n"
                f"🛡️ Unbanned by: {message.from_user.mention}\n"
                f"🆔 Admin ID: `{message.from_user.id}`"
            )
            
            await message.reply_text(f"✅ **Successfully unbanned user** `{user_id}`")
        else:
            await message.reply_text(f"❌ Failed to unban user `{user_id}`.")
            
    except ValueError:
        await message.reply_text("❌ Invalid user ID. Please provide a numeric ID.")
    except Exception as e:
        logger.error(f"Error in unban command: {e}")
        await message.reply_text(f"❌ Error: {str(e)}")

@Client.on_message(filters.private & filters.command("baninfo") & filters.user(Config.ADMIN))
async def ban_info_command(bot: Client, message: Message):
    try:
        if len(message.command) < 2:
            await message.reply_text(
                "**Usage:** `/baninfo <user_id>`\n\n"
                "**Example:** `/baninfo 123456789`"
            )
            return
        
        user_id = int(message.command[1])
        ban_info = await codeflixbots.get_ban_info(user_id)
        
        if ban_info:
            banned_on = ban_info.get("banned_on", "Unknown date")
            ban_reason = ban_info.get("ban_reason", "No reason provided")
            
            # Try to get user info
            try:
                user_info = await bot.get_users(user_id)
                user_name = user_info.first_name
                user_username = f"@{user_info.username}" if user_info.username else "No username"
            except:
                user_name = "Unknown"
                user_username = "Unknown"
            
            response = (
                f"🚫 **Ban Information**\n\n"
                f"👤 **User:** {user_name}\n"
                f"🆔 **User ID:** `{user_id}`\n"
                f"📛 **Username:** {user_username}\n\n"
                f"📅 **Banned On:** {banned_on}\n"
                f"📝 **Reason:** {ban_reason}\n"
            )
            
            if ban_info.get("ban_duration", 0) == 0:
                response += f"⏰ **Duration:** Permanent"
            else:
                response += f"⏰ **Duration:** {ban_info.get('ban_duration')} days"
        else:
            # User is not banned, show basic info
            try:
                user_info = await bot.get_users(user_id)
                user_name = user_info.first_name
                user_username = f"@{user_info.username}" if user_info.username else "No username"
            except:
                user_name = "Unknown"
                user_username = "Unknown"
            
            response = (
                f"✅ **User is NOT banned**\n\n"
                f"👤 **User:** {user_name}\n"
                f"🆔 **User ID:** `{user_id}`\n"
                f"📛 **Username:** {user_username}"
            )
        
        await message.reply_text(response)
        
    except ValueError:
        await message.reply_text("❌ Invalid user ID. Please provide a numeric ID.")
    except Exception as e:
        logger.error(f"Error in baninfo command: {e}")
        await message.reply_text(f"❌ Error: {str(e)}")

@Client.on_message(filters.private & filters.command("banned") & filters.user(Config.ADMIN))
async def list_banned_users(bot: Client, message: Message):
    """List all banned users"""
    try:
        all_users = await codeflixbots.get_all_users()
        banned_users = []
        
        async for user in all_users:
            if user.get("ban_status", {}).get("is_banned", False):
                banned_users.append(user)
        
        if not banned_users:
            await message.reply_text("✅ No users are currently banned.")
            return
        
        response = f"🚫 **Banned Users ({len(banned_users)})**\n\n"
        
        for i, user in enumerate(banned_users[:20]):  # Show first 20 only
            user_id = user["_id"]
            ban_reason = user.get("ban_status", {}).get("ban_reason", "No reason")
            banned_on = user.get("ban_status", {}).get("banned_on", "Unknown")
            
            response += f"{i+1}. `{user_id}` - {ban_reason} ({banned_on})\n"
        
        if len(banned_users) > 20:
            response += f"\n... and {len(banned_users) - 20} more banned users."
        
        await message.reply_text(response)
        
    except Exception as e:
        logger.error(f"Error listing banned users: {e}")
        await message.reply_text(f"❌ Error: {str(e)}")
