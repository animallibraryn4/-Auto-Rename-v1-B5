from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from helper.database import codeflixbots

QUALITY_TYPES = ["360p", "480p", "720p", "1080p", "HDrip", "2160p", "4K", "2K", "4kX264", "4kx265"]

async def generate_main_menu_buttons(user_id):
    buttons = []
    for i in range(0, len(QUALITY_TYPES), 3):
        row = QUALITY_TYPES[i:i+3]
        buttons.append([InlineKeyboardButton(q, f"quality_{q}") for q in row])
    
    buttons.extend([
        [InlineKeyboardButton("🌐 Global Thumb", "quality_global")],
        [InlineKeyboardButton("🗑 Delete All Thumbnails", "delete_all_thumbs")],
        [InlineKeyboardButton("❌ Close", "quality_close")]
    ])
    return buttons

@Client.on_message(filters.private & filters.command('smart_thumb'))
async def quality_menu(client, message):
    buttons = await generate_main_menu_buttons(message.from_user.id)
    await message.reply_text(
        "🎬 Thumbnail Manager",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

@Client.on_callback_query(filters.regex(r'^quality_global$'))
async def global_thumb_menu(client, callback):
    user_id = callback.from_user.id
    has_thumb = await codeflixbots.get_global_thumb(user_id)
    is_enabled = await codeflixbots.is_global_thumb_enabled(user_id)
    
    buttons = [
        [InlineKeyboardButton("👀 View Global Thumb", "view_global")],
        [InlineKeyboardButton("🖼️ Set Global Thumb", "set_global")],
        [InlineKeyboardButton("🗑 Delete Global Thumb", "delete_global")],
        [InlineKeyboardButton(f"🌐 Global Mode: {'ON ✅' if is_enabled else 'OFF ❌'}", "toggle_global_mode")],
        [InlineKeyboardButton("🔙 Main Menu", "back_to_main")]
    ]
    
    status_text = f"Status: {'✅ Set' if has_thumb else '❌ Not Set'}\nMode: {'🌐 Enabled' if is_enabled else '🚫 Disabled'}"
    await callback.message.edit_text(
        f"⚙️ Global Thumbnail Settings\n\n{status_text}",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

@Client.on_callback_query(filters.regex(r'^toggle_global_mode$'))
async def toggle_global_mode(client, callback):
    user_id = callback.from_user.id
    new_status = not await codeflixbots.is_global_thumb_enabled(user_id)
    await codeflixbots.toggle_global_thumb(user_id, new_status)
    await global_thumb_menu(client, callback)
    await callback.answer(f"Global Mode {'Enabled' if new_status else 'Disabled'}")

@Client.on_callback_query(filters.regex(r'^set_global$'))
async def set_global_thumb(client, callback):
    await codeflixbots.set_temp_quality(callback.from_user.id, "global")
    await callback.message.edit_text(
        "🖼️ Send me the Global Thumbnail (as photo)",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("↩️ Cancel", "quality_global")]
        ])
    )

@Client.on_message(filters.private & filters.photo & ~filters.command(''))
async def save_thumbnail(client, message):
    user_id = message.from_user.id
    quality = await codeflixbots.get_temp_quality(user_id)
    if not quality:
        return
    
    try:
        if quality == "global":
            # Delete all quality-specific thumbnails when setting global thumb
            await codeflixbots.col.update_one(
                {"_id": user_id},
                {"$set": {"global_thumb": message.photo.file_id, "thumbnails": {}}}
            )
            reply_text = "✅ Global thumbnail saved (all quality thumbnails cleared)"
        else:
            if await codeflixbots.is_global_thumb_enabled(user_id):
                await message.reply_text("❌ Global mode is active! Disable it first.")
                return
                
            await codeflixbots.set_quality_thumbnail(user_id, quality, message.photo.file_id)
            reply_text = f"✅ {quality.upper()} thumbnail saved!"
        
        await message.reply_text(
            reply_text,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("👀 View", f"view_{quality}")],
                [InlineKeyboardButton("⚙️ Settings", f"quality_{quality}")]
            ])
        )
    except Exception as e:
        await message.reply_text(f"❌ Error: {str(e)}")
    finally:
        await codeflixbots.clear_temp_quality(user_id)

@Client.on_callback_query(filters.regex(r'^view_global$'))
async def view_global_thumb(client, callback):
    thumb = await codeflixbots.get_global_thumb(callback.from_user.id)
    if thumb:
        await client.send_photo(
            callback.message.chat.id,
            photo=thumb,
            caption="📸 Global Thumbnail"
        )
    else:
        await callback.answer("No global thumbnail set!", show_alert=True)

