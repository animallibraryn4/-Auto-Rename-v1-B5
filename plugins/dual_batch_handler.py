"""
Dual-Batch Handler - Integrates with existing file_rename system
"""
import os
import asyncio
from typing import Dict, Optional, List  # Add this import
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from plugins.batch_tracker import batch_tracker
from plugins.batch_merger import batch_merger
from helper.database import codeflixbots
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class DualBatchHandler:
    def __init__(self):
        self.processing_users = set()
        self.user_settings = {}  # user_id -> settings
        
    async def handle_dual_batch_file(self, client: Client, message: Message, 
                                   file_path: str, filename: str) -> bool:
        """
        Main handler for dual-batch processing
        Returns True if file was handled as part of batch merge
        """
        user_id = message.from_user.id
        
        # Check if user has batch mode enabled
        user_pref = await self.get_user_preference(user_id)
        if not user_pref.get('batch_mode', False):
            return False
        
        # Extract episode number and quality
        episode_num = await batch_tracker.extract_episode_number(filename)
        if not episode_num:
            logger.info(f"No episode number found in {filename}")
            return False
        
        quality = await batch_tracker.extract_quality(filename)
        
        # Track the file
        merge_data = await batch_tracker.track_file(
            user_id, file_path, episode_num, quality
        )
        
        if merge_data and merge_data.get('ready'):
            # We have both batches for this episode!
            await self.process_batch_merge(client, message, merge_data, user_id)
            return True
        
        # File is tracked but waiting for counterpart
        batch_status = await batch_tracker.get_user_batch_status(user_id)
        await self.send_batch_status(message, batch_status, episode_num)
        return True
    
    async def get_user_preference(self, user_id: int) -> Dict:
        """Get user's batch processing preferences"""
        if user_id not in self.user_settings:
            # Default settings
            self.user_settings[user_id] = {
                'batch_mode': False,
                'auto_merge': True,
                'output_format': '{filename}_dual.{ext}',
                'cleanup_temp': True
            }
        return self.user_settings[user_id]
    
    async def set_user_preference(self, user_id: int, key: str, value):
        """Set user preference"""
        prefs = await self.get_user_preference(user_id)
        prefs[key] = value
        self.user_settings[user_id] = prefs
    
    async def send_batch_status(self, message: Message, status: Dict, 
                              current_episode: int = None):
        """Send batch tracking status to user"""
        if status['status'] == 'no_batches':
            return
        
        text = "**🔄 Dual-Batch Tracking Active**\n\n"
        text += f"• **Batch 1 Files:** {status['batch1_count']}\n"
        text += f"• **Batch 2 Files:** {status['batch2_count']}\n"
        
        if status['matched_episodes']:
            text += f"• **Ready to Merge:** {len(status['matched_episodes'])} episodes\n"
        
        if current_episode:
            text += f"\n📁 Current file (Episode {current_episode}) tracked.\n"
            if current_episode in status['matched_episodes']:
                text += "✅ **Counterpart found!** Merging will start soon...\n"
            else:
                text += "⏳ Waiting for counterpart batch...\n"
        
        # Add instructions
        text += "\n**Commands:**\n"
        text += "• `/batch on/off` - Toggle batch mode\n"
        text += "• `/batch status` - Check current status\n"
        text += "• `/batch clear` - Clear all tracked files\n"
        
        buttons = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🔄 Batch Status", callback_data="batch_status"),
                InlineKeyboardButton("❌ Clear All", callback_data="batch_clear")
            ],
            [
                InlineKeyboardButton("📖 Help", callback_data="batch_help"),
                InlineKeyboardButton("⚙️ Settings", callback_data="batch_settings")
            ]
        ])
        
        try:
            await message.reply_text(text, reply_markup=buttons)
        except:
            pass
    
    async def process_batch_merge(self, client: Client, message: Message, 
                                merge_data: Dict, user_id: int):
        """Process the actual batch merge"""
        try:
            # Create output directory
            output_dir = f"batch_output/{user_id}"
            os.makedirs(output_dir, exist_ok=True)
            
            # Send processing message
            status_msg = await message.reply_text(
                f"**🔄 Merging Episode {merge_data['episode']}**\n"
                f"Combining audio/subtitles from Batch 1 with Batch 2 video...\n"
                f"Quality: {merge_data['second_batch']['quality'].upper()}"
            )
            
            # Perform the merge
            merged_file = await batch_merger.create_dual_audio_version(
                merge_data, output_dir
            )
            
            if merged_file and os.path.exists(merged_file):
                # Get user's format template
                format_template = await codeflixbots.get_format_template(user_id)
                if format_template:
                    # Apply auto-rename formatting
                    from plugins.file_rename import extract_episode_number, extract_season_number, extract_quality
                    
                    ep_num = merge_data['episode']
                    season_num = extract_season_number(os.path.basename(merged_file))
                    quality = merge_data['second_batch']['quality']
                    
                    # Apply replacements
                    formatted_name = format_template
                    replacements = {
                        "[EP.NUM]": str(ep_num),
                        "{episode}": str(ep_num),
                        "[SE.NUM]": str(season_num or ""),
                        "{season}": str(season_num or ""),
                        "[QUALITY]": quality if quality != "unknown" else "",
                        "{quality}": quality if quality != "unknown" else "",
                        "[DUAL]": "Dual",
                        "{dual}": "Dual"
                    }
                    
                    for old, new in replacements.items():
                        formatted_name = formatted_name.replace(old, new)
                    
                    # Add extension
                    _, ext = os.path.splitext(merged_file)
                    final_filename = f"{formatted_name}{ext}"
                    final_path = os.path.join(output_dir, final_filename)
                    
                    # Rename file
                    os.rename(merged_file, final_path)
                    merged_file = final_path
                
                # Send merged file to user
                caption = f"**🎉 Merged Complete!**\nEpisode {merge_data['episode']} - Dual Audio"
                
                await client.send_document(
                    chat_id=user_id,
                    document=merged_file,
                    caption=caption,
                    file_name=os.path.basename(merged_file)
                )
                
                await status_msg.edit_text(
                    f"✅ **Episode {merge_data['episode']} Merged Successfully!**\n"
                    f"• Dual Audio: ✓\n"
                    f"• Dual Subtitles: ✓\n"
                    f"• Quality: {merge_data['second_batch']['quality'].upper()}"
                )
                
                # Cleanup
                try:
                    os.remove(merged_file)
                except:
                    pass
                
            else:
                await status_msg.edit_text(
                    f"❌ **Failed to merge Episode {merge_data['episode']}**\n"
                    f"Using original Batch 2 file instead."
                )
                
        except Exception as e:
            logger.error(f"Error in batch merge: {e}")
            try:
                await message.reply_text(f"❌ Error during batch merge: {str(e)}")
            except:
                pass

