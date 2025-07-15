from config import Config, Txt
from helper.database import codeflixbots
from pyrogram.types import Message
from pyrogram import Client, filters
from pyrogram.errors import FloodWait, InputUserDeactivated, UserIsBlocked, PeerIdInvalid, ChatAdminRequired, ChannelPrivate, MessageIdInvalid
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

@Client.on_message(filters.private & filters.command("link") & filters.user(Config.ADMIN))
async def get_channel_post_link(client, message):
    # Check if the message is a reply to a forwarded channel post
    if not message.reply_to_message or not message.reply_to_message.forward_from_chat:
        return await message.reply_text("Please reply to a forwarded message from a channel where I'm admin.")
    
    try:
        # Get the original channel and message ID
        channel = message.reply_to_message.forward_from_chat
        message_id = message.reply_to_message.forward_from_message_id
        
        # Check if bot is admin in the channel
        chat_member = await client.get_chat_member(channel.id, "me")
        if chat_member.status not in ["administrator", "creator"]:
            return await message.reply_text("I'm not an admin in this channel.")
        
        # Get the original message
        original_msg = await client.get_messages(channel.id, message_id)
        
        # Create new buttons (modify as needed)
        new_buttons = [
            [InlineKeyboardButton("Join Channel", url=f"https://t.me/{channel.username}")],
            [InlineKeyboardButton("Download Now", url=f"https://t.me/{Config.BOT_USERNAME}?start=download_{message_id}")]
        ]
        
        # Create the message text with link
        msg_text = f"🔗 **Post Link:** https://t.me/{channel.username}/{message_id}\n\n"
        if original_msg.caption:
            msg_text += original_msg.caption
        elif original_msg.text:
            msg_text += original_msg.text
            
        # Send the modified message
        await message.reply_text(
            msg_text,
            reply_markup=InlineKeyboardMarkup(new_buttons),
            disable_web_page_preview=True
        )
        
    except ChatAdminRequired:
        await message.reply_text("I don't have admin rights in that channel.")
    except ChannelPrivate:
        await message.reply_text("I can't access that private channel.")
    except MessageIdInvalid:
        await message.reply_text("Invalid message ID. Maybe the message was deleted.")
    except Exception as e:
        await message.reply_text(f"An error occurred: {str(e)}")
