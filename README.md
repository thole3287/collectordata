# Collector Data System

Hệ thống thu thập dữ liệu giao thông từ nhiều nguồn (YouTube, Pexels, Camera IP) và lưu trữ tập trung (MinIO, MongoDB).

## 🚀 Tính năng chính

1.  **Thu thập dữ liệu đa nguồn**:
    -   **YouTube**: Tải video theo từ khóa hoặc URL.
    -   **Pexels**: Tải video chất lượng cao cho dataset.
    -   **Camera IP**: Chụp ảnh định kỳ từ danh sách camera.
2.  **Lưu trữ thông minh**:
    -   **MinIO (S3 Validated)**: Lưu trữ file gốc (Video, Image, Frames).
    -   **MongoDB**: Lưu trữ metadata, đường dẫn file, trạng thái.
3.  **Xử lý dữ liệu**:
    -   **Frame Extraction**: Tự động cắt frame từ video tải về.
    -   **Vehicle Detection**: API nhận kết quả detect từ AI model (Bao gồm ảnh crop, biển số).
4.  **Kiến trúc Service**: Code được module hóa, dễ dàng mở rộng.

---

## 🛠 Cấu trúc hệ thống

Dự án được chia thành các Services trong thư mục `/services`:

-   `services/database.py`: Kết nối MongoDB.
-   `services/minio_service.py`: Xử lý upload/download file với MinIO.
-   `services/camera_service.py`: Quản lý Camera Collector.
-   `services/video_service.py`: Xử lý video (cắt frame).
-   `services/pexels_service.py`: Logic tải video từ Pexels.
-   `services/keyword_service.py`: Quản lý từ khóa tìm kiếm.

---

## 🔄 Luồng hoạt động (Workflow)

### 1. Luồng Tải Video (YouTube/Pexels)
1.  **User** gửi request (API/UI) để tải video (theo keyword hoặc URL).
2.  **App** gọi `yt_downloaderpy` (hoặc `PexelsService`).
3.  **Download**: Video được tải về máy chủ (thư mục `downloads` hoặc `pexels_traffic_dataset`).
4.  **Upload MinIO** (Nếu bật `UPLOAD_TO_MINIO=true`):
    -   Video gốc được đẩy lên MinIO bucket `videos`.
    -   Local file **tự động xóa** để tiết kiệm dung lượng.
5.  **Extract Frames**:
    -   Video được cắt thành ảnh (frames).
    -   Frames được đẩy lên MinIO bucket `frames`.
6.  **Save DB**: Metadata (ID, Title, MinIO Path, Frame Paths) được lưu vào MongoDB.

### 2. Luồng Camera Collector
1.  **Scheduler** chạy định kỳ (mặc định 5s - 60s tùy config).
2.  **Collector**: Kết nối đến từng Camera IP (RTSP/HTTP).
3.  **Capture**: Chụp ảnh hiện tại.
4.  **Save**:
    -   Lưu ảnh vào MinIO bucket `camera`.
    -   Lưu metadata (Camera ID, Timestamp) vào MongoDB.

### 3. Luồng Vehicle Detection (AI Integration)
1.  **AI Model** gửi kết quả detection về API `/api/vehicle-detection/upload`.
2.  **App**:
    -   Upload ảnh full, ảnh crop xe, ảnh biển số lên MinIO bucket `vehicle-detection`.
    -   Lưu thông tin chi tiết (Biển số, loại xe, màu sắc...) vào MongoDB.

---

## ⚙️ Cài đặt & Chạy ứng dụng

### 1. Cấu hình
Tạo file `.env` từ `env.example`:
```env
# MinIO Config
MINIO_ENDPOINT=localhost
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
UPLOAD_TO_MINIO=true   # Bật tính năng upload lên MinIO

# MongoDB Config
DB_HOST=localhost
DB_PORT=27017

# App Config
FLASK_PORT=5000
```

### 2. Chạy bằng Docker (Khuyên dùng)
```bash
docker-compose up -d --build
```
Hệ thống sẽ khởi tạo:
-   **App**: `http://localhost:5000`
-   **MinIO Console**: `http://localhost:9001` (User/Pass: minioadmin)
-   **MongoDB**: `localhost:27017`

### 3. Chạy thủ công (Dev)
```bash
pip install -r requirements.txt
python app.py
```

---

## 📂 Dữ liệu được lưu ở đâu?

| Loại dữ liệu | MinIO Bucket | MongoDB Collection | Mặc định Local (Nếu tắt MinIO) |
| :--- | :--- | :--- | :--- |
| **Video YouTube/Pexels** | `videos` | `downloaded_videos` | `downloads/` |
| **Ảnh trích xuất** | `frames` | `video_frames` | `dataset_extracted/` |
| **Ảnh Camera** | `camera` | `camera_images` | `camera_collector_data/` |
| **Vehicle Detection** | `vehicle-detection` | `vehicle_detections` | N/A |

---
*Created by Antigravity*