# Global handler instance
dual_batch_handler = DualBatchHandler()

# Command Handlers
@Client.on_message(filters.private & filters.command("batch"))
async def batch_command_handler(client: Client, message: Message):
    """Handle batch commands"""
    user_id = message.from_user.id
    args = message.text.split()[1:] if len(message.text.split()) > 1 else []
    
    if not args:
        # Show help
        help_text = """
**🔄 Dual-Batch Audio/Subtitle Merger**

**Usage:**
`/batch on` - Enable batch mode
`/batch off` - Disable batch mode
`/batch status` - Show current batch status
`/batch clear` - Clear all tracked files
`/batch help` - Show this help

**How it works:**
1. Enable batch mode with `/batch on`
2. Send files from Batch 1 (e.g., Japanese audio/subs)
3. Send files from Batch 2 (e.g., English audio/subs)
4. Bot automatically merges them by episode number

**Rules:**
• First batch sent = Source for audio/subtitles
• Second batch sent = Source for video quality
• Matching by episode number only
        """
        await message.reply_text(help_text)
        return
    
    cmd = args[0].lower()
    
    if cmd in ['on', 'enable', 'start']:
        await dual_batch_handler.set_user_preference(user_id, 'batch_mode', True)
        await message.reply_text(
            "✅ **Batch Mode Enabled!**\n\n"
            "Now send your files in two batches:\n"
            "1. First batch (source for audio/subtitles)\n"
            "2. Second batch (source for video quality)\n\n"
            "Files will be matched by episode number automatically."
        )
        
    elif cmd in ['off', 'disable', 'stop']:
        await dual_batch_handler.set_user_preference(user_id, 'batch_mode', False)
        await message.reply_text("✅ **Batch Mode Disabled**")
        
    elif cmd == 'status':
        status = await batch_tracker.get_user_batch_status(user_id)
        await dual_batch_handler.send_batch_status(message, status)
        
    elif cmd == 'clear':
        # Clear batch data
        if user_id in batch_tracker.user_batches:
            del batch_tracker.user_batches[user_id]
        await message.reply_text("✅ **All batch data cleared**")
        
    elif cmd == 'help':
        await message.reply_text(
            "**Need help with batch merging?**\n\n"
            "Contact: @Animelibraryn4\n"
            "Or visit: https://t.me/animelibraryn4"
        )
        
    else:
        await message.reply_text(
            "❌ Unknown batch command. Use `/batch help` for available commands."
        )

