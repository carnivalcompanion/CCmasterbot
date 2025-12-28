import os
import logging
import tempfile
import requests
from instagrapi import Client
from instagrapi.exceptions import LoginRequired, PleaseWaitFewMinutes, ChallengeRequired
import time

logger = logging.getLogger("InstagramManager")

class InstagramManager:
    def __init__(self):
        logger.info("📱 Instagram Manager initialized")
        self.client = None
        self.connected = False
        self._login()
        
    def _login(self):
        """Login to Instagram using instagrapi"""
        try:
            self.client = Client()
            
            # Get credentials from environment
            username = os.getenv("INSTA_USERNAME")
            password = os.getenv("INSTA_PASSWORD")
            
            if not username or not password:
                logger.error("❌ Instagram credentials not set in environment")
                logger.error("   Please set INSTA_USERNAME and INSTA_PASSWORD in Render environment variables")
                logger.error("   Current INSTA_USERNAME: " + ("Set" if username else "NOT SET"))
                logger.error("   Current INSTA_PASSWORD: " + ("Set" if password else "NOT SET"))
                return False
            
            logger.info(f"🔐 Attempting Instagram login for: {username}")
            
            # Try to load previous session if it exists
            session_file = "instagram_session.json"
            if os.path.exists(session_file):
                try:
                    self.client.load_settings(session_file)
                    logger.info("📁 Loaded previous session")
                except:
                    logger.info("📁 No valid session found, creating new login")
            
            # Login
            self.client.login(username, password)
            
            # Save session for future use
            self.client.dump_settings(session_file)
            
            # Test connection by getting user info
            user_id = self.client.user_id
            user_info = self.client.user_info(user_id)
            
            self.connected = True
            logger.info(f"✅ Successfully logged into Instagram")
            logger.info(f"   👤 Username: {user_info.username}")
            logger.info(f"   📊 Followers: {user_info.follower_count}")
            logger.info(f"   🔒 Private: {user_info.is_private}")
            
            return True
            
        except (LoginRequired, PleaseWaitFewMinutes, ChallengeRequired) as e:
            logger.error(f"❌ Instagram login error: {e}")
            logger.info("💡 This might be due to:")
            logger.info("   1. Incorrect username/password")
            logger.info("   2. 2FA enabled (instagrapi may not support 2FA)")
            logger.info("   3. Instagram suspecting suspicious login")
            return False
            
        except Exception as e:
            logger.error(f"❌ Instagram login failed: {type(e).__name__}: {e}")
            return False
    
    def _download_media(self, media_url, file_extension=".mp4"):
        """Download media from URL to a temporary file"""
        try:
            logger.info(f"📥 Downloading media from: {media_url[:50]}...")
            
            # Create temporary file
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=file_extension)
            temp_path = temp_file.name
            temp_file.close()
            
            # Download the file
            response = requests.get(media_url, stream=True, timeout=30)
            response.raise_for_status()
            
            with open(temp_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            # Check file size
            file_size = os.path.getsize(temp_path)
            logger.info(f"📦 Downloaded: {file_size / (1024*1024):.2f} MB")
            
            if file_size == 0:
                logger.error("❌ Downloaded file is empty")
                os.remove(temp_path)
                return None
            
            return temp_path
            
        except Exception as e:
            logger.error(f"❌ Failed to download media: {e}")
            return None
    
    def schedule_post(self, post_data):
        """
        Post to Instagram using instagrapi
        post_data should contain: media_url, caption, title
        """
        try:
            if not self.connected or not self.client:
                logger.error("❌ Instagram client not connected")
                if not self._login():
                    return False
            
            # Get data from post_data
            media_url = post_data.get('media_url') or post_data.get('public_media_url')
            caption = post_data.get('caption', 'Check out this track! #Music #Caribbean')
            title = post_data.get('title', 'Music Track')
            
            if not media_url:
                logger.error("❌ No media URL provided")
                return False
            
            logger.info(f"📤 Posting to Instagram: {title}")
            logger.info(f"   🔗 Source URL: {media_url[:60]}...")
            logger.info(f"   📝 Caption: {caption[:60]}...")
            
            # Determine file type from URL or mime type
            file_extension = ".mp4"  # Default to mp4 for videos
            if post_data.get('mime_type'):
                if 'image' in post_data['mime_type']:
                    file_extension = ".jpg"
            
            # Download the media
            local_path = self._download_media(media_url, file_extension)
            if not local_path:
                logger.error("❌ Failed to download media")
                return False
            
            # Post to Instagram
            success = False
            try:
                if file_extension in ['.mp4', '.mov', '.avi']:
                    # Post as video/reel
                    logger.info("🎬 Uploading as video...")
                    media = self.client.video_upload(
                        path=local_path,
                        caption=caption
                    )
                    logger.info(f"✅ Video uploaded successfully! Media ID: {media.id}")
                    success = True
                else:
                    # Post as photo
                    logger.info("📸 Uploading as photo...")
                    media = self.client.photo_upload(
                        path=local_path,
                        caption=caption
                    )
                    logger.info(f"✅ Photo uploaded successfully! Media ID: {media.id}")
                    success = True
                    
            except Exception as upload_error:
                logger.error(f"❌ Instagram upload failed: {upload_error}")
                success = False
            finally:
                # Clean up temporary file
                try:
                    os.remove(local_path)
                    logger.debug("🧹 Cleaned up temporary file")
                except:
                    pass
            
            return success
            
        except Exception as e:
            logger.error(f"❌ Instagram posting error: {type(e).__name__}: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return False
    
    def post_video(self, video_path, caption=""):
        """Post a video to Instagram (direct file path)"""
        try:
            if not self.connected or not self.client:
                logger.error("❌ Instagram client not connected")
                return False
            
            if not os.path.exists(video_path):
                logger.error(f"❌ Video file not found: {video_path}")
                return False
            
            logger.info(f"🎬 Uploading video: {os.path.basename(video_path)}")
            
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
        """Post a photo to Instagram (direct file path)"""
        try:
            if not self.connected or not self.client:
                logger.error("❌ Instagram client not connected")
                return False
            
            if not os.path.exists(photo_path):
                logger.error(f"❌ Photo file not found: {photo_path}")
                return False
            
            logger.info(f"📸 Uploading photo: {os.path.basename(photo_path)}")
            
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
        """Test Instagram connection and get account info"""
        try:
            if not self.connected or not self.client:
                if not self._login():
                    return False
            
            user_id = self.client.user_id
            user_info = self.client.user_info(user_id)
            
            logger.info("✅ Instagram connection test successful")
            logger.info(f"   Account: {user_info.username}")
            logger.info(f"   Full Name: {user_info.full_name}")
            logger.info(f"   Followers: {user_info.follower_count}")
            logger.info(f"   Following: {user_info.following_count}")
            logger.info(f"   Posts: {user_info.media_count}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Instagram connection test failed: {e}")
            return False
