# Replace the admin_panel.py file with this updated version
from config import Config, Txt
from helper.database import codeflixbots
from pyrogram.types import Message
from pyrogram import Client, filters
from pyrogram.errors import FloodWait, InputUserDeactivated, UserIsBlocked, PeerIdInvalid
import os, sys, time, asyncio, logging, datetime
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
# NOTE: Config.ADMIN is already used in the filters below, but keeping this definition
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

# ========== BAN COMMANDS ==========

# Updated decorator (removed filters.user(Config.ADMIN))
@Client.on_message(filters.private & filters.command("ban"))
async def ban_user_command(client: Client, message: Message):
    """Ban a user by their ID"""
    # Inline admin check added
    if message.from_user.id not in Config.ADMIN:
        return
        
    if len(message.command) < 2:
        return await message.reply_text(
            "**Usage:** `/ban <user_id> [duration_in_days] [reason]`\n\n"
            "**Example:** `/ban 123456789 7 Spamming`\n"
            "**Example:** `/ban 123456789` (permanent ban)"
        )
    
    try:
        # Parse command arguments
        args = message.text.split(maxsplit=3)
        user_id = int(args[1])
        ban_duration = int(args[2]) if len(args) > 2 else 0  # 0 = permanent
        ban_reason = args[3] if len(args) > 3 else "No reason provided"
        
        # Check if user exists
        if not await codeflixbots.is_user_exist(user_id):
            return await message.reply_text(f"❌ User with ID `{user_id}` not found in database.")
        
        # Ban the user
        success = await codeflixbots.ban_user(user_id, ban_duration, ban_reason)
        
        if success:
            duration_text = f"for {ban_duration} days" if ban_duration > 0 else "permanently"
            await message.reply_text(
                f"✅ **User Banned Successfully!**\n\n"
                f"**User ID:** `{user_id}`\n"
                f"**Duration:** {duration_text}\n"
                f"**Reason:** {ban_reason}"
            )
            
            # Try to notify the user if possible
            try:
                await client.send_message(
                    user_id,
                    f"🚫 **You have been banned from using this bot.**\n\n"
                    f"**Reason:** {ban_reason}\n"
                    f"**Duration:** {duration_text}\n\n"
                    f"If you believe this is a mistake, contact @Anime_Library_N4"
                )
            except:
                pass
        else:
            await message.reply_text("❌ Failed to ban user. Please check logs.")
            
    except ValueError:
        await message.reply_text("❌ Invalid user ID. Please provide a numeric user ID.")
    except Exception as e:
        logger.error(f"Error in ban command: {e}")
        await message.reply_text(f"❌ An error occurred: {str(e)}")

# Updated decorator (removed filters.user(Config.ADMIN))
@Client.on_message(filters.private & filters.command("unban"))
async def unban_user_command(client: Client, message: Message):
    """Unban a user by their ID"""
    # Inline admin check added
    if message.from_user.id not in Config.ADMIN:
        return
        
    if len(message.command) < 2:
        return await message.reply_text(
            "**Usage:** `/unban <user_id>`\n\n"
            "**Example:** `/unban 123456789`"
        )
    
    try:
        user_id = int(message.command[1])
        
        # Check if user exists
        if not await codeflixbots.is_user_exist(user_id):
            return await message.reply_text(f"❌ User with ID `{user_id}` not found in database.")
        
        # Check if user is actually banned
        if not await codeflixbots.is_user_banned(user_id):
            return await message.reply_text(f"ℹ️ User `{user_id}` is not currently banned.")
        
        # Unban the user
        success = await codeflixbots.unban_user(user_id)
        
        if success:
            await message.reply_text(
                f"✅ **User Unbanned Successfully!**\n\n"
                f"**User ID:** `{user_id}`\n"
                f"User can now use the bot again."
            )
            
            # Try to notify the user if possible
            try:
                await client.send_message(
                    user_id,
                    "✅ **Your ban has been lifted!**\n\n"
                    "You can now use the bot again. Welcome back!"
                )
            except:
                pass
        else:
            await message.reply_text("❌ Failed to unban user. Please check logs.")
            
    except ValueError:
        await message.reply_text("❌ Invalid user ID. Please provide a numeric user ID.")
    except Exception as e:
        logger.error(f"Error in unban command: {e}")
        await message.reply_text(f"❌ An error occurred: {str(e)}")

# Updated decorator (removed filters.user(Config.ADMIN))
@Client.on_message(filters.private & filters.command("baninfo"))
async def ban_info_command(client: Client, message: Message):
    """Check ban status of a user"""
    # Inline admin check added
    if message.from_user.id not in Config.ADMIN:
        return
        
    if len(message.command) < 2:
        return await message.reply_text(
            "**Usage:** `/baninfo <user_id>`\n\n"
            "**Example:** `/baninfo 123456789`"
        )
    
    try:
        user_id = int(message.command[1])
        
        # Check if user exists
        if not await codeflixbots.is_user_exist(user_id):
            return await message.reply_text(f"❌ User with ID `{user_id}` not found in database.")
        
        user = await codeflixbots.col.find_one({"_id": user_id})
        
        if user and "ban_status" in user:
            ban_info = user["ban_status"]
            is_banned = ban_info.get("is_banned", False)
            
            if is_banned:
                ban_reason = ban_info.get("ban_reason", "No reason provided")
                banned_on = ban_info.get("banned_on", "Unknown")
                ban_duration = ban_info.get("ban_duration", 0)
                
                duration_text = f"{ban_duration} days" if ban_duration > 0 else "Permanent"
                
                response = (
                    f"🚫 **User is Banned**\n\n"
                    f"**User ID:** `{user_id}`\n"
                    f"**Banned On:** {banned_on}\n"
                    f"**Duration:** {duration_text}\n"
                    f"**Reason:** {ban_reason}"
                )
            else:
                response = f"✅ **User is Not Banned**\n\n**User ID:** `{user_id}`"
        else:
            response = f"ℹ️ **No Ban Info Found**\n\n**User ID:** `{user_id}`"
        
        await message.reply_text(response)
        
    except ValueError:
        await message.reply_text("❌ Invalid user ID. Please provide a numeric user ID.")
    except Exception as e:
        logger.error(f"Error in baninfo command: {e}")
        await message.reply_text(f"❌ An error occurred: {str(e)}")
            
