#!/usr/bin/env python3
"""
CCmasterbot - Free Tier Optimized but Still Automated
"""

import os
import sys
import logging
import json
import traceback
import time
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
# MASTER BOT - Free Tier Optimized
# ==============================
class CCmasterbot:
    def __init__(self):
        logger.info("🚀 Booting CCmasterbot (Free Tier Optimized)")
        self.config = BOT_CONFIG
        self.running = False
        self.stats = {
            "drafts_created": 0,
            "posts_scheduled": 0,
            "last_success": None,
            "next_run": None,
            "instagram_connected": False,
            "free_tier_mode": os.environ.get("FREE_TIER_MODE", "false").lower() == "true"
        }

        # Initialize modules
        self.content_engine = CaribbeanContentEngine()
        logger.info("🎭 Caribbean Content Engine initialized")
        self.media_processor = MediaProcessor()
        logger.info("🎬 Media Processor initialized")
        self.scheduler = ContentScheduler()
        self.cloud_storage = CloudStorage()
        self.instagram = InstagramManager()
        logger.info("✅ All modules loaded")
        
        # Test Instagram connection
        self._test_instagram_connection()
        
        if self.stats["free_tier_mode"]:
            logger.info("🆓 FREE TIER MODE ACTIVE: Optimized for Render free tier")
            logger.info("   • Processing 1 video per cycle")
            logger.info("   • Extended intervals between cycles")
            logger.info("   • Lightweight FFmpeg settings")

    def _test_instagram_connection(self):
        """Simplified Instagram test for free tier"""
        logger.info("🔗 Checking Instagram credentials...")
        
        # Just check if credentials exist
        if hasattr(self.instagram, 'valid'):
            self.stats["instagram_connected"] = self.instagram.valid
        else:
            # Assume connected if MediaProcessor has credentials
            if hasattr(self.media_processor, 'ig_access_token') and self.media_processor.ig_access_token:
                self.stats["instagram_connected"] = True
            else:
                self.stats["instagram_connected"] = False
        
        if self.stats["instagram_connected"]:
            logger.info("✅ Instagram credentials available")
        else:
            logger.warning("⚠️ Instagram credentials not set")

    def run_single_cycle(self):
        """
        Optimized bot cycle for free tier
        """
        logger.info("🔄 Starting optimized bot cycle (free tier)")
        start = datetime.now()
        
        try:
            # Add small delay to prevent immediate CPU spike
            time.sleep(2)
            
            # Process videos with free tier limits
            processed_drafts = self.media_processor.process_new_links()
            
            if not processed_drafts:
                logger.info("ℹ️ No media files to process")
                # Still update stats to show activity
                self.stats["last_success"] = datetime.now().isoformat()
                interval = int(os.environ.get("CYCLE_INTERVAL", "30"))
                self.stats["next_run"] = (datetime.now() + timedelta(minutes=interval)).isoformat()
                return
            
            # Update statistics
            self.stats["drafts_created"] += len(processed_drafts)
            
            # Count successful Instagram posts
            successful_posts = sum(1 for draft in processed_drafts if draft.get("instagram_posted", False))
            self.stats["posts_scheduled"] += successful_posts
            
            logger.info(f"📊 Processing complete — {len(processed_drafts)} videos processed")
            logger.info(f"🎯 Successfully posted {successful_posts}/{len(processed_drafts)} to Instagram")
            
            self.stats["last_success"] = datetime.now().isoformat()
            interval = int(os.environ.get("CYCLE_INTERVAL", "30"))
            self.stats["next_run"] = (datetime.now() + timedelta(minutes=interval)).isoformat()
            elapsed = (datetime.now() - start).total_seconds()
            logger.info(f"✅ Cycle completed in {elapsed:.1f}s")
            
            # Free tier: Add cooldown after processing
            if self.stats["free_tier_mode"] and processed_drafts:
                logger.info("⏸️ Free tier cooldown: 60 seconds")
                time.sleep(60)
            
        except Exception as e:
            logger.exception(f"❌ Cycle failed: {str(e)}")
            # Free tier: Longer delay on error
            if self.stats["free_tier_mode"]:
                logger.info("🔄 Free tier: Waiting 5 minutes after error")
                time.sleep(300)

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
            
            # Use longer interval for free tier
            interval_minutes = int(os.environ.get("CYCLE_INTERVAL", "30"))
            
            scheduler.add_job(
                self.run_single_cycle,
                trigger=IntervalTrigger(minutes=interval_minutes),
                id="main_cycle",
                max_instances=1,
                coalesce=True,
                misfire_grace_time=300  # Allow 5 minute grace period
            )
            scheduler.start()
            self.running = True
            logger.info(f"⏰ Scheduler started ({interval_minutes} min interval - Free Tier)")
            
            # Don't run immediate cycle on free tier to avoid startup spike
            if not self.stats["free_tier_mode"]:
                self.run_single_cycle()
            else:
                logger.info("⏳ Free tier: Skipping immediate cycle to avoid CPU spike")
                
        except Exception as e:
            logger.error(f"❌ Failed to start scheduler: {e}")

