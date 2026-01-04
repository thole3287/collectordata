"""
MinIO Helper - Utility functions để upload/download files từ MinIO
Tích hợp với MongoDB để lưu metadata và storage references
"""
import os
from datetime import datetime
from minio import Minio
from minio.error import S3Error
from dotenv import load_dotenv

load_dotenv()

# Load MinIO configuration from environment
MINIO_ENDPOINT = os.getenv('MINIO_ENDPOINT', 'localhost')
MINIO_PORT = int(os.getenv('MINIO_PORT', 9000))
MINIO_ACCESS_KEY = os.getenv('MINIO_ACCESS_KEY', 'minioadmin')
MINIO_SECRET_KEY = os.getenv('MINIO_SECRET_KEY', 'minioadmin123')
MINIO_USE_SSL = os.getenv('MINIO_USE_SSL', 'False').lower() == 'true'

# Bucket names
MINIO_BUCKET_VIDEOS = os.getenv('MINIO_BUCKET_VIDEOS', 'videos')
MINIO_BUCKET_IMAGES = os.getenv('MINIO_BUCKET_IMAGES', 'images')
MINIO_BUCKET_FRAMES = os.getenv('MINIO_BUCKET_FRAMES', 'frames')
MINIO_BUCKET_CAMERA = os.getenv('MINIO_BUCKET_CAMERA', 'camera-images')
MINIO_BUCKET_VEHICLE_DETECTION = os.getenv('MINIO_BUCKET_VEHICLE_DETECTION', 'vehicle-detection')


def get_minio_client():
    """
    Tạo MinIO client connection
    
    Returns:
        Minio client object
    """
    endpoint = f"{MINIO_ENDPOINT}:{MINIO_PORT}"
    return Minio(
        endpoint,
        access_key=MINIO_ACCESS_KEY,
        secret_key=MINIO_SECRET_KEY,
        secure=MINIO_USE_SSL
    )


def ensure_buckets_exist():
    """
    Đảm bảo các buckets cần thiết đã được tạo
    """
    try:
        client = get_minio_client()
        buckets = [
            MINIO_BUCKET_VIDEOS,
            MINIO_BUCKET_IMAGES,
            MINIO_BUCKET_FRAMES,
            MINIO_BUCKET_CAMERA,
            MINIO_BUCKET_VEHICLE_DETECTION
        ]
        
        for bucket_name in buckets:
            if not client.bucket_exists(bucket_name):
                client.make_bucket(bucket_name)
                print(f"✓ Created bucket: {bucket_name}")
            else:
                print(f"✓ Bucket already exists: {bucket_name}")
        
        return True
    except S3Error as e:
        print(f"Error ensuring buckets exist: {e}")
        return False
    except Exception as e:
        print(f"Unexpected error: {e}")
        return False


def upload_file(file_path, bucket_name, object_name=None, content_type=None):
    """
    Upload file lên MinIO
    
    Args:
        file_path: Đường dẫn file local
        bucket_name: Tên bucket
        object_name: Tên object trong bucket (mặc định = tên file)
        content_type: MIME type (tự động detect nếu None)
    
    Returns:
        True nếu thành công, False nếu thất bại
    """
    try:
        if not os.path.exists(file_path):
            print(f"File not found: {file_path}")
            return False
        
        client = get_minio_client()
        
        # Đảm bảo bucket tồn tại
        if not client.bucket_exists(bucket_name):
            client.make_bucket(bucket_name)
        
        # Nếu không có object_name, dùng tên file
        if object_name is None:
            object_name = os.path.basename(file_path)
        
        # Upload file
        client.fput_object(
            bucket_name,
            object_name,
            file_path,
            content_type=content_type
        )
        
        print(f"✓ Uploaded {file_path} to {bucket_name}/{object_name}")
        return True
        
    except S3Error as e:
        print(f"Error uploading file: {e}")
        return False
    except Exception as e:
        print(f"Unexpected error: {e}")
        return False


