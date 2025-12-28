import os
import logging
import tempfile
import subprocess
import time
from datetime import datetime
from pydrive2.drive import GoogleDrive
from pydrive2.auth import GoogleAuth
import requests

logger = logging.getLogger("MediaProcessor")

class MediaProcessor:
    def __init__(self):
        logger.info("🎬 Media Processor initialized (Free Tier)")
        self.drive = self._authenticate_drive()
        self.source_folder_id = os.getenv("SOURCE_FOLDER_ID")
        self.processed_folder_id = os.getenv("PROCESSED_FOLDER_ID")
        self.logo_file = os.getenv("LOGO_FILE", "logo.png")
        self.max_duration = 90  # seconds
        
        # Instagram API credentials (for posting)
        self.ig_access_token = os.getenv("IG_ACCESS_TOKEN")
        self.ig_user_id = os.getenv("IG_USER_ID")
        
        # Free tier optimizations
        self.max_files_per_run = 1  # Process only ONE video
        self.timeout_seconds = 180  # 3 minute timeout
        self.optimize_for_free_tier = True
    
    def _authenticate_drive(self):
        """Simplified authentication for free tier"""
        try:
            gauth = GoogleAuth()
            
            # Try to load settings
            try:
                gauth.LoadSettingsFile("settings.yaml")
            except:
                # Create minimal settings
                import yaml
                settings = {
                    "client_config_backend": "service",
                    "service_config": {
                        "client_json_file_path": "service_account.json"
                    }
                }
                with open("settings.yaml", "w") as f:
                    yaml.dump(settings, f)
                gauth.LoadSettingsFile("settings.yaml")
            
            gauth.ServiceAuth()
            return GoogleDrive(gauth)
            
        except Exception as e:
            logger.error(f"❌ Google Drive auth failed: {e}")
            raise
    
    def _get_duration(self, path):
        """Get video duration - optimized"""
        try:
            cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", 
                   "-of", "default=noprint_wrappers=1:nokey=1", path]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            return float(result.stdout.strip())
        except:
            return 0
    
    def _extract_segment(self, input_path, output_path):
        """Extract segment - OPTIMIZED for free tier"""
        duration = self._get_duration(input_path)
        logger.info(f"🎬 Video duration: {duration:.1f}s")
        
        t = min(duration, self.max_duration)
        
        # FREE TIER OPTIMIZED SETTINGS
        cmd = [
            "ffmpeg", "-i", input_path, "-t", str(t),
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",  # Lower quality, faster
            "-c:a", "aac", "-b:a", "64k", "-ar", "22050",  # Lower audio quality
            "-vf", "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2:black",  # 720p
            "-threads", "1",  # Single thread
            "-movflags", "+faststart", "-y", output_path
        ]
        
        logger.info(f"✂️ Extracting {t}s segment (optimized)")
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=self.timeout_seconds)
            if result.returncode != 0:
                logger.error(f"❌ FFmpeg error: {result.stderr[:200]}")
                return False
            return True
        except subprocess.TimeoutExpired:
            logger.error(f"❌ FFmpeg timeout after {self.timeout_seconds}s")
            return False
    
    def _add_bounce_logo(self, input_path, output_path):
        """Add logo - optimized"""
        try:
            # Simplified filter for free tier
            cmd = [
                "ffmpeg", "-i", input_path, "-i", self.logo_file,
                "-filter_complex",
                "[0:v]scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2:black[bg];"
                "[1:v]scale=200:-1[logo];"
                "[bg][logo]overlay=x='(W-w)/2+50*sin(PI*t)':y='(H-h)/2+30*cos(PI*t/2)':enable='between(t,0,30)'",
                "-c:v", "libx264", "-preset", "ultrafast",
                "-c:a", "copy", "-y", output_path
            ]
            
            logger.info("🎨 Adding logo (optimized)")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            return result.returncode == 0
        except:
            return False
    
    def _upload_to_drive(self, local_path, folder_id):
        """Upload to Google Drive"""
        try:
            filename = os.path.basename(local_path)
            file = self.drive.CreateFile({
                "title": f"processed_{filename}",
                "parents": [{"id": folder_id}]
            })
            file.SetContentFile(local_path)
            file.Upload()
            
            # Make public
            file.InsertPermission({"type": "anyone", "value": "anyone", "role": "reader"})
            
            file_url = f"https://drive.google.com/uc?export=download&id={file['id']}"
            logger.info(f"✅ Uploaded: {file_url}")
            
            return {"url": file_url, "file_id": file['id'], "title": filename}
        except:
            return None
    
    def _post_to_instagram(self, video_url, caption=""):
        """Post to Instagram - with timeout"""
        if not self.ig_access_token or not self.ig_user_id:
            logger.warning("⚠️ Instagram credentials not set")
            return False
        
        try:
            # Simple post with timeout
            api_url = f"https://graph.facebook.com/v17.0/{self.ig_user_id}/media"
            response = requests.post(api_url, timeout=30, data={
                "video_url": video_url,
                "caption": caption,
                "access_token": self.ig_access_token,
            })
            
            if response.status_code != 200:
                logger.warning(f"⚠️ Instagram post failed: {response.text[:100]}")
                return False
            
            media_id = response.json().get("id")
            if not media_id:
                return False
            
            # Try to publish
            publish_url = f"https://graph.facebook.com/v17.0/{self.ig_user_id}/media_publish"
            response2 = requests.post(publish_url, timeout=30, data={
                "creation_id": media_id,
                "access_token": self.ig_access_token
            })
            
            success = response2.status_code == 200
            if success:
                logger.info("📱 Posted to Instagram")
            return success
            
        except Exception as e:
            logger.warning(f"⚠️ Instagram error: {str(e)[:100]}")
            return False
    
    def process_one_video(self):
        """
        Process exactly ONE video - for free tier manual processing
        Returns: List with one draft or empty list
        """
        try:
            if not self.source_folder_id:
                logger.error("❌ SOURCE_FOLDER_ID not set")
                return []
            
            logger.info("📂 Scanning for videos...")
            query = f"'{self.source_folder_id}' in parents and trashed=false"
            files = self.drive.ListFile({'q': query}).GetList()
            
            if not files:
                logger.info("📭 No videos found")
                return []
            
            # TAKE ONLY THE FIRST FILE
            file_obj = files[0]
            filename = file_obj['title']
            logger.info(f"🔧 Processing: {filename}")
            
            # Create temp files
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp_in:
                input_path = tmp_in.name
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp_seg:
                seg_path = tmp_seg.name
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp_final:
                final_path = tmp_final.name
            
            try:
                # Download
                file_obj.GetContentFile(input_path)
                
                # Process
                if not self._extract_segment(input_path, seg_path):
                    return []
                
                if not self._add_bounce_logo(seg_path, final_path):
                    return []
                
                # Upload
                upload_result = self._upload_to_drive(final_path, self.processed_folder_id)
                if not upload_result:
                    return []
                
                # Post to Instagram (optional)
                caption = f"🎵 {os.path.splitext(filename)[0][:100]} #Music"
                instagram_success = self._post_to_instagram(upload_result['url'], caption)
                
                # Delete original (optional)
                try:
                    file_obj.Delete()
                    logger.info("🗑 Deleted original")
                except:
                    pass
                
                # Return result
                draft = {
                    "title": filename,
                    "instagram_posted": instagram_success,
                    "created_at": datetime.now().isoformat()
                }
                
                logger.info(f"✅ Successfully processed: {filename}")
                return [draft]
                
            finally:
                # Cleanup
                for path in [input_path, seg_path, final_path]:
                    try:
                        if os.path.exists(path):
                            os.remove(path)
                    except:
                        pass
                
        except Exception as e:
            logger.error(f"❌ Processing failed: {e}")
            return []
    
    def process_new_links(self):
        """Alias for compatibility"""
        return self.process_one_video()
