import asyncio
import time
from pyrogram import Client

async def test_simple_upload(client, message):
    """Test simple upload without processing"""
    print("Testing simple upload...")
    
    # Download file
    path = await client.download_media(message, file_name="test_download.mp4")
    print(f"Downloaded to: {path}")
    
    # Upload back without processing
    start_time = time.time()
    await client.send_document(
        message.chat.id,
        document=path,
        caption="Test upload"
    )
    end_time = time.time()
    
    print(f"✅ Upload took {end_time - start_time:.2f} seconds")
    return True

# Add this handler in your main bot
@Client.on_message(filters.private & filters.command("testupload"))
async def test_upload_command(client, message):
    if message.reply_to_message and message.reply_to_message.document:
        await test_simple_upload(client, message.reply_to_message)
    else:
        await message.reply_text("Reply to a file with /testupload")