def download_file(bucket_name, object_name, file_path):
    """
    Download file từ MinIO
    
    Args:
        bucket_name: Tên bucket
        object_name: Tên object trong bucket
        file_path: Đường dẫn file local để lưu
    
    Returns:
        True nếu thành công, False nếu thất bại
    """
    try:
        client = get_minio_client()
        
        # Tạo thư mục nếu chưa có
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        # Download file
        client.fget_object(bucket_name, object_name, file_path)
        
        print(f"✓ Downloaded {bucket_name}/{object_name} to {file_path}")
        return True
        
    except S3Error as e:
        print(f"Error downloading file: {e}")
        return False
    except Exception as e:
        print(f"Unexpected error: {e}")
        return False


# Public access configuration (for browser)
MINIO_PUBLIC_ENDPOINT = os.getenv('MINIO_PUBLIC_ENDPOINT', 'localhost')
MINIO_PUBLIC_PORT = int(os.getenv('MINIO_PUBLIC_PORT', 9000))

def get_public_minio_client():
    """
    Tạo MinIO client cho public URL generation (không check connection)
    """
    endpoint = f"{MINIO_PUBLIC_ENDPOINT}:{MINIO_PUBLIC_PORT}"
    return Minio(
        endpoint,
        access_key=MINIO_ACCESS_KEY,
        secret_key=MINIO_SECRET_KEY,
        secure=MINIO_USE_SSL
    )

def get_file_url(bucket_name, object_name, expires=3600):
    """
    Lấy presigned URL để truy cập file (tạm thời)
    Sử dụng public endpoint để browser có thể truy cập
    """
    try:
        # Use public client to generate URL accessible from browser
        client = get_public_minio_client()
        url = client.presigned_get_object(bucket_name, object_name, expires=expires)
        return url
    except S3Error as e:
        print(f"Error getting presigned URL: {e}")
        return None
    except Exception as e:
        print(f"Unexpected error: {e}")
        return None


def list_files(bucket_name, prefix=None):
    """
    Liệt kê các files trong bucket
    
    Args:
        bucket_name: Tên bucket
        prefix: Prefix để filter (optional)
    
    Returns:
        List of object names
    """
    try:
        client = get_minio_client()
        objects = client.list_objects(bucket_name, prefix=prefix, recursive=True)
        return [obj.object_name for obj in objects]
    except S3Error as e:
        print(f"Error listing files: {e}")
        return []
    except Exception as e:
        print(f"Unexpected error: {e}")
        return []


def delete_file(bucket_name, object_name):
    """
    Xóa file từ MinIO
    
    Args:
        bucket_name: Tên bucket
        object_name: Tên object
    
    Returns:
        True nếu thành công, False nếu thất bại
    """
    try:
        client = get_minio_client()
        client.remove_object(bucket_name, object_name)
        print(f"✓ Deleted {bucket_name}/{object_name}")
        return True
    except S3Error as e:
        print(f"Error deleting file: {e}")
        return False
    except Exception as e:
        print(f"Unexpected error: {e}")
        return False


def generate_storage_path(camera_id, event_id, file_type='full', extension='jpg', timestamp=None):
    """
    Tạo đường dẫn có cấu trúc cho file trong MinIO
    Format: YYYY/MM/DD/{camera_id}/{event_id}_{type}.{ext}
    
    Args:
        camera_id: ID của camera
        event_id: ID của sự kiện detection
        file_type: Loại file (full, crop, plate, video)
        extension: Đuôi file (jpg, mp4, etc.)
        timestamp: Datetime object (mặc định = now)
    
    Returns:
        String path: YYYY/MM/DD/camera_id/event_id_type.ext
    """
    if timestamp is None:
        timestamp = datetime.now()
    
    date_path = timestamp.strftime("%Y/%m/%d")
    filename = f"{event_id}_{file_type}.{extension}"
    return f"{date_path}/{camera_id}/{filename}"


