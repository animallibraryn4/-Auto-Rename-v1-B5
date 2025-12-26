import asyncio
import time
from pyrogram import Client, filters
from pyrogram.types import Message
from helper.database import codeflixbots

# Import verification functions
try:
    from plugins import is_user_verified, send_verification
    from plugins.file_rename import recent_verification_checks
except ImportError:
    # Fallback if imports fail
    recent_verification_checks = {}
    
    async def is_user_verified(user_id):
        return True
        
    async def send_verification(client, message):
        pass

@Client.on_message(filters.private & (filters.document | filters.video))
async def route_files(client, message: Message):
    """Main router that directs files to either rename or merge processor"""
    user_id = message.from_user.id
    
    # Check verification
    if not await is_user_verified(user_id):
        curr = time.time()
        if curr - recent_verification_checks.get(user_id, 0) > 2:
            recent_verification_checks[user_id] = curr
            await send_verification(client, message)
        return
    
    # Check if merge mode is enabled
    is_merge_mode = await codeflixbots.get_merge_mode(user_id)
    
    if is_merge_mode:
        # Route to merge processor
        from plugins.merge_processor import merge_queues, merge_worker
        
        # Check if user has merge format set
        merge_format = await codeflixbots.get_merge_format(user_id)
        if not merge_format:
            await message.reply_text(
                "⚠️ **Please set merge format first!**\n\n"
                "Use: `/mergeformat [S[SE.NUM]-E[EP.NUM]] Title [[QUALITY]] [[DUAL]]`\n\n"
                "Example: `/mergeformat [S[SE.NUM]-E[EP.NUM]] Anime [[QUALITY]] [[DUAL]] @Animelibraryn4`"
            )
            return
        
        # Initialize merge queue if needed
        if user_id not in merge_queues:
            merge_queues[user_id] = {
                "queue": asyncio.Queue(),
                "task": asyncio.create_task(merge_worker(user_id, client))
            }
        
        # Check if this is batch 1 or batch 2
        batch1 = await codeflixbots.get_merge_batch1(user_id)
        
        if len(batch1) == 0:
            # First file - send batch 1 instructions
            await message.reply_text(
                "📥 **Batch 1 Started**\n\n"
                "I'll extract audio & subtitle tracks from these files.\n"
                "Send all Batch 1 files now..."
            )
        else:
            # Already have batch 1 files
            tracks = await codeflixbots.get_merge_tracks(user_id)
            
            if len(tracks) > 0 and len(batch1) == len(tracks):
                # Ready for batch 2
                await message.reply_text(
                    f"🎯 **Batch 2 Started**\n\n"
                    f"Found {len(tracks)} episodes in Batch 1.\n"
                    f"Now send matching Batch 2 files to merge tracks into..."
                )
        
        # Add to merge queue
        await merge_queues[user_id]["queue"].put(message)
        
    else:
        # Route to auto rename processor
        from plugins.file_rename import user_queues, user_worker
        
        # Check if user has rename format set
        format_template = await codeflixbots.get_format_template(user_id)
        if not format_template:
            await message.reply_text("Please Set An Auto Rename Format First Using /autorename")
            return
        
        # Initialize rename queue if needed
        if user_id not in user_queues:
            user_queues[user_id] = {
                "queue": asyncio.Queue(),
                "task": asyncio.create_task(user_worker(user_id, client))
            }
        
        # Add to rename queue
        await user_queues[user_id]["queue"].put(message)

# Also handle audio files for rename mode
@Client.on_message(filters.private & filters.audio)
async def route_audio_files(client, message: Message):
    """Route audio files (only for rename mode, not merge mode)"""
    user_id = message.from_user.id
    
    # Check verification
    if not await is_user_verified(user_id):
        curr = time.time()
        if curr - recent_verification_checks.get(user_id, 0) > 2:
            recent_verification_checks[user_id] = curr
            await send_verification(client, message)
        return
    
    # Check if merge mode is enabled - audio not supported for merge
    is_merge_mode = await codeflixbots.get_merge_mode(user_id)
    
    if is_merge_mode:
        await message.reply_text(
            "⚠️ **Audio files not supported in Merge Mode**\n\n"
            "Merge mode only works with video files.\n"
            "Please send video files only, or turn off merge mode with `/merging`"
        )
        return
    
    # Route to auto rename processor
    from plugins.file_rename import user_queues, user_worker
    
    # Check if user has rename format set
    format_template = await codeflixbots.get_format_template(user_id)
    if not format_template:
        await message.reply_text("Please Set An Auto Rename Format First Using /autorename")
        return
    
    # Initialize rename queue if needed
    if user_id not in user_queues:
        user_queues[user_id] = {
            "queue": asyncio.Queue(),
            "task": asyncio.create_task(user_worker(user_id, client))
        }
    
    # Add to rename queue
    await user_queues[user_id]["queue"].put(message)
