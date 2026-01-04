# Hướng dẫn Vehicle Detection Storage với MinIO + MongoDB

## Tổng quan

Hệ thống sử dụng mô hình **Hybrid Storage**:
- **MinIO**: Lưu trữ file (ảnh, video) - Object Storage
- **MongoDB**: Lưu trữ metadata và đường dẫn (key) tham chiếu đến MinIO

## Cấu trúc lưu trữ

### MinIO Bucket Structure

Bucket: `vehicle-detection`

Path format: `YYYY/MM/DD/{camera_id}/{event_id}_{type}.{ext}`

Ví dụ:
```
vehicle-detection/
├── 2024/01/02/
│   ├── cam_01/
│   │   ├── evt_12345_full.jpg      # Ảnh toàn cảnh
│   │   ├── evt_12345_crop.jpg      # Ảnh xe đã cắt
│   │   ├── evt_12345_plate.jpg     # Ảnh biển số
│   │   └── evt_12345_video.mp4     # Video clip
│   └── cam_02/
│       └── ...
```

### MongoDB Document Structure

```json
{
  "_id": "ObjectId('...')",
  "event_id": "evt_12345",
  "timestamp": "2024-01-02T10:30:00Z",
  "camera_id": "cam_01",
  "location": {
    "lat": 10.7769,
    "lng": 106.7009,
    "name": "Hầm Thủ Thiêm"
  },
  "detection_data": {
    "vehicle_type": "car",
    "license_plate": "59A-123.45",
    "color": "white",
    "confidence": 0.98
  },
  "storage_refs": {
    "bucket": "vehicle-detection",
    "full_frame_key": "2024/01/02/cam_01/evt_12345_full.jpg",
    "cropped_vehicle_key": "2024/01/02/cam_01/evt_12345_crop.jpg",
    "cropped_plate_key": "2024/01/02/cam_01/evt_12345_plate.jpg",
    "video_clip_key": "2024/01/02/cam_01/evt_12345_video.mp4"
  },
  "created_at": "2024-01-02T10:30:00Z",
  "updated_at": "2024-01-02T10:30:00Z"
}
```

## Luồng xử lý dữ liệu

### 1. Upload Detection (Detection → MinIO → MongoDB)

```python
import requests
import minio_helper

# Bước 1: AI Model phát hiện xe
detection_result = {
    'event_id': 'evt_12345',
    'camera_id': 'cam_01',
    'vehicle_type': 'car',
    'license_plate': '59A-123.45',
    'color': 'white',
    'confidence': 0.98,
    'location': {
        'lat': 10.7769,
        'lng': 106.7009,
        'name': 'Hầm Thủ Thiêm'
    }
}

# Bước 2: Upload ảnh lên MinIO
full_frame_result = minio_helper.upload_and_get_key(
    file_path='temp/full_frame.jpg',
    bucket_name='vehicle-detection',
    camera_id='cam_01',
    event_id='evt_12345',
    file_type='full'
)

cropped_result = minio_helper.upload_and_get_key(
    file_path='temp/cropped_vehicle.jpg',
    bucket_name='vehicle-detection',
    camera_id='cam_01',
    event_id='evt_12345',
    file_type='crop'
)

# Bước 3: Lưu metadata vào MongoDB
db = get_db_connection()
storage_refs = {
    'bucket': 'vehicle-detection',
    'full_frame_key': full_frame_result['key'],
    'cropped_vehicle_key': cropped_result['key']
}

doc_id = minio_helper.save_vehicle_detection_to_mongodb(
    db, 
    detection_result, 
    storage_refs
)
```

### 2. Sử dụng API Endpoint

#### Upload Detection

```bash
POST /api/vehicle-detection/upload
Content-Type: application/json

{
  "event_id": "evt_12345",
  "camera_id": "cam_01",
  "timestamp": "2024-01-02T10:30:00Z",
  "location": {
    "lat": 10.7769,
    "lng": 106.7009,
    "name": "Hầm Thủ Thiêm"
  },
  "vehicle_type": "car",
  "license_plate": "59A-123.45",
  "color": "white",
  "confidence": 0.98,
  "full_frame_path": "/path/to/full_frame.jpg",
  "cropped_vehicle_path": "/path/to/cropped.jpg",
  "cropped_plate_path": "/path/to/plate.jpg",
  "video_clip_path": "/path/to/clip.mp4"
}
```

