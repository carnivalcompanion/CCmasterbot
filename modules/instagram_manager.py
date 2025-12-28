import os
import logging
from instagrapi import Client
from instagrapi.exceptions import LoginRequired

logger = logging.getLogger("InstagramManager")

class InstagramManager:
    def __init__(self):
        logger.info("📱 Instagram Manager initialized")
        self.client = None
        self._login()
        
    def _login(self):
        """Login to Instagram"""
        try:
            self.client = Client()
            
            # Get credentials from environment
            username = os.getenv("INSTA_USERNAME")
            password = os.getenv("INSTA_PASSWORD")
            
            if not username or not password:
                logger.error("❌ Instagram credentials not set in environment")
                logger.error("Set INSTA_USERNAME and INSTA_PASSWORD environment variables")
                return False
            
            logger.info(f"🔐 Logging into Instagram as: {username}")
            
            # Try to login
            self.client.login(username, password)
            
            logger.info("✅ Successfully logged into Instagram")
            return True
            
        except Exception as e:
            logger.error(f"❌ Instagram login failed: {e}")
            logger.info("💡 Make sure INSTA_USERNAME and INSTA_PASSWORD are correct")
            self.client = None
            return False
    
    def schedule_post(self, post_data):
        """
        Schedule a post to Instagram
        post_data should contain: media_url, caption, title
        """
        try:
            if not self.client:
                logger.error("❌ Instagram client not initialized")
                return False
            
            # Get data from post_data
            media_url = post_data.get('media_url') or post_data.get('public_media_url')
            caption = post_data.get('caption', '')
            title = post_data.get('title', 'Untitled')
            
            if not media_url:
                logger.warning("⚠️ No media URL provided")
                return False
            
            logger.info(f"📤 Scheduling Instagram post: {title}")
            logger.info(f"🔗 Media URL: {media_url}")
            logger.info(f"📝 Caption: {caption[:50]}...")
            
            # For now, just log and simulate success
            # In a real implementation, you would:
            # 1. Download the media from the URL
            # 2. Upload to Instagram
            # 3. Post with caption
            
            logger.info(f"✅ Would post to Instagram: {title} - {caption[:30]}...")
            logger.info("💡 Actual posting requires downloading and uploading media")
            
            # Return True for testing
            return True
            
        except Exception as e:
            logger.error(f"❌ Instagram posting error: {e}")
            return False
    
    def post_video(self, video_path, caption=""):
        """Post a video to Instagram (requires local file path)"""
        try:
            if not self.client:
                logger.error("❌ Instagram client not initialized")
                return False
            
            if not os.path.exists(video_path):
                logger.error(f"❌ Video file not found: {video_path}")
                return False
            
            logger.info(f"🎬 Uploading video: {os.path.basename(video_path)}")
            
            # Upload video to Instagram
            # Note: instagrapi requires local file paths, not URLs
            media = self.client.video_upload(
                path=video_path,
                caption=caption
            )
            
            logger.info(f"✅ Video posted successfully! Media ID: {media.id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Video upload failed: {e}")
            return False
    
    def post_photo(self, photo_path, caption=""):
        """Post a photo to Instagram (requires local file path)"""
        try:
            if not self.client:
                logger.error("❌ Instagram client not initialized")
                return False
            
            if not os.path.exists(photo_path):
                logger.error(f"❌ Photo file not found: {photo_path}")
                return False
            
            logger.info(f"📸 Uploading photo: {os.path.basename(photo_path)}")
            
            # Upload photo to Instagram
            media = self.client.photo_upload(
                path=photo_path,
                caption=caption
            )
            
            logger.info(f"✅ Photo posted successfully! Media ID: {media.id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Photo upload failed: {e}")
            return False
    
    def test_connection(self):
        """Test Instagram connection"""
        try:
            if not self.client:
                logger.error("❌ Instagram client not initialized")
                return False
            
            # Get user info to test connection
            user_id = self.client.user_id
            user_info = self.client.user_info(user_id)
            
            logger.info(f"✅ Instagram connection test successful")
            logger.info(f"   User: {user_info.username}")
            logger.info(f"   Followers: {user_info.follower_count}")
            logger.info(f"   Following: {user_info.following_count}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Instagram connection test failed: {e}")
            return False
        logger.info("📤 Instagram reel scheduled successfully")
        return True

