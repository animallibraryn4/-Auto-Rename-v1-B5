from plugins import validate_token 
import random
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery

from helper.database import codeflixbots
from config import *
from config import Config

# --- NEW: Token Validation Placeholder ---
async def check_token_is_valid(token):
    """
    REPLACE THIS WITH YOUR ACTUAL TOKEN CHECK LOGIC!
    e.g., check an external token list, a database, or a simple hardcoded token.
    """
    # Example placeholder logic:
    return token.upper() == "PREMIUM123" 
# ----------------------------------------

# Start Command Handler
@Client.on_message(filters.private & filters.command("start"))
async def start(client, message: Message):
    user = message.from_user
    await codeflixbots.add_user(client, message)

    # Initial interactive text and sticker sequence
    m = await message.reply_text("ᴏɴᴇᴇ-ᴄʜᴀɴ!, ʜᴏᴡ ᴀʀᴇ ʏᴏᴜ \nᴡᴀɪᴛ ᴀ ᴍᴏᴍᴇɴᴛ. . .")
    await asyncio.sleep(0.4)
    await m.edit_text("🎊")
    await asyncio.sleep(0.5)
    await m.edit_text("⚡")
    await asyncio.sleep(0.5)
    await m.edit_text("ꜱᴛᴀʀᴛɪɴɢ...")
    await asyncio.sleep(0.4)
    await m.delete()

    # Send sticker after the text sequence
    await message.reply_sticker("CAACAgUAAxkBAAECroBmQKMAAQ-Gw4nibWoj_pJou2vP1a4AAlQIAAIzDxlVkNBkTEb1Lc4eBA")

    # Define buttons for the start message
    buttons = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("ᴍʏ ᴀʟʟ ᴄᴏᴍᴍᴀɴᴅs", callback_data='help')
        ],
        [
            InlineKeyboardButton('ᴜᴘᴅᴀᴛᴇs', url='https://t.me/Animelibraryn4')
        ],
        [
            InlineKeyboardButton('ᴀʙᴏᴜᴛ', callback_data='about'),
            InlineKeyboardButton('sᴏᴜʀᴄᴇ', callback_data='source')
        ]
    ])

    # Send start message with or without picture
    if Config.START_PIC:
        await message.reply_photo(
            Config.START_PIC,
            caption=Txt.START_TXT.format(user.mention),
            reply_markup=buttons
        )
    else:
        await message.reply_text(
            text=Txt.START_TXT.format(user.mention),
            reply_markup=buttons,
            disable_web_page_preview=True
        )


# Callback Query Handler
@Client.on_callback_query()
async def cb_handler(client, query: CallbackQuery):
    data = query.data
    user_id = query.from_user.id

    print(f"Callback data received: {data}")  # Debugging line

    if data == "home":
        await query.message.edit_text(
            text=Txt.START_TXT.format(query.from_user.mention),
            disable_web_page_preview=True,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("ᴍʏ ᴀʟʟ ᴄᴏᴍᴍᴀɴᴅs", callback_data='help')],
                [InlineKeyboardButton('ᴜᴘᴅᴀᴛᴇs', url='https://t.me/Animelibraryn4')],
                [InlineKeyboardButton('ᴀʙᴏᴜᴛ', callback_data='about'), InlineKeyboardButton('sᴏᴜʀᴄᴇ', callback_data='source')]
            ])
        )
    elif data == "caption":
        await query.message.edit_text(
            text=Txt.CAPTION_TXT,
            disable_web_page_preview=True,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("ʙᴀᴄᴋ", callback_data="help")]
            ])
        )
    elif data == "help":
        # Await get_me to get the bot's user object
        bot = await client.get_me()
        mention = bot.mention
        
        await query.message.edit_text(
            text=Txt.HELP_TXT.format(mention=mention),
            disable_web_page_preview=True,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("ᴀᴜᴛᴏ ʀᴇɴᴀᴍᴇ ғᴏʀᴍᴀᴛ •", callback_data='file_names')],
                [InlineKeyboardButton('ᴛʜᴜᴍʙɴᴀɪʟ', callback_data='thumbnail'), InlineKeyboardButton('ᴄᴀᴘᴛɪᴏɴ', callback_data='caption')],
                [InlineKeyboardButton('ᴍᴇᴛᴀᴅᴀᴛᴀ', callback_data='metadata_help'), InlineKeyboardButton('ᴄʟᴏꜱᴇ', callback_data='close_data')]
            ])
        )
    elif data == "about":
        await query.message.edit_text(
            text=Txt.ABOUT_TXT.format(client.mention),
            disable_web_page_preview=True,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("ʙᴀᴄᴋ", callback_data="home")]
            ])
        )
    elif data == "source":
        await query.message.edit_text(
            text=Txt.SOURCE_TXT,
            disable_web_page_preview=True,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("ʙᴀᴄᴋ", callback_data="home")]
            ])
        )
    elif data == "thumbnail":
        await query.message.edit_text(
            text=Txt.THUMBNAIL_TXT,
            disable_web_page_preview=True,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("ʙᴀᴄᴋ", callback_data="help")]
            ])
        )
    elif data == "file_names":
        await query.message.edit_text(
            text=Txt.FILE_NAME_TXT,
            disable_web_page_preview=True,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("ʙᴀᴄᴋ", callback_data="help")]
            ])
        )
    elif data == "metadata_help":
        await query.message.edit_text(
            text=Txt.SEND_METADATA,
            disable_web_page_preview=True,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("ʙᴀᴄᴋ", callback_data="help")]
            ])
        )
    elif data == "check_subscription":
        await validate_token(client, query)

    elif data == "close_data":
        try:
            await query.message.delete()
            await query.message.reply_to_message.delete()
        except:
            await query.message.delete()

