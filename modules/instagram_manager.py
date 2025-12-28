import os
import logging
import requests
import time
from datetime import datetime

logger = logging.getLogger("InstagramManager")

class InstagramManager:
    def __init__(self):
        logger.info("📱 Instagram Business/Creator Account Manager initialized")
        
        # Facebook/Instagram Graph API credentials
        self.access_token = os.getenv("IG_ACCESS_TOKEN")
        self.ig_business_account_id = os.getenv("IG_BUSINESS_ACCOUNT_ID")
        self.ig_user_id = os.getenv("IG_USER_ID")
        self.ig_page_id = os.getenv("IG_PAGE_ID")
        
        self._validate_credentials()
        
    def _validate_credentials(self):
        """Validate that all required credentials are set"""
        required_vars = {
            "IG_ACCESS_TOKEN": self.access_token,
            "IG_BUSINESS_ACCOUNT_ID": self.ig_business_account_id,
            "IG_USER_ID": self.ig_user_id,
            "IG_PAGE_ID": self.ig_page_id
        }
        
        missing = [var for var, value in required_vars.items() if not value]
        
        if missing:
            logger.error("❌ Missing Instagram Business API credentials:")
            for var in missing:
                logger.error(f"   - {var}")
            logger.error("💡 Please set these environment variables in Render")
            logger.error("💡 Get these from Facebook Developer Portal")
            self.valid = False
        else:
            logger.info("✅ All Instagram Business API credentials are set")
            self.valid = True
            
        # Optional: Test connection
        if self.valid:
            self.test_connection()
    
    def test_connection(self):
        """Test connection to Instagram Graph API"""
        try:
            logger.info("🔗 Testing Instagram Graph API connection...")
            
            # Test by getting basic page info
            url = f"https://graph.facebook.com/v17.0/{self.ig_page_id}"
            params = {
                "access_token": self.access_token,
                "fields": "id,name,instagram_business_account"
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            logger.info(f"✅ Instagram Graph API connection successful!")
            logger.info(f"   📄 Page: {data.get('name', 'Unknown')}")
            logger.info(f"   🆔 Page ID: {data.get('id')}")
            logger.info(f"   📱 Connected IG Account ID: {data.get('instagram_business_account', {}).get('id', 'Not found')}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Instagram Graph API connection failed: {e}")
            if hasattr(e, 'response') and e.response:
                try:
                    error_data = e.response.json()
                    logger.error(f"   Error details: {error_data}")
                except:
                    logger.error(f"   Status code: {e.response.status_code}")
            return False
    
    def _upload_media_to_instagram(self, media_url, media_type="REELS", caption=""):
        """
        Upload media to Instagram using Graph API
        Returns media container ID if successful
        """
        try:
            logger.info(f"📤 Creating media container for {media_type}...")
            
            # Step 1: Create media container
            url = f"https://graph.facebook.com/v17.0/{self.ig_business_account_id}/media"
            
            payload = {
                "media_type": media_type,
                "video_url": media_url if media_type == "REELS" else None,
                "image_url": media_url if media_type == "IMAGE" else None,
                "caption": caption,
                "access_token": self.access_token
            }
            
            # Remove None values
            payload = {k: v for k, v in payload.items() if v is not None}
            
            response = requests.post(url, data=payload, timeout=30)
            response.raise_for_status()
            result = response.json()
            
            if "id" not in result:
                logger.error(f"❌ Failed to create media container: {result}")
                return None
            
            media_container_id = result["id"]
            logger.info(f"✅ Media container created: {media_container_id}")
            
            # Step 2: Check media status (for videos, need to wait for processing)
            if media_type == "REELS":
                status_check_url = f"https://graph.facebook.com/v17.0/{media_container_id}"
                status_params = {
                    "access_token": self.access_token,
                    "fields": "status_code"
                }
                
                # Wait for video processing (max 60 seconds)
                max_wait = 60
                wait_time = 0
                
                while wait_time < max_wait:
                    status_response = requests.get(status_check_url, params=status_params, timeout=10)
                    status_data = status_response.json()
                    
                    status_code = status_data.get("status_code")
                    
                    if status_code == "FINISHED":
                        logger.info("✅ Video processing completed")
                        break
                    elif status_code == "ERROR":
                        logger.error(f"❌ Video processing error: {status_data}")
                        return None
                    else:
                        logger.info(f"⏳ Video processing: {status_code} (waiting {wait_time}s)")
                        time.sleep(5)
                        wait_time += 5
                
                if wait_time >= max_wait:
                    logger.warning("⚠️ Video processing timeout, attempting to publish anyway")
            
            return media_container_id
            
        except Exception as e:
            logger.error(f"❌ Failed to upload media to Instagram: {e}")
            if hasattr(e, 'response') and e.response:
                try:
                    error_data = e.response.json()
                    logger.error(f"   Error details: {error_data}")
                except:
                    logger.error(f"   Status code: {e.response.status_code}")
            return None
    
    def _publish_media(self, media_container_id):
        """Publish the media container to Instagram"""
        try:
            logger.info(f"🚀 Publishing media {media_container_id}...")
            
            url = f"https://graph.facebook.com/v17.0/{self.ig_business_account_id}/media_publish"
            payload = {
                "creation_id": media_container_id,
                "access_token": self.access_token
            }
            
            response = requests.post(url, data=payload, timeout=30)
            response.raise_for_status()
            result = response.json()
            
            if "id" not in result:
                logger.error(f"❌ Failed to publish media: {result}")
                return None
            
            media_id = result["id"]
            logger.info(f"✅ Media published successfully! Media ID: {media_id}")
            
            return media_id
            
        except Exception as e:
            logger.error(f"❌ Failed to publish media: {e}")
            if hasattr(e, 'response') and e.response:
                try:
                    error_data = e.response.json()
                    logger.error(f"   Error details: {error_data}")
                except:
                    logger.error(f"   Status code: {e.response.status_code}")
            return None
    
    def schedule_post(self, post_data):
        """
        Schedule/post to Instagram Business/Creator account
        post_data should contain: media_url, caption, title, mime_type
        """
        try:
            if not self.valid:
                logger.error("❌ Instagram credentials not valid")
                return False
            
            # Get data from post_data
            media_url = post_data.get('media_url') or post_data.get('public_media_url')
            caption = post_data.get('caption', 'Check out this track! #Music #Caribbean')
            title = post_data.get('title', 'Music Track')
            mime_type = post_data.get('mime_type', '')
            
            if not media_url:
                logger.error("❌ No media URL provided")
                return False
            
            logger.info(f"📤 Posting to Instagram Business Account: {title}")
            logger.info(f"   🔗 Media URL: {media_url[:60]}...")
            logger.info(f"   📝 Caption: {caption[:60]}...")
            
            # Determine media type
            if 'video' in mime_type.lower() or media_url.lower().endswith(('.mp4', '.mov', '.avi', '.mkv')):
                media_type = "REELS"
                logger.info("   🎬 Detected as video/REELS")
            else:
                media_type = "IMAGE"
                logger.info("   📸 Detected as image")
            
            # Upload media and get container ID
            media_container_id = self._upload_media_to_instagram(
                media_url=media_url,
                media_type=media_type,
                caption=caption
            )
            
            if not media_container_id:
                logger.error("❌ Failed to create media container")
                return False
            
            # Publish the media
            media_id = self._publish_media(media_container_id)
            
            if not media_id:
                logger.error("❌ Failed to publish media")
                return False
            
            logger.info(f"✅ Successfully posted to Instagram Business Account!")
            logger.info(f"   📊 Post ID: {media_id}")
            logger.info(f"   ⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Instagram posting error: {type(e).__name__}: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return False
    
    def schedule_reel(self, video_url, caption=""):
        """Schedule a reel specifically"""
        try:
            if not self.valid:
                logger.error("❌ Instagram credentials not valid")
                return False
            
            logger.info(f"🎬 Scheduling Reel: {video_url[:50]}...")
            
            media_container_id = self._upload_media_to_instagram(
                media_url=video_url,
                media_type="REELS",
                caption=caption
            )
            
            if not media_container_id:
                return False
            
            media_id = self._publish_media(media_container_id)
            
            if media_id:
                logger.info(f"✅ Reel scheduled successfully! Media ID: {media_id}")
                return True
            else:
                return False
                
        except Exception as e:
            logger.error(f"❌ Failed to schedule reel: {e}")
            return False
    
    def post_image(self, image_url, caption=""):
        """Post an image"""
        try:
            if not self.valid:
                logger.error("❌ Instagram credentials not valid")
                return False
            
            logger.info(f"📸 Posting Image: {image_url[:50]}...")
            
            media_container_id = self._upload_media_to_instagram(
                media_url=image_url,
                media_type="IMAGE",
                caption=caption
            )
            
            if not media_container_id:
                return False
            
            media_id = self._publish_media(media_container_id)
            
            if media_id:
                logger.info(f"✅ Image posted successfully! Media ID: {media_id}")
                return True
            else:
                return False
                
        except Exception as e:
            logger.error(f"❌ Failed to post image: {e}")
            return False
    
    def get_account_insights(self):
        """Get Instagram account insights"""
        try:
            if not self.valid:
                logger.error("❌ Instagram credentials not valid")
                return None
            
            url = f"https://graph.facebook.com/v17.0/{self.ig_business_account_id}/insights"
            params = {
                "access_token": self.access_token,
                "metric": "follower_count,impressions,reach,profile_views",
                "period": "day"
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            logger.info("📊 Instagram Account Insights:")
            for insight in data.get("data", []):
                logger.info(f"   📈 {insight.get('title')}: {insight.get('values', [{}])[0].get('value', 'N/A')}")
            
            return data
            
        except Exception as e:
            logger.error(f"❌ Failed to get insights: {e}")
            return None
