#!/usr/bin/env python3
"""
CCmasterbot - Free Tier Optimized Version
Simplified to stay within Render free tier limits
"""

import os
import sys
import logging
import json
import time
from datetime import datetime, timedelta
from threading import Thread, Lock
from flask import Flask, jsonify, render_template_string

# ==============================
# SAFE IMPORTS
# ==============================
try:
    from modules.media_processor import MediaProcessor
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
    handlers=[logging.StreamHandler()],  # No file handler for free tier
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
        self.processing_lock = Lock()  # Prevent concurrent processing
        self.stats = {
            "videos_processed": 0,
            "instagram_posts": 0,
            "last_processed": None,
            "next_run": None,
            "status": "idle"
        }

        # Initialize only essential modules
        self.media_processor = MediaProcessor()
        logger.info("✅ Media Processor initialized")
        
        # Disable scheduler if environment variable says so
        if os.environ.get("DISABLE_SCHEDULER", "false").lower() == "true":
            logger.info("⏸️ Scheduler disabled (free tier optimization)")
        else:
            # Start with manual triggers only
            logger.info("ℹ️ Using manual triggers (free tier)")
    
    def process_one_video(self):
        """
        Process exactly ONE video - optimized for free tier
        Returns immediately, runs in background
        """
        if self.processing_lock.locked():
            logger.warning("⚠️ Already processing a video, skipping")
            return {"status": "busy", "message": "Already processing"}
        
        # Start in background thread
        Thread(target=self._process_one_video_safe, daemon=True).start()
        return {"status": "started", "message": "Processing one video"}
    
    def _process_one_video_safe(self):
        """Safe wrapper to process one video with timeout"""
        with self.processing_lock:
            try:
                self.stats["status"] = "processing"
                start_time = time.time()
                
                logger.info("🔄 Starting single video processing")
                
                # Process ONE video
                processed = self.media_processor.process_one_video()
                
                if processed:
                    self.stats["videos_processed"] += 1
                    self.stats["instagram_posts"] += 1 if processed[0].get("instagram_posted", False) else 0
                    self.stats["last_processed"] = datetime.now().isoformat()
                    logger.info(f"✅ Processed video in {time.time() - start_time:.1f}s")
                else:
                    logger.warning("⚠️ No videos processed")
                
                self.stats["status"] = "idle"
                
            except Exception as e:
                logger.error(f"❌ Processing failed: {str(e)}")
                self.stats["status"] = "error"
    
    def get_status(self):
        """Get current status"""
        return {
            **self.stats,
            "uptime": self._get_uptime(),
            "memory_usage": self._get_memory_usage(),
            "is_processing": self.processing_lock.locked()
        }
    
    def _get_uptime(self):
        """Get system uptime if available"""
        try:
            with open('/proc/uptime', 'r') as f:
                uptime_seconds = float(f.readline().split()[0])
                return str(timedelta(seconds=uptime_seconds))
        except:
            return "unknown"
    
    def _get_memory_usage(self):
        """Get memory usage if available"""
        try:
            import psutil
            process = psutil.Process(os.getpid())
            mem_info = process.memory_info()
            return f"{mem_info.rss / 1024 / 1024:.1f} MB"
        except:
            return "unknown"

