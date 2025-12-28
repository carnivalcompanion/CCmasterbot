import os
import logging
from datetime import datetime

logger = logging.getLogger("MediaProcessor")

class MediaProcessor:
    def __init__(self):
        logger.info("🎬 Media Processor initialized")
        
    def process_new_links(self):
        """
        Find and process media files from Google Drive
        """
        try:
            # Import here to avoid circular imports
            from modules.cloud_storage import CloudStorage
            cloud_storage = CloudStorage()
            
            # Get files from Google Drive source folder
            source_folder_id = os.getenv("SOURCE_FOLDER_ID")
            if not source_folder_id:
                logger.error("❌ SOURCE_FOLDER_ID environment variable not set")
                return []
            
            logger.info(f"📂 Scanning Google Drive folder: {source_folder_id}")
            
            # Try to list files
            try:
                files = cloud_storage.list_files(source_folder_id)
            except Exception as e:
                logger.error(f"❌ Failed to list files from Google Drive: {e}")
                return []
            
            if not files:
                logger.info("📭 No files found in source folder")
                return []
            
            logger.info(f"📁 Found {len(files)} files in Google Drive")
            
            # Process files into drafts
            drafts = []
            for file_info in files[:5]:  # Process max 5 files at a time
                try:
                    # Skip non-media files
                    mime_type = file_info.get('mimeType', '')
                    title = file_info.get('title', '')
                    
                    # Check if it's a media file by extension
                    media_extensions = ['.mp4', '.mov', '.avi', '.mkv', '.mp3', '.wav', '.jpg', '.jpeg', '.png', '.gif']
                    is_media = any(title.lower().endswith(ext) for ext in media_extensions)
                    
                    if not is_media:
                        logger.debug(f"⏭️ Skipping non-media file: {title}")
                        continue
                    
                    # Create draft object
                    draft = {
                        "type": "media",
                        "title": title,
                        "caption": f"🎵 {os.path.splitext(title)[0]} #Music #Caribbean",
                        "media_path": None,
                        "file_id": file_info['id'],
                        "mime_type": mime_type,
                        "created_at": datetime.utcnow().isoformat(),
                        "source": "google_drive",
                        "scheduled_time": None,
                        "status": "pending"
                    }
                    
                    drafts.append(draft)
                    logger.info(f"✅ Added to queue: {title}")
                    
                except Exception as e:
                    logger.error(f"❌ Error processing file {file_info.get('title', 'unknown')}: {e}")
                    continue
            
            logger.info(f"📊 Media scan complete — {len(drafts)} media files queued")
            return drafts
            
        except Exception as e:
            logger.error(f"❌ Failed to process media links: {e}")
            return []
