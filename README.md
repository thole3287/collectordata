# Collector Data System

Hệ thống thu thập dữ liệu giao thông từ nhiều nguồn (YouTube, Pexels, Camera IP) và lưu trữ tập trung (MinIO, MongoDB).

## 🚀 Tính năng chính

1.  **Thu thập dữ liệu đa nguồn**:
    -   **YouTube**: Tải video theo từ khóa hoặc URL.
    -   **Pexels**: Tải video chất lượng cao cho dataset.
    -   **Camera IP**: Chụp ảnh định kỳ từ danh sách camera.
2.  **Lưu trữ thông minh (Hybrid Storage)**:
    -   **MinIO (Object Storage)**: Lưu trữ file gốc (Blob) như Video, Image, Frames.
    -   **MongoDB (Metadata)**: Lưu trữ thông tin nghiệp vụ và tham chiếu đến MinIO.
3.  **Xử lý dữ liệu**:
    -   **Frame Extraction**: Tự động cắt frame từ video tải về.
    -   **Vehicle Detection**: API nhận kết quả detect từ AI model (Bao gồm ảnh crop, biển số).
4.  **Kiến trúc Service**: Code được module hóa, dễ dàng mở rộng.

---

## 🏗 Kiến trúc Hybrid Storage

Hệ thống sử dụng mô hình **Hybrid Storage** kết hợp giữa MinIO và MongoDB.

### 1. Phân chia trách nhiệm
| Thành phần | Lưu cái gì? | Tại sao? |
| :--- | :--- | :--- |
| **MinIO** | Ảnh gốc (Full frame), ảnh cắt (Cropped vehicle/plate), video clip. | Tối ưu lưu file nhị phân lớn, rẻ, dễ mở rộng. |
| **MongoDB** | Biển số, loại xe, thời gian, tọa độ, **MinIO Key**. | Tối ưu tìm kiếm, lọc, thống kê nhanh. |

### 2. Schema Liên Kết (Link)
MongoDB lưu **Key** (đường dẫn tương đối) của object trong MinIO.

*   **MinIO Key**: `2024/01/02/cam_01/evt_12345_full.jpg`
*   **MongoDB Document**:
```json
{
  "_id": "ObjectId...",
  "event_id": "evt_12345",
  "storage_refs": {
    "bucket": "vehicle-detection",
    "full_frame_key": "2024/01/02/cam_01/evt_12345_full.jpg"
  }
}
```

---

## 🛠 Hướng dẫn xem Dữ liệu

### 1. Xem Metadata (MongoDB)
Cách tốt nhất là dùng **MongoDB Compass** (Miễn phí từ MongoDB).

*   **Tải về**: [Download MongoDB Compass](https://www.mongodb.com/try/download/compass)
*   **Connection String**: `mongodb://localhost:27017`
*   **Database**: `data_collection`
*   **Các Collections chính**:
    *   `downloaded_videos`: Video từ YouTube/Pexels.
    *   `video_frames`: Frame ảnh tách ra.
    *   `camera_images`: Ảnh chụp từ Camera IP.
    *   `vehicle_detections`: Kết quả nhận diện AI.

### 2. Xem File gốc (MinIO)
*   **Truy cập**: [http://localhost:9001](http://localhost:9001)
*   **User**: `minioadmin`
*   **Password**: `minioadmin123`
*   **Buckets**: `videos`, `frames`, `camera`, `vehicle-detection`.

---

## 🔄 Luồng hoạt động (Workflow)

### 1. Vehicle Detection
AI Model -> Upload MinIO (lấy Key) -> Save MongoDB (Metadata + Key).

### 2. Tải Video & Camera
File gốc -> MinIO. Thông tin -> MongoDB.

---

## ⚙️ Cài đặt & Chạy ứng dụng

### 1. Cấu hình (.env)
```env
MINIO_ENDPOINT=localhost
UPLOAD_TO_MINIO=true
DB_HOST=localhost
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=minioadmin123
```

### 2. Chạy (Docker)
```bash
docker-compose up -d --build
```
*   App: `http://localhost:5000`
*   MinIO: `http://localhost:9001`
*   Compass Kết nối: `localhost:27017`

## ❓ FAQ / Xử lý sự cố

### Q: Tại sao tôi thấy dữ liệu cũ trong MongoDB?
**A:** Docker sử dụng **Volumes** để giữ dữ liệu không bị mất khi bạn restart container.
*   Nếu bạn thấy "dữ liệu cũ", đó là tính năng (Data Persistence).
*   Nếu bạn muốn **XÓA TRẮNG** database để chạy lại từ đầu, hãy chạy lệnh này:
    ```bash
    docker-compose down -v
    ```
    *(Lệnh này sẽ xóa toàn bộ Volumes bao gồm Database và File MinIO cũ)*.

### Q: Tôi không kết nối được MongoDB ở localhost:27017?
**A:** Có thể bạn đang chạy một MongoDB khác trên máy tính (Windows Service).
*   Hãy tắt MongoDB trên Windows, hoặc đổi port trong `docker-compose.yml`.

---
*Created by Antigravity*
