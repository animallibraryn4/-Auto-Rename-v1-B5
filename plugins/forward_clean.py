import asyncio
import time
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup
from pyrogram.errors import FloodWait, ChatAdminRequired, ChannelPrivate
from config import Config

# Admin check function
async def is_admin(client, chat_id, user_id):
    try:
        member = await client.get_chat_member(chat_id, user_id)
        return member.status in ["creator", "administrator"]
    except:
        return False

# Progress message handler
async def update_progress_msg(client, progress_msg, current, total, start_time, channel_a, channel_b):
    elapsed = time.time() - start_time
    if elapsed > 2 or current == total:  # Update every 2 seconds or when done
        percent = (current / total) * 100
        speed = current / elapsed if elapsed > 0 else 0
        
        progress_bar = "█" * int(percent/5) + "░" * (20 - int(percent/5))
        
        text = (
            f"**📤 Forwarding Progress**\n\n"
            f"**From:** {channel_a}\n"
            f"**To:** {channel_b}\n\n"
            f"{progress_bar} {percent:.1f}%\n\n"
            f"**Processed:** {current}/{total} files\n"
            f"**Speed:** {speed:.1f} files/sec\n"
            f"**Elapsed:** {int(elapsed)} seconds"
        )
        
        try:
            await progress_msg.edit_text(text)
        except:
            pass

# Main RFC command handler
@Client.on_message(filters.command("rfc") & filters.user(Config.ADMIN))
async def remove_forward_caption(client: Client, message: Message):
    if len(message.command) < 2:
        await message.reply_text(
            "**Usage:** `/rfc @username`\n\n"
            "**Example:** `/rfc @anime24`\n\n"
            "Make sure the bot is admin in both channels."
        )
        return
    
    target_text = message.command[1].lower()
    
    # Ask for source and destination channels
    initial_msg = await message.reply_text(
        "**RFC - Remove & Forward Caption**\n\n"
        "Please provide:\n"
        "1. Source Channel (ID or @username)\n"
        "2. Destination Channel (ID or @username)\n\n"
        "**Format:** `source_channel destination_channel`\n\n"
        "**Example:** `-100123456789 -100987654321`",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Cancel", callback_data="rfc_cancel")]
        ])
    )
    
    try:
        # Wait for user response
        response = await client.listen.Message(filters.text & filters.user(message.from_user.id), timeout=60)
        
        if response.text == "/cancel":
            await initial_msg.edit_text("❌ Operation cancelled.")
            return
            
        parts = response.text.split()
        if len(parts) < 2:
            await initial_msg.edit_text("❌ Please provide both source and destination channels.")
            return
        
        source_channel = parts[0]
        dest_channel = parts[1]
        
        # Validate channel IDs
        try:
            source_chat = await client.get_chat(source_channel)
            dest_chat = await client.get_chat(dest_channel)
            
            source_id = source_chat.id
            dest_id = dest_chat.id
        except Exception as e:
            await initial_msg.edit_text(f"❌ Invalid channel: {str(e)}")
            return
        
        # Check bot admin status
        if not await is_admin(client, source_id, (await client.get_me()).id):
            await initial_msg.edit_text(f"❌ Bot is not admin in source channel: {source_chat.title}")
            return
            
        if not await is_admin(client, dest_id, (await client.get_me()).id):
            await initial_msg.edit_text(f"❌ Bot is not admin in destination channel: {dest_chat.title}")
            return
        
        # Start processing
        progress_msg = await initial_msg.edit_text(
            f"**🚀 Starting RFC Process**\n\n"
            f"**Source:** {source_chat.title}\n"
            f"**Destination:** {dest_chat.title}\n"
            f"**Target Text:** {target_text}\n\n"
            f"⏳ Gathering messages..."
        )
        
        # Collect messages from source channel
        all_messages = []
        async for msg in client.get_chat_history(source_id, limit=1000):  # Limit to 1000 messages
            if msg.media:  # Only process media messages
                all_messages.append(msg)
        
        if not all_messages:
            await progress_msg.edit_text("❌ No media files found in source channel.")
            return
        
        # Filter messages with target text in caption
        target_messages = []
        for msg in all_messages:
            if msg.caption and target_text in msg.caption.lower():
                target_messages.append(msg)
        
        total_files = len(target_messages)
        
        if total_files == 0:
            await progress_msg.edit_text(f"❌ No files found with '{target_text}' in caption.")
            return
        
        await progress_msg.edit_text(
            f"**✅ Found {total_files} files to process**\n\n"
            f"**Source:** {source_chat.title}\n"
            f"**Destination:** {dest_chat.title}\n"
            f"**Removing:** {target_text}\n\n"
            "Starting forwarding process..."
        )
        
        # Process files
        processed = 0
        failed = 0
        start_time = time.time()
        
        for idx, msg in enumerate(target_messages, 1):
            try:
                # Clean caption
                new_caption = None
                if msg.caption:
                    # Remove target text from caption
                    cleaned = msg.caption.replace(target_text, "").replace(target_text.upper(), "").replace(target_text.title(), "")
                    # Clean up extra spaces and newlines
                    cleaned = "\n".join([line.strip() for line in cleaned.split("\n") if line.strip()])
                    # If caption becomes empty or contains only @anime24, remove it
                    if cleaned and cleaned.strip() and cleaned.lower() != target_text:
                        new_caption = cleaned
                
                # Forward message with cleaned caption
                if msg.video:
                    await client.send_video(
                        chat_id=dest_id,
                        video=msg.video.file_id,
                        caption=new_caption,
                        duration=msg.video.duration,
                        width=msg.video.width,
                        height=msg.video.height,
                        thumb=msg.video.thumbs[0].file_id if msg.video.thumbs else None
                    )
                elif msg.document:
                    await client.send_document(
                        chat_id=dest_id,
                        document=msg.document.file_id,
                        caption=new_caption,
                        file_name=msg.document.file_name
                    )
                elif msg.audio:
                    await client.send_audio(
                        chat_id=dest_id,
                        audio=msg.audio.file_id,
                        caption=new_caption,
                        duration=msg.audio.duration,
                        performer=msg.audio.performer,
                        title=msg.audio.title
                    )
                elif msg.photo:
                    await client.send_photo(
                        chat_id=dest_id,
                        photo=msg.photo.file_id,
                        caption=new_caption
                    )
                
                processed += 1
                
                # Update progress
                if idx % 5 == 0 or idx == total_files:
                    await update_progress_msg(
                        client, progress_msg, idx, total_files, 
                        start_time, source_chat.title, dest_chat.title
                    )
                
                # Anti-flood delay
                await asyncio.sleep(1)
                
            except FloodWait as e:
                await asyncio.sleep(e.value)
                continue
            except Exception as e:
                failed += 1
                print(f"Failed to forward message {idx}: {e}")
                continue
        
        # Final report
        elapsed = time.time() - start_time
        await progress_msg.edit_text(
            f"**✅ RFC Process Complete!**\n\n"
            f"**Source:** {source_chat.title}\n"
            f"**Destination:** {dest_chat.title}\n"
            f"**Target Text:** {target_text}\n\n"
            f"**📊 Results:**\n"
            f"• Total found: {total_files}\n"
            f"• Successfully forwarded: {processed}\n"
            f"• Failed: {failed}\n"
            f"• Time taken: {int(elapsed)} seconds\n\n"
            f"**Average speed:** {processed/elapsed:.1f} files/second"
        )
        
    except asyncio.TimeoutError:
        await initial_msg.edit_text("❌ Timeout: No response received.")
    except Exception as e:
        await initial_msg.edit_text(f"❌ Error: {str(e)}")