def upload_and_get_key(file_path, bucket_name, camera_id=None, event_id=None, 
                       file_type='full', content_type=None, custom_path=None):
    """
    Upload file lên MinIO và trả về key (path) để lưu vào MongoDB
    
    Args:
        file_path: Đường dẫn file local
        bucket_name: Tên bucket
        camera_id: ID camera (để tạo path có cấu trúc)
        event_id: ID event (để tạo path có cấu trúc)
        file_type: Loại file (full, crop, plate, video)
        content_type: MIME type
        custom_path: Path tùy chỉnh (nếu không dùng generate_storage_path)
    
    Returns:
        dict với keys: 'success', 'bucket', 'key', 'error'
    """
    try:
        if not os.path.exists(file_path):
            return {
                'success': False,
                'error': f'File not found: {file_path}'
            }
        
        client = get_minio_client()
        
        # Đảm bảo bucket tồn tại
        if not client.bucket_exists(bucket_name):
            client.make_bucket(bucket_name)
        
        # Tạo object key
        if custom_path:
            object_key = custom_path
        elif camera_id and event_id:
            extension = os.path.splitext(file_path)[1][1:] or 'jpg'
            object_key = generate_storage_path(camera_id, event_id, file_type, extension)
        else:
            object_key = os.path.basename(file_path)
        
        # Upload file
        client.fput_object(
            bucket_name,
            object_key,
            file_path,
            content_type=content_type
        )
        
        return {
            'success': True,
            'bucket': bucket_name,
            'key': object_key
        }
        
    except S3Error as e:
        return {
            'success': False,
            'error': f'MinIO error: {str(e)}'
        }
    except Exception as e:
        return {
            'success': False,
            'error': f'Unexpected error: {str(e)}'
        }


def save_vehicle_detection_to_mongodb(db, detection_data, storage_refs):
    """
    Lưu metadata vehicle detection vào MongoDB với storage references
    
    Args:
        db: MongoDB database object
        detection_data: Dict chứa thông tin detection (vehicle_type, license_plate, etc.)
        storage_refs: Dict chứa bucket và keys (full_frame_key, cropped_vehicle_key, etc.)
    
    Returns:
        ObjectId của document đã tạo hoặc None nếu lỗi
    """
    try:
        collection = db['vehicle_detections']
        
        document = {
            'event_id': detection_data.get('event_id'),
            'timestamp': detection_data.get('timestamp', datetime.now()),
            'camera_id': detection_data.get('camera_id'),
            'location': detection_data.get('location', {}),
            'detection_data': {
                'vehicle_type': detection_data.get('vehicle_type'),
                'license_plate': detection_data.get('license_plate'),
                'color': detection_data.get('color'),
                'confidence': detection_data.get('confidence', 0.0)
            },
            'storage_refs': {
                'bucket': storage_refs.get('bucket', MINIO_BUCKET_VEHICLE_DETECTION),
                'full_frame_key': storage_refs.get('full_frame_key'),
                'cropped_vehicle_key': storage_refs.get('cropped_vehicle_key'),
                'cropped_plate_key': storage_refs.get('cropped_plate_key'),
                'video_clip_key': storage_refs.get('video_clip_key')
            },
            'created_at': datetime.now(),
            'updated_at': datetime.now()
        }
        
        result = collection.insert_one(document)
        return result.inserted_id
        
    except Exception as e:
        print(f"Error saving to MongoDB: {e}")
        return None


