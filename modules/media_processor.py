import os
import logging
from datetime import datetime
import tempfile
from modules.cloud_storage import CloudStorage

logger = logging.getLogger("MediaProcessor")

class MediaProcessor:
    def __init__(self):
        logger.info("🎬 Media Processor initialized")
        self.cloud_storage = CloudStorage()
        
    def process_new_links(self):
        """
        Find and process media files from Google Drive
        """
        try:
            # Get files from Google Drive source folder
            source_folder_id = os.getenv("SOURCE_FOLDER_ID")
            if not source_folder_id:
                logger.error("❌ SOURCE_FOLDER_ID environment variable not set")
                return []
            
            logger.info(f"📂 Scanning Google Drive folder: {source_folder_id}")
            files = self.cloud_storage.list_files(source_folder_id)
            
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
                    if not any(media_type in mime_type for media_type in ['video', 'image', 'audio']):
                        logger.debug(f"⏭️ Skipping non-media file: {file_info['title']}")
                        continue
                    
                    # Download the file locally
                    temp_dir = tempfile.gettempdir()
                    local_path = os.path.join(temp_dir, file_info['title'])
                    
                    logger.info(f"📥 Downloading: {file_info['title']}")
                    self.cloud_storage.download_file(file_info['id'], local_path)
                    
                    # Check if file was downloaded
                    if not os.path.exists(local_path):
                        logger.warning(f"⚠️ Failed to download: {file_info['title']}")
                        continue
                    
                    # Create draft object
                    draft = {
                        "type": "media",
                        "title": file_info['title'],
                        "caption": f"🎵 {os.path.splitext(file_info['title'])[0]} #Music #Caribbean",
                        "media_path": local_path,
                        "file_id": file_info['id'],
                        "mime_type": mime_type,
                        "created_at": datetime.utcnow().isoformat(),
                        "source": "google_drive",
                        "scheduled_time": None,
                        "status": "pending"
                    }
                    
                    drafts.append(draft)
                    logger.info(f"✅ Processed: {file_info['title']}")
                    
                except Exception as e:
                    logger.error(f"❌ Error processing file {file_info.get('title', 'unknown')}: {e}")
                    continue
            
            logger.info(f"📊 Media scan complete — {len(drafts)} new media files processed")
            return drafts
            
        except Exception as e:
            logger.error(f"❌ Failed to process media links: {e}")
            return []
