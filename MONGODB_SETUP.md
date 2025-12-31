# Hướng dẫn cấu hình MongoDB

## 1. Cài đặt MongoDB

### Windows (Laragon)
Nếu bạn dùng Laragon, MongoDB có thể đã được cài đặt sẵn. Kiểm tra:
- Mở Laragon
- Xem trong menu có MongoDB không
- Hoặc cài đặt MongoDB Community Server từ: https://www.mongodb.com/try/download/community

### Khởi động MongoDB
```bash
# Nếu dùng Laragon, khởi động từ Laragon menu
# Hoặc chạy lệnh:
mongod
```

## 2. Cấu hình file .env

File `.env` đã được tạo với cấu hình mặc định:

```env
# MongoDB Configuration
DB_HOST=localhost
DB_PORT=27017
DB_NAME=data_collection
DB_USER=
DB_PASSWORD=
```

### Các trường hợp sử dụng:

#### A. MongoDB local không có authentication (Mặc định)
```env
DB_HOST=localhost
DB_PORT=27017
DB_NAME=data_collection
DB_USER=
DB_PASSWORD=
```

#### B. MongoDB local có authentication
```env
DB_HOST=localhost
DB_PORT=27017
DB_NAME=data_collection
DB_USER=admin
DB_PASSWORD=your_password
```

#### C. MongoDB trên server khác
```env
DB_HOST=192.168.1.100
DB_PORT=27017
DB_NAME=data_collection
DB_USER=your_username
DB_PASSWORD=your_password
```

#### D. MongoDB Atlas (Cloud)
Nếu dùng MongoDB Atlas, bạn cần sửa code để hỗ trợ connection string. 
Connection string có dạng: `mongodb+srv://username:password@cluster.mongodb.net/database`

## 3. Kiểm tra kết nối

### Cách 1: Chạy ứng dụng
```bash
python app.py
```
Nếu kết nối thành công, server sẽ khởi động bình thường.

### Cách 2: Test kết nối bằng Python
```python
from pymongo import MongoClient
import os
from dotenv import load_dotenv

load_dotenv()

db_host = os.getenv('DB_HOST', 'localhost')
db_port = int(os.getenv('DB_PORT', 27017))
db_name = os.getenv('DB_NAME', 'data_collection')
db_user = os.getenv('DB_USER', '')
db_password = os.getenv('DB_PASSWORD', '')

if db_user and db_password:
    connection_string = f"mongodb://{db_user}:{db_password}@{db_host}:{db_port}/"
else:
    connection_string = f"mongodb://{db_host}:{db_port}/"

try:
    client = MongoClient(connection_string)
    client.admin.command('ping')
    print("✅ Kết nối MongoDB thành công!")
    
    db = client[db_name]
    collections = db.list_collection_names()
    print(f"📁 Database: {db_name}")
    print(f"📂 Collections: {collections}")
except Exception as e:
    print(f"❌ Lỗi kết nối: {e}")
```

## 4. Tạo Collections

Collections sẽ được tạo tự động khi bạn chạy ứng dụng lần đầu:
- `keywords` - Lưu các từ khóa tìm kiếm
- `downloaded_videos` - Lưu thông tin video đã tải

Hoặc tạo thủ công bằng MongoDB Compass hoặc mongo shell:
```javascript
use data_collection

// Collection keywords sẽ được tạo tự động khi insert document đầu tiên
// Collection downloaded_videos sẽ được tạo tự động khi insert document đầu tiên
```

## 5. Cấu trúc dữ liệu

### Collection: `keywords`
```json
{
  "_id": ObjectId("..."),
  "keyword": "Road traffic video",
  "num_videos": 1,
  "status": "pending",
  "total_downloaded": 0,
  "last_downloaded_at": null,
  "description": "",
  "is_active": true,
  "created_at": ISODate("2025-12-25T07:07:21Z"),
  "updated_at": ISODate("2025-12-25T07:42:01Z")
}
```

### Collection: `downloaded_videos`
```json
{
  "_id": ObjectId("..."),
  "video_id": "youtube_id_example",
  "title": "Road traffic in Saigon",
  "url": "https://youtube.com/watch?v=...",
  "file_path": "/data/videos/saigon_traffic.mp4",
  "media_type": "mp4",
  "metadata": {
    "duration": 120,
    "fps": 30,
    "width": 1920,
    "height": 1080,
    "resolution": "1920x1080"
  },
  "platform": "youtube",
  "keyword": "saigon traffic",
  "download_method": "keyword",
  "downloaded_at": ISODate("2025-12-31T10:00:00Z"),
  "created_at": ISODate("2025-12-31T10:00:00Z")
}
```

## 6. Troubleshooting

### Lỗi: "Connection refused"
- Kiểm tra MongoDB đã khởi động chưa
- Kiểm tra port 27017 có bị firewall chặn không
- Kiểm tra DB_HOST và DB_PORT trong .env

### Lỗi: "Authentication failed"
- Kiểm tra DB_USER và DB_PASSWORD trong .env
- Đảm bảo user có quyền truy cập database

### Lỗi: "Database not found"
- Database sẽ được tạo tự động khi insert document đầu tiên
- Hoặc tạo thủ công: `use data_collection`

## 7. MongoDB Tools

### MongoDB Compass (GUI)
Tải tại: https://www.mongodb.com/products/compass
- Giao diện đồ họa để quản lý MongoDB
- Xem và chỉnh sửa dữ liệu dễ dàng

### MongoDB Shell (mongo/mongosh)
```bash
mongosh
use data_collection
db.keywords.find()
db.downloaded_videos.find()
```

