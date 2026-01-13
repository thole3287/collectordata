# Tài Liệu Hệ Thống Thu Thập Dữ Liệu (Data Collector System)

## 1. Tổng Quan Hệ Thống (Overview)
Hệ thống **Data Collector** là một giải pháp toàn diện được thiết kế để tự động hóa quy trình thu thập, xử lý và lưu trữ dữ liệu hình ảnh/video quy mô lớn. Mục tiêu chính là xây dựng các bộ dữ liệu chất lượng cao (Dataset) phục vụ cho việc huấn luyện các mô hình Trí Tuệ Nhân Tạo (AI), đặc biệt trong các lĩnh vực giám sát giao thông, phát hiện phương tiện, và phân tích hành vi.

Hệ thống có khả năng tổng hợp dữ liệu từ đa nguồn:
1.  **Nền tảng chia sẻ video**: YouTube, Pexels.
2.  **Thiết bị giám sát thực**: IP Cameras (RTSP/HTTP Streams).

Điểm mạnh của hệ thống là khả năng **tự động hóa hoàn toàn** (từ tìm kiếm từ khóa đến lưu trữ), **xử lý ảnh thông minh** (tự động cân bằng sáng, giảm nhiễu theo thời tiết), và **lưu trữ tối ưu** (Object Storage + Metadata Database).

---

## 2. Kiến Trúc Hệ Thống (System Architecture)

Sơ đồ luồng dữ liệu tổng quát:

```mermaid
graph TD
    subgraph "Nguồn Dữ Liệu (Data Sources)"
        YT[YouTube]
        PX[Pexels]
        CAM[IP Camera / CCTV]
    end

    subgraph "Hàng Đợi & Điều Phối (Queue & Dispatch)"
        K[Apache Kafka]
        AC[Auto Collector Service]
    end

    subgraph "Xử Lý Trung Tâm (Worker Service)"
        subgraph "Downloaders"
            DL_YT[YouTube Downloader (yt-dlp)]
            DL_PX[Pexels Downloader API]
            DL_CAM[Camera Capture Stream]
        end
        
        subgraph "Processors"
            EXT[Frame Extractor (OpenCV)]
            FILTER[Smart Filter (Blur/Dark/Dup)]
            ENH[Smart Image Enhancer]
        end
    end

    subgraph "Lưu Trữ (Storage Layer)"
        MDB[(MongoDB - Metadata)]
        MIN[(MinIO - Object Storage)]
    end

    subgraph "Giao Diện (Frontend)"
        API[Flask REST API]
        DASH[Dashboard UI]
    end

    %% Luồng dữ liệu
    AC -- "Gửi task từ khóa" --> K
    K -- "Điều phối task" --> DL_YT & DL_PX
    CAM -- "Kết nối trực tiếp" --> DL_CAM
    
    YT --> DL_YT
    PX --> DL_PX
    
    DL_YT & DL_PX -- "Video thô" --> EXT
    EXT -- "Frames thô" --> FILTER
    FILTER -- "Frames đạt chuẩn" --> ENH
    DL_CAM -- "Ảnh chụp" --> ENH
    
    ENH -- "1. Phân tích ngữ cảnh (Ngày/Đêm/Mưa)" --> ENH
    ENH -- "2. Resize 640x640 (Padding)" --> ENH
    
    ENH -- "Ảnh 16-bit PNG" --> MIN
    ENH -- "Metadata (Hash, Weather, Path)" --> MDB
    
    MDB <--> API <--> DASH
```

### Giải Thích Các Thành Phần

#### A. Core Services
*   **Worker Service (`worker.py`)**: "Trái tim" của hệ thống. Chạy ngầm dưới dạng Docker Container, lắng nghe các lệnh từ Kafka để thực hiện các tác vụ nặng như tải video, cắt ảnh.
*   **Auto Collector (`auto_collector_service.py`)**: "Bộ não" tự động. Định kỳ quét danh sách từ khóa (Keywords) trong database, nếu thấy từ khóa nào chưa đủ dữ liệu sẽ tự động đẩy task vào Kafka để Worker đi thu thập thêm.

#### B. Xử Lý Hình Ảnh (`services/image_enhancement.py`)
Đây là module thông minh nhất của hệ thống, bao gồm các bước:
1.  **Phân Tích Ngữ Cảnh (Scene Analysis)**:
    *   Tự động tính toán độ sáng (Brightness), độ bão hòa màu (Saturation) và độ tương phản (Contrast).
    *   Phân loại ảnh thành: **Day** (Ngày), **Night** (Đêm), hoặc **Rain** (Mưa/Sương mù).
2.  **Cải Thiện Ảnh (Enhancement)**:
    *   Dựa vào loại ngữ cảnh, áp dụng bộ thông số (Profile) riêng biệt từ file cấu hình `enhance_settings.json`.
    *   *Ví dụ Night*: Tăng Gamma (1.2), áp dụng khử nhiễu (Denoise strength 3.0), cân bằng Histogram (CLAHE).
3.  **Chuẩn Hóa Đầu Ra (Standardization)**:
    *   Tất cả ảnh đều được Resize về kích thước chuẩn **640x640**.
    *   Sử dụng kỹ thuật **Padding (Letterbox)**: Giữ nguyên tỷ lệ khung hình gốc, thêm viền đen vào các phần thừa để ảnh không bị méo.

