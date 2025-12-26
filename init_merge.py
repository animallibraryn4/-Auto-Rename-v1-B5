"""
Merge Mode Initialization Script
Add this to your bot's startup
"""

import asyncio
import os
from helper.database import codeflixbots

async def initialize_merge_system():
    """Initialize merge system on bot startup"""
    print("Initializing merge system...")
    
    # Clear any active merge sessions from previous runs
    # This ensures clean state on restart
    all_users = await codeflixbots.get_all_users()
    async for user in all_users:
        user_id = user["_id"]
        await codeflixbots.clear_merge_data(user_id)
        await codeflixbots.set_merge_mode(user_id, False)
    
    print("Merge system initialized successfully")

# Call this function in your bot's startup
# Add to your bot.py after line 85 (after bot.start()):
# asyncio.create_task(initialize_merge_system())
