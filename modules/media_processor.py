import logging

logger = logging.getLogger("MediaProcessor")

class MediaProcessor:
    def __init__(self):
        logger.info("🎬 Media Processor initialized")

    def process_new_links(self):
        """
        Returns media drafts if available.
        Currently safe noop until ingestion is wired.
        """
        logger.info("📂 Media scan complete — no new media found")
        return []
