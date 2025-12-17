import os
import re
import time
import shutil
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message
from plugins.antinsfw import check_anti_nsfw
from helper.utils import progress_for_pyrogram, humanbytes, convert
from helper.database import codeflixbots
from config import Config
from plugins import is_user_verified, send_verification

# --- Global Concurrency Controls ---
MAX_CONCURRENT_TASKS = 3
global_semaphore = asyncio.Semaphore(MAX_CONCURRENT_TASKS)
user_queues = {}

# --- Extraction Patterns ---
pattern1 = re.compile(r'S(\d+)(?:E|EP)(\d+)')
pattern2 = re.compile(r'S(\d+)\s*(?:E|EP|-\s*EP)(\d+)')
pattern3 = re.compile(r'(?:[([<{]?\s*(?:E|EP)\s*(\d+)\s*[)\]>}]?)')
pattern3_2 = re.compile(r'(?:\s*-\s*(\d+)\s*)')
pattern4 = re.compile(r'S(\d+)[^\d]*(\d+)', re.IGNORECASE)
patternX = re.compile(r'(\d+)')
pattern5 = re.compile(r'\b(?:.*?(\d{3,4}[^\dp]*p).*?|.*?(\d{3,4}p))\b', re.IGNORECASE)
pattern6 = re.compile(r'[([<{]?\s*4k\s*[)\]>}]?', re.IGNORECASE)
pattern7 = re.compile(r'[([<{]?\s*2k\s*[)\]>}]?', re.IGNORECASE)
pattern8 = re.compile(r'[([<{]?\s*HdRip\s*[)\]>}]?|\bHdRip\b', re.IGNORECASE)
pattern9 = re.compile(r'[([<{]?\s*4kX264\s*[)\]>}]?', re.IGNORECASE)
pattern10 = re.compile(r'[([<{]?\s*4kx265\s*[)]>}]?', re.IGNORECASE)
pattern11 = re.compile(r'Vol(\d+)\s*-\s*Ch(\d+)', re.IGNORECASE)

# --- Helper Functions ---

def extract_quality(filename):
    for pattern, quality in [(pattern5, lambda m: m.group(1) or m.group(2)), (pattern6, "4k"), (pattern7, "2k"), (pattern8, "HdRip"), (pattern9, "4kX264"), (pattern10, "4kx265")]:
        match = re.search(pattern, filename)
        if match: return quality(match) if callable(quality) else quality
    return "Unknown"

def extract_episode_number(filename):
    for pattern in [pattern1, pattern2, pattern3, pattern3_2, pattern4, patternX]:
        match = re.search(pattern, filename)
        if match: return match.group(2) if pattern in [pattern1, pattern2, pattern4] else match.group(1)
    return None

def extract_season_number(filename):
    for pattern in [pattern1, pattern4]:
        match = re.search(pattern, filename)
        if match: return match.group(1)
    return None

def extract_volume_chapter(filename):
    match = re.search(pattern11, filename)
    if match: return match.group(1), match.group(2)
    return None, None

