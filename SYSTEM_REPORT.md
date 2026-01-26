# BÁO CÁO CHI TIẾT HỆ THỐNG THU THẬP VÀ XỬ LÝ DỮ LIỆU (DATA COLLECTOR SYSTEM)

---

## 1. GIỚI THIỆU CHUNG (INTRODUCTION)

### 1.1. Bối Cảnh & Mục Tiêu
Trong kỷ nguyên số hóa và trí tuệ nhân tạo (AI), dữ liệu đóng vai trò then chốt trong việc huấn luyện các mô hình học sâu (Deep Learning). Hệ thống **Data Collector** được phát triển nhằm giải quyết bài toán tự động hóa quy trình thu thập, xử lý và lưu trữ dữ liệu hình ảnh/video quy mô lớn từ đa nguồn (Camera giám sát, Video sharing platforms).

Mục tiêu chính của hệ thống:
1.  **Tự động hóa 100%**: Giảm thiểu sự can thiệp của con người trong quy trình thu thập dữ liệu.
2.  **Đảm bảo chất lượng dữ liệu**: Tự động lọc bỏ dữ liệu nhiễu, kém chất lượng ngay từ đầu vào.
3.  **Chuẩn hóa dữ liệu**: Đồng bộ định dạng, kích thước và gán nhãn tự động (Auto-labeling) về ngữ cảnh (Ngày/Đêm/Mưa).
4.  **Lưu trữ thông minh**: Tối ưu hóa dung lượng và khả năng truy xuất phục vụ huấn luyện Model AI.

### 1.2. Phạm Vi Ứng Dụng
Hệ thống được thiết kế để phục vụ các bài toán:
*   Phát hiện phương tiện giao thông (Vehicle Detection).
*   Giám sát an ninh trật tự (Security Surveillance).
*   Phân tích hành vi đám đông (Crowd Analysis).

---

## 2. KIẾN TRÚC HỆ THỐNG (SYSTEM ARCHITECTURE)

Hệ thống được xây dựng dựa trên kiến trúc **Microservices**, vận hành hoàn toàn trên nền tảng **Containerization (Docker)** để đảm bảo tính linh hoạt, dễ dàng mở rộng và triển khai.

### 2.1. Sơ Đồ Khối Tổng Quát

```mermaid
graph TD
    User[Người Quản Trị] -->|Truy cập Dashboard| WebApp["Web Application (Flask)"]
    
    WebApp -->|API Request| API[API Service]
    API -->|Metadata| Mongo[(MongoDB)]
    
    subgraph Sources [Nguồn Dữ Liệu]
        YT[YouTube]
        PX[Pexels]
        CCTV[IP Cameras]
    end
    
    AC[Auto Collector Service] -->|1. Tìm kiếm Video| API
    AC -->|2. Gửi Task Download| Kafka["Apache Kafka Message Queue"]
    
    Kafka -->|3. Phân phối Task| Worker[Worker Service Scalable]
    
    Worker -->|4. Download Video| DL[Downloader Module]
    DL -->|5. Trích xuất Frame| EXT[Frame Extractor]
    
    subgraph DataProcessing [Xử Lý Thông Minh]
        EXT -->|Raw Files| Filter["Smart Filter (Lọc Sáng/Mờ/Trùng)"]
        Filter -->|Clean Files| Enhance["Image Enhancer (Cải thiện ảnh)"]
        Enhance -->|Scene Tags| Analysis["Scene Analysis (Ngày/Đêm)"]
    end
    
    Analysis -->|6. Upload Ảnh (PNG 16-bit)| MinIO[("MinIO Object Storage")]
    Analysis -->|7. Lưu Metadata| Mongo
    
    CCTV --> APICam[Camera Collector Service]
    APICam --> DataProcessing
```

### 2.2. Các Thành Phần Chi Tiết

#### A. Tầng Giao Diện & Điều Khiển (Frontend & Control Plane)
*   **Web Dashboard**: Giao diện người dùng cho phép quản lý từ khóa (Keywords), theo dõi trạng thái hệ thống, và xem trước dữ liệu (Dataset Visualization).
*   **Flask API Gateway**: Cung cấp các RESTful API cho Dashboard và các Service nội bộ giao tiếp.

#### B. Tầng Thu Thập Tự Động (Auto Collection Layer)
*   **Service**: `AutoCollectorService`
*   **Chức năng**:
    *   Định kỳ quét danh sách từ khóa trong Database.
    *   Tự động phát hiện các từ khóa chưa đủ dữ liệu (Số video hiện có < Mục tiêu).
    *   Tự động gửi yêu cầu thu thập (Task) vào hàng đợi Kafka.

#### C. Tầng Xử Lý Tác Vụ (Worker Layer)
*   **Công nghệ**: Apache Kafka (Message Queue) & Python Workers.
*   **Chức năng**:
    *   **Decoupling**: Tách biệt việc nhận yêu cầu và xử lý thực tế, giúp hệ thống không bị quá tải khi có hàng nghìn yêu cầu cùng lúc.
    *   **Scalability**: Có thể chạy nhiều Worker container song song để tăng tốc độ xử lý.

#### D. Tầng Lưu Trữ (Storage Layer)
*   **MinIO (Object Storage)**:
    *   Đóng vai trò thay thế Amazon S3 để lưu trữ file nhị phân (Video, Hình ảnh).
    *   Cấu trúc lưu trữ phân tầng: `{Platform}/{Scene_Type}/{Video_ID}/{Filename}.png`.
