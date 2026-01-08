import threading
import time
import logging
import random
from datetime import datetime

import services.keyword_service as keyword_service
import services.pexels_service as pexels_service
import services.video_service as video_service
import services.yt_service as yt
import os
import services.minio_service as minio_service
from services.kafka_producer import kafka_queue
import extensions

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AutoCollectorService:
    def __init__(self):
        self._is_running = False
        self._thread = None
        self._interval = 60  # Sleep time between keyword cycles (seconds)
        self._status_message = "Stopped"

    def start(self):
        """Start the auto-collection loop"""
        if self._is_running:
            return {"success": False, "message": "Service is already running"}
        
        self._is_running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        self._status_message = "Running"
        return {"success": True, "message": "Auto collection started"}

    def stop(self):
        """Stop the auto-collection loop"""
        if not self._is_running:
            return {"success": False, "message": "Service is already stopped"}
        
        self._is_running = False
        # Thread will exit on next loop check
        self._status_message = "Stopping..."
        return {"success": True, "message": "Auto collection stopping"}

    def get_status(self):
        """Get current status"""
        return {
            "is_running": self._is_running,
            "message": self._status_message
        }

    def _loop(self):
        """Main collection loop"""
        logger.info("Auto Collector Loop Started")
        
        while self._is_running:
            try:
                # 1. Get Active Keywords
                keywords = keyword_service.get_all_keywords(active_only=True)
                
                if not keywords:
                    self._status_message = "Running (No active keywords)"
                    logger.info("No active keywords found. Sleeping...")
                    time.sleep(self._interval)
                    continue

                self._status_message = f"Processing {len(keywords)} keywords..."
                
                for kw_data in keywords:
                    if not self._is_running:
                        break
                        
                    keyword = kw_data.get('keyword')
                    if not keyword:
                        continue
                        
                    logger.info(f"Dispatching task for keyword: {keyword}")
                    
                    # --- YOUTUBE ---
                    try:
                        kafka_queue.send_task('youtube', keyword)
                    except Exception as e:
                        logger.error(f"Error dispatching YouTube task for {keyword}: {e}")

                    # --- PEXELS ---
                    try:
                        kafka_queue.send_task('pexels', keyword)
                    except Exception as e:
                        logger.error(f"Error dispatching Pexels task for {keyword}: {e}")
                    
                    # Short sleep just to avoid flooding the queue instantly (optional, can be removed for pure async)
                    time.sleep(1) 

                logger.info("Cycle completed. Sleeping.")
                self._status_message = "Sleeping..."
                
                # Sleep for interval, checking is_running
                for _ in range(self._interval):
                    if not self._is_running:
                        break
                    time.sleep(1)
                    
            except Exception as e:
                logger.error(f"Error in auto collector loop: {e}")
                self._status_message = f"Error: {e}"
                time.sleep(10) # Prevent tight error loop
        
        self._status_message = "Stopped"
        logger.info("Auto Collector Loop Stopped")

    def _process_downloaded_folder(self):
        """Helper to process 'downloads' folder for YouTube videos"""
        try:
            downloads_folder = extensions.DOWNLOADS_FOLDER
            if os.path.exists(downloads_folder):
                # Use video service to extract frames, convert, upload, etc.
                video_service.extract_frames_from_folder(downloads_folder)
                
                # Clean up downloads folder?
                # video_service doesn't delete the video files, only extracts frames.
                # But typically we might want to delete them if stored in MinIO?
                # The video files from yt_downloaderpy are saved to DB logic.
                # Checking yt_downloaderpy... it saves to disk and DB.
                # If we want to move to MinIO only for videos too, we'd need to update yt_downloaderpy.
                # For now, let's keep existing behavior (files stay in downloads or are managed by yt_downloaderpy if changed).
                # Actually, user previously asked to upload *images* to MinIO. 
                # Frame extraction uploads to MinIO.
                pass
        except Exception as e:
            logger.error(f"Error processing downloads folder: {e}")

# Global instance
auto_collector = AutoCollectorService()