@Client.on_callback_query(filters.regex(r'^delete_global$'))
async def delete_global_thumb(client, callback):
    user_id = callback.from_user.id
    await codeflixbots.set_global_thumb(user_id, None)
    await callback.message.edit_text(
        "🗑 Global thumbnail deleted!",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back", "quality_global")]
        ])
    )

@Client.on_callback_query(filters.regex('^back_to_main$'))
async def back_to_main(client, callback):
    buttons = await generate_main_menu_buttons(callback.from_user.id)
    await callback.message.edit_text(
        "🎬 Thumbnail Manager",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

@Client.on_callback_query(filters.regex('^delete_all_thumbs$'))
async def delete_all_thumbs(client, callback):
    user_id = callback.from_user.id
    await codeflixbots.col.update_one(
        {"_id": user_id},
        {"$set": {"thumbnails": {}, "global_thumb": None}}
    )
    await callback.message.edit_text(
        "✅ All thumbnails deleted successfully!",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Main Menu", "back_to_main")]
        ])
    )

@Client.on_callback_query(filters.regex(r'^quality_([a-zA-Z0-9]+)$'))
async def quality_handler(client, callback):
    user_id = callback.from_user.id
    quality = callback.matches[0].group(1)
    
    if quality == "close":
        await callback.message.delete()
        return
    
    if quality == "global":
        await global_thumb_menu(client, callback)
        return
    
    is_global = await codeflixbots.is_global_thumb_enabled(user_id)
    has_thumb = await codeflixbots.get_quality_thumbnail(user_id, quality)
    
    buttons = [
        [InlineKeyboardButton("👀 View", f"view_{quality}")],
        [InlineKeyboardButton("🖼️ Set New", f"set_{quality}")],
        [InlineKeyboardButton("🗑 Delete", f"delete_{quality}")],
        [InlineKeyboardButton("🔙 Main Menu", "back_to_main")]
    ]
    
    status_text = "🌐 (Global)" if is_global else f"{'✅ Set' if has_thumb else '❌ Not Set'}"
    await callback.message.edit_text(
        f"⚙️ {quality.upper()} Settings\n\nStatus: {status_text}",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

@Client.on_callback_query(filters.regex(r'^set_([a-zA-Z0-9]+)$'))
async def set_thumbnail_handler(client, callback):
    quality = callback.matches[0].group(1)
    await codeflixbots.set_temp_quality(callback.from_user.id, quality)
    
    await callback.message.edit_text(
        f"🖼️ Send {quality.upper()} Thumbnail\n\nSend as photo (not document):",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("↩️ Cancel", f"quality_{quality}")]
        ])
    )

@Client.on_callback_query(filters.regex(r'^view_([a-zA-Z0-9]+)$'))
async def view_thumbnail(client, callback):
    user_id = callback.from_user.id
    quality = callback.matches[0].group(1)
    
    if quality == "global":
        thumb = await codeflixbots.get_global_thumb(user_id)
    elif await codeflixbots.is_global_thumb_enabled(user_id):
        thumb = await codeflixbots.get_global_thumb(user_id)
    else:
        thumb = await codeflixbots.get_quality_thumbnail(user_id, quality)
    
    if thumb:
        await client.send_photo(
            callback.message.chat.id,
            photo=thumb,
            caption=f"📸 {quality.upper()} Thumbnail{' (Global)' if await codeflixbots.is_global_thumb_enabled(user_id) else ''}"
        )
    else:
        await callback.answer("No thumbnail set!", show_alert=True)

@Client.on_callback_query(filters.regex(r'^delete_([a-zA-Z0-9]+)$'))
async def delete_thumbnail(client, callback):
    user_id = callback.from_user.id
    quality = callback.matches[0].group(1)
    
    if quality == "global":
        await codeflixbots.set_global_thumb(user_id, None)
        reply_text = "🗑 Global thumbnail deleted!"
    elif await codeflixbots.is_global_thumb_enabled(user_id):
        await callback.answer("Global mode is active!", show_alert=True)
        return
    else:
        await codeflixbots.set_quality_thumbnail(user_id, quality, None)
        reply_text = f"🗑 {quality.upper()} thumbnail deleted!"
    
    await callback.message.edit_text(
        reply_text,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back", f"quality_{quality}")]
        ])
    )
    
