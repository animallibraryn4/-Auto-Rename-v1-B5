# Replace the force_subs.py file with this updated version
import os
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from pyrogram.errors import UserNotParticipant
from config import Config
from helper.database import codeflixbots

FORCE_SUB_CHANNELS = Config.FORCE_SUB_CHANNELS
IMAGE_URL = "https://graph.org/file/a27d85469761da836337c.jpg"

async def not_subscribed(_, __, message):
    # Check if user is banned first
    if await codeflixbots.is_user_banned(message.from_user.id):
        return False  # Don't check subscription if banned
    
    for channel in FORCE_SUB_CHANNELS:
        try:
            user = await message._client.get_chat_member(channel, message.from_user.id)
            if user.status in {"kicked", "left"}:
                return True
        except UserNotParticipant:
            return True
    return False

@Client.on_message(filters.private & filters.create(not_subscribed))
async def forces_sub(client, message):
    # Check if user is banned
    if await codeflixbots.is_user_banned(message.from_user.id):
        await message.reply_text(
            "🚫 **You are banned and cannot use this bot.**\n\n"
            "If you want access, request permission from @Anime_Library_N4."
        )
        return
    
    not_joined_channels = []
    for channel in FORCE_SUB_CHANNELS:
        try:
            user = await client.get_chat_member(channel, message.from_user.id)
            if user.status in {"kicked", "left"}:
                not_joined_channels.append(channel)
        except UserNotParticipant:
            not_joined_channels.append(channel)

    buttons = [
        [
            InlineKeyboardButton(
                text=f"Join {channel.capitalize()}", url=f"https://t.me/{channel}"
            )
        ]
        for channel in not_joined_channels
    ]
    buttons.append(
        [
            InlineKeyboardButton(
                text="I have joined", callback_data="check_subscription"
            )
        ]
    )

    text = "** ЩбіАбіЛбіЛбіА!!,  ПбіПбіЬ' АбіЗ …ібіПбіЫ біКбіП…™…ібіЗбіЕ біЫбіП біА Я Я  АбіЗ«ЂбіЬ…™ АбіЗбіЕ біД ЬбіА…і…ібіЗ Яs, біКбіП…™…і біЫ ЬбіЗ біЬбіШбіЕбіАбіЫбіЗ біД ЬбіА…і…ібіЗ Яs біЫбіП біДбіП…ібіЫ…™…ібіЬбіЗ**"
    await message.reply_photo(
        photo=IMAGE_URL,
        caption=text,
        reply_markup=InlineKeyboardMarkup(buttons)
    )

@Client.on_callback_query(filters.regex("check_subscription"))
async def check_subscription(client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    
    # Check if user is banned
    if await codeflixbots.is_user_banned(user_id):
        await callback_query.answer("🚫 You are banned from using this bot.", show_alert=True)
        return
    
    not_joined_channels = []

    for channel in FORCE_SUB_CHANNELS:
        try:
            user = await client.get_chat_member(channel, user_id)
            if user.status in {"kicked", "left"}:
                not_joined_channels.append(channel)
        except UserNotParticipant:
            not_joined_channels.append(channel)

    if not not_joined_channels:
        new_text = "** ПбіПбіЬ  ЬбіАбі†біЗ біКбіП…™…ібіЗбіЕ біА Я Я біЫ ЬбіЗ  АбіЗ«ЂбіЬ…™ АбіЗбіЕ біД ЬбіА…і…ібіЗ Яs. біЫ ЬбіА…ібіЛ  ПбіПбіЬ! рЯШК /start …ібіПбі°**"
        if callback_query.message.caption != new_text:
            await callback_query.message.edit_caption(
                caption=new_text,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("вАҐ …ібіПбі° біД Я…™біДбіЛ  ЬбіЗ АбіЗ вАҐ", callback_data='help')]
                ])
            )
    else:
        buttons = [
            [
                InlineKeyboardButton(
                    text=f"Join {channel.capitalize()}",
                    url=f"https://t.me/{channel}",
                )
            ]
            for channel in not_joined_channels
        ]
        buttons.append(
            [
                InlineKeyboardButton(
                    text="I have joined", callback_data="check_subscription"
                )
            ]
        )

        text = "** ПбіПбіЬ  ЬбіАбі†біЗ біКбіП…™…ібіЗбіЕ біА Я Я біЫ ЬбіЗ  АбіЗ«ЂбіЬ…™ АбіЗбіЕ біД ЬбіА…і…ібіЗ Яs. біШ ЯбіЗбіАsбіЗ біКбіП…™…і біЫ ЬбіЗ біЬбіШбіЕбіАбіЫбіЗ біД ЬбіА…і…ібіЗ Яs біЫбіП біДбіП…ібіЫ…™…ібіЬбіЗ**"
        if callback_query.message.caption != text:
            await callback_query.message.edit_caption(
                caption=text,
                reply_markup=InlineKeyboardMarkup(buttons)
            )