def get_presigned_urls_for_detection(db, event_id, expires=3600):
    """
    Lấy presigned URLs cho tất cả files của một detection event
    
    Args:
        db: MongoDB database object
        event_id: ID của event
        expires: Thời gian hết hạn URL (giây)
    
    Returns:
        Dict chứa presigned URLs hoặc None nếu không tìm thấy
    """
    try:
        collection = db['vehicle_detections']
        detection = collection.find_one({'event_id': event_id})
        
        if not detection:
            return None
        
        storage_refs = detection.get('storage_refs', {})
        bucket = storage_refs.get('bucket', MINIO_BUCKET_VEHICLE_DETECTION)
        
        urls = {}
        client = get_minio_client()
        
        # Tạo presigned URL cho từng file
        if storage_refs.get('full_frame_key'):
            urls['full_frame'] = client.presigned_get_object(
                bucket, storage_refs['full_frame_key'], expires=expires
            )
        
        if storage_refs.get('cropped_vehicle_key'):
            urls['cropped_vehicle'] = client.presigned_get_object(
                bucket, storage_refs['cropped_vehicle_key'], expires=expires
            )
        
        if storage_refs.get('cropped_plate_key'):
            urls['cropped_plate'] = client.presigned_get_object(
                bucket, storage_refs['cropped_plate_key'], expires=expires
            )
        
        if storage_refs.get('video_clip_key'):
            urls['video_clip'] = client.presigned_get_object(
                bucket, storage_refs['video_clip_key'], expires=expires
            )
        
        return {
            'event_id': event_id,
            'detection_data': detection.get('detection_data'),
            'urls': urls
        }
        
    except Exception as e:
        print(f"Error getting presigned URLs: {e}")
        return None


def save_frame_to_mongodb(db, video_id, platform, frame_index, minio_key, bucket_name, 
                          frame_number, video_frame_number, timestamp=None):
    """
    Lưu metadata của một frame vào MongoDB
    
    Args:
        db: MongoDB database object
        video_id: ID của video
        platform: Platform (youtube, pexels)
        frame_index: Index của frame trong danh sách frames đã extract (0, 1, 2, ...)
        minio_key: Key của frame trong MinIO
        bucket_name: Tên bucket trong MinIO
        frame_number: Số thứ tự frame trong file (fr00000, fr00001, ...)
        video_frame_number: Số frame trong video gốc (frame thứ bao nhiêu trong video)
        timestamp: Thời gian extract (mặc định = now)
    
    Returns:
        ObjectId của document đã tạo hoặc None nếu lỗi
    """
    try:
        if timestamp is None:
            timestamp = datetime.now()
        
        collection = db['video_frames']
        
        document = {
            'video_id': video_id,
            'platform': platform,
            'frame_index': frame_index,  # Thứ tự trong danh sách frames đã extract
            'frame_number': frame_number,  # Số thứ tự trong tên file (fr00000)
            'video_frame_number': video_frame_number,  # Số frame trong video gốc
            'storage_refs': {
                'bucket': bucket_name,
                'key': minio_key
            },
            'extracted_at': timestamp,
            'created_at': datetime.now()
        }
        
        result = collection.insert_one(document)
        return result.inserted_id
        
    except Exception as e:
        print(f"Error saving frame to MongoDB: {e}")
        return None


