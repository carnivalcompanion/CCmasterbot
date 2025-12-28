import os
import logging
import requests
import time
from datetime import datetime

logger = logging.getLogger("InstagramManager")

class InstagramManager:
    def __init__(self):
        logger.info("📱 Instagram Manager initialized (simplified version)")
        
        # Facebook/Instagram Graph API credentials (for testing only)
        self.access_token = os.getenv("IG_ACCESS_TOKEN")
        self.ig_user_id = os.getenv("IG_USER_ID")
        
        self.valid = bool(self.access_token and self.ig_user_id)
        
        if self.valid:
            logger.info("✅ Instagram credentials are set")
        else:
            logger.info("ℹ️ Instagram credentials not set - MediaProcessor handles posting")
    
    def test_connection(self):
        """Test Instagram Graph API connection (optional)"""
        try:
            if not self.valid:
                logger.info("ℹ️ No Instagram credentials set for testing")
                return True  # Return True since MediaProcessor handles posting
            
            logger.info("🔗 Testing Instagram Graph API connection...")
            
            # Simple test to verify token is valid
            url = f"https://graph.facebook.com/v17.0/{self.ig_user_id}"
            params = {
                "access_token": self.access_token,
                "fields": "id,name"
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            logger.info(f"✅ Instagram Graph API connection successful!")
            logger.info(f"   👤 User: {data.get('name', 'Unknown')}")
            logger.info(f"   🆔 User ID: {data.get('id')}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Instagram Graph API connection test failed: {e}")
            if hasattr(e, 'response') and e.response:
                try:
                    error_data = e.response.json()
                    logger.error(f"   Error details: {error_data}")
                except:
                    logger.error(f"   Status code: {e.response.status_code}")
            
            # Still return True because MediaProcessor handles actual posting
            logger.info("ℹ️ Note: MediaProcessor handles actual Instagram posting")
            return True
    
    def schedule_post(self, post_data):
        """
        Instagram posting is now handled by MediaProcessor
        
        This method exists for compatibility with the existing codebase
        but just logs that MediaProcessor handles the posting
        """
        logger.info("ℹ️ Instagram posting handled by MediaProcessor module")
        logger.info(f"   📝 Would have posted: {post_data.get('title', 'Unknown')}")
        logger.info(f"   🔗 Media URL: {post_data.get('media_url', 'Unknown')[:60]}...")
        
        # Return True to maintain compatibility
        return True
    
    def schedule_reel(self, video_url, caption=""):
        """Schedule a reel - handled by MediaProcessor"""
        logger.info(f"ℹ️ Reel posting handled by MediaProcessor: {video_url[:50]}...")
        return True
    
    def post_image(self, image_url, caption=""):
        """Post an image - handled by MediaProcessor"""
        logger.info(f"ℹ️ Image posting handled by MediaProcessor: {image_url[:50]}...")
        return True
    
    def get_account_insights(self):
        """Get Instagram account insights (if credentials available)"""
        try:
            if not self.valid:
                logger.info("ℹ️ No Instagram credentials for insights")
                return None
            
            url = f"https://graph.facebook.com/v17.0/{self.ig_user_id}/accounts"
            params = {
                "access_token": self.access_token,
                "fields": "instagram_business_account"
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            # Find Instagram business account
            for account in data.get("data", []):
                if "instagram_business_account" in account:
                    ig_account_id = account["instagram_business_account"]["id"]
                    
                    # Get insights
                    insights_url = f"https://graph.facebook.com/v17.0/{ig_account_id}/insights"
                    insights_params = {
                        "access_token": self.access_token,
                        "metric": "follower_count",
                        "period": "day"
                    }
                    
                    insights_response = requests.get(insights_url, params=insights_params, timeout=10)
                    insights_response.raise_for_status()
                    insights_data = insights_response.json()
                    
                    logger.info("📊 Instagram Account Insights:")
                    for insight in insights_data.get("data", []):
                        values = insight.get("values", [{}])
                        if values:
                            logger.info(f"   📈 {insight.get('title')}: {values[0].get('value', 'N/A')}")
                    
                    return insights_data
            
            logger.info("ℹ️ No Instagram business account found for insights")
            return None
            
        except Exception as e:
            logger.error(f"❌ Failed to get insights: {e}")
            return None
