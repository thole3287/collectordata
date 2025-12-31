"""Camera image collector service."""
import os
import logging
import requests
from datetime import datetime
from typing import List, Dict, Optional

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
        """
        Set cookies to mimic browser session.
        Cookies are set for the domain giaothong.hochiminhcity.gov.vn
        """
        cookies = {
            'ASP.NET_SessionId': 'ss4j2qn2xxpgfy1whbcyoxje',
            '.VDMS': 'DF33FAAFE9A0CB23AA1890D816F9927B32446150CDBC6F7CD0BBC69C1426719AF8191A17B90EF8A3CDB6D3C9CD89C9704CB97F1BF5980E26CE614A1E7CBE0AA782BB6B756974344DA5EAAA3ACC9811A536B8D3F76B06DCB4208133075B10FC32FEF5B85CD44BF76151404F439F94769BE37DF18E',
            '_pk_ref.1.2f14': '%5B%22%22%2C%22%22%2C1766635896%2C%22https%3A%2F%2Fwww.google.com%2F%22%5D',
            '_ga': 'GA1.3.636055033.1766635896',
            '_gid': 'GA1.3.1310372542.1766635896',
            'CurrentLanguage': 'vi',
            '_pk_id.1.2f14': '4bc4c33106b17e80.1766635896.1.1766636173.1766635896.',
            '_ga_JCXT8BPG4E': 'GS2.3.s1766635897$o1$g1$t1766636172$j1$10$h0',
            '_frontend': '!Fgzs7NaRjg7Qnv64P1VY/IC/bQptjqZArGFACw/vWoY4eFuJgyE8wW2qRukgfDI/X4fsfylre44Js0Y=',
        }
        
        # Set cookies for the domain
        for name, value in cookies.items():
            self.session.cookies.set(name, value, domain='giaothong.hochiminhcity.gov.vn')
        
        logger.debug(f"Set {len(cookies)} cookies for session")
    
    def _get_headers(self) -> Dict[str, str]:
        """
        Get HTTP headers to mimic browser request.
        
        Returns:
            Dictionary of HTTP headers
        """
        return {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br, zstd',
            'Accept-Language': 'en-US,en;q=0.9,vi;q=0.8',
            'Connection': 'keep-alive',
            'Host': 'giaothong.hochiminhcity.gov.vn',
            'Sec-Ch-Ua': '"Google Chrome";v="143", "Chromium";v="143", "Not A(Brand";v="24"',
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Ch-Ua-Platform': '"macOS"',
            'Sec-Fetch-Dest': 'image',
            'Sec-Fetch-Mode': 'no-cors',
            'Sec-Fetch-Site': 'same-origin',
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36',
            'Referer': 'https://giaothong.hochiminhcity.gov.vn/Map.aspx'
        }
    
    def _get_image_url(self, camera_id: str) -> str:
        """
        Generate image URL with timestamp to avoid cache.
        
        Args:
            camera_id: Camera ID
            
        Returns:
            Complete URL with query parameters
        """
        timestamp_ms = int(datetime.now().timestamp() * 1000)
        return f"{self.API_BASE_URL}?id={camera_id}&t={timestamp_ms}"
    
    def _get_storage_path(self, camera_id: str) -> str:
        """
        Generate storage path for a camera based on current timestamp.
        
        Args:
            camera_id: Camera ID
            
        Returns:
            Full path to the image file
        """
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
    
    def collect_image(self, camera_id: str) -> bool:
        """
        Download and save image for a single camera.
        
        Args:
            camera_id: Camera ID to collect image from
            
        Returns:
            True if successful, False otherwise
        """
        try:
            url = self._get_image_url(camera_id)
            
            # Log HTTP Request
            logger.info(f"[HTTP REQUEST] GET {url}")
            logger.info(f"[HTTP REQUEST] Camera ID: {camera_id}")
            
            # Use session to maintain cookies and connection
            response = self.session.get(url, timeout=self.REQUEST_TIMEOUT)
            
            response.raise_for_status()
            
            # Verify content type
            content_type = response.headers.get('Content-Type', '')
            if 'image' not in content_type.lower():
                logger.warning(
                    f"Unexpected content type for camera {camera_id}: {content_type}"
                )
            
            # Save image
            file_path = self._get_storage_path(camera_id)
            with open(file_path, 'wb') as f:
                f.write(response.content)
            
            file_size = len(response.content)
            logger.info(
                f"Successfully collected image for camera {camera_id} "
                f"({file_size} bytes) -> {file_path}"
            )
            return True
            
        except requests.exceptions.Timeout:
            logger.error(f"[HTTP ERROR] Timeout while fetching image for camera {camera_id}")
            return False
        except requests.exceptions.RequestException as e:
            logger.error(f"[HTTP ERROR] Request error while fetching image for camera {camera_id}: {e}")
            return False
        except IOError as e:
            logger.error(f"File I/O error while saving image for camera {camera_id}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error while collecting image for camera {camera_id}: {e}")
            return False
    
    def collect_all(self) -> None:
        """
        Collect images from all configured cameras.
        Updates statistics and handles errors gracefully.
        """
        logger.debug("Starting collection cycle for all cameras")
        self.collection_stats['total_attempts'] += len(self.cameras)
        
        for camera in self.cameras:
            camera_id = camera['id']
            camera_name = camera.get('name', camera_id)
            
            success = self.collect_image(camera_id)
            
            if success:
                self.collection_stats['successful'] += 1
            else:
                self.collection_stats['failed'] += 1
                # Continue with next camera even if this one failed
                logger.warning(
                    f"Failed to collect image for camera {camera_name} ({camera_id}), "
                    "continuing with next camera"
                )
        
        self.last_collection_time = datetime.now()
        logger.info(
            f"Collection cycle completed. "
            f"Successful: {self.collection_stats['successful']}, "
            f"Failed: {self.collection_stats['failed']}"
        )
    
    def get_status(self) -> Dict:
        """
        Get current collector status.
        
        Returns:
            Dictionary with status information
        """
        return {
            'status': 'running',
            'cameras': [
                {'id': cam['id'], 'name': cam.get('name', cam['id'])}
                for cam in self.cameras
            ],
            'last_collection': (
                self.last_collection_time.isoformat()
                if self.last_collection_time
                else None
            ),
            'statistics': self.collection_stats.copy()
        }
    
    def get_recent_images(self, limit: int = 10) -> List[Dict]:
        """
        Get list of recently collected images.
        
        Args:
            limit: Maximum number of images to return
            
        Returns:
            List of image dictionaries with path, camera_id, camera_name, and timestamp
        """
        images = []
        cameras_base = os.path.join(self.storage_path, "cameras")
        
        if not os.path.exists(cameras_base):
            return images
        
        # Iterate through all cameras
        for camera in self.cameras:
            camera_id = camera['id']
            camera_name = camera.get('name', camera_id)
            camera_dir = os.path.join(cameras_base, camera_id)
            
            if not os.path.exists(camera_dir):
                continue
            
            # Walk through date directories
            for date_dir in os.listdir(camera_dir):
                date_path = os.path.join(camera_dir, date_dir)
                if not os.path.isdir(date_path):
                    continue
                
                # Get all image files in this date directory
                for filename in os.listdir(date_path):
                    if filename.endswith('.jpg'):
                        file_path = os.path.join(date_path, filename)
                        file_stat = os.stat(file_path)
                        
                        # Parse timestamp from filename (HH-MM-SS.jpg) and date directory (YYYY-MM-DD)
                        try:
                            time_part = filename.replace('.jpg', '')
                            hour, minute, second = map(int, time_part.split('-'))
                            year, month, day = map(int, date_dir.split('-'))
                            timestamp = datetime(year, month, day, hour, minute, second)
                            
                            # Create relative path for URL
                            rel_path = os.path.join("cameras", camera_id, date_dir, filename)
                            
                            images.append({
                                'path': rel_path.replace(os.sep, '/'),
                                'camera_id': camera_id,
                                'camera_name': camera_name,
                                'timestamp': timestamp.isoformat(),
                                'file_size': file_stat.st_size,
                                'modified_time': datetime.fromtimestamp(file_stat.st_mtime).isoformat()
                            })
                        except (ValueError, IndexError) as e:
                            logger.warning(f"Error parsing timestamp from {file_path}: {e}")
                            continue
        
        # Sort by timestamp (newest first) and return limited results
        images.sort(key=lambda x: x['timestamp'], reverse=True)
        return images[:limit]



