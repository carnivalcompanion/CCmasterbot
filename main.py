#!/usr/bin/env python3
"""
CCmasterbot - Master Orchestrator
Fully merged and optimized for Render deployment
"""

import os
import sys
import logging
import json
import traceback
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
            "next_run": None,
            "instagram_connected": False
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

    def _test_instagram_connection(self):
        """Test Instagram Business API connection"""
        logger.info("🔗 Testing Instagram Business API connection...")
        
        # Check if InstagramManager has 'valid' attribute (Business API)
        if hasattr(self.instagram, 'valid'):
            if self.instagram.valid:
                logger.info("✅ Instagram Business API credentials are valid")
                if hasattr(self.instagram, 'test_connection'):
                    if self.instagram.test_connection():
                        logger.info("✅ Instagram Graph API connection successful!")
                        self.stats["instagram_connected"] = True
                    else:
                        logger.warning("⚠️ Instagram Graph API connection test failed")
                        logger.warning("💡 Check IG_ACCESS_TOKEN, IG_BUSINESS_ACCOUNT_ID, IG_USER_ID, IG_PAGE_ID")
                        self.stats["instagram_connected"] = False
                else:
                    logger.info("ℹ️ Instagram Manager doesn't have test_connection method")
            else:
                logger.error("❌ Instagram Business API credentials are missing or invalid")
                logger.error("💡 Please set these environment variables in Render:")
                logger.error("   - IG_ACCESS_TOKEN")
                logger.error("   - IG_BUSINESS_ACCOUNT_ID")
                logger.error("   - IG_USER_ID")
                logger.error("   - IG_PAGE_ID")
                self.stats["instagram_connected"] = False
        else:
            # For the simplified InstagramManager
            if hasattr(self.instagram, 'test_connection'):
                if self.instagram.test_connection():
                    logger.info("✅ Instagram connection successful")
                    self.stats["instagram_connected"] = True
                else:
                    logger.warning("⚠️ Instagram connection test failed")
                    self.stats["instagram_connected"] = False
            else:
                logger.info("ℹ️ Instagram posting handled by MediaProcessor")
                self.stats["instagram_connected"] = True

    def run_single_cycle(self):
        """
        Main bot cycle - simplified since media_processor now handles Instagram posting
        """
        logger.info("🔄 Starting single bot cycle")
        start = datetime.now()
        try:
            # Process videos and post to Instagram automatically
            processed_drafts = self.media_processor.process_new_links()
            
            if not processed_drafts:
                logger.info("ℹ️ No media files to process")
                return
            
            # Update statistics
            self.stats["drafts_created"] += len(processed_drafts)
            
            # Count successful Instagram posts
            successful_posts = sum(1 for draft in processed_drafts if draft.get("instagram_posted", False))
            self.stats["posts_scheduled"] += successful_posts
            
            logger.info(f"📊 Processing complete — {len(processed_drafts)} videos processed")
            logger.info(f"🎯 Successfully posted {successful_posts}/{len(processed_drafts)} to Instagram")
            
            self.stats["last_success"] = datetime.now().isoformat()
            self.stats["next_run"] = (datetime.now() + timedelta(minutes=20)).isoformat()
            elapsed = (datetime.now() - start).total_seconds()
            logger.info(f"✅ Cycle completed in {elapsed:.1f}s")
            
        except Exception as e:
            logger.exception(f"❌ Cycle failed: {str(e)}")

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
    # Get bot instance if available
    bot_stats = {}
    instagram_status = "Not initialized"
    
    if hasattr(app, "bot"):
        bot_stats = app.bot.stats
        instagram_status = "✅ Connected" if app.bot.stats.get("instagram_connected") else "❌ Not Connected"
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>🎭 CCmasterbot Dashboard</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 40px; }}
            .card {{ background: #f5f5f5; padding: 20px; border-radius: 10px; margin: 20px 0; }}
            .btn {{ display: inline-block; padding: 10px 20px; background: #007bff; color: white; text-decoration: none; border-radius: 5px; margin: 5px; }}
            .btn:hover {{ background: #0056b3; }}
            .success {{ color: green; }}
            .error {{ color: red; }}
            .warning {{ color: orange; }}
            .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin: 20px 0; }}
            .stat-box {{ background: white; padding: 15px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
            .stat-value {{ font-size: 24px; font-weight: bold; }}
            .stat-label {{ color: #666; font-size: 14px; }}
            .status-indicator {{ display: inline-block; width: 12px; height: 12px; border-radius: 50%; margin-right: 8px; }}
            .status-on {{ background: green; }}
            .status-off {{ background: red; }}
        </style>
    </head>
    <body>
        <h1>🎭 CCmasterbot Dashboard</h1>
        
        <div class="card">
            <h2>Status: <span class="success">● Running</span></h2>
            <p>Automated video processing and Instagram posting system</p>
            <p><strong>Instagram Status:</strong> {instagram_status}</p>
            <p><strong>Processing Mode:</strong> Auto-Instagram posting via MediaProcessor</p>
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
                    <div class="stat-value">{bot_stats.get('last_success', 'Never')[:19] if bot_stats.get('last_success') else 'Never'}</div>
                    <div class="stat-label">Last Success</div>
                </div>
            </div>
        </div>
        
        <div class="card">
            <h2>Quick Actions</h2>
            <a href="/run-cycle" class="btn">▶️ Run Cycle Now</a>
            <a href="/health" class="btn">🩺 Health Check</a>
            <a href="/stats" class="btn">📊 Statistics API</a>
            <a href="/test-instagram" class="btn">📱 Test Instagram</a>
        </div>
        
        <div class="card">
            <h2>Endpoints</h2>
            <ul>
                <li><code>GET /</code> - This dashboard</li>
                <li><code>GET /health</code> - Health status</li>
                <li><code>GET /run-cycle</code> - Trigger manual cycle</li>
                <li><code>GET /stats</code> - Bot statistics (JSON)</li>
                <li><code>GET /test-instagram</code> - Test Instagram connection</li>
            </ul>
        </div>
        
        <div class="card">
            <h2>About</h2>
            <p>CCmasterbot automatically processes videos from Google Drive and posts to Instagram.</p>
            <p>1. Finds videos in source folder</p>
            <p>2. Trims to 90s and adds bouncing logo</p>
            <p>3. Uploads to processed folder</p>
            <p>4. Posts directly to Instagram</p>
            <p><strong>Runs automatically every 20 minutes</strong></p>
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
        "uptime": "Always running" if app.bot.running else "Not scheduled",
        "note": "Instagram posting handled by MediaProcessor module"
    }
    return jsonify(stats_data)

@app.route("/test-instagram")
def test_instagram():
    """Test Instagram connection"""
    if not hasattr(app, "bot"):
        return jsonify(success=False, message="Bot not initialized"), 500
    
    try:
        # Test Instagram connection
        instagram_status = "Not tested"
        
        if hasattr(app.bot.instagram, 'test_connection'):
            if app.bot.instagram.test_connection():
                instagram_status = "✅ Connected and working"
                app.bot.stats["instagram_connected"] = True
            else:
                instagram_status = "❌ Connection test failed"
                app.bot.stats["instagram_connected"] = False
        elif hasattr(app.bot.instagram, 'valid'):
            if app.bot.instagram.valid:
                instagram_status = "✅ Credentials valid (Business API)"
                app.bot.stats["instagram_connected"] = True
            else:
                instagram_status = "❌ Credentials invalid (Business API)"
                app.bot.stats["instagram_connected"] = False
        else:
            instagram_status = "ℹ️ Using simplified Instagram Manager"
            app.bot.stats["instagram_connected"] = True
        
        response = {
            "success": True,
            "message": "Instagram connection test completed",
            "instagram_status": instagram_status,
            "timestamp": datetime.utcnow().isoformat(),
            "note": "Actual Instagram posting is handled by MediaProcessor"
        }
        
        return jsonify(response)
        
    except Exception as e:
        return jsonify(success=False, message=f"Instagram test failed: {str(e)}"), 500

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
