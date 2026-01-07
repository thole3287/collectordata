import os
from datetime import datetime
import services.minio_service as minio_service

# Mock config
os.environ['MINIO_BUCKET_CAMERA'] = 'dataset'
os.environ['UPLOAD_TO_MINIO'] = 'true'

def test_path_generation():
    camera_id = "test_camera_1"
    file_path = "test_image.png"
    now = datetime.now()
    
    # Logic copied from camera_collector.py (updated version)
    object_key = f"camera/{now.strftime('%Y/%m/%d')}/{camera_id}/{os.path.basename(file_path)}"
    
    print(f"Generated Key: {object_key}")
    print(f"Target Bucket: {minio_service.MINIO_BUCKET_CAMERA}") # Should be whatever env var is set to
    print(f"Expected Bucket (from env.example update logic, assuming user updates .env): dataset")

if __name__ == "__main__":
    test_path_generation()
