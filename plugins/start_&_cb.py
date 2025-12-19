from plugins import validate_token
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery

from helper.database import codeflixbots
from config import *
from config import Config


# =========================
# START COMMAND (NO VERIFY)
# =========================
@Client.on_message(filters.private & filters.command("start"))
async def start(client, message: Message):

    # Handle verification link like /start verify-xxxx
    if hasattr(message, "command") and len(message.command) == 2:
        data = message.command[1]
        if data.split("-")[0] == "verify":
            await validate_token(client, message, data)
            return

    user = message.from_user
    await codeflixbots.add_user(client, message)

    # Welcome animation
    m = await message.reply_text("ᴏɴᴇᴇ-ᴄʜᴀɴ!, ʜᴏᴡ ᴀʀᴇ ʏᴏᴜ\nᴡᴀɪᴛ ᴀ ᴍᴏᴍᴇɴᴛ...")
    await asyncio.sleep(0.4)
    await m.edit_text("🎊")
    await asyncio.sleep(0.5)
    await m.edit_text("⚡")
    await asyncio.sleep(0.5)
    await m.edit_text("ꜱᴛᴀʀᴛɪɴɢ...")
    await asyncio.sleep(0.4)
    await m.delete()

    await message.reply_sticker(
        "CAACAgUAAxkBAAECroBmQKMAAQ-Gw4nibWoj_pJou2vP1a4AAlQIAAIzDxlVkNBkTEb1Lc4eBA"
    )

    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("ᴍʏ ᴀʟʟ ᴄᴏᴍᴍᴀɴᴅs", callback_data="help")],
        [InlineKeyboardButton("ᴜᴘᴅᴀᴛᴇs", url="https://t.me/Animelibraryn4")],
        [
            InlineKeyboardButton("ᴀʙᴏᴜᴛ", callback_data="about"),
            InlineKeyboardButton("sᴏᴜʀᴄᴇ", callback_data="source")
        ]
    ])

    if Config.START_PIC:
        await message.reply_photo(
            Config.START_PIC,
            caption=Txt.START_TXT.format(user.mention),
            reply_markup=buttons
        )
    else:
        await message.reply_text(
            Txt.START_TXT.format(user.mention),
            reply_markup=buttons,
            disable_web_page_preview=True
        )


# =========================
# CALLBACK HANDLER
# =========================
@Client.on_callback_query()
async def cb_handler(client, query: CallbackQuery):
    data = query.data
    user_id = query.from_user.id

    if data == "home":
        await query.message.edit_text(
            Txt.START_TXT.format(query.from_user.mention),
            disable_web_page_preview=True,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("ᴍʏ ᴀʟʟ ᴄᴏᴍᴍᴀɴᴅs", callback_data="help")],
                [InlineKeyboardButton("ᴜᴘᴅᴀᴛᴇs", url="https://t.me/Animelibraryn4")],
                [
                    InlineKeyboardButton("ᴀʙᴏᴜᴛ", callback_data="about"),
                    InlineKeyboardButton("sᴏᴜʀᴄᴇ", callback_data="source")
                ]
            ])
        )

    elif data == "help":
        await query.message.edit_text(
            Txt.HELP_TXT.format(client.mention),
            disable_web_page_preview=True,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("ᴀᴜᴛᴏ ʀᴇɴᴀᴍᴇ ғᴏʀᴍᴀᴛ", callback_data="file_names")],
                [
                    InlineKeyboardButton("ᴛʜᴜᴍʙɴᴀɪʟ", callback_data="thumbnail"),
                    InlineKeyboardButton("ᴄᴀᴘᴛɪᴏɴ", callback_data="caption")
                ],
                [
                    InlineKeyboardButton("ᴍᴇᴛᴀᴅᴀᴛᴀ", callback_data="meta"),
                    InlineKeyboardButton("ᴅᴏɴᴀᴛᴇ", callback_data="donate")
                ],
                [InlineKeyboardButton("ʜᴏᴍᴇ", callback_data="home")]
            ])
        )

    elif data == "file_names":
        fmt = await codeflixbots.get_format_template(user_id)
        await query.message.edit_text(
            Txt.FILE_NAME_TXT.format(format_template=fmt),
            disable_web_page_preview=True,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("ʙᴀᴄᴋ", callback_data="help")]
            ])
        )

    elif data == "about":
        await query.message.edit_text(
            Txt.ABOUT_TXT,
            disable_web_page_preview=True,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("ʙᴀᴄᴋ", callback_data="home")]
            ])
        )

    elif data == "source":
        await query.message.edit_text(
            Txt.SOURCE_TXT,
            disable_web_page_preview=True,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("ʙᴀᴄᴋ", callback_data="home")]
            ])
        )

    elif data == "close":
        await query.message.delete()


# =========================
# HELP COMMAND
# =========================
@Client.on_message(filters.private & filters.command("help"))
async def help_command(client, message):
    bot = await client.get_me()
    await message.reply_text(
        Txt.HELP_TXT.format(bot.mention),
        disable_web_page_preview=True
    )
