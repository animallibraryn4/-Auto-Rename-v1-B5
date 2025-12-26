from pyrogram import Client, filters
from helper.database import codeflixbots

@Client.on_message(filters.private & filters.command("mergeformat"))
async def merge_format_command(client, message):
    user_id = message.from_user.id
    
    # Check if merge mode is enabled
    if not await codeflixbots.get_merge_mode(user_id):
        await message.reply_text(
            "❌ **Merge mode is not enabled!**\n\n"
            "Please enable merge mode first using `/merging`"
        )
        return
    
    # Extract and validate the format from the command
    command_parts = message.text.split(maxsplit=1)
    if len(command_parts) < 2 or not command_parts[1].strip():
        await message.reply_text(
            "**Please provide a format for merged files**\n\n"
            "**Variables:**\n"
            "• `[SE.NUM]` - Season number\n"
            "• `[EP.NUM]` - Episode number\n"
            "• `[QUALITY]` - Video quality\n"
            "• `[DUAL]` - Will show 'Dual' if audio merged\n\n"
            "**Example:**\n"
            "`/mergeformat [S[SE.NUM]-E[EP.NUM]] Title [[QUALITY]] [[DUAL]] @Animelibraryn4`"
        )
        return
    
    format_template = command_parts[1].strip()
    
    # Save the format template
    await codeflixbots.set_merge_format(user_id, format_template)
    
    await message.reply_text(
        f"✅ **Merge format saved!**\n\n"
        f"**Your format:** `{format_template}`\n\n"
        "Now you can:\n"
        "1. Send Batch 1 files (source for audio/subtitles)\n"
        "2. Then send Batch 2 files (target videos)\n\n"
        "Files will be processed in the order received."
    )

@Client.on_message(filters.private & filters.command("mergeclear"))
async def merge_clear_command(client, message):
    user_id = message.from_user.id
    
    await codeflixbots.clear_merge_data(user_id)
    await codeflixbots.set_merge_mode(user_id, False)
    
    await message.reply_text(
        "✅ **Merge session cleared!**\n\n"
        "All merge data has been deleted.\n"
        "Merge mode is now disabled.\n"
        "Auto rename is active again."
    )