# ==============================
# FLASK ROUTES - Simplified
# ==============================
@app.route("/")
def dashboard():
    bot = app.bot if hasattr(app, "bot") else None
    status = bot.get_status() if bot else {}
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>🎬 Video Processor (Free Tier)</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
            .container {{ max-width: 800px; margin: 0 auto; }}
            .card {{ background: white; padding: 20px; border-radius: 10px; margin: 15px 0; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
            .btn {{ display: inline-block; padding: 12px 24px; background: #007bff; color: white; text-decoration: none; border-radius: 5px; margin: 5px; border: none; cursor: pointer; font-size: 16px; }}
            .btn:hover {{ background: #0056b3; }}
            .btn-success {{ background: #28a745; }}
            .btn-success:hover {{ background: #1e7e34; }}
            .btn-danger {{ background: #dc3545; }}
            .btn-danger:hover {{ background: #c82333; }}
            .btn:disabled {{ background: #6c757d; cursor: not-allowed; }}
            .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 10px; margin: 15px 0; }}
            .stat {{ background: #e9ecef; padding: 15px; border-radius: 8px; text-align: center; }}
            .stat-value {{ font-size: 24px; font-weight: bold; margin: 5px 0; }}
            .stat-label {{ color: #666; font-size: 14px; }}
            .status-idle {{ color: #6c757d; }}
            .status-processing {{ color: #ffc107; animation: pulse 1.5s infinite; }}
            .status-error {{ color: #dc3545; }}
            @keyframes pulse {{ 0% {{ opacity: 1; }} 50% {{ opacity: 0.5; }} 100% {{ opacity: 1; }} }}
            .log-container {{ max-height: 200px; overflow-y: auto; background: #212529; color: #fff; padding: 15px; border-radius: 5px; font-family: monospace; font-size: 12px; margin: 15px 0; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🎬 Video Processor (Free Tier)</h1>
            <p>Manually process videos to stay within Render free tier limits</p>
            
            <div class="card">
                <h2>Current Status: <span class="status-{status.get('status', 'idle')}">● {status.get('status', 'idle').upper()}</span></h2>
                <div class="stats">
                    <div class="stat">
                        <div class="stat-value">{status.get('videos_processed', 0)}</div>
                        <div class="stat-label">Videos Processed</div>
                    </div>
                    <div class="stat">
                        <div class="stat-value">{status.get('instagram_posts', 0)}</div>
                        <div class="stat-label">Instagram Posts</div>
                    </div>
                    <div class="stat">
                        <div class="stat-value">{status.get('last_processed', 'Never')[:16] if status.get('last_processed') else 'Never'}</div>
                        <div class="stat-label">Last Processed</div>
                    </div>
                    <div class="stat">
                        <div class="stat-value">{status.get('memory_usage', 'N/A')}</div>
                        <div class="stat-label">Memory Used</div>
                    </div>
                </div>
            </div>
            
            <div class="card">
                <h2>Quick Actions</h2>
                <button onclick="processVideo()" class="btn btn-success" id="processBtn" {'disabled' if status.get('is_processing') else ''}>
                    {'⏳ Processing...' if status.get('is_processing') else '▶️ Process One Video'}
                </button>
                <a href="/health" class="btn">🩺 Health Check</a>
                <a href="/status" class="btn">📊 Status API</a>
                <a href="/logs" class="btn">📝 View Logs</a>
            </div>
            
            <div class="card">
                <h2>How it Works</h2>
                <p>1. Finds videos in Google Drive source folder</p>
                <p>2. Processes ONE video at a time (free tier limit)</p>
                <p>3. Trims to 90s and adds bouncing logo</p>
                <p>4. Uploads to processed folder</p>
                <p>5. Posts to Instagram (if credentials set)</p>
                <p><strong>Note:</strong> Manual processing only to avoid free tier limits</p>
            </div>
            
            <div class="card">
                <h3>Recent Activity</h3>
                <div class="log-container" id="logs">
                    Loading logs...
                </div>
            </div>
        </div>
        
        <script>
            function processVideo() {{
                const btn = document.getElementById('processBtn');
                btn.disabled = true;
                btn.textContent = '⏳ Processing...';
                
                fetch('/process-one')
                    .then(response => response.json())
                    .then(data => {{
                        alert(data.message || 'Processing started');
                        setTimeout(() => location.reload(), 2000);
                    }})
                    .catch(error => {{
                        alert('Error: ' + error);
                        btn.disabled = false;
                        btn.textContent = '▶️ Process One Video';
                    }});
            }}
            
            // Auto-refresh status every 10 seconds
            setInterval(() => {{
                fetch('/status')
                    .then(r => r.json())
                    .then(data => {{
                        if (data.is_processing === false) {{
                            document.getElementById('processBtn').disabled = false;
                            document.getElementById('processBtn').textContent = '▶️ Process One Video';
                        }}
                    }});
            }}, 10000);
        </script>
    </body>
    </html>
    """
    return render_template_string(html)

@app.route("/health")
def health():
    """Lightweight health check"""
    return jsonify({
        "status": "healthy",
        "service": "video-processor",
        "timestamp": datetime.now().isoformat(),
        "free_tier": True
    })

@app.route("/status")
def status():
    """Get bot status"""
    if not hasattr(app, "bot"):
        return jsonify(error="Bot not initialized"), 500
    return jsonify(app.bot.get_status())

@app.route("/process-one")
def process_one_video():
    """Process exactly one video"""
    if not hasattr(app, "bot"):
        return jsonify(success=False, message="Bot not initialized"), 500
    
    result = app.bot.process_one_video()
    return jsonify(result)

@app.route("/logs")
def get_logs():
    """Get recent logs"""
    try:
        log_lines = []
        if os.path.exists("logs/ccmasterbot.log"):
            with open("logs/ccmasterbot.log", "r") as f:
                log_lines = f.readlines()[-50:]  # Last 50 lines
        return jsonify({"logs": log_lines})
    except:
        return jsonify({"logs": ["No logs available"]})

# ==============================
# ENTRYPOINT - Free Tier Optimized
# ==============================
def create_app():
    """Create and initialize the Flask application for free tier"""
    try:
        # Use simple Flask app without heavy initialization
        app.bot = CCmasterbot()
        return app
    except Exception as e:
        logger.error(f"❌ Failed to create app: {e}")
        # Return minimal app anyway
        return app

# Gunicorn will import 'app'
app = create_app()

if __name__ == "__main__":
    # Development server - not used in production
    port = int(os.environ.get("PORT", 10000))
    logger.info(f"🌐 Starting on port {port}")
    app.run(
        host="0.0.0.0",
        port=port,
        debug=False,
        threaded=True
    )
