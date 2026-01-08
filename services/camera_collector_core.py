"""Camera image collector service."""
import os
import logging
import requests
from datetime import datetime
from typing import List, Dict, Optional
import numpy as np
import cv2
import services.minio_service as minio_service
import services.database as db_service
import services.scene_analysis as scene_analysis


logger = logging.getLogger(__name__)


class CameraCollector:
    """Service for collecting images from traffic cameras."""
    
    API_BASE_URL = "https://giaothong.hochiminhcity.gov.vn/render/ImageHandler.ashx"
    REQUEST_TIMEOUT = 30  # seconds
    
    def __init__(self, cameras: List[Dict[str, str]], storage_path: str = "data"):
        """
        Initialize the camera collector.
        
        Args:
            cameras: List of camera dictionaries with 'id' and 'name' keys
            storage_path: Base path for storing collected images
        """
        self.cameras = cameras
        self.storage_path = storage_path
        self.last_collection_time: Optional[datetime] = None
        self.collection_stats = {
            'total_attempts': 0,
            'successful': 0,
            'failed': 0
        }
        
        # Create a session to maintain cookies and connection pooling
        self.session = requests.Session()
        self.session.headers.update(self._get_headers())
        self._set_cookies()
        
        # Ensure base storage directory exists
        os.makedirs(storage_path, exist_ok=True)
        logger.info(f"Initialized CameraCollector with {len(cameras)} camera(s)")
    
    def _set_cookies(self) -> None:
        """Set cookies to mimic browser session."""
        cookies = {
            'ASP.NET_SessionId': 'ss4j2qn2xxpgfy1whbcyoxje',
            '.VDMS': 'DF33FAAFE9A0CB23AA1890D816F9927B32446150CDBC6F7CD0BBC69C1426719AF8191A17B90EF8A3CDB6D3C9CD89C9704CB97F1BF5980E26CE614A1E7CBE0AA782BB6B756974344DA5EAAA3ACC9811A536B8D3F76B06DCB4208133075B10FC32FEF5B85CD44BF76151404F439F94769BE37DF18E',  # Should update this periodically or fetch fresh
            # ... (truncated for brevity, real implementation should probably fetch dynamic cookies if possible)
        }
        # Simplified cookie set for now
        self.session.cookies.set('ASP.NET_SessionId', 'ss4j2qn2xxpgfy1whbcyoxje', domain='giaothong.hochiminhcity.gov.vn')

    def _get_headers(self) -> Dict[str, str]:
        """Get HTTP headers to mimic browser request."""
        return {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://giaothong.hochiminhcity.gov.vn/Map.aspx'
        }
    
    def _get_image_url(self, camera_id: str) -> str:
        timestamp_ms = int(datetime.now().timestamp() * 1000)
        return f"{self.API_BASE_URL}?id={camera_id}&t={timestamp_ms}"
    
    def _get_storage_path(self, camera_id: str) -> str:
        """Generate local storage path."""
        now = datetime.now()
        date_dir = now.strftime("%Y-%m-%d")
        time_filename = now.strftime("%H-%M-%S.jpg")
        
        camera_dir = os.path.join(
            self.storage_path,
            "cameras",
            camera_id,
            date_dir
        )
        os.makedirs(camera_dir, exist_ok=True)
        return os.path.join(camera_dir, time_filename)
    
    def save_metadata_to_db(self, camera_id: str, camera_name: str, file_path: str, minio_key: str = None, file_size: int = 0, scene_type: str = 'day'):
        """Save metadata to MongoDB."""
        try:
            db = db_service.get_db_connection()
            if db is None:
                return

            doc = {
                'camera_id': camera_id,
                'camera_name': camera_name,
                'timestamp': datetime.now(),
                'file_path': file_path, # Local path (might be deleted later)
                'file_size': file_size,
                'scene_type': scene_type,
                'weather': scene_type,
                'created_at': datetime.now()
            }

            if minio_key:
                doc['storage_refs'] = {
                    'bucket': minio_service.MINIO_BUCKET_FRAMES,
                    'key': minio_key
                }
                # Add explicit path for easier frontend/proxy access
                doc['minio_url_path'] = f"{minio_service.MINIO_BUCKET_FRAMES}/{minio_key}"

            db['camera_images'].insert_one(doc)
        except Exception as e:
            logger.error(f"Failed to save metadata to MongoDB: {e}")

    def collect_image(self, camera_id: str) -> bool:
        """Download and save image -> MinIO -> MongoDB."""
        try:
            # 1. Download Image
            url = self._get_image_url(camera_id)
            response = self.session.get(url, timeout=self.REQUEST_TIMEOUT)
            response.raise_for_status()
            
            # 2. Save Locally
            file_path = self._get_storage_path(camera_id)
            with open(file_path, 'wb') as f:
                f.write(response.content)
            
            file_size = len(response.content)
            
            minio_key = None
            file_size = 0
            
            # Determine local file path (initially with .jpg, will be updated to .png)
            original_file_path = self._get_storage_path(camera_id)
            
            if response.status_code == 200:
                # Process image to PNG 16-bit
                image_array = np.asarray(bytearray(response.content), dtype=np.uint8)
                img = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
                
                if img is not None:
                    # Resize to 1280x720 standard
                    img = cv2.resize(img, (1280, 720), interpolation=cv2.INTER_AREA)

                    # --- Feature Extraction for Scene Classification ---
                    scene_type = scene_analysis.analyze_scene_features(img)
                    # ---------------------------------------------------

                    # Convert to 16-bit (scale 8-bit [0-255] to 16-bit [0-65535])
                    img_16bit = img.astype(np.uint16) * 256
                    
                    # Ensure filename is .png
                    filename_base = os.path.splitext(original_file_path)[0]
                    file_path = f"{filename_base}.png"
                    
                    # Save as PNG 16-bit
                    cv2.imwrite(file_path, img_16bit)
                    
                    file_size = os.path.getsize(file_path)
                    
                    # 3. Upload to MinIO
                    should_upload_minio = os.getenv('UPLOAD_TO_MINIO', 'true').lower() == 'true'
                    
                    if should_upload_minio:
                        now = datetime.now()
                        # Key format: camera/YYYY/MM/DD/{camera_id}/{scene_type}/HH-MM-SS.png
                        object_key = f"camera/{now.strftime('%Y/%m/%d')}/{camera_id}/{scene_type}/{os.path.basename(file_path)}"
                        
                        result = minio_service.upload_and_get_key(
                            file_path=file_path,
                            bucket_name=minio_service.MINIO_BUCKET_FRAMES, # Changed to frames bucket
                            custom_path=object_key,
                            content_type='image/png' # Changed to PNG
                        )
                        
                        if result['success']:
                            minio_key = result['key']
                            # Auto delete local file if MinIO upload success
                            try:
                                os.remove(file_path)
                            except Exception as e:
                                logger.warning(f"Failed to delete local file {file_path} after MinIO upload: {e}")
                            
                            # Also delete the original raw file (jpg) if it exists and is different
                            if original_file_path != file_path and os.path.exists(original_file_path):
                                try:
                                    os.remove(original_file_path)
                                except Exception as e:
                                    logger.warning(f"Failed to delete local original file {original_file_path}: {e}")
                        else:
                            logger.warning(f"MinIO Upload Failed for {camera_id}")

                    # 4. Save Metadata
                    camera_name = next((c.get('name', camera_id) for c in self.cameras if c['id'] == camera_id), camera_id)
                    self.save_metadata_to_db(camera_id, camera_name, file_path, minio_key, file_size, scene_type)
                    return True
                else:
                    logger.error(f"Failed to decode image for {camera_id}")
                    return False
            else:
                logger.error(f"Failed to download image for {camera_id}. Status code: {response.status_code}")
                return False
            
        except Exception as e:
            logger.error(f"Error collecting image for {camera_id}: {e}")
            return False
    
    def collect_all(self) -> None:
        """Collect images from all cameras."""
        self.collection_stats['total_attempts'] += len(self.cameras)
        for camera in self.cameras:
            if self.collect_image(camera['id']):
                self.collection_stats['successful'] += 1
            else:
                self.collection_stats['failed'] += 1
        self.last_collection_time = datetime.now()
    
    def get_status(self) -> Dict:
        return {
            'status': 'running',
            'cameras': [{'id': c['id'], 'name': c.get('name', c['id'])} for c in self.cameras],
            'last_collection': self.last_collection_time.isoformat() if self.last_collection_time else None,
            'statistics': self.collection_stats.copy()
        }

    # NOTE: get_recent_images logic moved to camera_service to query DB directly
    def get_recent_images(self, limit: int = 10) -> List[Dict]:
        """Legacy fallback if needed, but service should handle DB queries."""
        return []