@Client.on_callback_query(filters.regex(r'^batch_'))
async def batch_callback_handler(client, callback):
    """Handle batch callback queries"""
    data = callback.data
    user_id = callback.from_user.id
    
    if data == 'batch_status':
        status = await batch_tracker.get_user_batch_status(user_id)
        await dual_batch_handler.send_batch_status(callback.message, status)
        await callback.answer()
        
    elif data == 'batch_clear':
        if user_id in batch_tracker.user_batches:
            del batch_tracker.user_batches[user_id]
        await callback.message.edit_text("✅ All batch data cleared")
        await callback.answer()
        
    elif data == 'batch_help':
        await callback.message.edit_text(
            "**Batch Merge Help**\n\n"
            "1. Enable batch mode: `/batch on`\n"
            "2. Send first batch files\n"
            "3. Send second batch files\n"
            "4. Bot merges automatically\n\n"
            "**Note:** Files are matched by episode number."
        )
        await callback.answer()
        
    elif data == 'batch_settings':
        prefs = await dual_batch_handler.get_user_preference(user_id)
        text = "**Batch Settings**\n\n"
        text += f"• Mode: {'✅ ON' if prefs['batch_mode'] else '❌ OFF'}\n"
        text += f"• Auto Merge: {'✅ Yes' if prefs['auto_merge'] else '❌ No'}\n"
        
        buttons = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    f"{'🔴 Disable' if prefs['batch_mode'] else '🟢 Enable'} Batch Mode",
                    callback_data="batch_toggle_mode"
                )
            ],
            [
                InlineKeyboardButton(
                    f"{'🔴 Turn Off' if prefs['auto_merge'] else '🟢 Turn On'} Auto Merge",
                    callback_data="batch_toggle_auto"
                )
            ],
            [InlineKeyboardButton("🔙 Back", callback_data="batch_status")]
        ])
        
        await callback.message.edit_text(text, reply_markup=buttons)
        await callback.answer()
        
    elif data == 'batch_toggle_mode':
        prefs = await dual_batch_handler.get_user_preference(user_id)
        new_mode = not prefs['batch_mode']
        await dual_batch_handler.set_user_preference(user_id, 'batch_mode', new_mode)
        await callback.answer(f"Batch mode {'enabled' if new_mode else 'disabled'}")
        await batch_callback_handler(client, callback)  # Refresh
        
    elif data == 'batch_toggle_auto':
        prefs = await dual_batch_handler.get_user_preference(user_id)
        new_auto = not prefs['auto_merge']
        await dual_batch_handler.set_user_preference(user_id, 'auto_merge', new_auto)
        await callback.answer(f"Auto merge {'enabled' if new_auto else 'disabled'}")
        await batch_callback_handler(client, callback)  # Refresh
