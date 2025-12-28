import os
import logging
from datetime import datetime
import tempfile
import traceback

logger = logging.getLogger("MediaProcessor")

class MediaProcessor:
    def __init__(self):
        logger.info("🎬 Media Processor initialized")
        self.cloud_storage = None
        self._initialize_cloud_storage()
        
    def _initialize_cloud_storage(self):
        """Initialize cloud storage with error handling"""
        try:
            from modules.cloud_storage import CloudStorage
            self.cloud_storage = CloudStorage()
        except Exception as e:
            logger.error(f"❌ Failed to initialize CloudStorage: {e}")
            logger.error(traceback.format_exc())
            self.cloud_storage = None
        
    def process_new_links(self):
        """
        Find and process media files from Google Drive
        """
        if not self.cloud_storage:
            logger.error("❌ CloudStorage not initialized")
            return []
            
        try:
            # Get files from Google Drive source folder
            source_folder_id = os.getenv("SOURCE_FOLDER_ID")
            if not source_folder_id:
                logger.error("❌ SOURCE_FOLDER_ID environment variable not set")
                return []
            
            logger.info(f"📂 Scanning Google Drive folder: {source_folder_id}")
            
            # Try to list files
            try:
                files = self.cloud_storage.list_files(source_folder_id)
            except Exception as e:
                logger.error(f"❌ Failed to list files from Google Drive: {e}")
                logger.error(f"Error details: {traceback.format_exc()}")
                return []
            
            if not files:
                logger.info("📭 No files found in source folder")
                # Let's check what's actually in the folder
                self._debug_folder_contents(source_folder_id)
                return []
            
            logger.info(f"📁 Found {len(files)} files in Google Drive")
            
            # Log first few files for debugging
            for i, file_info in enumerate(files[:3]):
                logger.info(f"  File {i+1}: {file_info.get('title', 'Unknown')} - Type: {file_info.get('mimeType', 'Unknown')}")
            
            # Process files into drafts (simplified version)
            drafts = []
            for file_info in files[:3]:  # Process max 3 files at a time
                try:
                    # Skip non-media files
                    mime_type = file_info.get('mimeType', '')
                    title = file_info.get('title', '')
                    
                    # Check if it's a media file
                    is_media = any(ext in title.lower() for ext in ['.mp4', '.mov', '.avi', '.mkv', '.mp3', '.wav', '.jpg', '.jpeg', '.png', '.gif'])
                    
                    if not is_media and not any(media_type in mime_type.lower() for media_type in ['video', 'image', 'audio']):
                        logger.debug(f"⏭️ Skipping non-media file: {title}")
                        continue
                    
                    # Create draft object without downloading (for now)
                    draft = {
                        "type": "media",
                        "title": title,
                        "caption": f"🎵 {os.path.splitext(title)[0]} #Music #Caribbean",
                        "media_path": None,  # We'll handle this differently
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
            logger.error(f"Full traceback: {traceback.format_exc()}")
            return []
    
    def _debug_folder_contents(self, folder_id):
        """Debug method to check folder contents"""
        try:
            logger.info(f"🔍 Debugging folder {folder_id}")
            
            # Try a simpler query
            query = f"'{folder_id}' in parents"
            file_list = self.cloud_storage.drive.ListFile({'q': query}).GetList()
            
            if file_list:
                logger.info(f"📂 Found {len(file_list)} items in folder:")
                for i, file in enumerate(file_list[:5]):
                    logger.info(f"  {i+1}. {file['title']} ({file['mimeType']})")
            else:
                logger.info("📭 Folder appears to be empty")
                
        except Exception as e:
            logger.error(f"❌ Debug failed: {e}")