# Cancel callback
@Client.on_callback_query(filters.regex("^rfc_cancel$"))
async def rfc_cancel(client, callback_query):
    await callback_query.message.edit_text("❌ RFC operation cancelled.")
    await callback_query.answer()

# Quick RFC command (alternative simplified version)
@Client.on_message(filters.command("quickrfc") & filters.user(Config.ADMIN))
async def quick_rfc(client: Client, message: Message):
    if len(message.command) < 4:
        await message.reply_text(
            "**Quick RFC Usage:**\n"
            "`/quickrfc @target_text source_channel dest_channel`\n\n"
            "**Example:**\n"
            "`/quickrfc @anime24 -100123456789 -100987654321`"
        )
        return
    
    target_text = message.command[1].lower()
    source_channel = message.command[2]
    dest_channel = message.command[3]
    
    try:
        # Get chats
        source_chat = await client.get_chat(source_channel)
        dest_chat = await client.get_chat(dest_channel)
        
        # Check admin status
        if not await is_admin(client, source_chat.id, (await client.get_me()).id):
            await message.reply_text(f"❌ Bot is not admin in source channel: {source_chat.title}")
            return
            
        if not await is_admin(client, dest_chat.id, (await client.get_me()).id):
            await message.reply_text(f"❌ Bot is not admin in destination channel: {dest_chat.title}")
            return
        
        # Start processing
        progress_msg = await message.reply_text(
            f"**⚡ Quick RFC Started**\n\n"
            f"**Source:** {source_chat.title}\n"
            f"**Destination:** {dest_chat.title}\n"
            f"**Removing:** {target_text}\n\n"
            f"⏳ Processing..."
        )
        
        # Process messages
        processed = 0
        total = 0
        
        async for msg in client.get_chat_history(source_chat.id):
            if msg.media and msg.caption and target_text in msg.caption.lower():
                total += 1
                
                # Clean caption
                new_caption = msg.caption.replace(target_text, "").strip()
                if not new_caption or new_caption.lower() == target_text:
                    new_caption = None
                
                # Forward with cleaned caption
                try:
                    await msg.copy(dest_chat.id, caption=new_caption)
                    processed += 1
                    
                    # Update progress every 10 files
                    if processed % 10 == 0:
                        await progress_msg.edit_text(
                            f"**⚡ Quick RFC Progress**\n\n"
                            f"**Processed:** {processed} files\n"
                            f"**Source:** {source_chat.title}\n"
                            f"**Destination:** {dest_chat.title}"
                        )
                    
                    await asyncio.sleep(0.5)  # Small delay to avoid flood
                    
                except Exception as e:
                    print(f"Error forwarding: {e}")
                    continue
        
        await progress_msg.edit_text(
            f"**✅ Quick RFC Complete**\n\n"
            f"**Source:** {source_chat.title}\n"
            f"**Destination:** {dest_chat.title}\n"
            f"**Removed:** {target_text}\n\n"
            f"**Results:** {processed}/{total} files forwarded"
        )
        
    except Exception as e:
        await message.reply_text(f"❌ Error: {str(e)}")
