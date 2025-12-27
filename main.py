#!/usr/bin/env python3
"""
CCmasterbot - Master Orchestrator
Fully merged and optimized for Render deployment
"""

import os
import sys
import logging
from datetime import datetime, timedelta
from threading import Thread
from flask import Flask, jsonify, render_template_string

# ==============================
# SAFE IMPORTS
# ==============================
try:
    from modules.scheduler import ContentScheduler
    from modules.content_engine import CaribbeanContentEngine
    from modules.media_processor import MediaProcessor
    from modules.instagram_manager import InstagramManager
    from modules.cloud_storage import CloudStorage
    from config.settings import BOT_CONFIG
except ImportError as e:
    print(f"❌ Missing module: {e}")
    sys.exit(1)

# ==============================
# LOGGING
# ==============================
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=getattr(logging, BOT_CONFIG["logging"]["level"]),
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("logs/ccmasterbot.log"), logging.StreamHandler()],
)
logger = logging.getLogger("CCmasterbot")

# ==============================
# FLASK APP
# ==============================
app = Flask(__name__)

# ==============================
# MASTER BOT
# ==============================
class CCmasterbot:
    def __init__(self):
        logger.info("🚀 Booting CCmasterbot")
        self.config = BOT_CONFIG
        self.running = False
        self.stats = {
            "drafts_created": 0,
            "posts_scheduled": 0,
            "last_success": None,
            "next_run": None
        }

        # Initialize modules
        self.content_engine = CaribbeanContentEngine()
        self.media_processor = MediaProcessor()
        self.scheduler = ContentScheduler()
        self.instagram = InstagramManager()
        self.cloud_storage = CloudStorage()
        logger.info("✅ All modules loaded")

    def run_single_cycle(self):
        logger.info("🔄 Starting single bot cycle")
        start = datetime.now()
        try:
            caribbean = self.content_engine.generate_drafts()
            music = self.media_processor.process_new_links()
            drafts = caribbean + music

            if not drafts:
                logger.info("ℹ️ No drafts found")
                return

            self.stats["drafts_created"] += len(drafts)
            scheduled = self.scheduler.schedule_drafts(drafts)

            uploaded = []
            for draft in scheduled:
                url = self.cloud_storage.upload_media(draft)
                if url:
                    draft["public_media_url"] = url
                    uploaded.append(draft)

            if self.config.get("auto_post", True):
                for draft in uploaded:
                    if self.instagram.schedule_post(draft):
                        self.stats["posts_scheduled"] += 1

            self.stats["last_success"] = datetime.now().isoformat()
            self.stats["next_run"] = (datetime.now() + timedelta(minutes=20)).isoformat()
            elapsed = (datetime.now() - start).total_seconds()
            logger.info(f"✅ Cycle completed in {elapsed:.1f}s")

        except Exception:
            logger.exception("❌ Cycle failed")

    def start_scheduler(self):
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.interval import IntervalTrigger

        scheduler = BackgroundScheduler()
        scheduler.add_job(
            self.run_single_cycle,
            trigger=IntervalTrigger(minutes=20),
            id="main_cycle",
            max_instances=1,
            coalesce=True
        )
        scheduler.start()
        self.running = True
        logger.info("⏰ Scheduler started (20 min interval)")
        # Run an immediate first cycle
        self.run_single_cycle()

# ==============================
# FLASK ROUTES
# ==============================
@app.route("/")
def dashboard():
    return render_template_string("""
    <h1>🎭 CCmasterbot</h1>
    <p>Status: Running</p>
    <ul>
        <li><a href="/health">Health</a></li>
        <li><a href="/run-cycle">Run Cycle</a></li>
    </ul>
    """)

@app.route("/health")
def health():
    return jsonify(status="healthy", service="ccmasterbot", timestamp=datetime.utcnow().isoformat())

@app.route("/run-cycle")
def manual_run():
    if not hasattr(app, "bot"):
        return jsonify(success=False, message="Bot not initialized"), 500
    Thread(target=app.bot.run_single_cycle, daemon=True).start()
    return jsonify(success=True, message="Cycle started")

# ==============================
# ENTRYPOINT
# ==============================
def create_app():
    app.bot = CCmasterbot()  # attach bot to Flask app
    Thread(target=app.bot.start_scheduler, daemon=True).start()
    return app

if __name__ == "__main__":
    app = create_app()
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=False
    )