*   **MongoDB (NoSQL Database)**:
    *   Lưu trữ dữ liệu phi cấu trúc và Metadata.
    *   Quản lý liên kết giữa file trên MinIO và các thông tin mô tả (Thời gian, Kích thước, Độ phân giải, Thời tiết).

---

## 3. CHI TIẾT TÍNH NĂNG & CÔNG NGHỆ CỐT LÕI

### 3.1. Bộ Lọc Dữ Liệu Thông Minh (Smart Filtering)
Để đảm bảo chất lượng Dataset đầu ra, hệ thống áp dụng pipeline lọc đa tầng nghiêm ngặt (tại `services/video_service.py`):

1.  **Lọc Theo Độ Sáng (Brightness Filtering)**:
    *   *Nguyên lý*: Tính cường độ sáng trung bình (Mean Intensity) của ảnh.
    *   *Ngưỡng*: Loại bỏ ảnh quá tối (<40) hoặc cháy sáng (>220).
2.  **Lọc Theo Độ Mờ (Blur Detection)**:
    *   *Thuật toán*: Variance of Laplacian.
    *   *Mục đích*: Loại bỏ các frame bị nhòe do chuyển động nhanh hoặc mất nét.
3.  **Khử Trùng Lặp (Deduplication)**:
    *   *Thuật toán*: Histogram Comparison (Correlation).
    *   *Cơ chế*: So sánh biểu đồ màu của frame hiện tại với frame trước đó. Nếu độ tương đồng > 95%, hệ thống coi là trùng lặp và loại bỏ.

### 3.2. Cải Thiện & Chuẩn Hóa Ảnh (Image Enhancement)
(Module: `services/image_enhancement.py`)

Hệ thống không chỉ thu thập mà còn chủ động cải thiện chất lượng ảnh:
1.  **Phân Tích Ngữ Cảnh (Scene Analysis)**:
    *   Tự động phân loại ảnh thành **Day** (Ngày), **Night** (Đêm), hoặc **Rain** (Mưa) dựa trên đặc trưng hình ảnh.
2.  **Áp Dụng Profile Xử Lý**:
    *   Mỗi ngữ cảnh có bộ tham số (Profile) riêng biệt.
    *   *Ví dụ (Night Profile)*: Tăng Gamma (1.2) để làm sáng vùng tối, tăng Denoise (3.0) để khử nhiễu hạt.
3.  **Chuẩn Hóa Kích Thước (Resizing with Padding)**:
    *   Tất cả ảnh được đưa về kích thước chuẩn **640x640** (hoặc 1280x720 tùy cấu hình).
    *   Sử dụng kỹ thuật **Padding (Letterbox)** để giữ nguyên tỷ lệ khung hình gốc, tránh làm méo mó đối tượng trong ảnh.

### 3.3. Thu Thập Dữ Liệu Camera (Real-time Camera Collector)
(Module: `camera_collector.py`)
*   **Cơ chế**: Kết nối trực tiếp tới luồng dữ liệu của Camera Giao thông.
*   **Giả lập Browser**: Sử dụng Session và Cookies giả lập để vượt qua cơ chế chặn bot đơn giản.
*   **Quy trình**:
    *   Tải ảnh Snapshot thời gian thực.
    *   Sơ chế (Lọc sáng/mờ).
    *   Chuyển đổi sang định dạng `PNG 16-bit` (chất lượng cao).
    *   Upload thẳng lên MinIO và xóa file tạm để tiết kiệm ổ cứng.

---

## 4. CẤU TRÚC DỮ LIỆU (DATABASE SCHEMA)

Hệ thống sử dụng MongoDB với thiết kế Schema linh hoạt:

### 4.1. Collection `keywords` (Quản lý từ khóa)
| Field | Type | Description |
| :--- | :--- | :--- |
| `_id` | ObjectId | Khóa chính |
| `keyword` | String | Từ khóa tìm kiếm (VD: "Street CCTV") |
| `num_videos` | Int | Số lượng video mục tiêu |
| `status` | String | Trạng thái (`active`, `pending`) |
| `total_downloaded` | Int | Số lượng đã thu thập được |

### 4.2. Collection `video_frames` (Metadata Frame Ảnh)
| Field | Type | Description |
| :--- | :--- | :--- |
| `video_name` | String | Tên video gốc |
| `platform` | String | Nguồn (`youtube`, `pexels`) |
| `frame_index` | Int | Vị trí frame trong video |
| `scene_type` | String | Phân loại (`day`, `night`, `rain`) |
| `storage_refs` | Object | Tham chiếu MinIO (`bucket`, `key`) |
| `created_at` | Date | Thời gian tạo |

---

## 5. HƯỚNG PHÁT TRIỂN & MỞ RỘNG (ROADMAP)

Được thiết kế theo hướng mở, hệ thống sẵn sàng cho các nâng cấp trong tương lai:

1.  **AI-based Filtering**: Thay thế thuật toán lọc CV truyền thống bằng mô hình Deep Learning (ví dụ: CNN classifier) để lọc ảnh rác chính xác hơn.
2.  **Object Detection Pipeline**: Tích hợp sẵn mô hình YOLO để tự động gán nhãn (Auto-labeling) bounding box cho xe cộ/người ngay sau khi cắt frame.
3.  **Multi-node Scaling**: Triển khai Kafka và Worker trên nhiều server vật lý khác nhau để tăng năng suất xử lý lên hàng triệu ảnh/ngày.