# ==============================
# FLASK ROUTES (same as before, just updated text)
# ==============================
@app.route("/")
def dashboard():
    bot = app.bot if hasattr(app, "bot") else None
    bot_stats = bot.stats if bot else {}
    
    free_tier_info = ""
    if bot and bot.stats.get("free_tier_mode"):
        free_tier_info = """
        <div class="card warning">
            <h3>🆓 Free Tier Mode Active</h3>
            <p>Optimized for Render free tier limits:</p>
            <ul>
                <li>Processing 1 video per cycle</li>
                <li>30+ minute intervals between cycles</li>
                <li>Lightweight video processing</li>
                <li>Automatic cooldown periods</li>
            </ul>
        </div>
        """
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>🎭 CCmasterbot Dashboard (Free Tier)</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 40px; }}
            .card {{ background: #f5f5f5; padding: 20px; border-radius: 10px; margin: 20px 0; }}
            .warning {{ background: #fff3cd; border-left: 4px solid #ffc107; }}
            .btn {{ display: inline-block; padding: 10px 20px; background: #007bff; color: white; text-decoration: none; border-radius: 5px; margin: 5px; }}
            .btn:hover {{ background: #0056b3; }}
            .success {{ color: green; }}
            .error {{ color: red; }}
            .warning {{ color: orange; }}
            .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin: 20px 0; }}
            .stat-box {{ background: white; padding: 15px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
            .stat-value {{ font-size: 24px; font-weight: bold; }}
            .stat-label {{ color: #666; font-size: 14px; }}
        </style>
    </head>
    <body>
        <h1>🎭 CCmasterbot Dashboard</h1>
        
        {free_tier_info}
        
        <div class="card">
            <h2>Status: <span class="success">● Automated</span></h2>
            <p>Automated video processing and Instagram posting system</p>
            <p><strong>Instagram Status:</strong> {'✅ Connected' if bot_stats.get('instagram_connected') else '❌ Not Connected'}</p>
            <p><strong>Mode:</strong> {'🆓 Free Tier Optimized' if bot_stats.get('free_tier_mode') else '🚀 Full Power'}</p>
        </div>
        
        <div class="card">
            <h2>Statistics</h2>
            <div class="stats">
                <div class="stat-box">
                    <div class="stat-value">{bot_stats.get('drafts_created', 0)}</div>
                    <div class="stat-label">Videos Processed</div>
                </div>
                <div class="stat-box">
                    <div class="stat-value">{bot_stats.get('posts_scheduled', 0)}</div>
                    <div class="stat-label">Instagram Posts</div>
                </div>
                <div class="stat-box">
                    <div class="stat-value">{'Yes' if bot_stats.get('instagram_connected') else 'No'}</div>
                    <div class="stat-label">Instagram Connected</div>
                </div>
                <div class="stat-box">
                    <div class="stat-value">{bot_stats.get('last_success', 'Never')[:16] if bot_stats.get('last_success') else 'Never'}</div>
                    <div class="stat-label">Last Success</div>
                </div>
            </div>
        </div>
        
        <div class="card">
            <h2>Quick Actions</h2>
            <a href="/run-cycle" class="btn">▶️ Run Cycle Now</a>
            <a href="/health" class="btn">🩺 Health Check</a>
            <a href="/stats" class="btn">📊 Statistics API</a>
        </div>
        
        <div class="card">
            <h2>Automation Status</h2>
            <p>The bot runs automatically every <strong>{os.environ.get('CYCLE_INTERVAL', '30')} minutes</strong></p>
            <p>Next scheduled run: <strong>{bot_stats.get('next_run', 'Unknown')[:16] if bot_stats.get('next_run') else 'Unknown'}</strong></p>
            <p><strong>Note:</strong> On free tier, processing is optimized to avoid limits</p>
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
        "free_tier": os.environ.get("FREE_TIER_MODE", "false").lower() == "true"
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
        "message": "Cycle started (free tier optimized)",
        "timestamp": datetime.utcnow().isoformat()
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
            "free_tier_mode": app.bot.stats.get("free_tier_mode", False),
            "cycle_interval": os.environ.get("CYCLE_INTERVAL", "30")
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
