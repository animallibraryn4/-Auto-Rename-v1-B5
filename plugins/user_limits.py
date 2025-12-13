import time
import hashlib
from datetime import datetime, timedelta
from config import Config
from helper.database import codeflixbots

class UserLimits:
    def __init__(self):
        self.user_file_counts = {}
        self.user_tokens = {}
        
    async def check_user_limit(self, user_id):
        """Check if user has exceeded file limit and needs ad token"""
        if user_id in Config.ADMIN:
            return True, None  # Admins have no limits
            
        # Get user's file count
        file_count = self.user_file_counts.get(user_id, 0)
        
        if file_count >= 12:
            # Check if user has valid token
            token_info = self.user_tokens.get(user_id)
            if token_info and token_info['expires_at'] > datetime.now():
                return True, None  # Has valid token
            return False, token_info  # Needs new token
        
        return True, None
    
    def increment_file_count(self, user_id):
        """Increment file count for user"""
        if user_id not in Config.ADMIN:  # Don't count admin files
            current = self.user_file_counts.get(user_id, 0)
            self.user_file_counts[user_id] = current + 1
    
    def reset_file_count(self, user_id):
        """Reset file count for user"""
        self.user_file_counts[user_id] = 0
    
    def generate_token(self, user_id):
        """Generate ad token for user"""
        # Generate unique token using user_id and timestamp
        timestamp = str(time.time())
        token_string = f"{user_id}_{timestamp}_{'596f423cdf22b174e43d0b48a36a8274759ec2a3'}"
        token = hashlib.sha256(token_string.encode()).hexdigest()[:32]
        
        # Set expiration (30 minutes from now)
        expires_at = datetime.now() + timedelta(minutes=30)
        
        # Store token
        self.user_tokens[user_id] = {
            'token': token,
            'expires_at': expires_at,
            'generated_at': datetime.now()
        }
        
        return token
    
    def verify_token(self, user_id, token):
        """Verify if token is valid for user"""
        token_info = self.user_tokens.get(user_id)
        if not token_info:
            return False
        
        if token_info['token'] != token:
            return False
        
        if token_info['expires_at'] <= datetime.now():
            return False
        
        return True
    
    def get_token_status(self, user_id):
        """Get token status for user"""
        token_info = self.user_tokens.get(user_id)
        if not token_info:
            return None
        
        return {
            'has_token': True,
            'expires_at': token_info['expires_at'],
            'is_valid': token_info['expires_at'] > datetime.now(),
            'minutes_left': max(0, (token_info['expires_at'] - datetime.now()).seconds // 60)
        }

# Global instance
user_limits = UserLimits()
