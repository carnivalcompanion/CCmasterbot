import logging
from datetime import datetime

logger = logging.getLogger("CaribbeanContentEngine")

class CaribbeanContentEngine:
    def __init__(self):
        logger.info("🎭 Caribbean Content Engine initialized")

    def generate_drafts(self):
        """
        Generates culture-based text drafts
        """
        captions = [
            "🎭 Carnival is culture, not a costume.",
            "🔊 New music. New energy. Same roots.",
            "🇯🇲 Caribbean vibes — loud, proud, unstoppable.",
            "🔥 If you know, you know. Carnival Companion."
        ]

        drafts = []
        for caption in captions:
            drafts.append({
                "type": "text",
                "caption": caption,
                "media_path": None,
                "created_at": datetime.utcnow().isoformat(),
                "source": "content_engine"
            })

        logger.info(f"📝 Generated {len(drafts)} content drafts")
        return drafts
