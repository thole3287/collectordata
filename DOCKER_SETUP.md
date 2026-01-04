# Hướng dẫn Setup Docker cho Collector Data

## Yêu cầu

- Docker Desktop (Windows/Mac) hoặc Docker Engine + Docker Compose (Linux)
- Git (để clone project)

## Cấu trúc Docker

Project sử dụng Docker Compose với 3 services:
- **MongoDB**: Database server
- **MinIO**: Object storage (S3-compatible) cho video và ảnh
- **App**: Flask application

## Các bước setup

### 1. Tạo file .env

Copy file `env.example` thành `.env` và cập nhật các giá trị:

```bash
cp env.example .env
```

**Lưu ý**: Khi chạy với Docker, các biến môi trường sau sẽ được tự động set:
- `DB_HOST=mongodb` (tên service trong docker-compose)
- `DB_PORT=27017`
- `FLASK_HOST=0.0.0.0` (để có thể truy cập từ bên ngoài container)
- `MINIO_ENDPOINT=minio` (tên service trong docker-compose)
- `MINIO_PORT=9000`
- `MINIO_ACCESS_KEY=minioadmin` (mặc định)
- `MINIO_SECRET_KEY=minioadmin123` (mặc định)

Bạn chỉ cần điền:
- `PEXELS_API_KEY` (nếu dùng tính năng Pexels)

### 2. Build và chạy containers

```bash
# Build và start tất cả services
docker-compose up -d

# Xem logs
docker-compose logs -f

# Xem logs của một service cụ thể
docker-compose logs -f app
docker-compose logs -f mongodb
```

### 3. Truy cập ứng dụng

- **Flask App**: http://localhost:5000
- **MongoDB**: localhost:27017
- **MinIO Console**: http://localhost:9001
  - Username: `minioadmin`
  - Password: `minioadmin123`
- **MinIO API**: http://localhost:9000

### 4. Các lệnh hữu ích

```bash
# Dừng containers
docker-compose stop

# Dừng và xóa containers
docker-compose down

# Dừng và xóa containers + volumes (xóa cả data)
docker-compose down -v

# Rebuild containers sau khi thay đổi code
docker-compose up -d --build

# Xem status các containers
docker-compose ps

# Vào shell của container app
docker-compose exec app bash

# Vào MongoDB shell
docker-compose exec mongodb mongosh
```

### 5. Backup và Restore MongoDB

#### Backup:
```bash
docker-compose exec mongodb mongodump --out /data/backup
docker-compose cp mongodb:/data/backup ./mongodb_backup
```

#### Restore:
```bash
docker-compose cp ./mongodb_backup mongodb:/data/backup
docker-compose exec mongodb mongorestore /data/backup
```

## MinIO Object Storage

MinIO được sử dụng để lưu trữ video và ảnh. Các buckets sẽ được tạo tự động khi app khởi động:

- **videos**: Lưu các video đã tải về
- **images**: Lưu các ảnh đã extract
- **frames**: Lưu các frames từ video
- **camera-images**: Lưu ảnh từ camera collector

### Sử dụng MinIO trong code

Import và sử dụng `minio_helper.py`:

```python
from minio_helper import upload_file, download_file, get_file_url

# Upload video
upload_file(
    file_path="downloads/video.mp4",
    bucket_name="videos",
    object_name="my-video.mp4"
)

# Download file
download_file(
    bucket_name="videos",
    object_name="my-video.mp4",
    file_path="local-video.mp4"
)

# Lấy URL để truy cập file
url = get_file_url("videos", "my-video.mp4", expires=3600)
```

### Truy cập MinIO Console

1. Mở http://localhost:9001
2. Đăng nhập với:
   - Username: `minioadmin`
   - Password: `minioadmin123`
3. Tại đây bạn có thể:
   - Xem các buckets và files
   - Upload/download files thủ công
   - Quản lý access policies
   - Tạo buckets mới

## Volumes

Các thư mục sau được mount từ host vào container để dữ liệu được lưu trữ bền vững:

- `./downloads` → Video đã tải về (có thể sync lên MinIO)
- `./dataset_extracted` → Frames đã extract (có thể sync lên MinIO)
- `./pexels_traffic_dataset` → Video từ Pexels (có thể sync lên MinIO)
- `./camera_collector_data` → Ảnh từ camera collector (có thể sync lên MinIO)
- `./camera_collector_config` → Config camera

**Lưu ý**: Dữ liệu trong MinIO được lưu trong Docker volume `minio_data`, không mất khi restart container.

## Troubleshooting

### Port đã được sử dụng

Nếu port 5000, 27017, 9000, hoặc 9001 đã được sử dụng, bạn có thể:

1. Thay đổi port trong `docker-compose.yml`:
```yaml
ports:
  - "5001:5000"  # Thay 5000 thành 5001
  - "9002:9000"  # Thay MinIO API port
  - "9003:9001"  # Thay MinIO Console port
```

2. Hoặc dừng service đang dùng port đó

### MongoDB không kết nối được

Kiểm tra:
1. MongoDB container đã chạy: `docker-compose ps`
2. Logs của MongoDB: `docker-compose logs mongodb`
3. Đảm bảo `DB_HOST=mongodb` trong .env (không phải localhost)

### App không start

1. Kiểm tra logs: `docker-compose logs app`
2. Kiểm tra file .env có tồn tại
3. Rebuild: `docker-compose up -d --build`

### MinIO không kết nối được

1. Kiểm tra MinIO container đã chạy: `docker-compose ps`
2. Logs của MinIO: `docker-compose logs minio`
3. Đảm bảo `MINIO_ENDPOINT=minio` trong .env (không phải localhost khi chạy trong Docker)
4. Truy cập MinIO Console để kiểm tra: http://localhost:9001

## Development

Khi phát triển, bạn có thể mount code vào container để thay đổi code không cần rebuild:

```yaml
volumes:
  - .:/app  # Mount toàn bộ code
```

**Lưu ý**: Cách này có thể chậm hơn, chỉ dùng khi development.

## Production

Để deploy production:

1. Set `FLASK_DEBUG=False` trong .env
2. Sử dụng reverse proxy (nginx) trước Flask app
3. Setup SSL/TLS
4. Sử dụng MongoDB với authentication
5. Backup database định kỳ


