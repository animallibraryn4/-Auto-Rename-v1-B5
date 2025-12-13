import motor.motor_asyncio
import datetime
import logging
from config import Config
from .utils import send_log

class Database:
    def __init__(self, uri, database_name):
        try:
            self._client = motor.motor_asyncio.AsyncIOMotorClient(uri)
            self._client.server_info()
            logging.info("Successfully connected to MongoDB")
        except Exception as e:
            logging.error(f"Failed to connect to MongoDB: {e}")
            raise e
        self.codeflixbots = self._client[database_name]
        self.col = self.codeflixbots.user

    def new_user(self, id):
        return dict(
            _id=int(id),
            join_date=datetime.date.today().isoformat(),
            file_id=None,
            caption=None,
            metadata=True,
            metadata_code="Telegram : @Animelibraryn4",
            format_template=None,
            thumbnails={},
            temp_quality=None,
            use_global_thumb=False,
            global_thumb=None,
            ban_status=dict(
                is_banned=False,
                ban_duration=0,
                banned_on=datetime.date.max.isoformat(),
                ban_reason=''
            ),
            # Preserving all existing metadata fields
            title='Encoded by @Animelibraryn4',
            author='@Animelibraryn4',
            artist='@Animelibraryn4',
            audio='By @Animelibraryn4',
            subtitle='By @Animelibraryn4',
            video_title='By @Animelibraryn4',
            # FIXED: Consolidated user info fields to avoid conflicts
            user_info=dict(
                username=None,
                first_name=None,
                last_name=None,
                mention=None
            )
        )

    async def add_user(self, client, message):
        user = message.from_user
        user_id = user.id
        
        try:
            # Check if user exists
            existing_user = await self.col.find_one({"_id": int(user_id)})
            
            if existing_user:
                # Update only user_info for existing users
                update_data = {
                    "user_info.username": user.username,
                    "user_info.first_name": user.first_name,
                    "user_info.last_name": user.last_name,
                    "user_info.mention": user.mention
                }
                
                # Remove None values to avoid overwriting with None
                update_data = {k: v for k, v in update_data.items() if v is not None}
                
                if update_data:  # Only update if there's something to update
                    await self.col.update_one(
                        {"_id": int(user_id)},
                        {"$set": update_data}
                    )
            else:
                # Create new user with all fields
                user_data = self.new_user(user_id)
                user_data["user_info"] = {
                    "username": user.username,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "mention": user.mention
                }
                
                await self.col.insert_one(user_data)
                logging.info(f"New user added: {user_id}")
                
                # Send log only for new users
                await send_log(client, user)
                
        except Exception as e:
            logging.error(f"Error adding/updating user {user_id}: {e}", exc_info=True)

    async def get_format_template(self, id):
        """Get user's auto-rename format template."""
        try:
            user = await self.col.find_one({"_id": int(id)})
            return user.get("format_template") if user else None
        except Exception as e:
            logging.error(f"Error getting format template for user {id}: {e}")
            return None

    async def set_format_template(self, id, template):
        """Set user's auto-rename format template."""
        try:
            await self.col.update_one(
                {"_id": int(id)},
                {"$set": {"format_template": template}},
                upsert=True
            )
        except Exception as e:
            logging.error(f"Error setting format template for user {id}: {e}")

    # Caption Methods
    async def get_caption(self, id):
        """Get user's custom caption."""
        try:
            user = await self.col.find_one({"_id": int(id)})
            return user.get("caption") if user else None
        except Exception as e:
            logging.error(f"Error getting caption for user {id}: {e}")
            return None

    async def set_caption(self, id, caption):
        """Set user's custom caption."""
        try:
            await self.col.update_one(
                {"_id": int(id)},
                {"$set": {"caption": caption}},
                upsert=True
            )
        except Exception as e:
            logging.error(f"Error setting caption for user {id}: {e}")

    # Thumbnail Methods (Single)
    async def get_thumbnail(self, id):
        """Get user's single thumbnail file_id."""
        try:
            user = await self.col.find_one({"_id": int(id)})
            return user.get("file_id") if user else None
        except Exception as e:
            logging.error(f"Error getting thumbnail for user {id}: {e}")
            return None

    async def set_thumbnail(self, id, file_id):
        """Set user's single thumbnail file_id."""
        try:
            await self.col.update_one(
                {"_id": int(id)},
                {"$set": {"file_id": file_id}},
                upsert=True
            )
        except Exception as e:
            logging.error(f"Error setting thumbnail for user {id}: {e}")

    # Metadata Toggle Methods
    async def get_metadata(self, id):
        """Get user's metadata toggle status."""
        try:
            user = await self.col.find_one({"_id": int(id)})
            return user.get("metadata", False) if user else False
        except Exception as e:
            logging.error(f"Error getting metadata status for user {id}: {e}")
            return False

    async def set_metadata(self, id, status: bool):
        """Set user's metadata toggle status."""
        try:
            await self.col.update_one(
                {"_id": int(id)},
                {"$set": {"metadata": status}},
                upsert=True
            )
        except Exception as e:
            logging.error(f"Error setting metadata status for user {id}: {e}")

    # Metadata Value Methods
    async def get_metadata_code(self, id):
        """Get user's metadata code."""
        try:
            user = await self.col.find_one({"_id": int(id)})
            return user.get("metadata_code") if user else None
        except Exception as e:
            logging.error(f"Error getting metadata code for user {id}: {e}")
            return None

    async def set_metadata_code(self, id, code):
        """Set user's metadata code."""
        try:
            await self.col.update_one(
                {"_id": int(id)},
                {"$set": {"metadata_code": code}},
                upsert=True
            )
        except Exception as e:
            logging.error(f"Error setting metadata code for user {id}: {e}")
            
    # Title
    async def get_title(self, id):
        """Get user's custom title."""
        try:
            user = await self.col.find_one({"_id": int(id)})
            return user.get("title") if user else None
        except Exception as e:
            logging.error(f"Error getting title for user {id}: {e}")
            return None

    async def set_title(self, id, title):
        """Set user's custom title."""
        try:
            await self.col.update_one(
                {"_id": int(id)},
                {"$set": {"title": title}},
                upsert=True
            )
        except Exception as e:
            logging.error(f"Error setting title for user {id}: {e}")

    # Author
    async def get_author(self, id):
        """Get user's custom author."""
        try:
            user = await self.col.find_one({"_id": int(id)})
            return user.get("author") if user else None
        except Exception as e:
            logging.error(f"Error getting author for user {id}: {e}")
            return None

    async def set_author(self, id, author):
        """Set user's custom author."""
        try:
            await self.col.update_one(
                {"_id": int(id)},
                {"$set": {"author": author}},
                upsert=True
            )
        except Exception as e:
            logging.error(f"Error setting author for user {id}: {e}")

    # Artist
    async def get_artist(self, id):
        """Get user's custom artist."""
        try:
            user = await self.col.find_one({"_id": int(id)})
            return user.get("artist") if user else None
        except Exception as e:
            logging.error(f"Error getting artist for user {id}: {e}")
            return None

    async def set_artist(self, id, artist):
        """Set user's custom artist."""
        try:
            await self.col.update_one(
                {"_id": int(id)},
                {"$set": {"artist": artist}},
                upsert=True
            )
        except Exception as e:
            logging.error(f"Error setting artist for user {id}: {e}")

    # Audio
    async def get_audio(self, id):
        """Get user's custom audio."""
        try:
            user = await self.col.find_one({"_id": int(id)})
            return user.get("audio") if user else None
        except Exception as e:
            logging.error(f"Error getting audio for user {id}: {e}")
            return None

    async def set_audio(self, id, audio):
        """Set user's custom audio."""
        try:
            await self.col.update_one(
                {"_id": int(id)},
                {"$set": {"audio": audio}},
                upsert=True
            )
        except Exception as e:
            logging.error(f"Error setting audio for user {id}: {e}")
            
    # Subtitle
    async def get_subtitle(self, id):
        """Get user's custom subtitle."""
        try:
            user = await self.col.find_one({"_id": int(id)})
            return user.get("subtitle") if user else None
        except Exception as e:
            logging.error(f"Error getting subtitle for user {id}: {e}")
            return None

    async def set_subtitle(self, id, subtitle):
        """Set user's custom subtitle."""
        try:
            await self.col.update_one(
                {"_id": int(id)},
                {"$set": {"subtitle": subtitle}},
                upsert=True
            )
        except Exception as e:
            logging.error(f"Error setting subtitle for user {id}: {e}")
    
    # Video Title
    async def get_video(self, id):
        """Get user's custom video title."""
        try:
            user = await self.col.find_one({"_id": int(id)})
            return user.get("video_title") if user else None
        except Exception as e:
            logging.error(f"Error getting video title for user {id}: {e}")
            return None

    async def set_video(self, id, video_title):
        """Set user's custom video title."""
        try:
            await self.col.update_one(
                {"_id": int(id)},
                {"$set": {"video_title": video_title}},
                upsert=True
            )
        except Exception as e:
            logging.error(f"Error setting video title for user {id}: {e}")

    # Quality Thumbnail Methods
    async def set_quality_thumbnail(self, id, quality, file_id):
        """Set a thumbnail file_id for a specific quality for the user."""
        try:
            # Use dot notation to update a field within the 'thumbnails' dictionary
            update_field = f"thumbnails.{quality}"
            await self.col.update_one(
                {"_id": int(id)},
                {"$set": {update_field: file_id}},
                upsert=True
            )
        except Exception as e:
            logging.error(f"Error setting {quality} thumbnail for user {id}: {e}")

    async def get_quality_thumbnail(self, id, quality):
        """Get the thumbnail file_id for a specific quality for the user."""
        try:
            user = await self.col.find_one({"_id": int(id)})
            if user and user.get('thumbnails'):
                return user['thumbnails'].get(quality)
            return None
        except Exception as e:
            logging.error(f"Error getting {quality} thumbnail for user {id}: {e}")
            return None

    async def delete_all_quality_thumbnails(self, id):
        """Delete all quality-specific thumbnails for the user."""
        try:
            await self.col.update_one(
                {"_id": int(id)},
                {"$set": {"thumbnails": {}}},
                upsert=True
            )
        except Exception as e:
            logging.error(f"Error deleting all quality thumbnails for user {id}: {e}")

    # Temp Quality Setting
    async def get_temp_quality(self, id):
        """Get user's temporary quality setting."""
        try:
            user = await self.col.find_one({"_id": int(id)})
            return user.get("temp_quality") if user else None
        except Exception as e:
            logging.error(f"Error getting temp quality for user {id}: {e}")
            return None

    async def set_temp_quality(self, id, quality):
        """Set user's temporary quality setting."""
        try:
            await self.col.update_one(
                {"_id": int(id)},
                {"$set": {"temp_quality": quality}},
                upsert=True
            )
        except Exception as e:
            logging.error(f"Error setting temp quality for user {id}: {e}")

    # Global Thumbnail Methods
    async def set_global_thumb(self, id, file_id):
        try:
            await self.col.update_one(
                {"_id": int(id)},
                {"$set": {"global_thumb": file_id}},
                upsert=True
            )
        except Exception as e:
            logging.error(f"Error setting global thumbnail for user {id}: {e}")

    async def get_global_thumb(self, id):
        try:
            user = await self.col.find_one({"_id": int(id)})
            return user.get("global_thumb") if user else None
        except Exception as e:
            logging.error(f"Error getting global thumbnail for user {id}: {e}")
            return None

    async def toggle_global_thumb(self, id, status: bool):
        try:
            await self.col.update_one(
                {"_id": int(id)},
                {"$set": {"use_global_thumb": status}},
                upsert=True
            )
        except Exception as e:
            logging.error(f"Error toggling global thumb for user {id}: {e}")

    async def is_global_thumb_enabled(self, id):
        try:
            user = await self.col.find_one({"_id": int(id)})
            return user.get("use_global_thumb", False) if user else False
        except Exception as e:
            logging.error(f"Error checking global thumb status for user {id}: {e}")
            return False

    # Ban Status Methods
    async def is_user_banned(self, id):
        """Check if a user is banned."""
        try:
            user = await self.col.find_one({"_id": int(id)})
            if user and user.get('ban_status'):
                return user['ban_status']['is_banned']
            return False
        except Exception as e:
            logging.error(f"Error checking ban status for user {id}: {e}")
            return False

    async def ban_user(self, id, reason=""):
        """Ban a user."""
        try:
            await self.col.update_one(
                {"_id": int(id)},
                {"$set": {
                    "ban_status.is_banned": True,
                    "ban_status.banned_on": datetime.date.today().isoformat(),
                    "ban_status.ban_reason": reason
                }},
                upsert=True
            )
            return True
        except Exception as e:
            logging.error(f"Error banning user {id}: {e}")
            return False

    async def unban_user(self, id):
        """Unban a user."""
        try:
            await self.col.update_one(
                {"_id": int(id)},
                {"$set": {
                    "ban_status.is_banned": False,
                    "ban_status.banned_on": datetime.date.max.isoformat(),
                    "ban_status.ban_reason": ''
                }}
            )
            return True
        except Exception as e:
            logging.error(f"Error unbanning user {id}: {e}")
            return False

    # ADDITIONAL METHODS FOR ADMIN PANEL
    async def total_users_count(self):
        """Get total number of users."""
        try:
            count = await self.col.count_documents({})
            return count
        except Exception as e:
            logging.error(f"Error counting users: {e}")
            return 0

    async def get_all_users(self):
        """Get all users."""
        try:
            return self.col.find({})
        except Exception as e:
            logging.error(f"Error getting all users: {e}")
            return []

    async def delete_user(self, user_id):
        """Delete a user from the database."""
        try:
            await self.col.delete_one({'_id': int(user_id)})
            return True
        except Exception as e:
            logging.error(f"Error deleting user {user_id}: {e}")
            return False

    async def is_banned(self, id):
        """Alias for is_user_banned for backward compatibility."""
        return await self.is_user_banned(id)

    async def get_user(self, id):
        """Get complete user document."""
        try:
            user = await self.col.find_one({"_id": int(id)})
            return user
        except Exception as e:
            logging.error(f"Error getting user {id}: {e}")
            return None

    async def update_user_info(self, id, username=None, first_name=None, last_name=None, mention=None):
        """Update user information separately."""
        try:
            update_data = {}
            if username is not None:
                update_data["user_info.username"] = username
            if first_name is not None:
                update_data["user_info.first_name"] = first_name
            if last_name is not None:
                update_data["user_info.last_name"] = last_name
            if mention is not None:
                update_data["user_info.mention"] = mention
            
            if update_data:
                await self.col.update_one(
                    {"_id": int(id)},
                    {"$set": update_data},
                    upsert=True
                )
            return True
        except Exception as e:
            logging.error(f"Error updating user info for {id}: {e}")
            return False

# Initialize database connection
codeflixbots = Database(Config.DB_URL, Config.DB_NAME)
