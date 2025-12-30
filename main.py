from flask import Flask, request, jsonify
import os
import threading
import time
import logging
from videoprocessor import VideoProcessor

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Initialize processor once
processor = None

def get_processor():
    """Lazy initialize to avoid startup errors"""
    global processor
    if processor is None:
        try:
            # Get config from environment
            video_inbox_id = os.environ.get('VIDEO_INBOX_FOLDER_ID')
            processed_folder_id = os.environ.get('PROCESSED_FOLDER_ID')
            logo_file = os.environ.get('LOGO_FILE', 'logo_real.png')
            service_account_file = os.environ.get('GOOGLE_SERVICE_ACCOUNT', 'service_account.json')
            
            if not all([video_inbox_id, processed_folder_id, service_account_file]):
                logger.error("Missing required environment variables")
                return None
            
            processor = VideoProcessor(
                credentials_file=service_account_file,
                video_inbox_id=video_inbox_id,
                processed_folder_id=processed_folder_id,
                logo_path=logo_file
            )
            logger.info("✅ Video processor initialized")
        except Exception as e:
            logger.error(f"❌ Failed to initialize processor: {e}")
    return processor

def process_one_video():
    """Process a single video (free tier optimized)"""
    try:
        proc = get_processor()
        if not proc:
            return False, "Processor not initialized"
        
        # Check for videos
        videos = proc.check_for_new_videos()
        if not videos:
            return True, "No videos to process"
        
        # Take first video only (free tier limitation)
        video = videos[0]
        logger.info(f"🎬 Processing: {video['name']}")
        
        # Process with minimal memory usage
        success = proc.process_single_video_fast(video)
        
        if success:
            return True, f"Processed: {video['name']}"
        else:
            return False, f"Failed: {video['name']}"
            
    except Exception as e:
        logger.error(f"Processing error: {e}")
        return False, str(e)

@app.route('/webhook', methods=['POST'])
def webhook():
    """Trigger from Google Apps Script when video is dropped"""
    logger.info("🔔 Webhook received - starting processing")
    
    # Process in background thread
    thread = threading.Thread(target=process_one_video)
    thread.daemon = True
    thread.start()
    
    return jsonify({
        'status': 'started',
        'message': 'Processing started in background'
    }), 202

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'service': 'video-processor'}), 200

@app.route('/process', methods=['GET'])
def process_manual():
    """Manual trigger endpoint"""
    success, message = process_one_video()
    return jsonify({'success': success, 'message': message}), 200 if success else 500

# Start processing on startup (for scheduled jobs)
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    logger.info(f"🚀 Starting on port {port}")
    
    # Process any pending videos on startup
    threading.Thread(target=process_one_video).start()
    
    app.run(host='0.0.0.0', port=port, threaded=True)
