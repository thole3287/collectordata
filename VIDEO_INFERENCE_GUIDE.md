# 🚗 Video Inference & Traffic Analytics Guide

Tài liệu này giải thích cách thức hoạt động của hệ thống nhận diện video, đếm phương tiện và phân tích lưu lượng giao thông trong ứng dụng **CollectorData**.

---

## 🏗️ 1. Kiến trúc hệ thống (Architecture)

Hệ thống được thiết kế theo mô hình **Asynchronous Task Queue** (Hàng chờ tác vụ bất đồng bộ) để đảm bảo web không bị treo khi xử lý các video nặng.

1.  **Web API (Flask)**: Nhận file video upload, lưu Metadata (Camera, Vị trí) và đẩy tác vụ vào Kafka.
2.  **Message Broker (Kafka)**: Đóng vai trò trung chuyển, giữ các tác vụ xử lý video trong hàng chờ.
3.  **Inference Worker (YOLOv8)**: Một dịch vụ chạy ngầm chuyên trách việc đọc video, chạy mô hình AI và vẽ Bounding Boxes.
4.  **Database (MongoDB)**: 
    -   `inference_jobs`: Theo dõi trạng thái realtime (đang xử lý, tiến độ %, FPS).
    -   `traffic_stats`: Lưu trữ kết quả cuối cùng sau khi xử lý xong để phục vụ Analytics.

---

## 🔄 2. Quy trình xử lý (Workflow)

### Bước 1: Tiếp nhận (Upload & Metadata)
Khi người dùng upload video tại trang **Video Inference**, hệ thống yêu cầu:
-   **Video File**: Các định dạng hỗ trợ (mp4, avi, mov).
-   **Metadata**: Chọn Camera ID, thời gian quay và vị trí để phục vụ thống kê sau này.
-   **Counting Settings**: Tùy chọn bật/tắt đếm xe và vị trí đường ngang (Line Y) để tính lượt qua lại.

### Bước 2: Xử lý AI (Inference & Tracking)
Worker nhận tác vụ và khởi tạo `InferenceService`:
-   **Model**: Sử dụng YOLOv8 (file weights: `best.pt`) được train đặc biệt cho các loại xe: `car`, `motorcycle`, `bus`, `truck`, `bicycle`.
-   **Tracking**: Sử dụng thuật toán `persist=True` (ByteTrack/BoT-SORT) để gán ID duy nhất cho mỗi đối tượng.
-   **Counting**: Khi tâm của đối tượng (Centroid) cắt qua đường kẻ ngang (Line Y), hệ thống sẽ tăng bộ đếm cho loại xe đó.

### Bước 3: Xem trực tiếp (Live Preview)
Trong khi xử lý, Worker liên tục cập nhật vào MongoDB:
-   **Preview Image**: Cứ mỗi 15 frame, một ảnh chụp màn hình mới nhất được lưu vào `static/inference_results/previews/`.
-   **Snapshots**: Tự động chụp lại ảnh tại các mốc 10%, 20%, ..., 100% tiến độ để tạo thành Album ảnh preview.
-   **Realtime Stats**: Cập nhật FPS xử lý và số lượng xe đã đếm được ngay lúc đó.

---

## 📊 3. Phân tích dữ liệu (Analytics)

Sau khi video xử lý xong (`status: completed`), dữ liệu được tổng hợp vào bộ sưu tập `traffic_stats`:

-   **Hourly Trends**: Tổng hợp số lượng xe theo từng khung giờ trong ngày để tìm giờ cao điểm.
-   **Camera/Location Ranking**: Xếp hạng các điểm giao thông đông nhất.
-   **Congestion Detection**: Hệ thống tự động tính toán ngưỡng tắc đường (**Congestion Threshold**) dựa trên thuật toán trung bình cộng và độ lệch chuẩn của dữ liệu lịch sử.

---

## 🛠️ 4. Các file quan trọng

| File | Vai trò |
| :--- | :--- |
| `routes/inference_routes.py` | Quản lý API Upload, Status và Analytics. |
| `worker.py` | Kafka Consumer, điều phối các tác vụ xử lý video. |
| `services/inference_service.py` | Trái tim của hệ thống: Chứa logic YOLO, Vẽ Box và Đếm xe. |
| `static/inference_results/` | Thư mục lưu trữ video đầu vào, đầu ra và ảnh preview. |

---

## 💡 Lưu ý vận hành
-   **GPU Acceleration**: Để đạt FPS cao, Worker nên được chạy trên máy có hỗ trợ NVIDIA GPU (CUDA).
-   **FFmpeg**: Hệ thống yêu cầu FFmpeg để nén video (`libx264`) giúp trình duyệt web có thể xem lại file đầu ra một cách mượt mà.
