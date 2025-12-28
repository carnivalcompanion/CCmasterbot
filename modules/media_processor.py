import os
import logging
import tempfile
import subprocess
import time
from datetime import datetime
from pydrive2.drive import GoogleDrive
from oauth2client.service_account import ServiceAccountCredentials
import requests

logger = logging.getLogger("MediaProcessor")

class MediaProcessor:
    def __init__(self):
        logger.info("🎬 Media Processor initialized")
        self.drive = self._authenticate_drive()
        self.source_folder_id = os.getenv("SOURCE_FOLDER_ID")
        self.processed_folder_id = os.getenv("PROCESSED_FOLDER_ID")
        self.logo_file = os.getenv("LOGO_FILE", "logo.png")
        self.max_duration = 90  # seconds
        
        # Instagram API credentials (for posting)
        self.ig_access_token = os.getenv("IG_ACCESS_TOKEN")
        self.ig_business_account_id = os.getenv("IG_BUSINESS_ACCOUNT_ID")
        self.ig_user_id = os.getenv("IG_USER_ID")
    
    def _authenticate_drive(self):
        """Authenticate with Google Drive"""
        try:
            scopes = ["https://www.googleapis.com/auth/drive"]
            
            # Try to read service account from environment variable or secret file
            service_account_json = os.getenv("GOOGLE_SERVICE_ACCOUNT")
            if service_account_json:
                try:
                    import json
                    credentials_dict = json.loads(service_account_json)
                    credentials = ServiceAccountCredentials.from_json_keyfile_dict(
                        credentials_dict, scopes
                    )
                except:
                    # If it's a file path
                    credentials = ServiceAccountCredentials.from_json_keyfile_name(
                        service_account_json, scopes
                    )
            else:
                # Try secret file
                secret_file_path = '/etc/secrets/google-service-account.json'
                if os.path.exists(secret_file_path):
                    credentials = ServiceAccountCredentials.from_json_keyfile_name(
                        secret_file_path, scopes
                    )
                else:
                    raise RuntimeError("Google Service Account credentials not found")
            
            return GoogleDrive(credentials)
            
        except Exception as e:
            logger.error(f"❌ Google Drive authentication failed: {e}")
            raise
    
    def _get_duration(self, path):
        """Get video duration using ffprobe"""
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            path
        ]
        try:
            out = subprocess.check_output(cmd).decode().strip()
            return float(out)
        except Exception as e:
            logger.error(f"❌ Could not get video duration: {e}")
            return 0
    
    def _extract_segment(self, input_path, output_path):
        """Extract max 90s segment from video"""
        duration = self._get_duration(input_path)
        logger.info(f"🎬 Video duration: {duration:.1f}s")
        
        t = min(duration, self.max_duration)
        cmd = [
            "ffmpeg", "-i", input_path, "-t", str(t),
            "-c:v", "libx264", "-preset", "fast", "-crf", "22",
            "-c:a", "aac", "-b:a", "128k", "-ar", "48000",
            "-vf", "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black",
            "-movflags", "+faststart", "-y", output_path
        ]
        
        logger.info(f"✂️ Extracting {t}s segment")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        
        if result.returncode != 0:
            logger.error(f"❌ FFmpeg error: {result.stderr[:300]}")
            return False
        return True
    
    def _add_bounce_logo(self, input_path, output_path):
        """Add bouncing logo in black bars (16:9 video)"""
        # Create filter for bouncing logo in black bars only
        bounce_filter = (
            "[0:v]scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black[bg];"
            f"[1:v]scale=400:-1[logo];"
            "[bg][logo]overlay="
            "x='(W-w)/2+120*sin(2.1*PI*t/10)+80*cos(1.6*PI*t/6)':"
            "y='if(gt(Y,H/9),(H/9-h)/2,if(lt(Y,8*H/9),(H/9-h)/2,0))':"
            "enable='between(t,0,30)'"
        )
        
        cmd = [
            "ffmpeg", "-i", input_path, "-i", self.logo_file,
            "-filter_complex", bounce_filter,
            "-c:v", "libx264", "-preset", "veryfast",
            "-c:a", "copy", "-y", output_path
        ]
        
        logger.info(f"🎨 Adding bouncing logo")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        
        if result.returncode != 0:
            logger.error(f"❌ FFmpeg error: {result.stderr[:300]}")
            return False
        return True
    
    def _upload_to_drive(self, local_path, folder_id):
        """Upload file to Google Drive and make it public"""
        filename = os.path.basename(local_path)
        
        file = self.drive.CreateFile({
            "title": filename,
            "parents": [{"id": folder_id}]
        })
        
        file.SetContentFile(local_path)
        file.Upload()
        
        # Make file publicly accessible
        file.InsertPermission({
            "type": "anyone",
            "value": "anyone",
            "role": "reader"
        })
        
        file_url = f"https://drive.google.com/uc?export=download&id={file['id']}"
        logger.info(f"✅ Uploaded to Google Drive: {file_url}")
        
        return {
            "url": file_url,
            "file_id": file['id'],
            "title": filename
        }
    
    def _post_to_instagram(self, video_url, caption=""):
        """Post video to Instagram using Meta Graph API"""
        if not self.ig_access_token or not self.ig_user_id:
            logger.warning("⚠️ Instagram credentials not set, skipping post")
            return False
        
        try:
            # Step 1: Create media container
            api_url = f"https://graph.facebook.com/v17.0/{self.ig_user_id}/media"
            payload = {
                "video_url": video_url,
                "caption": caption,
                "access_token": self.ig_access_token,
            }
            
            logger.info(f"📤 Creating Instagram media container...")
            resp = requests.post(api_url, data=payload, timeout=30)
            
            if resp.status_code != 200:
                logger.error(f"❌ Instagram creation failed: {resp.text}")
                return False
            
            media_id = resp.json().get("id")
            logger.info(f"✅ Media container created: {media_id}")
            
            # Step 2: Publish
            publish_url = f"https://graph.facebook.com/v17.0/{self.ig_user_id}/media_publish"
            resp2 = requests.post(publish_url, data={
                "creation_id": media_id,
                "access_token": self.ig_access_token
            }, timeout=30)
            
            if resp2.status_code != 200:
                logger.error(f"❌ Instagram publish failed: {resp2.text}")
                return False
            
            logger.info(f"📱 Posted to Instagram successfully!")
            return True
            
        except Exception as e:
            logger.error(f"❌ Instagram posting error: {e}")
            return False
    
    def process_new_links(self):
        """
        Main method: Find videos, process them, upload, and post to Instagram
        Returns: List of processed media drafts
        """
        try:
            if not self.source_folder_id:
                logger.error("❌ SOURCE_FOLDER_ID not set")
                return []
            
            logger.info(f"📂 Scanning Google Drive folder: {self.source_folder_id}")
            
            # List files in source folder
            query = f"'{self.source_folder_id}' in parents and trashed=false"
            files = self.drive.ListFile({'q': query}).GetList()
            
            if not files:
                logger.info("📭 No files found in source folder")
                return []
            
            logger.info(f"📁 Found {len(files)} files")
            
            processed_drafts = []
            
            for file_obj in files:
                try:
                    filename = file_obj['title']
                    logger.info(f"🔧 Processing: {filename}")
                    
                    # Download file
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp_in:
                        input_path = tmp_in.name
                    
                    file_obj.GetContentFile(input_path)
                    
                    # Extract segment (max 90s)
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp_seg:
                        seg_path = tmp_seg.name
                    
                    if not self._extract_segment(input_path, seg_path):
                        os.remove(input_path)
                        continue
                    
                    # Add bouncing logo
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp_final:
                        final_path = tmp_final.name
                    
                    if not self._add_bounce_logo(seg_path, final_path):
                        os.remove(input_path)
                        os.remove(seg_path)
                        continue
                    
                    # Upload to processed folder
                    upload_result = self._upload_to_drive(final_path, self.processed_folder_id)
                    
                    if not upload_result:
                        os.remove(input_path)
                        os.remove(seg_path)
                        os.remove(final_path)
                        continue
                    
                    # Post to Instagram
                    caption = f"🎵 {os.path.splitext(filename)[0]} #Music #Caribbean"
                    instagram_success = self._post_to_instagram(upload_result['url'], caption)
                    
                    # Cleanup temporary files
                    os.remove(input_path)
                    os.remove(seg_path)
                    os.remove(final_path)
                    
                    # Delete original file from source folder
                    try:
                        file_obj.Delete()
                        logger.info(f"🗑 Deleted original: {filename}")
                    except:
                        logger.warning(f"⚠️ Could not delete original: {filename}")
                    
                    # Create draft object
                    draft = {
                        "type": "media",
                        "title": filename,
                        "caption": caption,
                        "media_url": upload_result['url'],
                        "public_media_url": upload_result['url'],
                        "file_id": upload_result['file_id'],
                        "mime_type": "video/mp4",
                        "created_at": datetime.now().isoformat(),
                        "source": "google_drive",
                        "scheduled_time": None,
                        "status": "posted" if instagram_success else "processed",
                        "instagram_posted": instagram_success
                    }
                    
                    processed_drafts.append(draft)
                    logger.info(f"✅ Successfully processed: {filename}")
                    
                except Exception as e:
                    logger.error(f"❌ Error processing {file_obj.get('title', 'unknown')}: {e}")
                    continue
            
            logger.info(f"📊 Processing complete — {len(processed_drafts)} videos processed")
            return processed_drafts
            
        except Exception as e:
            logger.error(f"❌ Failed to process media links: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return []
        except Exception as e:
            logger.error(f"❌ Failed to process media links: {e}")
            return []