def extract_and_upload_frames(video_path, video_id, platform='youtube', 
                               fps=None, interval_seconds=None, target_width=1280, target_height=720, db=None):
    """
    Extract frames từ video và upload lên MinIO, đồng thời lưu metadata vào MongoDB
    
    Args:
        video_path: Đường dẫn video local
        video_id: ID của video
        platform: Platform (youtube, pexels)
        fps: FPS của video (nếu None sẽ tự động detect từ video)
        interval_seconds: Cứ bao nhiêu giây lấy 1 ảnh (nếu None sẽ đọc từ env FRAME_INTERVAL_SECONDS, mặc định 1.0)
        target_width: Chiều rộng ảnh output
        target_height: Chiều cao ảnh output
        db: MongoDB database object (optional, nếu có sẽ lưu metadata vào MongoDB)
    
    Returns:
        dict với keys: 'success', 'frames_uploaded', 'frame_keys', 'frame_ids', 'fps', 'frame_step', 'error'
    """
    try:
        # Đọc interval từ env nếu không được truyền vào
        if interval_seconds is None:
            interval_seconds = float(os.getenv('FRAME_INTERVAL_SECONDS', 1.0))
        import cv2
        import tempfile
        import shutil
        
        if not os.path.exists(video_path):
            return {
                'success': False,
                'error': f'Video file not found: {video_path}'
            }
        
        client = get_minio_client()
        bucket_name = MINIO_BUCKET_FRAMES
        
        # Đảm bảo bucket tồn tại
        if not client.bucket_exists(bucket_name):
            client.make_bucket(bucket_name)
        
        # Tạo temp directory để lưu frames tạm thời
        temp_dir = tempfile.mkdtemp()
        frame_keys = []
        frame_ids = []  # MongoDB ObjectIds
        frames_uploaded = 0
        extract_timestamp = datetime.now()
        
        try:
            # Mở video
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                return {
                    'success': False,
                    'error': 'Cannot open video file'
                }
            
            # Lấy FPS từ video nếu chưa có
            if fps is None:
                video_fps = cap.get(cv2.CAP_PROP_FPS)
                if video_fps and video_fps > 0:
                    fps = video_fps
                else:
                    # Fallback: dùng 30 fps nếu không detect được
                    fps = 30.0
                    print(f"  ⚠ Không thể detect FPS, dùng mặc định: {fps} fps")
            else:
                video_fps = fps
            
            # Tính frame_step dựa trên FPS và interval
            # Ví dụ: fps=30, interval=1 giây → frame_step=30
            # Ví dụ: fps=60, interval=1 giây → frame_step=60
            # Ví dụ: fps=30, interval=0.5 giây → frame_step=15
            frame_step = int(fps * interval_seconds)
            if frame_step < 1:
                frame_step = 1
            
            print(f"  📹 Video FPS: {fps:.2f}, Interval: {interval_seconds}s → Frame step: {frame_step}")
            
            count = 0
            saved_count = 0
            
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                
                # Extract frame theo step (tính từ FPS)
                if count % frame_step == 0:
                    try:
                        # Resize frame
                        resized_frame = cv2.resize(
                            frame, 
                            (target_width, target_height), 
                            interpolation=cv2.INTER_AREA
                        )
                        
                        # Lưu frame tạm thời
                        frame_filename = f"{video_id}_fr{saved_count:05d}.jpg"
                        temp_frame_path = os.path.join(temp_dir, frame_filename)
                        cv2.imwrite(temp_frame_path, resized_frame)
                        
                        # Tạo object key: platform/video_id/frame_xxx.jpg
                        object_key = f"{platform}/{video_id}/{frame_filename}"
                        
                        # Upload lên MinIO
                        client.fput_object(
                            bucket_name,
                            object_key,
                            temp_frame_path,
                            content_type='image/jpeg'
                        )
                        
                        frame_keys.append(object_key)
                        frames_uploaded += 1
                        
                        # Lưu metadata vào MongoDB nếu có db connection
                        if db is not None:
                            frame_id = save_frame_to_mongodb(
                                db=db,
                                video_id=video_id,
                                platform=platform,
                                frame_index=saved_count,  # Index trong danh sách frames đã extract
                                minio_key=object_key,
                                bucket_name=bucket_name,
                                frame_number=f"fr{saved_count:05d}",
                                video_frame_number=count,  # Số frame trong video gốc
                                timestamp=extract_timestamp
                            )
                            if frame_id:
                                frame_ids.append(str(frame_id))
                        
                        saved_count += 1
                        
                    except Exception as e:
                        print(f"Error processing frame {count}: {e}")
                
                count += 1
            
            cap.release()
            
            return {
                'success': True,
                'frames_uploaded': frames_uploaded,
                'frame_keys': frame_keys,
                'frame_ids': frame_ids,  # MongoDB ObjectIds
                'bucket': bucket_name,
                'fps': fps,
                'frame_step': frame_step,
                'interval_seconds': interval_seconds
            }
            
        finally:
            # Xóa temp directory
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
                
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


if __name__ == "__main__":
    # Test connection và tạo buckets
    print("Testing MinIO connection...")
    if ensure_buckets_exist():
        print("✓ MinIO setup successful!")
    else:
        print("✗ MinIO setup failed!")