Response:
```json
{
  "success": true,
  "event_id": "evt_12345",
  "document_id": "65a1b2c3d4e5f6...",
  "storage_refs": {
    "bucket": "vehicle-detection",
    "full_frame_key": "2024/01/02/cam_01/evt_12345_full.jpg",
    "cropped_vehicle_key": "2024/01/02/cam_01/evt_12345_crop.jpg"
  }
}
```

#### Lấy Detection với Presigned URLs

```bash
GET /api/vehicle-detection/evt_12345?expires=3600
```

Response:
```json
{
  "event_id": "evt_12345",
  "detection_data": {
    "vehicle_type": "car",
    "license_plate": "59A-123.45",
    "color": "white",
    "confidence": 0.98
  },
  "urls": {
    "full_frame": "http://minio:9000/vehicle-detection/2024/01/02/cam_01/evt_12345_full.jpg?X-Amz-Algorithm=...",
    "cropped_vehicle": "http://minio:9000/vehicle-detection/2024/01/02/cam_01/evt_12345_crop.jpg?X-Amz-Algorithm=...",
    "cropped_plate": "http://minio:9000/vehicle-detection/2024/01/02/cam_01/evt_12345_plate.jpg?X-Amz-Algorithm=..."
  }
}
```

#### Tìm kiếm Detections

```bash
GET /api/vehicle-detection/search?license_plate=59A&vehicle_type=car&page=1&per_page=20
```

Query Parameters:
- `license_plate`: Tìm theo biển số (regex)
- `vehicle_type`: Loại xe (car, motorcycle, truck, etc.)
- `camera_id`: ID camera
- `date_from`: Từ ngày (ISO format)
- `date_to`: Đến ngày (ISO format)
- `page`: Số trang
- `per_page`: Số items mỗi trang

Response:
```json
{
  "total": 150,
  "page": 1,
  "per_page": 20,
  "total_pages": 8,
  "detections": [
    {
      "_id": "...",
      "event_id": "evt_12345",
      "timestamp": "2024-01-02T10:30:00Z",
      "camera_id": "cam_01",
      "detection_data": {...},
      "storage_refs": {...}
    },
    ...
  ]
}
```

## Sử dụng trong Python Code

### Upload Detection

```python
from minio_helper import upload_and_get_key, save_vehicle_detection_to_mongodb
from app import get_db_connection

# Upload files
full_result = upload_and_get_key(
    'full_frame.jpg',
    'vehicle-detection',
    camera_id='cam_01',
    event_id='evt_12345',
    file_type='full'
)

# Lưu metadata
db = get_db_connection()
detection_data = {
    'event_id': 'evt_12345',
    'camera_id': 'cam_01',
    'vehicle_type': 'car',
    'license_plate': '59A-123.45',
    'confidence': 0.98
}

storage_refs = {
    'bucket': 'vehicle-detection',
    'full_frame_key': full_result['key']
}

doc_id = save_vehicle_detection_to_mongodb(db, detection_data, storage_refs)
```

### Retrieve với Presigned URLs

```python
from minio_helper import get_presigned_urls_for_detection
from app import get_db_connection

db = get_db_connection()
result = get_presigned_urls_for_detection(db, 'evt_12345', expires=3600)

if result:
    print(f"Full frame URL: {result['urls']['full_frame']}")
    print(f"Detection: {result['detection_data']}")
```

## Lợi ích của mô hình này

1. **Hiệu năng cao**: MongoDB chỉ lưu metadata nhẹ, không lưu blob
2. **Dễ mở rộng**: MinIO dễ scale, MongoDB tối ưu cho query
3. **Linh hoạt**: Có thể đổi MinIO endpoint mà không cần update MongoDB
4. **Bảo mật**: Presigned URLs có thời hạn, không expose internal IP
5. **Tổ chức tốt**: Path có cấu trúc dễ quản lý và backup

## Lưu ý

- **Chỉ lưu Key trong MongoDB**, không lưu full URL
- **Presigned URLs** được tạo động khi cần, có thời hạn
- **Path structure** giúp dễ backup và migrate theo ngày/tháng
- **Bucket policy** có thể set public read hoặc private tùy nhu cầu