# --- NEW: Token Handling for Trial Users ---
@Client.on_message(filters.private & filters.text & ~filters.command)
async def handle_text_message(client, message: Message):
    user_id = message.from_user.id
    
    # Check if user is waiting for token (trial finished)
    if not await codeflixbots.check_trial_available(user_id):
        token = message.text.strip()
        
        # Check if the token is valid
        token_is_valid = await check_token_is_valid(token)
        
        if token_is_valid:
            # Mark as premium
            await codeflixbots.set_user_premium(user_id)
            await message.reply_text(
                "✅ **Token Verified!**\n"
                "You now have unlimited access. You can now send files for renaming."
            )
        else:
            await message.reply_text(
                "❌ Invalid token. Please try again."
            )

# --- NEW: Usage Check Command ---
@Client.on_message(filters.command("myusage") & filters.private)
async def check_usage(client, message: Message):
    user_id = message.from_user.id
    
    # Retrieve user data from MongoDB
    user_data = await codeflixbots.col.find_one({"_id": int(user_id)})
    
    if user_data:
        trial_used = user_data.get('trial_used', 0)
        is_premium = user_data.get('is_premium', False)
        
        if is_premium:
            status = "✅ **Premium User** (Unlimited access)"
        else:
            remaining = 10 - trial_used
            if remaining < 0: remaining = 0 # Safety check
            status = (
                f"🆓 **Trial User**\n"
                f"**Used:** `{trial_used}`/10\n"
                f"**Remaining:** `{remaining}`\n\n"
                "Buy a token for unlimited access!"
            )
        
        await message.reply_text(f"**🌟 Your Account Status**\n\n{status}")
    else:
        # This should rarely happen as user is added on /start
        await message.reply_text("You haven't started the bot yet. Type /start.")

# ... (Rest of the start_&_cb.py content, like /bought, /help)
@Client.on_message(filters.private & filters.command("bought"))
async def bought_handler(client, message):
    if len(message.command) == 1:
        return await message.reply_text("<b>Reply to a screenshot with the /bought command</b>")
    
    replied = message.reply_to_message
    if not replied or not (replied.photo or replied.document):
        return await message.reply_text("<b>Reply to a screenshot with the /bought command</b>")
        
    LOG_CHANNEL = Config.LOG_CHANNEL
    
    if replied.photo:
        await client.send_photo(
            chat_id=LOG_CHANNEL,
            photo=replied.photo.file_id,
            caption=f'<b>User - {message.from_user.mention}\nUser id - <code>{message.from_user.id}</code>\nUsername - <code>{message.from_user.username}</code>\nName - <code>{message.from_user.first_name}</code></b>',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Close", callback_data="close_data")]
            ])
        )
        await message.reply_text('<b>Your screenshot has been sent to Admins</b>')
    elif replied.document:
        await client.send_document(
            chat_id=LOG_CHANNEL,
            document=replied.document.file_id,
            caption=f'<b>User - {message.from_user.mention}\nUser id - <code>{message.from_user.id}</code>\nUsername - <code>{message.from_user.username}</code>\nName - <code>{message.from_user.first_name}</code></b>',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Close", callback_data="close_data")]
            ])
        )
        await message.reply_text('<b>Your screenshot has been sent to Admins</b>')


@Client.on_message(filters.private & filters.command("help"))
async def help_command(client, message):
    # Await get_me to get the bot's user object
    bot = await client.get_me()
    mention = bot.mention

    # Send the help message with inline buttons
    await message.reply_text(
        text=Txt.HELP_TXT.format(mention=mention),
        disable_web_page_preview=True,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("ᴀᴜᴛᴏ ʀᴇɴᴀᴍᴇ ғᴏʀᴍᴀᴛ •", callback_data='file_names')],
            [InlineKeyboardButton('ᴛʜᴜᴍʙɴᴀɪʟ', callback_data='thumbnail'), InlineKeyboardButton('ᴄᴀᴘᴛɪᴏɴ', callback_data='caption')],
            [InlineKeyboardButton('ᴍᴇᴛᴀᴅᴀᴛᴀ', callback_data='metadata_help'), InlineKeyboardButton('ᴄʟᴏꜱᴇ', callback_data='close_data')]
        ])
        )
    
