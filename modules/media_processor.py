import os
import logging
import tempfile
import subprocess
import time
import json
from datetime import datetime
from pydrive2.drive import GoogleDrive
from pydrive2.auth import GoogleAuth
from oauth2client.service_account import ServiceAccountCredentials
import requests

logger = logging.getLogger("MediaProcessor")

class MediaProcessor:
    def __init__(self):
        logger.info("🎬 Media Processor initialized")
        
        # Free tier optimizations
        self.free_tier_mode = os.environ.get("FREE_TIER_MODE", "false").lower() == "true"
        self.max_files_per_cycle = int(os.environ.get("PROCESS_LIMIT", "1"))
        self.video_timeout = 180 if self.free_tier_mode else 300  # Shorter timeout for free tier
        
        # Drive setup
        self.drive = self._authenticate_drive()
        self.source_folder_id = os.getenv("SOURCE_FOLDER_ID")
        self.processed_folder_id = os.getenv("PROCESSED_FOLDER_ID")
        self.logo_file = os.getenv("LOGO_FILE", "logo.png")
        self.max_duration = 90  # seconds
        
        # Instagram API credentials
        self.ig_access_token = os.getenv("IG_ACCESS_TOKEN")
        self.ig_business_account_id = os.getenv("IG_BUSINESS_ACCOUNT_ID")
        self.ig_user_id = os.getenv("IG_USER_ID")
        
        if self.free_tier_mode:
            logger.info("🆓 FREE TIER MODE: Processing max {} videos per cycle".format(self.max_files_per_cycle))
            logger.info("   • Timeout: {}s".format(self.video_timeout))
            logger.info("   • Optimized FFmpeg settings")
    
    def _authenticate_drive(self):
        """Authenticate with Google Drive - Optimized for reliability"""
        try:
            gauth = GoogleAuth()
            
            # Try service account from environment variable
            service_account_json = os.getenv("GOOGLE_SERVICE_ACCOUNT")
            
            if service_account_json:
                try:
                    # Parse JSON from environment
                    credentials_dict = json.loads(service_account_json)
                    
                    # Write to temporary file
                    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                        json.dump(credentials_dict, f)
                        temp_file = f.name
                    
                    # Create settings for pydrive2
                    settings = {
                        "client_config_backend": "service",
                        "service_config": {
                            "client_json_file_path": temp_file
                        }
                    }
                    
                    # Write settings file
                    import yaml
                    with open("settings.yaml", "w") as f:
                        yaml.dump(settings, f)
                    
                    gauth.LoadSettingsFile("settings.yaml")
                    gauth.ServiceAuth()
                    
                    # Clean up temp file
                    os.unlink(temp_file)
                    
                except json.JSONDecodeError:
                    # If it's a file path
                    gauth.ServiceAuth()
            else:
                # Try to load existing settings
                try:
                    gauth.LoadSettingsFile("settings.yaml")
                except:
                    # Create default settings
                    settings = {
                        "client_config_backend": "service",
                        "service_config": {
                            "client_json_file_path": "service_account.json"
                        }
                    }
                    import yaml
                    with open("settings.yaml", "w") as f:
                        yaml.dump(settings, f)
                    gauth.LoadSettingsFile("settings.yaml")
                
                gauth.ServiceAuth()
            
            logger.info("✅ Google Drive authentication successful")
            return GoogleDrive(gauth)
            
        except Exception as e:
            logger.error(f"❌ Google Drive authentication failed: {e}")
            # Try one more time with simplified approach
            return self._authenticate_drive_fallback()
    
    def _authenticate_drive_fallback(self):
        """Fallback authentication method"""
        try:
            gauth = GoogleAuth()
            gauth.ServiceAuth()
            logger.info("✅ Google Drive authentication (fallback) successful")
            return GoogleDrive(gauth)
        except Exception as e:
            logger.error(f"❌ Fallback authentication failed: {e}")
            raise
    
    def _get_duration(self, path):
        """Get video duration using ffprobe - with timeout"""
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            path
        ]
        try:
            out = subprocess.check_output(cmd, timeout=10).decode().strip()
            return float(out)
        except subprocess.TimeoutExpired:
            logger.error("❌ ffprobe timeout after 10s")
            return 0
        except Exception as e:
            logger.error(f"❌ Could not get video duration: {e}")
            return 0
    
    def _extract_segment(self, input_path, output_path):
        """Extract max 90s segment from video - Free tier optimized"""
        duration = self._get_duration(input_path)
        if duration == 0:
            logger.error("❌ Could not read video duration")
            return False
        
        logger.info(f"🎬 Video duration: {duration:.1f}s")
        
        t = min(duration, self.max_duration)
        
        # OPTIMIZED FFMPEG SETTINGS FOR FREE TIER
        if self.free_tier_mode:
            # Free tier: faster processing, lower quality
            cmd = [
                "ffmpeg", "-i", input_path, "-t", str(t),
                "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
                "-c:a", "aac", "-b:a", "96k", "-ar", "44100",
                "-vf", "scale=1280:720:force_original_aspect_ratio=decrease,"
                       "pad=1280:720:(ow-iw)/2:(oh-ih)/2:black",
                "-threads", "1",  # Single thread for free tier
                "-movflags", "+faststart",
                "-y", output_path
            ]
            logger.info(f"✂️ Extracting {t}s segment (free tier optimized)")
        else:
            # Full quality for paid tier
            cmd = [
                "ffmpeg", "-i", input_path, "-t", str(t),
                "-c:v", "libx264", "-preset", "fast", "-crf", "22",
                "-c:a", "aac", "-b:a", "128k", "-ar", "48000",
                "-vf", "scale=1920:1080:force_original_aspect_ratio=decrease,"
                       "pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black",
                "-movflags", "+faststart",
                "-y", output_path
            ]
            logger.info(f"✂️ Extracting {t}s segment")
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=self.video_timeout)
            
            if result.returncode != 0:
                logger.error(f"❌ FFmpeg error: {result.stderr[:200]}")
                return False
            
            return True
            
        except subprocess.TimeoutExpired:
            logger.error(f"❌ FFmpeg timeout after {self.video_timeout}s")
            return False
        except Exception as e:
            logger.error(f"❌ FFmpeg error: {e}")
            return False
    
    def _add_bounce_logo(self, input_path, output_path):
        """Add bouncing logo in black bars - Optimized for free tier"""
        try:
            # Simplified filter for free tier
            if self.free_tier_mode:
                filter_complex = (
                    "[0:v]scale=1280:720:force_original_aspect_ratio=decrease,"
                    "pad=1280:720:(ow-iw)/2:(oh-ih)/2:black[bg];"
                    "[1:v]scale=200:-1[logo];"
                    "[bg][logo]overlay="
                    "x='(W-w)/2+50*sin(PI*t)':"
                    "y='(H-h)/2+30*cos(PI*t/2)':"
                    "enable='between(t,0,30)'"
                )
                preset = "ultrafast"
                logger.info("🎨 Adding bouncing logo (free tier optimized)")
            else:
                filter_complex = (
                    "[0:v]scale=1920:1080:force_original_aspect_ratio=decrease,"
                    "pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black[bg];"
                    "[1:v]scale=400:-1[logo];"
                    "[bg][logo]overlay="
                    "x='(W-w)/2+120*sin(2.1*PI*t/10)+80*cos(1.6*PI*t/6)':"
                    "y='if(gt(Y,H/9),(H/9-h)/2,if(lt(Y,8*H/9),(H/9-h)/2,0))':"
                    "enable='between(t,0,30)'"
                )
                preset = "veryfast"
                logger.info("🎨 Adding bouncing logo")
            
            cmd = [
                "ffmpeg", "-i", input_path, "-i", self.logo_file,
                "-filter_complex", filter_complex,
                "-c:v", "libx264", "-preset", preset,
                "-c:a", "copy",
                "-y", output_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            
            if result.returncode != 0:
                logger.error(f"❌ FFmpeg logo error: {result.stderr[:200]}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Logo processing error: {e}")
            return False
    
    def _upload_to_drive(self, local_path, folder_id):
        """Upload file to Google Drive and make it public"""
        try:
            filename = os.path.basename(local_path)
            processed_filename = f"processed_{filename}"
            
            file = self.drive.CreateFile({
                "title": processed_filename,
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
            logger.info(f"✅ Uploaded to Google Drive: {processed_filename}")
            
            return {
                "url": file_url,
                "file_id": file['id'],
                "title": processed_filename
            }
            
        except Exception as e:
            logger.error(f"❌ Drive upload failed: {e}")
            return None
    
    def _post_to_instagram(self, video_url, caption=""):
        """Post video to Instagram using Meta Graph API - With error handling"""
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
                "media_type": "REELS"
            }
            
            logger.info(f"📤 Creating Instagram media container...")
            resp = requests.post(api_url, data=payload, timeout=30)
            
            if resp.status_code != 200:
                error_msg = resp.text[:200] if len(resp.text) > 200 else resp.text
                logger.error(f"❌ Instagram creation failed ({resp.status_code}): {error_msg}")
                return False
            
            response_json = resp.json()
            if "id" not in response_json:
                logger.error(f"❌ No media ID in response: {response_json}")
                return False
            
            media_id = response_json["id"]
            logger.info(f"✅ Media container created: {media_id}")
            
            # Wait a moment for processing (Instagram sometimes needs this)
            time.sleep(2)
            
            # Step 2: Publish
            publish_url = f"https://graph.facebook.com/v17.0/{self.ig_user_id}/media_publish"
            resp2 = requests.post(publish_url, data={
                "creation_id": media_id,
                "access_token": self.ig_access_token
            }, timeout=30)
            
            if resp2.status_code != 200:
                error_msg = resp2.text[:200] if len(resp2.text) > 200 else resp2.text
                logger.error(f"❌ Instagram publish failed ({resp2.status_code}): {error_msg}")
                return False
            
            publish_response = resp2.json()
            if "id" not in publish_response:
                logger.error(f"❌ No post ID in response: {publish_response}")
                return False
            
            logger.info(f"📱 Posted to Instagram successfully! Post ID: {publish_response['id']}")
            return True
            
        except requests.exceptions.Timeout:
            logger.error("❌ Instagram API timeout")
            return False
        except Exception as e:
            logger.error(f"❌ Instagram posting error: {e}")
            return False
    
    def process_new_links(self):
        """
        Main method: Find videos, process them, upload, and post to Instagram
        Optimized for free tier: Processes limited number of files
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
            
            # FREE TIER: Limit number of files to process
            if self.free_tier_mode:
                files = files[:self.max_files_per_cycle]
                logger.info(f"🆓 Free tier: Processing only {len(files)} file(s)")
            
            processed_drafts = []
            
            for file_obj in files:
                try:
                    filename = file_obj['title']
                    logger.info(f"🔧 Processing: {filename}")
                    
                    # Create temporary files
                    temp_files = []
                    try:
                        # Download file
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp_in:
                            input_path = tmp_in.name
                            temp_files.append(input_path)
                        
                        file_obj.GetContentFile(input_path)
                        
                        # Extract segment (max 90s)
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp_seg:
                            seg_path = tmp_seg.name
                            temp_files.append(seg_path)
                        
                        if not self._extract_segment(input_path, seg_path):
                            continue
                        
                        # Add bouncing logo
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp_final:
                            final_path = tmp_final.name
                            temp_files.append(final_path)
                        
                        if not self._add_bounce_logo(seg_path, final_path):
                            continue
                        
                        # Upload to processed folder
                        upload_result = self._upload_to_drive(final_path, self.processed_folder_id)
                        
                        if not upload_result:
                            continue
                        
                        # Post to Instagram
                        clean_name = os.path.splitext(filename)[0]
                        caption = f"🎵 {clean_name[:100]} #Music #Caribbean #Viral"
                        instagram_success = self._post_to_instagram(upload_result['url'], caption)
                        
                        # Delete original file from source folder
                        try:
                            file_obj.Delete()
                            logger.info(f"🗑 Deleted original: {filename}")
                        except Exception as delete_error:
                            logger.warning(f"⚠️ Could not delete original: {delete_error}")
                        
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
                        
                        # Free tier: Add delay between processing files
                        if self.free_tier_mode and len(processed_drafts) < len(files):
                            wait_time = 15  # 15 seconds between files
                            logger.info(f"⏳ Free tier: Waiting {wait_time}s before next file")
                            time.sleep(wait_time)
                        
                    finally:
                        # Cleanup temporary files
                        for temp_file in temp_files:
                            try:
                                if os.path.exists(temp_file):
                                    os.remove(temp_file)
                            except:
                                pass
                    
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
