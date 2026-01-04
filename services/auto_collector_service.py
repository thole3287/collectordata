import threading
import time
import logging
import random
from datetime import datetime

import services.keyword_service as keyword_service
import services.pexels_service as pexels_service
import services.video_service as video_service
import yt_downloaderpy as yt
import os
import services.minio_service as minio_service

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
                        
                    logger.info(f"Auto-Collecting for keyword: {keyword}")
                    
                    # --- YOUTUBE ---
                    try:
                        # Download 1 video per cycle to be gentle
                        videos = yt.download_by_keyword(keyword, num_videos=1)
                        if videos:
                             self._process_downloaded_folder()
                    except Exception as e:
                        logger.error(f"Error auto-downloading YouTube for {keyword}: {e}")

                    # --- PEXELS ---
                    try:
                        # Download 1 video per cycle
                        api_key = os.getenv('PEXELS_API_KEY')
                        if api_key:
                            pexels_service.download_pexels_videos(keyword, num_videos=1, api_key=api_key)
                            # Pexels service handles its own frame extraction/cleanup internally 
                            # inside save_pexels_video_to_database via minio helper extraction call
                            # But wait, pexels_service.download_pexels_videos saves file to disk and then calls save...
                            # We might need to ensure frame extraction happens if it wasn't automatic.
                            # Checking pexels_service: it calls save_pexels_video_to_database -> extract_and_upload_frames.
                            # So it is handled.
                    except Exception as e:
                        logger.error(f"Error auto-downloading Pexels for {keyword}: {e}")
                    
                    # Short sleep between keywords to avoid rate limits
                    time.sleep(5) 

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
            downloads_folder = os.path.join(os.getcwd(), 'downloads')
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
