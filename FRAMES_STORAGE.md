# Hướng dẫn Frame Storage trong MongoDB

## Tổng quan

Khi extract frames từ video, hệ thống sẽ tự động:
1. Extract frames từ video (30 frame/1 ảnh, resize 1280x720)
2. Upload frames lên MinIO (bucket: `frames`)
3. Lưu metadata của từng frame vào MongoDB collection `video_frames`

## Schema MongoDB - Collection: `video_frames`

```json
{
  "_id": "ObjectId('...')",
  "video_id": "abc123xyz",           // ID của video gốc
  "platform": "youtube",             // Platform: youtube, pexels
  "frame_index": 0,                  // Thứ tự trong danh sách frames đã extract (0, 1, 2, ...)
  "frame_number": "fr00000",         // Số thứ tự trong tên file
  "video_frame_number": 0,            // Số frame trong video gốc (frame thứ bao nhiêu trong video)
  "storage_refs": {
    "bucket": "frames",
    "key": "youtube/abc123xyz/abc123xyz_fr00000.jpg"
  },
  "extracted_at": "2024-01-02T10:30:00Z",
  "created_at": "2024-01-02T10:30:00Z"
}
```

## Luồng hoạt động

```
1. Download video → Lưu local
2. Upload video lên MinIO
3. Extract frames từ video:
   - Mỗi 30 frame lấy 1 ảnh
   - Resize về 1280x720
   - Upload từng frame lên MinIO
   - Lưu metadata vào MongoDB (collection: video_frames)
4. Lưu thông tin tổng hợp vào video document (storage_refs.frames_count)
```

## API Endpoints

### 1. Lấy danh sách frames của một video

```bash
GET /api/videos/{video_id}/frames?page=1&per_page=50&expires=3600
```

**Query Parameters:**
- `page`: Số trang (mặc định: 1)
- `per_page`: Số frames mỗi trang (mặc định: 50)
- `expires`: Thời gian hết hạn presigned URL (giây, mặc định: 3600)

**Response:**
```json
{
  "video_id": "abc123xyz",
  "total": 150,
  "page": 1,
  "per_page": 50,
  "total_pages": 3,
  "frames": [
    {
      "_id": "...",
      "video_id": "abc123xyz",
      "platform": "youtube",
      "frame_index": 0,
      "frame_number": "fr00000",
      "video_frame_number": 0,
      "storage_refs": {
        "bucket": "frames",
        "key": "youtube/abc123xyz/abc123xyz_fr00000.jpg"
      },
      "url": "http://minio:9000/frames/...?X-Amz-Algorithm=...",
      "extracted_at": "2024-01-02T10:30:00Z",
      "created_at": "2024-01-02T10:30:00Z"
    },
    ...
  ]
}
```

### 2. Lấy presigned URL cho một frame cụ thể

```bash
GET /api/frames/{frame_id}/url?expires=3600
```

**Response:**
```json
{
  "frame_id": "...",
  "video_id": "abc123xyz",
  "frame_index": 0,
  "url": "http://minio:9000/frames/...?X-Amz-Algorithm=...",
  "expires_in": 3600
}
```

## Sử dụng trong Python Code

### Query frames theo video_id

```python
from app import get_db_connection
from bson import ObjectId

db = get_db_connection()
collection = db['video_frames']

# Lấy tất cả frames của một video
frames = list(collection.find({'video_id': 'abc123xyz'})
              .sort('frame_index', 1))

# Lấy frame đầu tiên
first_frame = collection.find_one({
    'video_id': 'abc123xyz',
    'frame_index': 0
})

# Đếm số frames của một video
frame_count = collection.count_documents({'video_id': 'abc123xyz'})
```

### Lấy presigned URL cho frame

```python
from minio_helper import get_file_url

frame = collection.find_one({'_id': ObjectId(frame_id)})
storage_refs = frame['storage_refs']
url = get_file_url(
    storage_refs['bucket'],
    storage_refs['key'],
    expires=3600
)
```

## Quan hệ giữa Collections

### `downloaded_videos` → `video_frames`

- Một video có nhiều frames
- `downloaded_videos.video_id` = `video_frames.video_id`
- `downloaded_videos.storage_refs.frames_count` = số lượng frames

### Ví dụ query kết hợp

```python
# Lấy video và số frames
video = db['downloaded_videos'].find_one({'video_id': 'abc123xyz'})
frame_count = db['video_frames'].count_documents({'video_id': 'abc123xyz'})

# Lấy video và frames đầu tiên
video = db['downloaded_videos'].find_one({'video_id': 'abc123xyz'})
first_frame = db['video_frames'].find_one({
    'video_id': 'abc123xyz',
    'frame_index': 0
})
```

## Indexes đề xuất

Để tối ưu query, nên tạo indexes:

```javascript
// Trong MongoDB shell
use data_collection

// Index cho video_id (query frames theo video)
db.video_frames.createIndex({ "video_id": 1, "frame_index": 1 })

// Index cho platform
db.video_frames.createIndex({ "platform": 1 })

// Index cho extracted_at (tìm frames theo thời gian)
db.video_frames.createIndex({ "extracted_at": -1 })
```

## Lợi ích

1. **Truy vấn nhanh**: Biết frame nào thuộc video nào
2. **Metadata đầy đủ**: Lưu thông tin về frame (index, số frame trong video, thời gian extract)
3. **Dễ quản lý**: Có thể query, filter, sort frames
4. **Liên kết rõ ràng**: Mỗi frame biết rõ nó được cắt từ video nào



