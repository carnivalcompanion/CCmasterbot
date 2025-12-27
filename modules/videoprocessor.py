#!/usr/bin/env python3
"""
VideoProcessor for Carnival Companion
Processes videos, creates Instagram-ready reels with cinematic bounce,
uploads to public Google Drive, and returns public URLs.
No local files are permanently saved.
"""

import os
import subprocess
import json
import tempfile
import logging
from datetime import datetime
from pydrive2.drive import GoogleDrive
from oauth2client.service_account import ServiceAccountCredentials

# ==============================
# CONFIG
# ==============================
SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_SERVICE_ACCOUNT", "service_account.json")
PUBLIC_DRIVE_FOLDER_ID = os.getenv("PUBLIC_DRIVE_FOLDER_ID")
LOGO_FILE = os.getenv("LOGO_FILE", "logo_real.png")

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

    # ---------- Metadata ----------
    def extract_metadata(self, video_path):
        try:
            cmd = [
                "ffprobe", "-v", "quiet",
                "-print_format", "json",
                "-show_format", "-show_streams",
                video_path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            return json.loads(result.stdout)
        except Exception as e:
            logger.error(f"Metadata extraction error: {e}")
            return {}

    def get_duration(self, video_path):
        metadata = self.extract_metadata(video_path)
        try:
            return float(metadata["format"]["duration"])
        except Exception:
            return 0

    # ---------- 90s segment ----------
    def find_90s_segment(self, video_path):
        duration = self.get_duration(video_path)
        logger.info(f"🎬 Video duration: {duration:.1f}s")
        if duration <= 90:
            return 0, duration
        skip = duration * 0.1
        available = duration - skip * 2
        start = skip if available >= 90 else max(0, (duration - 90) / 2)
        end = min(start + 90, duration)
        logger.info(f"   Segment: {start:.1f}s → {end:.1f}s")
        return start, end

    # ---------- Extract segment ----------
    def extract_segment(self, input_path, start_time, output_path):
        cmd = [
            "ffmpeg", "-i", input_path,
            "-ss", str(start_time), "-t", "90",
            "-c:v", "libx264", "-preset", "fast",
            "-crf", "22", "-c:a", "aac", "-b:a", "128k",
            "-ar", "48000", "-vf", "scale=1080:-2",
            "-movflags", "+faststart", "-y", output_path
        ]
        logger.info(f"✂️ Extracting 90s segment: {output_path}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logger.error(f"❌ FFmpeg error: {result.stderr[:300]}")
            return False
        return True

    # ---------- Cinematic bounce ----------
    def add_bounce_logo(self, input_path, output_path, logo_path=LOGO_FILE):
        bounce_filter = (
            "[0:v]scale=1080:608:force_original_aspect_ratio=increase,"
            "crop=1080:608,pad=1080:1920:0:656:color=black[bg];"
            "[1:v]scale=350:-1[logo];"
            "[bg][logo]overlay="
            "x='if(gte(t,0),(W-w)/2+120*sin(2.1*PI*t/10)+80*cos(1.6*PI*t/6),0)':"
            "y='if(gte(t,0),280+90*sin(1.8*PI*t/8)+60*cos(2.3*PI*t/5),0)':"
            "enable='between(t,0,30)'"
        )
        cmd = [
            "ffmpeg", "-i", input_path, "-i", logo_path,
            "-filter_complex", bounce_filter,
            "-c:v", "libx264", "-preset", "veryfast",
            "-c:a", "copy", "-y", output_path
        ]
        logger.info(f"🎬 Adding cinematic bounce: {output_path}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logger.error(f"❌ FFmpeg error: {result.stderr[:300]}")
            return False
        return True

    # ---------- Upload to Google Drive ----------
    def upload_to_drive(self, local_path):
        filename = os.path.basename(local_path)
        file = self.drive.CreateFile({
            "title": filename,
            "parents": [{"id": PUBLIC_DRIVE_FOLDER_ID}]
        })
        file.SetContentFile(local_path)
        file.Upload()
        file.InsertPermission({"type": "anyone", "value": "anyone", "role": "reader"})
        url = f"https://drive.google.com/uc?export=download&id={file['id']}"
        logger.info(f"✅ Uploaded to public Drive: {url}")
        return url

    # ---------- Full pipeline ----------
    def process_video(self, input_path):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp_seg:
            seg_path = tmp_seg.name
        start, end = self.find_90s_segment(input_path)
        if not self.extract_segment(input_path, start, seg_path):
            return None

        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp_final:
            final_path = tmp_final.name
        if not self.add_bounce_logo(seg_path, final_path):
            os.remove(seg_path)
            return None

        url = self.upload_to_drive(final_path)
        os.remove(seg_path)
        os.remove(final_path)
        return url


# ==============================
# TEST / CLI
# ==============================
if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python VideoProcessor.py <input_video>")
        sys.exit(1)

    input_video = sys.argv[1]
    drive = authenticate_drive()
    processor = VideoProcessor(drive)
    public_url = processor.process_video(input_video)
    if public_url:
        print(f"✅ Public URL: {public_url}")
    else:
        print("❌ Processing failed")
