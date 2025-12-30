import os
import io
import tempfile
import logging
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload
from googleapiclient.errors import HttpError

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class VideoProcessor:
    def __init__(self, credentials_file, video_inbox_id, processed_folder_id, logo_path=None):
        """Initialize with Google Drive credentials"""
        self.creds = service_account.Credentials.from_service_account_file(
            credentials_file,
            scopes=['https://www.googleapis.com/auth/drive']
        )
        self.drive_service = build('drive', 'v3', credentials=self.creds)
        self.video_inbox_id = video_inbox_id
        self.processed_folder_id = processed_folder_id
        self.logo_path = logo_path
        
        # Optimized settings for free tier
        self.target_duration = 90
        self.max_width = 1080
        self.max_height = 1920
        
        logger.info(f"📁 Watching folder: {video_inbox_id}")
    
    def check_for_new_videos(self):
        """Check for new video files in inbox"""
        try:
            query = f"'{self.video_inbox_id}' in parents and mimeType contains 'video/'"
            results = self.drive_service.files().list(
                q=query,
                pageSize=5,
                orderBy='createdTime desc',
                fields='files(id, name, mimeType, size)'
            ).execute()
            
            files = results.get('files', [])
            logger.info(f"Found {len(files)} video(s)")
            return files
        except Exception as e:
            logger.error(f"Error checking videos: {e}")
            return []
    
    def download_video(self, file_id, file_name):
        """Download video to temp file"""
        try:
            request = self.drive_service.files().get_media(fileId=file_id)
            file_data = io.BytesIO()
            downloader = MediaIoBaseDownload(file_data, request)
            
            done = False
            while not done:
                _, done = downloader.next_chunk()
            
            # Save to temp file
            temp_dir = tempfile.gettempdir()
            safe_name = ''.join(c for c in file_name if c.isalnum() or c in '._- ')
            temp_path = os.path.join(temp_dir, safe_name)
            
            with open(temp_path, 'wb') as f:
                f.write(file_data.getvalue())
            
            logger.info(f"Downloaded: {file_name} ({os.path.getsize(temp_path)//1024}KB)")
            return temp_path
            
        except Exception as e:
            logger.error(f"Download failed: {e}")
            raise
    
    def process_single_video_fast(self, video_info):
        """Ultra-fast processing for free tier"""
        temp_path = None
        processed_path = None
        
        try:
            # 1. Download
            temp_path = self.download_video(video_info['id'], video_info['name'])
            
            # 2. Ultra-fast processing (minimal memory usage)
            processed_path = self._process_fast(temp_path, video_info['name'])
            
            # 3. Upload to processed
            upload_id = self._upload_to_processed(processed_path, video_info['name'])
            
            # 4. Delete original
            self._delete_original(video_info['id'])
            
            logger.info(f"✅ Successfully processed: {video_info['name']}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Processing failed: {e}")
            return False
            
        finally:
            # 5. Always cleanup temp files
            self._cleanup_files([temp_path, processed_path])
    
    def _process_fast(self, input_path, original_name):
        """Minimal processing for max throughput"""
        import subprocess
        import uuid
        
        # Generate unique output filename
        output_name = f"processed_{uuid.uuid4().hex[:8]}_{original_name}"
        output_path = os.path.join(tempfile.gettempdir(), output_name)
        
        # OPTION A: Use FFmpeg directly (FASTER than MoviePy)
        # This is more efficient for simple operations
        
        # 1. Trim to 90 seconds if needed
        duration_cmd = [
            'ffprobe', '-v', 'error', '-show_entries', 
            'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', input_path
        ]
        
        try:
            duration = float(subprocess.check_output(duration_cmd).decode().strip())
            trim_filter = f',trim=duration=90' if duration > 90 else ''
        except:
            trim_filter = ''
        
        # 2. Scale to 1080x607 (16:9) and pad to 1080x1920 with black borders
        # 3. Overlay logo in top border if exists
        ffmpeg_cmd = [
            'ffmpeg',
            '-i', input_path,
            '-vf', f'scale=1080:607:force_original_aspect_ratio=disable{trim_filter},'
                   f'pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black',
            '-c:v', 'libx264',
            '-preset', 'ultrafast',      # Fastest encoding
            '-crf', '28',                # Lower quality = faster
            '-c:a', 'aac',
            '-b:a', '96k',               # Low audio bitrate
            '-movflags', '+faststart',
            '-y',                        # Overwrite output
            output_path
        ]
        
        # Add logo if exists
        if self.logo_path and os.path.exists(self.logo_path):
            # Resize logo first
            logo_resized = os.path.join(tempfile.gettempdir(), 'logo_resized.png')
            subprocess.run([
                'ffmpeg', '-i', self.logo_path, 
                '-vf', 'scale=100:50',
                '-y', logo_resized
            ], capture_output=True)
            
            # Update command to overlay logo
            ffmpeg_cmd[4] = f'scale=1080:607:force_original_aspect_ratio=disable{trim_filter},'
                           f'pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black,'
                           f'overlay=(W-w)/2:30'
            ffmpeg_cmd.insert(3, '-i')
            ffmpeg_cmd.insert(4, logo_resized)
            
            # Cleanup resized logo
            if os.path.exists(logo_resized):
                os.remove(logo_resized)
        
        # Run FFmpeg
        logger.info(f"Processing with FFmpeg...")
        result = subprocess.run(
            ffmpeg_cmd,
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            logger.error(f"FFmpeg error: {result.stderr[:500]}")
            raise Exception("Video processing failed")
        
        logger.info(f"Processed: {output_path} ({os.path.getsize(output_path)//1024}KB)")
        return output_path
    
    def _upload_to_processed(self, file_path, original_name):
        """Upload to processed folder"""
        try:
            file_metadata = {
                'name': f'processed_{original_name}',
                'parents': [self.processed_folder_id]
            }
            
            media = MediaFileUpload(
                file_path,
                mimetype='video/mp4',
                resumable=True
            )
            
            file = self.drive_service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id'
            ).execute()
            
            logger.info(f"Uploaded to processed folder: {file['id']}")
            return file['id']
            
        except Exception as e:
            logger.error(f"Upload failed: {e}")
            raise
    
    def _delete_original(self, file_id):
        """Delete from inbox"""
        try:
            self.drive_service.files().delete(fileId=file_id).execute()
            logger.info(f"Deleted original: {file_id}")
        except Exception as e:
            logger.error(f"Delete failed: {e}")
            # Don't raise - continue even if delete fails
    
    def _cleanup_files(self, file_paths):
        """Cleanup temporary files"""
        for path in file_paths:
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                except:
                    pass
