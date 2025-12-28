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
            # Regular instagrapi version
            if hasattr(self.instagram, 'connected'):
                if self.instagram.connected:
                    logger.info("✅ Instagram connection successful (instagrapi)")
                    self.stats["instagram_connected"] = True
                else:
                    logger.warning("⚠️ Instagram connection failed (instagrapi)")
                    logger.warning("💡 Check INSTA_USERNAME and INSTA_PASSWORD")
                    self.stats["instagram_connected"] = False
            else:
                logger.info("ℹ️ Using mock Instagram Manager for testing")
                self.stats["instagram_connected"] = True  # Mock always succeeds

    def run_single_cycle(self):
        logger.info("🔄 Starting single bot cycle")
        start = datetime.now()
        try:
            # Skip text drafts for now
            media_drafts = self.media_processor.process_new_links()
            logger.info(f"📂 Found {len(media_drafts)} media files")
            
            if not media_drafts:
                logger.info("ℹ️ No media files to process")
                return

            uploaded = []
            for i, draft in enumerate(media_drafts):
                try:
                    logger.info(f"📤 Processing media {i+1}/{len(media_drafts)}: {draft.get('title', 'Unknown')}")
                    
                    # Get file ID
                    file_id = draft.get('file_id')
                    if not file_id:
                        logger.warning(f"⚠️ No file_id for {draft.get('title', 'Unknown')}")
                        continue
                    
                    # Method 1: Try to make file public
                    success = False
                    public_url = None
                    
                    try:
                        file = self.cloud_storage.drive.CreateFile({'id': file_id})
                        file.FetchMetadata()  # This verifies the file exists
                        
                        # Check if file is already public
                        try:
                            permissions = file.GetPermissions()
                            # Look for public permission
                            for perm in permissions:
                                if perm.get('type') == 'anyone' and perm.get('role') == 'reader':
                                    public_url = f"https://drive.google.com/uc?export=download&id={file_id}"
                                    logger.info(f"✅ File is already public: {public_url}")
                                    success = True
                                    break
                        except:
                            pass  # No permissions or can't read them
                        
                        # If not public, make it public
                        if not success:
                            file.InsertPermission({
                                "type": "anyone",
                                "value": "anyone",
                                "role": "reader"
                            })
                            public_url = f"https://drive.google.com/uc?export=download&id={file_id}"
                            logger.info(f"✅ Made file public: {public_url}")
                            success = True
                            
                    except Exception as e:
                        logger.error(f"❌ Method 1 failed for {file_id}: {e}")
                        
                    # Method 2: Try webContentLink
                    if not success:
                        try:
                            file = self.cloud_storage.drive.CreateFile({'id': file_id})
                            file.FetchMetadata()
                            
                            if 'webContentLink' in file:
                                public_url = file['webContentLink']
                                logger.info(f"✅ Using webContentLink: {public_url}")
                                success = True
                            elif 'alternateLink' in file:
                                public_url = file['alternateLink']
                                logger.info(f"✅ Using alternateLink: {public_url}")
                                success = True
                        except Exception as e:
                            logger.error(f"❌ Method 2 failed for {file_id}: {e}")
                    
                    # Method 3: Construct direct URL
                    if not success:
                        public_url = f"https://drive.google.com/file/d/{file_id}/view?usp=sharing"
                        logger.info(f"⚠️ Using constructed URL (may not be accessible): {public_url}")
                        success = True  # Try anyway
                    
                    if success and public_url:
                        draft["public_media_url"] = public_url
                        draft["media_url"] = public_url  # Add this for Instagram Manager compatibility
                        uploaded.append(draft)
                        logger.info(f"📝 Added to upload queue: {draft.get('title')}")
                    else:
                        logger.warning(f"⚠️ Could not get public URL for: {draft.get('title')}")
                        
                except Exception as e:
                    logger.error(f"❌ Failed to process media {i+1}: {str(e)}")
                    continue

            logger.info(f"📊 Successfully processed {len(uploaded)}/{len(media_drafts)} files")

            # Post to Instagram if auto_post enabled and Instagram is connected
            if uploaded and self.config.get("auto_post", True) and self.stats["instagram_connected"]:
                logger.info(f"📲 Attempting to post {len(uploaded)} files to Instagram...")
                successful_posts = 0
                for draft in uploaded:
                    try:
                        # Prepare Instagram post data
                        post_data = {
                            "media_url": draft.get("media_url") or draft.get("public_media_url"),
                            "public_media_url": draft.get("public_media_url"),  # Include both for compatibility
                            "caption": draft.get("caption", "Check out this track! #Music #Caribbean"),
                            "title": draft.get("title", "Music Track"),
                            "file_id": draft.get("file_id"),
                            "mime_type": draft.get("mime_type", "video/mp4")  # Add mime_type for Business API
                        }
                        
                        # Log what we're trying to post
                        logger.info(f"📤 Posting to Instagram: {draft.get('title')}")
                        
                        # Try to post
                        if self.instagram.schedule_post(post_data):
                            successful_posts += 1
                            self.stats["posts_scheduled"] += 1
                            logger.info(f"✅ Scheduled Instagram post: {draft.get('title', 'Untitled')}")
                        else:
                            logger.warning(f"⚠️ Instagram returned False for: {draft.get('title', 'Unknown')}")
                    except Exception as e:
                        logger.error(f"❌ Instagram scheduling error: {str(e)}")
                        logger.error(f"Error details: {traceback.format_exc()}")
                
                logger.info(f"🎯 Successfully scheduled {successful_posts}/{len(uploaded)} posts")
            elif uploaded and not self.stats["instagram_connected"]:
                logger.warning("⚠️ Skipping Instagram posts - Instagram not connected")
                logger.info(f"   Would have posted {len(uploaded)} files if connected")
            elif uploaded and not self.config.get("auto_post", True):
                logger.info("⏸️ Auto-posting disabled in config")
            else:
                logger.info("ℹ️ No files to post or Instagram not configured")

            self.stats["last_success"] = datetime.now().isoformat()
            self.stats["next_run"] = (datetime.now() + timedelta(minutes=20)).isoformat()
            elapsed = (datetime.now() - start).total_seconds()
            logger.info(f"✅ Cycle completed in {elapsed:.1f}s - Processed {len(uploaded)} media files")

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
            <p>Automated content generation and posting system</p>
            <p><strong>Instagram Status:</strong> {instagram_status}</p>
        </div>
        
        <div class="card">
            <h2>Statistics</h2>
            <div class="stats">
                <div class="stat-box">
                    <div class="stat-value">{bot_stats.get('drafts_created', 0)}</div>
                    <div class="stat-label">Drafts Created</div>
                </div>
                <div class="stat-box">
                    <div class="stat-value">{bot_stats.get('posts_scheduled', 0)}</div>
                    <div class="stat-label">Posts Scheduled</div>
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
            <p>CCmasterbot automates content creation, media processing, and social media posting.</p>
            <p>Runs automatically every 20 minutes or can be triggered manually.</p>
            <p><strong>Current Mode:</strong> Business/Creator Account (Facebook Graph API)</p>
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
            instagram_status = "ℹ️ Using mock Instagram Manager"
            app.bot.stats["instagram_connected"] = True
        
        response = {
            "success": True,
            "message": "Instagram connection test completed",
            "instagram_status": instagram_status,
            "timestamp": datetime.utcnow().isoformat()
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
