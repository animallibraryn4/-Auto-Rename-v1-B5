from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# SAFE LOAD: Import ADMIN using try-except to avoid import error
try:
    from config import ADMIN
except:
    ADMIN = ["5380609667"]  # fallback or placeholder if import fails

# 🔐 Filter for allowed admins
def is_admin():
    return filters.user(ADMIN)

# 🧠 Memory per admin
user_data = {}

@Client.on_message(filters.command("postlink") & is_admin())
async def postlink_handler(client, message):
    if len(message.command) != 2:
        return await message.reply("❌ Use: `/postlink https://t.me/channel/1234`")

    try:
        link = message.command[1]
        parts = link.split("/")
        if "t.me" not in link or len(parts) < 5:
            return await message.reply("⚠️ Invalid link format!")

        chat_username = parts[3]
        message_id = int(parts[4])
        user_id = message.from_user.id

        user_data[user_id] = {
            "chat": chat_username,
            "message_id": message_id
        }

        await message.reply("✅ Post link saved. Now send `/oldlink <old_url>`")

    except Exception as e:
        await message.reply(f"❌ Error: `{e}`")


@Client.on_message(filters.command("oldlink") & is_admin())
async def oldlink_handler(client, message):
    if len(message.command) != 2:
        return await message.reply("❌ Use: `/oldlink https://old.com`")

    user_id = message.from_user.id
    if user_id not in user_data or "message_id" not in user_data[user_id]:
        return await message.reply("⚠️ First send `/postlink`")

    user_data[user_id]["old_link"] = message.command[1]
    await message.reply("✅ Old link saved. Now send `/newlink <new_url>`")


@Client.on_message(filters.command("newlink") & is_admin())
async def newlink_handler(client, message):
    if len(message.command) != 2:
        return await message.reply("❌ Use: `/newlink https://new.com`")

    user_id = message.from_user.id
    if user_id not in user_data or "old_link" not in user_data[user_id]:
        return await message.reply("⚠️ First send `/oldlink`")

    new_link = message.command[1]
    chat = user_data[user_id]["chat"]
    message_id = user_data[user_id]["message_id"]
    old_link = user_data[user_id]["old_link"]

    try:
        msg = await client.get_messages(chat_id=chat, message_ids=message_id)
        keyboard = msg.reply_markup.inline_keyboard
        new_keyboard = []

        for row in keyboard:
            new_row = []
            for button in row:
                if button.url and old_link in button.url:
                    new_row.append(InlineKeyboardButton(button.text, url=button.url.replace(old_link, new_link)))
                else:
                    new_row.append(button)
            new_keyboard.append(new_row)

        await client.edit_message_reply_markup(
            chat_id=chat,
            message_id=message_id,
            reply_markup=InlineKeyboardMarkup(new_keyboard)
        )

        await message.reply("✅ Link replaced successfully!")
        user_data.pop(user_id)

    except Exception as e:
        await message.reply(f"❌ Error: `{e}`")
