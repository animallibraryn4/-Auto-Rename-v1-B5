
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# Replace with your Telegram user ID to restrict access (or remove this filter)
ALLOWED_USER_ID = 22299340  # 🔄 Replace this with your user ID

@Client.on_message(filters.command("link") & filters.user(ALLOWED_USER_ID))
async def replace_button(client, message):
    if not message.reply_to_message:
        return await message.reply_text("⚠️ Reply to a message with inline buttons.")

    try:
        parts = message.text.split()
        if len(parts) != 3:
            return await message.reply_text("❌ Use: `/link old_link new_link`", quote=True)

        old_link = parts[1]
        new_link = parts[2]

        keyboard = message.reply_to_message.reply_markup.inline_keyboard
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
            chat_id=message.reply_to_message.chat.id,
            message_id=message.reply_to_message.message_id,
            reply_markup=InlineKeyboardMarkup(new_keyboard)
        )

        await message.reply_text("✅ Button link replaced successfully.")

    except Exception as e:
        await message.reply_text(f"❌ Error: `{e}`", quote=True)