async def convert_to_mkv(input_path, output_path):
    ffmpeg_cmd = shutil.which('ffmpeg')
    if not ffmpeg_cmd: raise Exception("FFmpeg not found")
    command = [ffmpeg_cmd, '-i', input_path, '-map', '0', '-c', 'copy', '-loglevel', 'error', output_path]
    process = await asyncio.create_subprocess_exec(*command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    await process.communicate()

# --- Core Processing ---

async def process_rename(client: Client, message: Message):
    user_id = message.from_user.id
    format_template = await codeflixbots.get_format_template(user_id)
    media_preference = await codeflixbots.get_media_preference(user_id)

    if not format_template:
        return await message.reply_text("Please Set An Auto Rename Format First Using /autorename")

    # Metadata extraction
    if message.document:
        file_name, file_size = message.document.file_name, message.document.file_size
        media_type = media_preference or "document"
        is_pdf = message.document.mime_type == "application/pdf"
    elif message.video:
        file_name, file_size = (message.video.file_name or "video.mp4"), message.video.file_size
        media_type = media_preference or "video"
        is_pdf = False
    elif message.audio:
        file_name, file_size = (message.audio.file_name or "audio.mp3"), message.audio.file_size
        media_type = media_preference or "audio"
        is_pdf = False
    else: return

    if await check_anti_nsfw(file_name, message): return

    # Renaming Logic
    ep = extract_episode_number(file_name)
    se = extract_season_number(file_name)
    vol, ch = extract_volume_chapter(file_name)
    qual = extract_quality(file_name) if not is_pdf else ""

    replacements = {"[EP.NUM]": str(ep or ""), "{episode}": str(ep or ""), "[SE.NUM]": str(se or ""), "{season}": str(se or ""), "[Vol{volume}]": f"Vol{vol}" if vol else "", "[Ch{chapter}]": f"Ch{ch}" if ch else "", "[QUALITY]": qual or "", "{quality}": qual or ""}
    for old, new in replacements.items():
        format_template = format_template.replace(old, new)
    
    format_template = re.sub(r'\s+', ' ', format_template).strip().replace("_", " ")
    _, extension = os.path.splitext(file_name)
    renamed_name = f"{format_template}{extension}"
    
    # Unique paths per message to avoid cross-user interference
    msg_id = message.id
    download_path = f"downloads/{msg_id}_{renamed_name}"
    final_path = f"Metadata/{msg_id}_{renamed_name}"
    os.makedirs("downloads", exist_ok=True)
    os.makedirs("Metadata", exist_ok=True)

    ms = await message.reply_text("`Downloading...`")
    try:
        path = await client.download_media(message, file_name=download_path, progress=progress_for_pyrogram, progress_args=("Download Started...", ms, time.time()))
    except Exception as e:
        return await ms.edit(f"Download Error: {e}")

    # FFmpeg & Metadata (Limited by Semaphore)
    async with global_semaphore:
        await ms.edit("`Processing (Waiting for slot)...`")
        if (media_type in ["document", "video"]) and not path.lower().endswith('.mkv'):
            temp = f"{path}.mkv"
            await convert_to_mkv(path, temp)
            if os.path.exists(path): os.remove(path)
            path = temp
            renamed_name = f"{format_template}.mkv"
            final_path = f"Metadata/{msg_id}_{renamed_name}"

        ffmpeg_cmd = shutil.which('ffmpeg')
        metadata_cmd = [ffmpeg_cmd, '-i', path, '-metadata', f'title={await codeflixbots.get_title(user_id)}', '-metadata', f'artist={await codeflixbots.get_artist(user_id)}', '-map', '0', '-c', 'copy', '-loglevel', 'error', final_path]
        proc = await asyncio.create_subprocess_exec(*metadata_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        await proc.communicate()
        # The processed file is now at 'final_path'

    # Prepare Upload
    await ms.edit("`Uploading...`")
    c_caption = await codeflixbots.get_caption(message.chat.id)
    caption = c_caption.format(filename=renamed_name, filesize=humanbytes(file_size), duration=convert(0)) if c_caption else f"**{renamed_name}**"
    
    ph_path = None
    c_thumb = await codeflixbots.get_thumbnail(user_id)
    if c_thumb: ph_path = await client.download_media(c_thumb)

    try:
        # 1. Main Upload to User
        if media_type == "document":
            sent_msg = await client.send_document(message.chat.id, document=final_path, thumb=ph_path, caption=caption, progress=progress_for_pyrogram, progress_args=("Uploading...", ms, time.time()))
        elif media_type == "video":
            sent_msg = await client.send_video(message.chat.id, video=final_path, caption=caption, thumb=ph_path, progress=progress_for_pyrogram, progress_args=("Uploading...", ms, time.time()))
        else:
            sent_msg = await client.send_audio(message.chat.id, audio=final_path, caption=caption, thumb=ph_path, progress=progress_for_pyrogram, progress_args=("Uploading...", ms, time.time()))

        # 2. Forward to Dump Channel (Now we await it to prevent file deletion errors)
        if Config.DUMP_CHANNEL:
            try:
                dump_caption = f"➜ **File Renamed**\n\n» **User:** {message.from_user.mention}\n» **ID:** `{user_id}`\n➲ **Original:** `{file_name}`\n➲ **Renamed:** `{renamed_name}`"
                await sent_msg.copy(Config.DUMP_CHANNEL, caption=dump_caption)
            except Exception as e:
                print(f"Dump Error: {e}")

    finally:
        await ms.delete()
        # Cleanup all temporary files for this specific task
        for f in [path, final_path, ph_path]:
            if f and os.path.exists(f):
                try: os.remove(f)
                except: pass

# --- Worker Logic ---

async def user_worker(user_id, client):
    queue = user_queues[user_id]["queue"]
    while True:
        try:
            message = await asyncio.wait_for(queue.get(), timeout=300)
            await process_rename(client, message)
            queue.task_done()
        except asyncio.TimeoutError: break
        except Exception as e: print(f"User Worker Error: {e}")
    if user_id in user_queues: del user_queues[user_id]

@Client.on_message(filters.private & (filters.document | filters.video | filters.audio))
async def auto_rename_files(client, message):
    user_id = message.from_user.id
    if not await is_user_verified(user_id):
        await send_verification(client, message)
        return
    
    if user_id not in user_queues:
        user_queues[user_id] = {"queue": asyncio.Queue(), "task": asyncio.create_task(user_worker(user_id, client))}
    
    await user_queues[user_id]["queue"].put(message)
