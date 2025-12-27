import os
import subprocess
import logging
import requests
from datetime import datetime
from threading import Thread
from flask import Flask, send_from_directory
from pydrive2.auth import GoogleAuth
from pydrive2.drive import GoogleDrive
from dotenv import load_dotenv
import tempfile
import time

# ================== ENV ==================
load_dotenv()

INSTA_ACCESS_TOKEN = os.getenv("INSTA_ACCESS_TOKEN")
IG_BUSINESS_ACCOUNT_ID = os.getenv("IG_BUSINESS_ACCOUNT_ID")
DRIVE_FOLDER_ID = os.getenv("DRIVE_FOLDER_ID")
PUBLIC_DRIVE_FOLDER_ID = os.getenv("PUBLIC_DRIVE_FOLDER_ID")
CLIENT_SECRETS_FILE = os.getenv("GOOGLE_CLIENT_SECRETS", "client_secrets.json")
LOGO_FILE = os.getenv("LOGO_FILE", "logo_real.png")

# ================== FLASK MEDIA SERVER ==================
app = Flask(__name__)
TEMP_DIR = tempfile.mkdtemp()

@app.route("/media/<path:filename>")
def serve_media(filename):
    return send_from_directory(TEMP_DIR, filename, as_attachment=False)

def start_media_server():
    app.run(host="0.0.0.0", port=5050, debug=False, use_reloader=False)

# ================== LOGGER ==================
logger = logging.getLogger("InstagramScheduler")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)

# ================== GOOGLE DRIVE ==================
def authenticate_drive():
    gauth = GoogleAuth()
    gauth.LoadClientConfigFile(CLIENT_SECRETS_FILE)
    gauth.LocalWebserverAuth()
    return GoogleDrive(gauth)

# ================== VIDEO PROCESSING ==================
def process_video(input_path, output_path):
    filter_chain = (
        "[0:v]scale=1080:608:force_original_aspect_ratio=increase,"
        "crop=1080:608,pad=1080:1920:0:656:black[bg];"
        "[1:v]scale=350:-1[logo];"
        "[bg][logo]overlay=x='(W-w)/2+120*sin(2*PI*t/10)':y='280+90*sin(2*PI*t/8)'"
    )
    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-i", LOGO_FILE,
        "-filter_complex", filter_chain,
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        output_path
    ]
    logger.info(f"🎬 Processing: {os.path.basename(input_path)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        logger.error(f"❌ FFmpeg failed: {result.stderr[:200]}")
        return False
    return True

# ================== UPLOAD TO PUBLIC DRIVE ==================
def upload_to_public_drive(drive, local_path):
    filename = os.path.basename(local_path)
    file = drive.CreateFile({"title": filename, "parents": [{"id": PUBLIC_DRIVE_FOLDER_ID}]})
    file.SetContentFile(local_path)
    file.Upload()
    file.InsertPermission({"type": "anyone", "value": "anyone", "role": "reader"})
    file_id = file["id"]
    url = f"https://drive.google.com/uc?export=download&id={file_id}"
    logger.info(f"✅ Video uploaded: {url}")
    return url

# ================== SCHEDULE INSTAGRAM REEL ==================
def schedule_instagram_reel(video_url, caption=""):
    resp = requests.post(
        f"https://graph.facebook.com/v17.0/{IG_BUSINESS_ACCOUNT_ID}/media",
        data={"access_token": INSTA_ACCESS_TOKEN, "media_type": "REELS", "video_url": video_url, "caption": caption}
    ).json()

    if "id" not in resp:
        logger.error(f"❌ Scheduling failed: {resp}")
        return False
    logger.info(f"⏳ Scheduled for review: {video_url}")
    return True

# ================== MAIN LOOP ==================
def run_scheduler():
    drive = authenticate_drive()
    logger.info("🚀 Instagram Scheduler running...")

    while True:
        files = drive.ListFile({"q": f"'{DRIVE_FOLDER_ID}' in parents and trashed=false"}).GetList()
        if not files:
            time.sleep(30)
            continue

        for f in files:
            filename = f["title"]
            with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(filename)[1]) as tmp_input:
                f.GetContentFile(tmp_input.name)
                tmp_output = os.path.join(TEMP_DIR, f"processed_{filename}")

                if not process_video(tmp_input.name, tmp_output):
                    os.remove(tmp_input.name)
                    continue

                video_url = upload_to_public_drive(drive, tmp_output)
                schedule_instagram_reel(video_url, caption="")

                # DELETE local temp files immediately
                os.remove(tmp_input.name)
                os.remove(tmp_output)

        time.sleep(60)

# ================== BOOT ==================
if __name__ == "__main__":
    Thread(target=start_media_server, daemon=True).start()
    run_scheduler()
