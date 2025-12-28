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
                "[bg][logo]over
