from pyrogram import Client, filters 
from pyrogram.types import Message
from helper.database import codeflixbots
from helper.ban_filter import is_not_banned_filter # <-- NEW IMPORT

@Client.on_message(filters.private & filters.command('set_caption') & is_not_banned_filter) # <-- MODIFIED
async def add_caption(client, message: Message):
    if len(message.command) == 1:
       return await message.reply_text("**Give The Caption\n\nExample :- `/set_caption 📕Name ➠ : {filename} \n\n🔗 Size ➠ : {filesize} \n\n⏰ Duration ➠ : {duration}`**")
    caption = message.text.split(" ", 1)[1]
    await codeflixbots.set_caption(message.from_user.id, caption=caption)
    await message.reply_text("**Your Caption Successfully Added ✅**")

@Client.on_message(filters.private & filters.command('del_caption') & is_not_banned_filter) # <-- MODIFIED
async def delete_caption(client, message: Message):
    caption = await codeflixbots.get_caption(message.from_user.id)  
    if not caption:
       return await message.reply_text("**You Don't Have Any Caption ❌**")
    await codeflixbots.set_caption(message.from_user.id, caption=None)
    await message.reply_text("**Your Caption Successfully Deleted 🗑️**")

@Client.on_message(filters.private & filters.command(['see_caption', 'view_caption']) & is_not_banned_filter) # <-- MODIFIED
async def see_caption(client, message: Message):
    caption = await codeflixbots.get_caption(message.from_user.id)  
    if caption:
       await message.reply_text(f"**Your Caption :**\n\n`{caption}`")
    else:
       await message.reply_text("**You Don't Have Any Caption ❌**")


@Client.on_message(filters.private & filters.command(['view_thumb', 'viewthumb']) & is_not_banned_filter) # <-- MODIFIED
async def viewthumb(client, message: Message):    
    # Get the global thumbnail, as this command is for the general thumb view
    thumb = await codeflixbots.get_global_thumb(message.from_user.id)
    if thumb:
       await client.send_photo(chat_id=message.chat.id, photo=thumb)
    else:
        await message.reply_text("**You Don't Have Any Thumbnail ❌**") 

@Client.on_message(filters.private & filters.command(['del_thumb', 'delthumb']) & is_not_banned_filter) # <-- MODIFIED
async def removethumb(client, message: Message):
    # This command now clears the GLOBAL thumbnail
    await codeflixbots.set_global_thumb(message.from_user.id, file_id=None)
    await message.reply_text("**Global Thumbnail Deleted Successfully 🗑️**")

@Client.on_message(filters.private & filters.photo & is_not_banned_filter) # <-- MODIFIED
async def addthumbs(client, message: Message):
    if message.reply_to_message and message.reply_to_message.forward_date:
        # Ignore forwarded photo if not part of a specific reply flow
        return
        
    # Check if the user is currently in a quality setting flow (this logic is typically in quality_thumb.py callbacks)
    # If not in a specific flow, save the photo as the GLOBAL thumbnail
    
    # Check if a global thumbnail already exists
    current_thumb = await codeflixbots.get_global_thumb(message.from_user.id)
    
    if current_thumb:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("Yes, Replace It", callback_data=f"replace_global_thumb_{message.photo.file_id}")],
            [InlineKeyboardButton("No, Keep Old", callback_data="cancel_thumb_replace")]
        ])
        await message.reply_text(
            "**You already have a Global Thumbnail. Do you want to replace it?**",
            reply_markup=keyboard
        )
    else:
        # Save the new global thumbnail directly
        await codeflixbots.set_global_thumb(message.from_user.id, file_id=message.photo.file_id)
        await message.reply_text("**Global Thumbnail Successfully Added ✅**")

# Handler for thumbnail replacement confirmation (part of the new logic for addthumbs)
@Client.on_callback_query(filters.regex("^replace_global_thumb_"))
async def confirm_thumb_replace(client, callback):
    file_id = callback.data.split("_", 3)[3]
    user_id = callback.from_user.id
    
    await codeflixbots.set_global_thumb(user_id, file_id)
    await callback.message.edit_text("**Global Thumbnail Successfully Replaced ✅**")
    await callback.answer("Global Thumbnail Replaced!")

@Client.on_callback_query(filters.regex("^cancel_thumb_replace"))
async def cancel_thumb_replace(client, callback):
    await callback.message.edit_text("**Replacement Cancelled. Old Global Thumbnail Kept.**")
    await callback.answer("Replacement Cancelled.")
    
