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
from services.image_enhancement import process_image, smart_process_image, load_settings
import services.augmentation_service as augmentation_service


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
        self.last_camera_hists = {} # Cache for deduplication per camera
        
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
                    # Resize to 1280x720 standard - REMOVED per user request
                    # img = cv2.resize(img, (1280, 720), interpolation=cv2.INTER_AREA)


                    # --- Feature Extraction for Scene Classification ---
                    # scene_type = scene_analysis.analyze_scene_features(img)
                    
                    # --- SMART FILTERING (Brightness, Blur, Deduplication) ---
                    # 1. Convert to gray for analysis
                    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                    
                    # 2. BRIGHTNESS FILTER (Default params: 40-220)
                    avg_brightness = np.mean(gray)
                    if avg_brightness < 40 or avg_brightness > 220:
                        logger.info(f"Skipping camera {camera_id}: Brightness {avg_brightness:.2f} out of range")
                        return False

                    # 3. BLUR FILTER (Default 100)
                    blur_score = cv2.Laplacian(gray, cv2.CV_64F).var()
                    if blur_score < 100:
                        logger.info(f"Skipping camera {camera_id}: Blur score {blur_score:.2f} too low")
                        return False

                    # --- DEDUPLICATION CHECK ---
                    # Tính histogram của ảnh hiện tại
                    curr_hist = cv2.calcHist([img], [0], None, [256], [0, 256])
                    cv2.normalize(curr_hist, curr_hist, 0, 1, cv2.NORM_MINMAX)

                    # Lấy histogram cũ của camera này
                    last_hist = self.last_camera_hists.get(camera_id)
                    
                    is_duplicate = False
                    if last_hist is not None:
                        # Compare method CORREL
                        score = cv2.compareHist(last_hist, curr_hist, cv2.HISTCMP_CORREL)
                        if score > 0.95: # SAME IMAGE
                            is_duplicate = True
                    
                    if is_duplicate:
                        logger.info(f"Skipping duplicate frame for Camera {camera_id}")
                        return False # Changed from None to False to match method signature
                    
                    # --- IMAGE ENHANCEMENT ---
                    # Load settings (Note: In production might want to cache this to avoid reading file every second)
                    # For now invalid/missing file is handled by load_settings returning defaults
                    # --- AUGMENTATION (1 -> 5 images) ---
                    # Generates Original + 4 Variants
                    augmented_frames = augmentation_service.augment_image(img)
                    
                    saved_any = False
                    
                    for variant_idx, (aug_frame, suffix) in enumerate(augmented_frames):
                        # --- IMAGE ENHANCEMENT ---
                        enhance_settings = load_settings()
                        scene_type = 'day' # Default
                        processed_frame = aug_frame

                        if enhance_settings.get('enabled_camera', False):
                            try:
                                # Smart Process (detects scene -> calls process_image)
                                processed_frame, scene_type = smart_process_image(aug_frame, enhance_settings)
                            except Exception as e:
                                logger.error(f"Error enhancing camera image variant {suffix}: {e}")
                                # Fallback analysis
                                scene_type = scene_analysis.analyze_scene_features(aug_frame)
                        else:
                            # Analysis only
                            scene_type = scene_analysis.analyze_scene_features(aug_frame)
                        # -------------------------

                        if processed_frame is None: continue

                        # Cập nhật histogram mới nhất cho camera này (using the ORIGINAL image's histogram for consistency)
                        if variant_idx == 0: # Only update once per collection cycle
                            self.last_camera_hists[camera_id] = curr_hist
                        
                        # Convert to 16-bit
                        img_16bit = processed_frame.astype(np.uint16) * 256
                        
                        # Generate filename with suffix
                        filename_base = os.path.splitext(original_file_path)[0]
                        file_path = f"{filename_base}{suffix}.png"
                        
                        # Save as PNG 16-bit
                        cv2.imwrite(file_path, img_16bit)
                        
                        file_size = os.path.getsize(file_path)
                        
                        # 3. Upload to MinIO
                        minio_key = None
                        should_upload_minio = os.getenv('UPLOAD_TO_MINIO', 'true').lower() == 'true'
                        
                        if should_upload_minio:
                            now = datetime.now()
                            # Key format: camera/YYYY/MM/DD/{camera_id}/{scene_type}/HH-MM-SS_suffix.png
                            object_key = f"camera/{now.strftime('%Y/%m/%d')}/{camera_id}/{scene_type}/{os.path.basename(file_path)}"
                            
                            result = minio_service.upload_and_get_key(
                                file_path=file_path,
                                bucket_name=minio_service.MINIO_BUCKET_FRAMES,
                                custom_path=object_key,
                                content_type='image/png'
                            )
                            
                            if result['success']:
                                minio_key = result['key']
                                # Auto delete local file if MinIO upload success
                                try:
                                    os.remove(file_path)
                                except Exception as e:
                                    logger.warning(f"Failed to delete local file {file_path} after MinIO upload: {e}")
                                
                                # Update file_path to MinIO path for database storage
                                file_path = f"{minio_service.MINIO_BUCKET_FRAMES}/{minio_key}"
                            else:
                                logger.warning(f"MinIO Upload Failed for {camera_id} variant {suffix}")

                        # 4. Save Metadata
                        camera_name = next((c.get('name', camera_id) for c in self.cameras if c['id'] == camera_id), camera_id)
                        # Note: We might want to store 'variant' field in db, currently just relying on filename/path
                        self.save_metadata_to_db(camera_id, camera_name, file_path, minio_key, file_size, scene_type)
                        saved_any = True
                        
                    return saved_any
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




