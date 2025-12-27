import logging
from datetime import datetime, timedelta

logger = logging.getLogger("ContentScheduler")

class ContentScheduler:
    def __init__(self, interval_minutes=30):
        self.interval_minutes = interval_minutes

    def schedule_drafts(self, drafts):
        """
        Adds scheduled_time to each draft
        """
        scheduled = []
        now = datetime.utcnow()

        for index, draft in enumerate(drafts):
            draft["scheduled_time"] = (
                now + timedelta(minutes=self.interval_minutes * index)
            ).isoformat()

            draft.setdefault("status", "scheduled")
            scheduled.append(draft)

        logger.info(f"📅 Scheduled {len(scheduled)} drafts")
        return scheduled