#### C. Lưu Trữ (Storage)
*   **MinIO**: Hệ thống lưu trữ đối tượng (tương tự Amazon S3).
    *   Lưu trữ file Video gốc và file Ảnh (Frames) dưới dạng nhị phân.
    *   Cấu trúc đường dẫn khoa học: `bucket/platform/video_id/filename.png` hoặc `bucket/camera_id/YYYY/MM/DD/...`.
*   **MongoDB**: Cơ sở dữ liệu NoSQL.
    *   Lưu trữ thông tin metadata: Kích thước, độ phân giải, thời gian chụp, Hash (SHA256) để chống trùng, và đặc biệt là đường dẫn tham chiếu sang MinIO.

---

## 3. Quy Trình Thu Thập Dữ Liệu Chi Tiết

### A. YouTube Downloader (`yt_downloaderpy.py`)
Hệ thống sử dụng thư viện `yt-dlp` với các tùy chỉnh nâng cao:
1.  **Lazy Infinite Search**: Thay vì tải một cục dữ liệu, hệ thống sử dụng Generator để duyệt qua hàng nghìn kết quả tìm kiếm (Limit 2000+).
2.  **Duplication Check**: Trước khi tải bất kỳ video nào, hệ thống kiểm tra ID hoặc Hash trong Database. Nếu đã tồn tại -> **Bỏ qua ngay lập tức**, giúp tiết kiệm băng thông và thời gian.
3.  **H.264 Enforce**: Bắt buộc tải video định dạng H.264 (AVC1) để tránh lỗi giải mã AV1 trên các máy tính không có GPU hỗ trợ, đảm bảo Worker hoạt động mượt mà 24/7.

### B. Smart Frame Filtering & Extraction (Bộ Lọc Frame Thông Minh)
Trước khi được lưu trữ hay xử lý nâng cao, các frames trích xuất từ video phải vượt qua quy trình **Lọc Đa Tầng** nghiêm ngặt để đảm bảo chất lượng Dataset:

1.  **Lọc Độ Sáng (Brightness Filter)**:
    *   Tính toán cường độ sáng trung bình (Mean Intensity).
    *   **Loại bỏ** các frame quá tối ( < 40) hoặc cháy sáng ( > 220).
2.  **Lọc Độ Mờ (Blur Detection)**:
    *   Sử dụng thuật toán **Variance of Laplacian**.
    *   **Loại bỏ** các frame bị nhòe, mất nét (Blur Score < 100).
3.  **Lọc Trùng Lặp (Similarity Check)**:
    *   So sánh Histogram màu của frame hiện tại với frame đã lưu trước đó.
    *   Nếu độ tương đồng (Correlation) > **0.95**, hệ thống coi là frame dư thừa và **bỏ qua**.

### C. Pexels Downloader (`services/pexels_service.py`)
1.  **Continuous Pagination**: Hệ thống tự động lật trang (Page 1 -> Page 2 -> ...) liên tục trong vòng lặp.
2.  **Target Met**: Vòng lặp chỉ dừng lại khi ĐÃ LƯU ĐỦ số lượng video yêu cầu vào Database. Các video trùng lặp hoặc bị lỗi sẽ không được tính vào chỉ tiêu (Quota).
3.  **Regex Filtering**: Hỗ trợ lọc nâng cao bằng biểu thức chính quy (Regex) ngay từ tiêu đề video để loại bỏ rác.

### C. Camera Collector (`camera_collector.py`)
1.  Kết nối trực tiếp tới luồng RTSP của Camera.
2.  Chụp ảnh theo chu kỳ (Interval).
3.  Ảnh chụp được xử lý ngay lập tức (Enhance + Resize) và upload thẳng lên MinIO.
4.  Dữ liệu tạm trên ổ cứng (Local) sẽ bị xóa ngay sau khi upload thành công để giải phóng dung lượng.

---

## 4. Hướng Dẫn Vận Hành Cơ Bản

### Khởi Động Hệ Thống
Hệ thống hoạt động trên nền tảng Docker. Để khởi động toàn bộ:
```bash
docker-compose up -d
```
Lệnh này sẽ khởi chạy các container: `mongodb`, `minio`, `zookeeper`, `kafka`, `app` (Web), và `worker`.

### Thêm Từ Khóa Mới
Có thể thêm thông qua API hoặc Giao diện Web:
*   **Keyword**: Từ khóa tìm kiếm (VD: "Street CCTV Vietnam").
*   **Num Videos**: Số lượng video mục tiêu (VD: 100).
*   **Auto-Collector**: Worker sẽ tự động nhận diện từ khóa mới và bắt đầu quy trình tìm kiếm -> tải về -> trích xuất -> lưu trữ.

### Cấu Hình Xử Lý Ảnh
Chỉnh sửa file `enhance_settings.json` tại thư mục gốc nếu muốn thay đổi thông số:
```json
{
  "profiles": {
    "night": {
      "resize_640": true,
      "gamma": 1.5,       // Tăng độ sáng cho ảnh đêm
      "denoise_strength": 5.0
    }
  }
}
```
Sau khi sửa, cần khởi động lại Worker:
```bash
docker restart collectordata_worker
```

---

*Tài liệu được cập nhật ngày 13/01/2026 bởi Đội ngũ Phát triển Hệ thống (System Dev Team).*
