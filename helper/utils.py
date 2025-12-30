import math, time
from datetime import datetime
from pytz import timezone
from config import Config, Txt 
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
import re

# Cache for last update times to prevent too frequent updates
_last_update_times = {}

async def progress_for_pyrogram(current, total, ud_type, message, start):
    """Optimized progress bar for large files with reduced update frequency"""
    
    now = time.time()
    diff = now - start
    
    # Get unique identifier for this upload/download
    task_id = f"{message.chat.id}_{message.id}"
    
    # Get last update time for this task
    last_update = _last_update_times.get(task_id, 0)
    
    # Calculate progress percentage
    percentage = current * 100 / total
    
    # DECREASE UPDATE FREQUENCY FOR LARGE FILES
    # Update conditions:
    # 1. If it's the first update
    # 2. If progress is complete (100%)
    # 3. If at least 3 seconds have passed since last update
    # 4. If significant progress has been made (10% increment for small files, 5% for large)
    update_interval = 3  # Minimum seconds between updates
    
    # For large files (over 500MB), increase interval
    if total > 500 * 1024 * 1024:  # 500MB
        update_interval = 5
        progress_increment = 2  # Update every 2% for very large files
    elif total > 100 * 1024 * 1024:  # 100MB
        update_interval = 4
        progress_increment = 3  # Update every 3% for large files
    else:
        progress_increment = 5  # Update every 5% for smaller files
    
    # Calculate progress since last update
    last_percentage = _last_update_times.get(f"{task_id}_percent", 0)
    percent_diff = percentage - last_percentage
    
    should_update = (
        current == total or  # Always update on completion
        diff == 0 or  # First update
        (now - last_update >= update_interval and percent_diff >= progress_increment) or  # Time + progress threshold
        percent_diff >= 10  # Significant progress made
    )
    
    if not should_update and current != total:
        return
    
    # Calculate speed and ETA
    speed = current / diff if diff > 0 else 0
    
    # Format speed
    if speed > 0:
        estimated_total_time = (total - current) / speed
        eta = TimeFormatter(milliseconds=estimated_total_time * 1000)
    else:
        eta = "Calculating..."
    
    # Update last update time and percentage
    _last_update_times[task_id] = now
    _last_update_times[f"{task_id}_percent"] = percentage
    
    # Create progress bar (simplified for large files)
    progress_width = 20
    filled_length = int(progress_width * percentage // 100)
    
    # Use simpler characters for faster rendering
    if total > 100 * 1024 * 1024:  # For files > 100MB
        progress_bar = '▓' * filled_length + '░' * (progress_width - filled_length)
    else:
        progress_bar = '█' * filled_length + '▒' * (progress_width - filled_length)
    
    # Format file sizes
    current_size = humanbytes(current)
    total_size = humanbytes(total)
    speed_formatted = humanbytes(speed) + "/s" if speed > 0 else "0 B/s"
    
    # Create progress text
    progress_text = f"""
**{ud_type}**

{progress_bar} **{percentage:.1f}%**

📊 **Progress:** {current_size} / {total_size}
⚡ **Speed:** {speed_formatted}
⏰ **ETA:** {eta}
🕐 **Elapsed:** {TimeFormatter(milliseconds=diff * 1000)}
"""
    
    try:
        await message.edit(
            text=progress_text,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ ᴄᴀɴᴄᴇʟ", callback_data="close")]
            ]) if current != total else None
        )
    except Exception as e:
        # Silent fail for progress updates to prevent breaking the main process
        pass

def humanbytes(size):    
    """Optimized human-readable bytes formatter"""
    if not size or size <= 0:
        return "0 B"
    
    # Use power of 1024 for binary prefixes
    power = 1024
    n = 0
    power_labels = {0: 'B', 1: 'KB', 2: 'MB', 3: 'GB', 4: 'TB'}
    
    while size >= power and n < len(power_labels) - 1:
        size /= power
        n += 1
    
    # Format with appropriate decimal places
    if n == 0:  # Bytes
        return f"{int(size)} {power_labels[n]}"
    elif n <= 2:  # KB or MB - 2 decimal places
        return f"{size:.2f} {power_labels[n]}"
    else:  # GB or TB - 1 decimal place
        return f"{size:.1f} {power_labels[n]}"

def TimeFormatter(milliseconds: int) -> str:
    """Optimized time formatter for progress updates"""
    if milliseconds <= 0:
        return "0s"
    
    seconds = milliseconds // 1000
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)
    
    # Build time string efficiently
    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    if seconds > 0 or not parts:  # Always show seconds if nothing else
        parts.append(f"{seconds}s")
    
    return " ".join(parts) if parts else "0s"

def convert(seconds):
    """Convert seconds to HH:MM:SS format"""
    seconds = int(seconds)
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    seconds = seconds % 60
    
    if hours > 0:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    else:
        return f"{minutes}:{seconds:02d}"

async def send_log(b, u):
    if Config.LOG_CHANNEL is not None:
        curr = datetime.now(timezone("Asia/Kolkata"))
        date = curr.strftime('%d %B, %Y')
        time = curr.strftime('%I:%M:%S %p')
        # Get bot's user object to get mention
        bot_user = await b.get_me()
        await b.send_message(
            Config.LOG_CHANNEL,
            f"**--Nᴇᴡ Uꜱᴇʀ Sᴛᴀʀᴛᴇᴅ Tʜᴇ Bᴏᴛ--**\n\nUꜱᴇʀ: {u.mention}\nIᴅ: `{u.id}`\nUɴ: @{u.username}\n\nDᴀᴛᴇ: {date}\nTɪᴍᴇ: {time}\n\nBy: {bot_user.mention}"
        )

def add_prefix_suffix(input_string, prefix='', suffix=''):
    """Add prefix and suffix to filename"""
    if not input_string:
        return input_string
    
    # Find the last dot for extension
    dot_pos = input_string.rfind('.')
    
    if dot_pos == -1:  # No extension
        filename = input_string
        extension = ''
    else:
        filename = input_string[:dot_pos]
        extension = input_string[dot_pos:]
    
    # Apply prefix and suffix
    result = f"{prefix}{filename}{suffix}{extension}"
    return result.strip()
