import os
import logging
from pyrogram import Client, filters
from helper.database import codeflixbots
from helper.utils import progress_for_pyrogram, humanbytes
from config import Config

logger = logging.getLogger(__name__)

@Client.on_message(filters.private & filters.command("file"))
async def toggle_file_split(client, message):
    """Toggle large file splitting feature on/off"""
    user_id = message.from_user.id
    current_status = await codeflixbots.get_split_large_files(user_id)
    new_status = not current_status
    await codeflixbots.set_split_large_files(user_id, new_status)
    
    status_text = "✅ Enabled" if new_status else "❌ Disabled"
    await message.reply_text(
        f"**Large File Splitting Feature:** {status_text}\n\n"
        "When enabled, files larger than 2GB will be automatically split into smaller parts."
    )

async def split_file(file_path, chunk_size=2*1024*1024*1024):
    """Split large file into chunks"""
    try:
        file_size = os.path.getsize(file_path)
        if file_size <= chunk_size:
            return [file_path]  # No splitting needed
        
        base_name = os.path.basename(file_path)
        output_dir = os.path.dirname(file_path)
        chunk_files = []
        
        with open(file_path, 'rb') as f:
            part_num = 1
            while True:
                chunk_data = f.read(chunk_size)
                if not chunk_data:
                    break
                    
                chunk_name = f"{base_name}.part{part_num:03d}"
                chunk_path = os.path.join(output_dir, chunk_name)
                
                with open(chunk_path, 'wb') as chunk_file:
                    chunk_file.write(chunk_data)
                    
                chunk_files.append(chunk_path)
                part_num += 1
        
        return chunk_files
    except Exception as e:
        logger.error(f"Error splitting file: {e}")
        raise

async def process_large_file(client, message, file_path, format_template, media_type):
    """Process and upload large file in parts"""
    try:
        # Notify user
        processing_msg = await message.reply_text(
            "📦 **Processing large file...**\n"
            "This may take a while depending on file size."
        )
        
        # Split the file
        chunk_files = await split_file(file_path)
        
        # Process each chunk
        for i, chunk_path in enumerate(chunk_files, 1):
            # Update progress
            await processing_msg.edit_text(
                f"🔄 Processing part {i}/{len(chunk_files)}...\n"
                f"File: {os.path.basename(chunk_path)}"
            )
            
            # Upload the chunk
            await upload_chunk(client, message, chunk_path, media_type)
            
            # Clean up
            if os.path.exists(chunk_path):
                os.remove(chunk_path)
                
        await processing_msg.edit_text(
            "✅ **File processing completed!**\n"
            f"Total parts uploaded: {len(chunk_files)}"
        )
        
    except Exception as e:
        logger.error(f"Error in process_large_file: {e}")
        await message.reply_text(f"❌ Error processing large file: {e}")
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)

async def upload_chunk(client, message, chunk_path, media_type):
    """Upload a single chunk of file"""
    try:
        # Get user settings
        user_id = message.from_user.id
        c_caption = await codeflixbots.get_caption(user_id)
        c_thumb = await codeflixbots.get_thumbnail(user_id)
        
        # Prepare caption
        chunk_name = os.path.basename(chunk_path)
        file_size = os.path.getsize(chunk_path)
        caption = (
            c_caption.format(
                filename=chunk_name,
                filesize=humanbytes(file_size),
                duration="N/A",
            )
            if c_caption
            else f"**{chunk_name}**"
        )
        
        # Upload based on media type
        if media_type == "document":
            await client.send_document(
                chat_id=message.chat.id,
                document=chunk_path,
                caption=caption,
                thumb=c_thumb,
                progress=progress_for_pyrogram,
                progress_args=("Uploading...", message, time.time()),
            )
        elif media_type == "video":
            await client.send_video(
                chat_id=message.chat.id,
                video=chunk_path,
                caption=caption,
                thumb=c_thumb,
                progress=progress_for_pyrogram,
                progress_args=("Uploading...", message, time.time()),
            )
        elif media_type == "audio":
            await client.send_audio(
                chat_id=message.chat.id,
                audio=chunk_path,
                caption=caption,
                thumb=c_thumb,
                progress=progress_for_pyrogram,
                progress_args=("Uploading...", message, time.time()),
            )
            
    except Exception as e:
        logger.error(f"Error uploading chunk {chunk_path}: {e}")
        raise
