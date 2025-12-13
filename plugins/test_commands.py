# plugins/test_commands.py - For testing the token system

from pyrogram import Client, filters
from config import Config
from .user_limits import user_limits

@Client.on_message(filters.private & filters.command("testreset") & filters.user(Config.ADMIN))
async def test_reset_command(client, message):
    """Reset file count for testing (admin only)"""
    if len(message.command) > 1:
        try:
            user_id = int(message.command[1])
            user_limits.user_file_counts[user_id] = 0
            if user_id in user_limits.user_tokens:
                del user_limits.user_tokens[user_id]
            await message.reply_text(f"✅ Reset user {user_id} file count to 0")
        except:
            await message.reply_text("Usage: /testreset <user_id>")
    else:
        # Show current counts
        counts_text = "**Current User Counts:**\n"
        for user_id, count in user_limits.user_file_counts.items():
            counts_text += f"User {user_id}: {count}/12\n"
        await message.reply_text(counts_text)

@Client.on_message(filters.private & filters.command("testlimit") & filters.user(Config.ADMIN))
async def test_limit_command(client, message):
    """Set file count to test limit (admin only)"""
    if len(message.command) > 2:
        try:
            user_id = int(message.command[1])
            count = int(message.command[2])
            user_limits.user_file_counts[user_id] = count
            await message.reply_text(f"✅ Set user {user_id} file count to {count}/12")
        except:
            await message.reply_text("Usage: /testlimit <user_id> <count>")
    else:
        await message.reply_text("Usage: /testlimit <user_id> <count>")
