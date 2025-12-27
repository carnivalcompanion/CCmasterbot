import os
import logging
import requests

logger = logging.getLogger("InstagramManager")

class InstagramManager:
    def schedule_post(self, draft):
        if not draft.get("public_media_url"):
            logger.warning("⚠️ No media URL, skipping post")
            return False

        access_token = os.getenv("INSTA_ACCESS_TOKEN")
        ig_id = os.getenv("IG_BUSINESS_ACCOUNT_ID")

        if not access_token or not ig_id:
            logger.error("❌ Instagram credentials missing")
            return False

        response = requests.post(
            f"https://graph.facebook.com/v17.0/{ig_id}/media",
            data={
                "access_token": access_token,
                "media_type": "REELS",
                "video_url": draft["public_media_url"],
                "caption": draft.get("caption", "")
            }
        ).json()

        if "id" not in response:
            logger.error(f"❌ Instagram API error: {response}")
            return False

        logger.info("📤 Instagram reel scheduled successfully")
        return True

