#!/usr/bin/env python3
"""
Full video pipeline:
- Scan source folder for videos
- Process to 16:9 with black bars and bouncing logo
- Clip to max 90s
- Upload processed video to processed folder
- Delete original video
- Post to Instagram via Meta Graph API
- Run once at start and daily at 18:00
"""

import os
import io
import json
import time
import shutil
import logging
import tempfile
import subprocess
from datetime import datetime, timedelta
from pydrive2.drive import GoogleDrive
from oauth2client.service_account import ServiceAccountCredentials
import requests

# ==============================
# CONFIG / ENV VARS
# ==============================
SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_SERVICE_ACCOUNT")
SOURCE_FOLDER_ID = os.getenv("SOURCE_FOLDER_ID")
PROCESSED_FOLDER_ID = os.getenv("PROCESSED_FOLDER_ID")
LOGO_FILE = os.getenv("LOGO_FILE")

IG_ACCESS_TOKEN = os.getenv("IG_ACCESS_TOKEN")
IG_BUSINESS_ACCOUNT_ID = os.getenv("IG_BUSINESS_ACCOUNT_ID")
IG_USER_ID = os.getenv("IG_USER_ID")
TIMEZONE = os.getenv("TIMEZONE", "UTC")  # optional, default UTC

MAX_DURATION = 90  # seconds

# ==============================
# LOGGER
# ==============================
logger = logging.getLogger("VideoProcessor")
logger.setLevel(logging.INFO)
if not logger.handlers:
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(ch)

# ==============================
# GOOGLE DRIVE AUTH
# ==============================
def authenticate_drive():
    scopes = ["https://www.googleapis.com/auth/drive"]
    credentials = ServiceAccountCredentials.from_json_keyfile_name(
        SERVICE_ACCOUNT_FILE, scopes
    )
    return GoogleDrive(credentials)

# ==============================
# VIDEO PROCESSOR CLASS
# ==============================
class VideoProcessor:
    def __init__(self, drive):
        self.drive = drive

    # ----- Metadata -----
    def get_duration(self, path):
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            path
        ]
        try:
            out = subprocess.check_output(cmd).decode().strip()
            return float(out)
        except Exception:
            return 0

    # ----- Extract max 90s segment -----
    def extract_segment(self, input_path, output_path):
        duration = self.get_duration(input_path)
        logger.info(f"🎬 Video duration: {duration:.1f}s")
        t = min(duration, MAX_DURATION)
        cmd = [
            "ffmpeg", "-i", input_path, "-t", str(t),
            "-c:v", "libx264", "-preset", "fast", "-crf", "22",
            "-c:a", "aac", "-b:a", "128k", "-ar", "48000",
            "-vf", "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black",
            "-movflags", "+faststart", "-y", output_path
        ]
        logger.info(f"✂️ Extracting segment (max 90s): {output_path}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logger.error(f"❌ FFmpeg error: {result.stderr[:300]}")
            return False
        return True

    # ----- Add bouncing logo in black bars only -----
    def add_bounce_logo(self, input_path, output_path):
        bounce_filter = (
            "[0:v]scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black[bg];"
            f"[1:v]scale=400:-1[logo];"
            "[bg][logo]overlay="
            "x='(W-w)/2+120*sin(2.1*PI*t/10)+80*cos(1.6*PI*t/6)':"
            "y='if(gt(Y,H/9),(H/9-h)/2,if(lt(Y,8*H/9),(H/9-h)/2,0))':"
            "enable='between(t,0,30)'"
        )
        cmd = [
            "ffmpeg", "-i", input_path, "-i", LOGO_FILE,
            "-filter_complex", bounce_filter,
            "-c:v", "libx264", "-preset", "veryfast",
            "-c:a", "copy", "-y", output_path
        ]
        logger.info(f"🎬 Adding bouncing logo: {output_path}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logger.error(f"❌ FFmpeg error: {result.stderr[:300]}")
            return False
        return True

    # ----- Upload to Google Drive -----
    def upload_to_drive(self, local_path, folder_id):
        filename = os.path.basename(local_path)
        file = self.drive.CreateFile({
            "title": filename,
            "parents": [{"id": folder_id}]
        })
        file.SetContentFile(local_path)
        file.Upload()
        file.InsertPermission({"type": "anyone", "value": "anyone", "role": "reader"})
        url = f"https://drive.google.com/uc?export=download&id={file['id']}"
        logger.info(f"✅ Uploaded: {url}")
        return url

    # ----- Full pipeline -----
    def process_and_upload(self, file_obj):
        # Download
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp_in:
            input_path = tmp_in.name
        file_obj.GetContentFile(input_path)

        # Segment
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp_seg:
            seg_path = tmp_seg.name
        if not self.extract_segment(input_path, seg_path):
            os.remove(input_path)
            return None

        # Logo bounce
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp_final:
            final_path = tmp_final.name
        if not self.add_bounce_logo(seg_path, final_path):
            os.remove(input_path)
            os.remove(seg_path)
            return None

        # Upload processed
        url = self.upload_to_drive(final_path, PROCESSED_FOLDER_ID)

        # Cleanup
        os.remove(input_path)
        os.remove(seg_path)
        os.remove(final_path)

        # Delete original
        file_obj.Delete()
        logger.info(f"🗑 Deleted original file: {file_obj['title']}")

        return url

# ==============================
# INSTAGRAM POST
# ==============================
def post_to_instagram(video_url, caption=""):
    """Post a video to Instagram using Meta Graph API"""
    api_url = f"https://graph.facebook.com/v17.0/{IG_USER_ID}/media"
    # Step 1: Create media object
    payload = {
        "video_url": video_url,
        "caption": caption,
        "access_token": IG_ACCESS_TOKEN,
    }
    resp = requests.post(api_url, data=payload)
    if resp.status_code != 200:
        logger.error(f"❌ Instagram creation failed: {resp.text}")
        return False
    media_id = resp.json().get("id")
    # Step 2: Publish
    publish_url = f"https://graph.facebook.com/v17.0/{IG_USER_ID}/media_publish"
    resp2 = requests.post(publish_url, data={
        "creation_id": media_id,
        "access_token": IG_ACCESS_TOKEN
    })
    if resp2.status_code != 200:
        logger.error(f"❌ Instagram publish failed: {resp2.text}")
        return False
    logger.info(f"📱 Posted to Instagram: {video_url}")
    return True

# ==============================
# MAIN LOOP
# ==============================
def run_pipeline():
    drive = authenticate_drive()
    processor = VideoProcessor(drive)
    items = drive.ListFile({'q': f"'{SOURCE_FOLDER_ID}' in parents and trashed=false"}).GetList()
    if not items:
        logger.info("⚠️ No files found in source folder.")
        return
    for file_obj in items:
        logger.info(f"Processing: {file_obj['title']}")
        url = processor.process_and_upload(file_obj)
        if url:
            post_to_instagram(url, caption=f"Posted {datetime.now().strftime('%Y-%m-%d')}")

# ==============================
# SCHEDULER
# ==============================
def schedule_daily(hour=18):
    while True:
        now = datetime.now()
        run_pipeline()  # run immediately
        next_run = datetime.combine(now.date(), datetime.min.time()) + timedelta(hours=hour)
        if next_run < now:
            next_run += timedelta(days=1)
        sleep_seconds = (next_run - now).total_seconds()
        logger.info(f"⏱ Next run at {next_run}")
        time.sleep(sleep_seconds)

# ==============================
# ENTRY POINT
# ==============================
if __name__ == "__main__":
    schedule_daily(hour=18)
