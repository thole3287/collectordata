# services/boxplot_service.py

import cv2
import numpy as np
import matplotlib.pyplot as plt
import os
import shutil
import time
from services.minio_service import get_minio_client

# Định nghĩa bucket (thêm nếu chưa có trong minio_service)
MINIO_BUCKET_FRAMES = "frames"  # Hoặc lấy từ extensions/config
MINIO_BUCKET_VIDEOS = "videos"  # Bucket chứa video gốc


def generate_boxplot_for_prefix(
    bucket: str,
    prefix: str = "",
    local_root: str = "downloads/temp_boxplot",
    output_dir: str = "resources/static/boxplots",
) -> dict:
    """
    Tạo boxplot cho dữ liệu trong bucket + prefix.
    Tự động phân biệt frame ảnh hay video.
    """
    start_time = time.time()
    print(f"🚀 Tạo boxplot - Bucket: {bucket} | Prefix: {prefix}")

    try:
        os.makedirs(local_root, exist_ok=True)
        os.makedirs(output_dir, exist_ok=True)

        client = get_minio_client()

        if prefix and not prefix.endswith("/"):
            prefix += "/"

        objects = list(client.list_objects(bucket, prefix=prefix, recursive=True))
        if not objects:
            return {
                "success": False,
                "message": f"Không tìm thấy dữ liệu trong {bucket}/{prefix}",
            }

        # Detect loại dữ liệu
        is_video_bucket = bucket.lower() in [
            "videos",
            "raw_videos",
            "youtube_videos",
            "video",
        ]
        sample_exts = [
            obj.object_name.lower()[-5:]
            for obj in objects[:20]
            if "." in obj.object_name
        ]
        has_video_ext = any(
            ext in sample_exts
            for ext in [".mp4", ".avi", ".mov", ".mkv", ".webm", ".mpg"]
        )
        is_video = is_video_bucket or has_video_ext

        # Mặc định type_str trước để tránh lỗi UnboundLocalError
        type_str = "VIDEO" if is_video else "FRAME ẢNH"

        # Tải file
        local_paths = []
        count = 0
        for obj in objects:
            if obj.object_name.endswith("/"):
                continue
            filename = os.path.basename(obj.object_name)
            safe_name = f"{bucket}_{prefix.replace('/', '_')}_{filename}"
            local_path = os.path.join(local_root, safe_name)
            try:
                client.fget_object(bucket, obj.object_name, local_path)
                local_paths.append(local_path)
                count += 1
            except Exception as e:
                print(f"Cảnh báo: Không tải được {obj.object_name}: {e}")

        if count == 0:
            return {"success": False, "message": "Không tải được file nào hợp lệ"}

        print(f"📥 Tải về {count} {'video' if is_video else 'frame'}")

        # Khởi tạo data chung
        data = {}
        features = []
        feature_names_vn = {}

        if is_video:
            # Đặc trưng video
            features = [
                "duration",
                "bitrate",
                "frame_rate",
                "width",
                "height",
                "file_size_mb",
            ]
            feature_names_vn = {
                "duration": "Thời lượng (giây)",
                "bitrate": "Bitrate (kbps)",
                "frame_rate": "FPS",
                "width": "Chiều rộng (px)",
                "height": "Chiều cao (px)",
                "file_size_mb": "Kích thước (MB)",
            }
            data = {f: [] for f in features}

            for path in local_paths:
                try:
                    cap = cv2.VideoCapture(path)
                    if not cap.isOpened():
                        continue

                    fps = cap.get(cv2.CAP_PROP_FPS)
                    frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
                    duration = frame_count / fps if fps > 0 else 0
                    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                    file_size_mb = os.path.getsize(path) / (1024 * 1024)
                    bitrate = (file_size_mb * 8192) / duration if duration > 0 else 0

                    data["duration"].append(duration if duration > 0 else 0)
                    data["bitrate"].append(bitrate)
                    data["frame_rate"].append(fps if fps > 0 else 0)
                    data["width"].append(width)
                    data["height"].append(height)
                    data["file_size_mb"].append(file_size_mb)

                    cap.release()
                except Exception as e:
                    print(f"Lỗi xử lý video {path}: {e}")
                    continue

        else:
            # Đặc trưng frame ảnh
            features = ["brightness", "contrast", "blur", "noise_level", "edge_density"]
            feature_names_vn = {
                "brightness": "Độ sáng",
                "contrast": "Độ tương phản",
                "blur": "Độ nét (Laplacian)",
                "noise_level": "Độ nhiễu",
                "edge_density": "Mật độ cạnh",
            }
            data = {f: [] for f in features}

            for path in local_paths:
                try:
                    img = cv2.imread(path)
                    if img is None:
                        continue
                    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

                    data["brightness"].append(float(np.mean(gray)))
                    data["contrast"].append(float(np.std(gray)))
                    data["blur"].append(float(cv2.Laplacian(gray, cv2.CV_64F).var()))

                    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
                    data["noise_level"].append(float(np.std(gray - blurred)))

                    edges = cv2.Canny(gray, 100, 200)
                    data["edge_density"].append(float(np.sum(edges > 0) / edges.size))
                except Exception as e:
                    print(f"Lỗi xử lý ảnh {path}: {e}")
                    continue

        # Kiểm tra có dữ liệu hợp lệ không
        valid_features = [f for f in features if len(data[f]) > 0]
        if not valid_features:
            return {
                "success": False,
                "message": "Không trích xuất được đặc trưng nào từ dữ liệu",
            }

        # Vẽ boxplot chỉ với các feature có dữ liệu
        n = len(valid_features)
        fig, axes = plt.subplots(1, n, figsize=(6 * n, 10))
        if n == 1:
            axes = [axes]

        fig.suptitle(
            f"Boxplot Phát Hiện Outliers - {type_str}\n"
            f"Nguồn: {bucket}/{prefix.rstrip('/')}\n"
            f"({len(data[valid_features[0]])} mẫu hợp lệ)",
            fontsize=18,
            y=0.98,
        )

        for i, feat in enumerate(valid_features):
            values = [v for v in data[feat] if not np.isnan(v) and not np.isinf(v)]
            if not values:
                continue
            bp = axes[i].boxplot(values, patch_artist=True, notch=True, showfliers=True)
            axes[i].set_title(feature_names_vn[feat], fontsize=14)
            axes[i].grid(axis="y", alpha=0.3)
            bp["boxes"][0].set_facecolor("lightblue")
            for flier in bp["fliers"]:
                flier.set(marker="o", color="red", alpha=0.8, markersize=6)

        plt.tight_layout()

        # Tên file an toàn
        slug = f"{bucket}_{prefix.strip('/').replace('/', '_')}".strip("_")
        filename = f"boxplot_{slug or 'all'}.png"
        path = os.path.join(output_dir, filename)
        plt.savefig(path, dpi=200, bbox_inches="tight")
        plt.close(fig)

        # Dọn dẹp
        if os.path.exists(local_root):
            shutil.rmtree(local_root)

        elapsed = time.time() - start_time
        print(f"✅ Hoàn tất boxplot ({type_str.lower()}) trong {elapsed:.1f}s")

        return {
            "success": True,
            "message": f"Đã phân tích {len(data[valid_features[0]])} {type_str.lower()} từ '{bucket}/{prefix}'",
            "image_url": f"/static/boxplots/{filename}",
            "type": "video" if is_video else "frame",
        }

    except Exception as e:
        print("❌ Lỗi nghiêm trọng trong generate_boxplot_for_prefix:", e)
        import traceback

        traceback.print_exc()
        if os.path.exists(local_root):
            shutil.rmtree(local_root)
        return {"success": False, "message": f"Lỗi xử lý: {str(e)}"}
