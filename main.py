#!/usr/bin/env python3
"""
CCmasterbot - Master Orchestrator
Fully merged and optimized for Render deployment
"""

import os
import sys
import logging
import json
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
        logger.info("🎭 Caribbean Content Engine initialized")
        self.media_processor = MediaProcessor()
        logger.info("🎬 Media Processor initialized")
        self.scheduler = ContentScheduler()
        self.instagram = InstagramManager()
        self.cloud_storage = CloudStorage()
        logger.info("✅ All modules loaded")

    def run_single_cycle(self):
        logger.info("🔄 Starting single bot cycle")
        start = datetime.now()
        try:
            caribbean = self.content_engine.generate_drafts()
            logger.info(f"📝 Generated {len(caribbean)} content drafts")
            music = self.media_processor.process_new_links()
            logger.info(f"📂 Media scan complete — {len(music)} new media found")
            drafts = caribbean + music

            if not drafts:
                logger.info("ℹ️ No drafts found")
                return

            self.stats["drafts_created"] += len(drafts)
            logger.info(f"📅 Scheduling {len(drafts)} drafts...")
            scheduled = self.scheduler.schedule_drafts(drafts)
            logger.info(f"📅 Scheduled {len(scheduled)} drafts")

            uploaded = []
            for i, draft in enumerate(scheduled):
                try:
                    logger.info(f"📤 Processing draft {i+1}/{len(scheduled)}")
                    
                    # Debug: Log what the draft contains
                    logger.debug(f"Draft type: {type(draft)}")
                    if isinstance(draft, dict):
                        logger.debug(f"Draft keys: {list(draft.keys())}")
                        if 'content' in draft:
                            logger.debug(f"Content type: {type(draft['content'])}")
                    
                    # Try to upload media
                    url = self.cloud_storage.upload_media(draft)
                    if url:
                        logger.info(f"✅ Upload successful: {url}")
                        draft["public_media_url"] = url
                        uploaded.append(draft)
                    else:
                        logger.warning(f"⚠️ Upload returned no URL for draft {i+1}")
                        
                except Exception as e:
                    logger.error(f"❌ Failed to process draft {i+1}: {str(e)}")
                    # Continue with other drafts
                    continue

            logger.info(f"📊 Successfully uploaded {len(uploaded)}/{len(scheduled)} drafts")

            if self.config.get("auto_post", True) and uploaded:
                logger.info("📲 Auto-posting to Instagram...")
                for draft in uploaded:
                    try:
                        if self.instagram.schedule_post(draft):
                            self.stats["posts_scheduled"] += 1
                            logger.info(f"✅ Scheduled post: {draft.get('title', 'Untitled')}")
                        else:
                            logger.warning(f"⚠️ Failed to schedule post for draft")
                    except Exception as e:
                        logger.error(f"❌ Instagram scheduling error: {str(e)}")

            self.stats["last_success"] = datetime.now().isoformat()
            self.stats["next_run"] = (datetime.now() + timedelta(minutes=20)).isoformat()
            elapsed = (datetime.now() - start).total_seconds()
            logger.info(f"✅ Cycle completed in {elapsed:.1f}s - {len(uploaded)} posts ready")

        except Exception as e:
            logger.exception(f"❌ Cycle failed: {str(e)}")
            # Re-raise to see full traceback in logs
            raise

    def start_scheduler(self):
        try:
            from apscheduler.schedulers.background import BackgroundScheduler
            from apscheduler.triggers.interval import IntervalTrigger
        except ImportError as e:
            logger.error(f"❌ Missing APScheduler module: {e}")
            logger.info("💡 Add 'APScheduler==3.10.4' to requirements.txt")
            return

        try:
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
        except Exception as e:
            logger.error(f"❌ Failed to start scheduler: {e}")

# ==============================
# FLASK ROUTES
# ==============================
@app.route("/")
def dashboard():
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>🎭 CCmasterbot Dashboard</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; }
            .card { background: #f5f5f5; padding: 20px; border-radius: 10px; margin: 20px 0; }
            .btn { display: inline-block; padding: 10px 20px; background: #007bff; color: white; text-decoration: none; border-radius: 5px; }
            .btn:hover { background: #0056b3; }
            .success { color: green; }
            .error { color: red; }
        </style>
    </head>
    <body>
        <h1>🎭 CCmasterbot Dashboard</h1>
        
        <div class="card">
            <h2>Status: <span class="success">● Running</span></h2>
            <p>Automated content generation and posting system</p>
        </div>
        
        <div class="card">
            <h2>Quick Actions</h2>
            <a href="/run-cycle" class="btn">▶️ Run Cycle Now</a>
            <a href="/health" class="btn">🩺 Health Check</a>
            <a href="/stats" class="btn">📊 Statistics</a>
        </div>
        
        <div class="card">
            <h2>Endpoints</h2>
            <ul>
                <li><code>GET /</code> - This dashboard</li>
                <li><code>GET /health</code> - Health status</li>
                <li><code>GET /run-cycle</code> - Trigger manual cycle</li>
                <li><code>GET /stats</code> - Bot statistics</li>
            </ul>
        </div>
        
        <div class="card">
            <h2>About</h2>
            <p>CCmasterbot automates content creation, media processing, and social media posting.</p>
            <p>Runs automatically every 20 minutes or can be triggered manually.</p>
        </div>
    </body>
    </html>
    """
    return render_template_string(html)

@app.route("/health")
def health():
    """Health check endpoint"""
    status = {
        "status": "healthy",
        "service": "ccmasterbot",
        "timestamp": datetime.utcnow().isoformat(),
        "running": hasattr(app, "bot") and app.bot.running,
        "environment": "production" if not app.debug else "development"
    }
    return jsonify(status)

@app.route("/run-cycle")
def manual_run():
    """Manually trigger a bot cycle"""
    if not hasattr(app, "bot"):
        return jsonify(success=False, message="Bot not initialized"), 500
    
    # Run in background thread
    Thread(target=app.bot.run_single_cycle, daemon=True).start()
    
    response = {
        "success": True,
        "message": "Cycle started",
        "timestamp": datetime.utcnow().isoformat(),
        "next_check": "Check logs for progress"
    }
    return jsonify(response)

@app.route("/stats")
def stats():
    """Get bot statistics"""
    if not hasattr(app, "bot"):
        return jsonify(error="Bot not initialized"), 500
    
    stats_data = {
        "bot_statistics": app.bot.stats,
        "config": {
            "auto_post": app.bot.config.get("auto_post", True),
            "logging_level": app.bot.config["logging"]["level"]
        },
        "timestamp": datetime.utcnow().isoformat(),
        "uptime": "Always running" if app.bot.running else "Not scheduled"
    }
    return jsonify(stats_data)

# ==============================
# ENTRYPOINT
# ==============================
def create_app():
    """Create and initialize the Flask application"""
    try:
        app.bot = CCmasterbot()  # attach bot to Flask app
        Thread(target=app.bot.start_scheduler, daemon=True).start()
        return app
    except Exception as e:
        logger.error(f"❌ Failed to create app: {e}")
        raise

if __name__ == "__main__":
    app = create_app()
    port = int(os.environ.get("PORT", 5000))
    logger.info(f"🌐 Starting web server on port {port}")
    app.run(
        host="0.0.0.0",
        port=port,
        debug=False
    )
