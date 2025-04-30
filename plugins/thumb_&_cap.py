from pyrogram import Client, filters 
from helper.database import codeflixbots

@Client.on_message(filters.private & filters.command('set_caption'))
async def add_caption(client, message):
    if len(message.command) == 1:
       return await message.reply_text("**Give The Caption\n\nExample :- `/set_caption 📕Name ➠ : {filename} \n\n🔗 Size ➠ : {filesize} \n\n⏰ Duration ➠ : {duration}`**")
    caption = message.text.split(" ", 1)[1]
    await codeflixbots.set_caption(message.from_user.id, caption=caption)
    await message.reply_text("**Your Caption Successfully Added ✅**")

@Client.on_message(filters.private & filters.command('del_caption'))
async def delete_caption(client, message):
    caption = await codeflixbots.get_caption(message.from_user.id)  
    if not caption:
       return await message.reply_text("**You Don't Have Any Caption ❌**")
    await codeflixbots.set_caption(message.from_user.id, caption=None)
    await message.reply_text("**Your Caption Successfully Deleted 🗑️**")

@Client.on_message(filters.private & filters.command(['see_caption', 'view_caption']))
async def see_caption(client, message):
    caption = await codeflixbots.get_caption(message.from_user.id)  
    if caption:
       await message.reply_text(f"**Your Caption :**\n\n`{caption}`")
    else:
       await message.reply_text("**You Don't Have Any Caption ❌**")

@Client.on_message(filters.private & filters.command(['view_thumb', 'viewthumb']))
async def viewthumb(client, message):    
    thumb = await codeflixbots.get_thumbnail(message.from_user.id)
    if thumb:
       await client.send_photo(chat_id=message.chat.id, photo=thumb)
    else:
        await message.reply_text("**You Don't Have Any Thumbnail ❌**") 

@Client.on_message(filters.private & filters.command(['del_thumb', 'delthumb']))
async def removethumb(client, message):
    await codeflixbots.set_thumbnail(message.from_user.id, file_id=None)
    await message.reply_text("**Thumbnail Deleted Successfully 🗑️**")

@Client.on_message(filters.private & filters.photo)
async def addthumbs(client, message):
    mkn = await message.reply_text("Please Wait ...")
    await codeflixbots.set_thumbnail(message.from_user.id, file_id=message.photo.file_id)                
    await mkn.edit("**Thumbnail Saved Successfully ✅️**")

# Watermark Commands
@Client.on_message(filters.private & filters.command('set_watermark'))
async def set_watermark(client, message):
    if len(message.command) == 1:
        return await message.reply_text(
            "**Give The Watermark Text\n\n"
            "Example:** `/set_watermark @Animelibraryn4`\n\n"
            "**Note:** This text will appear in the top-left corner of your videos"
        )
    watermark = message.text.split(" ", 1)[1]
    await codeflixbots.set_watermark_text(message.from_user.id, watermark=watermark)
    await message.reply_text("**✅ Watermark Text Successfully Added!**\n\n"
                           "It will appear on all your future video uploads.")

@Client.on_message(filters.private & filters.command('del_watermark'))
async def delete_watermark(client, message):
    watermark = await codeflixbots.get_watermark_text(message.from_user.id)
    if not watermark:
        return await message.reply_text("**You Don't Have Any Watermark Set ❌**")
    await codeflixbots.set_watermark_text(message.from_user.id, watermark=None)
    await message.reply_text("**🗑️ Watermark Successfully Deleted!**\n\n"
                           "It will no longer appear on your videos.")

@Client.on_message(filters.private & filters.command(['see_watermark', 'view_watermark']))
async def view_watermark(client, message):
    watermark = await codeflixbots.get_watermark_text(message.from_user.id)
    if watermark:
        await message.reply_text(
            "**Your Current Watermark:**\n\n"
            f"`{watermark}`\n\n"
            "**Preview Position:** Top-Left Corner\n"
            "**Appearance:** White text with semi-transparent black background",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✏️ Edit Watermark", callback_data="edit_watermark"),
                [InlineKeyboardButton("🗑️ Remove Watermark", callback_data="remove_watermark")]
            ])
        )
    else:
        await message.reply_text(
            "**No Watermark Set ❌**\n\n"
            "Use /set_watermark to add a text watermark to your videos",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ Set Watermark", callback_data="set_watermark")]
            ])
        )

@Client.on_callback_query(filters.regex("^edit_watermark$"))
async def edit_watermark_callback(client, callback_query):
    await callback_query.message.edit_text(
        "✏️ **Edit Your Watermark Text**\n\n"
        "Send me the new watermark text you want to use.\n\n"
        "Example: `@Animelibraryn4`",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back", callback_data="cancel_watermark")]
        ])
    )

@Client.on_callback_query(filters.regex("^remove_watermark$"))
async def remove_watermark_callback(client, callback_query):
    await codeflixbots.set_watermark_text(callback_query.from_user.id, watermark=None)
    await callback_query.message.edit_text(
        "✅ **Watermark Removed Successfully!**\n\n"
        "Your videos will no longer have a watermark.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back", callback_data="cancel_watermark")]
        ])
    )

@Client.on_callback_query(filters.regex("^cancel_watermark$"))
async def cancel_watermark_callback(client, callback_query):
    watermark = await codeflixbots.get_watermark_text(callback_query.from_user.id)
    if watermark:
        await callback_query.message.edit_text(
            f"**Your Current Watermark:**\n\n`{watermark}`",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✏️ Edit", callback_data="edit_watermark"),
                 InlineKeyboardButton("🗑️ Remove", callback_data="remove_watermark")]
            ])
        )
    else:
        await callback_query.message.edit_text(
            "**No Watermark Set**",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ Set Watermark", callback_data="set_watermark")]
            ])
        )
