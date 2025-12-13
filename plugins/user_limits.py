# user_limits.py - Updated with direct Telegram verification

import time
import hashlib
import json
import base64
from datetime import datetime, timedelta
from config import Config

class UserLimits:
    def __init__(self):
        self.user_file_counts = {}
        self.user_tokens = {}
        self.secret_key = "596f423cdf22b174e43d0b48a36a8274759ec2a3"
        
    async def check_user_limit(self, user_id):
        """Check if user has exceeded file limit and needs ad token"""
        if str(user_id) in map(str, Config.ADMIN) or user_id in Config.ADMIN:
            return True, None  # Admins have no limits
            
        # Get user's file count
        file_count = self.user_file_counts.get(user_id, 0)
        
        print(f"[LIMIT CHECK] User {user_id}: {file_count}/12 files")
        
        if file_count >= 12:
            # Check if user has valid token
            token_info = self.user_tokens.get(user_id)
            if token_info and token_info['expires_at'] > datetime.now():
                print(f"[LIMIT CHECK] User {user_id} has valid token")
                return True, token_info  # Has valid token
            print(f"[LIMIT CHECK] User {user_id} needs token")
            return False, token_info  # Needs new token
        
        return True, None
    
    def increment_file_count(self, user_id):
        """Increment file count for user"""
        if str(user_id) not in map(str, Config.ADMIN) and user_id not in Config.ADMIN:
            current = self.user_file_counts.get(user_id, 0)
            self.user_file_counts[user_id] = current + 1
            print(f"[COUNT] User {user_id}: {self.user_file_counts[user_id]}/12 files")
    
    def reset_file_count(self, user_id):
        """Reset file count for user"""
        self.user_file_counts[user_id] = 0
        print(f"[RESET] User {user_id} count reset to 0")
    
    def generate_token(self, user_id):
        """Generate token for user"""
        # Create token data
        token_data = {
            'user_id': user_id,
            'timestamp': time.time(),
            'expires': time.time() + 1800,  # 30 minutes
        }
        
        # Convert to string and hash
        token_string = json.dumps(token_data) + self.secret_key
        token_hash = hashlib.sha256(token_string.encode()).hexdigest()[:16]
        
        # Create full token
        token = f"{user_id}:{token_hash}"
        
        # Store in memory
        self.user_tokens[user_id] = {
            'token': token,
            'expires_at': datetime.fromtimestamp(token_data['expires']),
            'generated_at': datetime.now()
        }
        
        print(f"[TOKEN] Generated for user {user_id}: {token[:10]}...")
        return token
    
    def verify_token(self, user_id, token):
        """Verify if token is valid for user"""
        token_info = self.user_tokens.get(user_id)
        
        if not token_info:
            print(f"[TOKEN] No token found for user {user_id}")
            return False
        
        if token_info['token'] != token:
            print(f"[TOKEN] Token mismatch for user {user_id}")
            return False
        
        if token_info['expires_at'] <= datetime.now():
            print(f"[TOKEN] Token expired for user {user_id}")
            # Remove expired token
            del self.user_tokens[user_id]
            return False
        
        print(f"[TOKEN] Token valid for user {user_id}")
        return True
    
    def get_token_status(self, user_id):
        """Get token status for user"""
        token_info = self.user_tokens.get(user_id)
        if not token_info:
            return None
        
        time_left = token_info['expires_at'] - datetime.now()
        minutes_left = max(0, int(time_left.total_seconds() // 60))
        seconds_left = int(time_left.total_seconds() % 60)
        
        return {
            'has_token': True,
            'expires_at': token_info['expires_at'],
            'is_valid': token_info['expires_at'] > datetime.now(),
            'minutes_left': minutes_left,
            'seconds_left': seconds_left
        }

# Global instance
user_limits = UserLimits()
