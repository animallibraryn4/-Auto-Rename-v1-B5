import random
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery

from helper.database import codeflixbots
from config import *
from config import Config
from helper.ban_filter import is_not_banned_filter # <-- NEW IMPORT

# Start Command Handler
@Client.on_message(filters.private & filters.command("start") & is_not_banned_filter) # <-- MODIFIED
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
            InlineKeyboardButton('ᴜᴘᴅᴀᴛᴇs', url='https://t.me/animelibraryn4'),
            InlineKeyboardButton('sᴜᴘᴘᴏʀᴛ', url='https://t.me/Anime_Library_N4_Support')
        ]
    ])

    # Final start message with buttons
    await message.reply_text(
        Txt.START_TXT.format(
            user=user.mention, 
            bot_mention=client.mention
        ),
        reply_markup=buttons,
        disable_web_page_preview=True
    )

# Callback Query Handler
@Client.on_callback_query()
async def cb_handler(client, query: CallbackQuery):
    data = query.data
    user_id = query.from_user.id
    message = query.message
    
    # Callback queries are generally safe from the ban filter as they follow a message.

    if data == "start":
        # Delete the previous message and send the start message again
        await message.delete()
        user = query.from_user
        buttons = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("ᴍʏ ᴀʟʟ ᴄᴏᴍᴍᴀɴᴅs", callback_data='help')
            ],
            [
                InlineKeyboardButton('ᴜᴘᴅᴀᴛᴇs', url='https://t.me/animelibraryn4'),
                InlineKeyboardButton('sᴜᴘᴘᴏʀᴛ', url='https://t.me/Anime_Library_N4_Support')
            ]
        ])
        await query.message.reply_text(
            Txt.START_TXT.format(
                user=user.mention, 
                bot_mention=client.mention
            ),
            reply_markup=buttons,
            disable_web_page_preview=True
        )

    elif data == "help":
        # Delete the previous message and send the help message
        await message.delete()
        bot = await client.get_me()
        mention = bot.mention
        await query.message.reply_text(
            text=Txt.HELP_TXT.format(mention=mention),
            disable_web_page_preview=True,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("ᴀᴜᴛᴏ ʀᴇɴᴀᴍᴇ ғᴏʀᴍᴀᴛ •", callback_data='file_names')],
                [InlineKeyboardButton('ᴛʜᴜᴍʙɴᴀɪʟ', callback_data='thumbnail'), InlineKeyboardButton('ᴄᴀᴘᴛɪᴏɴ', callback_data='caption')],
                [InlineKeyboardButton('ᴍᴇᴛᴀᴅᴀᴛᴀ', callback_data='metadata'), InlineKeyboardButton('sᴏᴜʀᴄᴇ', callback_data='source')],
                [InlineKeyboardButton("⚡ ᴄʟᴏsᴇ", callback_data="close_data"), InlineKeyboardButton("⬅️ ʙᴀᴄᴋ", callback_data="start")]
            ])
        )

    elif data == "file_names":
        # Send file name help text
        format_template = await codeflixbots.get_format_template(user_id)
        await query.message.edit_text(
            text=Txt.FILE_NAME_TXT.format(format_template=format_template),
            disable_web_page_preview=True,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ ʙᴀᴄᴋ", callback_data="help")]
            ])
        )

    elif data == "metadata":
        # Send metadata help text
        await query.message.edit_text(
            text=Txt.SEND_METADATA,
            disable_web_page_preview=True,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ ʙᴀᴄᴋ", callback_data="help")]
            ])
        )

    elif data == "caption":
        # Send caption help text
        caption = await codeflixbots.get_caption(user_id)
        await query.message.edit_text(
            text=Txt.CAPTION_TXT.format(caption=caption if caption else 'Not Set'),
            disable_web_page_preview=True,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ ʙᴀᴄᴋ", callback_data="help")]
            ])
        )

    elif data == "thumbnail":
        # Send thumbnail help text
        await query.message.edit_text(
            text=Txt.THUMBNAIL_TXT,
            disable_web_page_preview=True,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ ʙᴀᴄᴋ", callback_data="help")]
            ])
        )

    elif data == "source":
        # Send source info
        await query.message.edit_text(
            text=Txt.SOURCE_TXT,
            disable_web_page_preview=True,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ ʙᴀᴄᴋ", callback_data="help")]
            ])
        )

    elif data == "close_data":
        # Close the message
        await message.delete()


# Bought Command Handler
@Client.on_message(filters.private & filters.command("bought") & is_not_banned_filter) # <-- MODIFIED
async def bought_command(client, message):
    replied = message.reply_to_message
    LOG_CHANNEL = Config.LOG_CHANNEL

    if not replied:
        return await message.reply_text("<b>Reply to your screenshot, then reply to it using the '/bought' command</b>")
    elif replied.photo:
        await client.send_photo(
            chat_id=LOG_CHANNEL,
            photo=replied.photo.file_id,
            caption=f'<b>User - {message.from_user.mention}\nUser id - <code>{message.from_user.id}</code>\nUsername - <code>{message.from_user.username}</code>\nName - <code>{message.from_user.first_name}</code></b>',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Close", callback_data="close_data")]
            ])
        )
        await message.reply_text('<b>Your screenshot has been sent to Admins</b>')


@Client.on_message(filters.private & filters.command("help") & is_not_banned_filter) # <-- MODIFIED
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
            [InlineKeyboardButton('ᴍᴇᴛᴀᴅᴀᴛᴀ', callback_data='metadata'), InlineKeyboardButton('sᴏᴜʀᴄᴇ', callback_data='source')],
            [InlineKeyboardButton("⚡ ᴄʟᴏsᴇ", callback_data="close_data"), InlineKeyboardButton("⬅️ ʙᴀᴄᴋ", callback_data="start")]
        ])
    )
    
