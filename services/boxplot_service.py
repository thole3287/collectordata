import cv2
import numpy as np
import os
import shutil
import time
import random
import traceback

from services.minio_service import (
    get_minio_client,
    list_objects_recursive,
    download_object
)
from services.database import get_db_connection

# Cấu hình
MAX_SAMPLES = 9999
TEMP_DIR = "downloads/temp_boxplot"

FRAMES_BUCKET_NAMES = ["frames", "dataset"]  # Thêm "dataset" nếu bạn dùng bucket này

def generate_boxplot_for_prefix(
    bucket: str,
    prefix: str = "",
    local_root: str = TEMP_DIR,
) -> dict:
    """
    Tạo dữ liệu boxplot từ bucket/prefix, dùng chung logic MinIO từ minio_service.
    Trả dữ liệu thô cho Chart.js (không vẽ base64 nữa).
    """
    start_time = time.time()
    print(f"🚀 Boxplot - Bucket: {bucket} | Prefix: '{prefix}'")

    try:
        os.makedirs(local_root, exist_ok=True)
        client = get_minio_client()

        # Chuẩn hóa prefix
        if prefix:
            prefix = prefix.strip().rstrip('/') + '/'

        local_paths = []
        type_str = ""
        source_info = ""

        # ── List objects dùng hàm chung ────────────────────────────────────────
        print(f"Listing recursive với prefix: '{prefix}'")
        all_objects = list_objects_recursive(client, bucket, prefix)

        if not all_objects:
            return {"success": False, "message": f"Không tìm thấy object nào trong {bucket}/{prefix.rstrip('/')}"}

        is_frame_bucket = bucket in FRAMES_BUCKET_NAMES or 'frame' in bucket.lower()

        valid_items = []
        for obj in all_objects:
            key = obj.object_name
            if key.endswith("/"): continue

            lower_key = key.lower()
            if is_frame_bucket:
                if lower_key.endswith(('.png', '.jpg', '.jpeg')):
                    valid_items.append((bucket, key))
            else:
                # Video hoặc media
                if any(lower_key.endswith(ext) for ext in ('.mp4', '.avi', '.mov', '.mkv', '.webm')):
                    valid_items.append((bucket, key))

        print(f"→ Tìm thấy {len(valid_items)} file hợp lệ")

        # Giới hạn số lượng
        valid_items = valid_items[:MAX_SAMPLES]

        # Tải về local dùng hàm chung
        for idx, (bkt, key) in enumerate(valid_items):
            filename = os.path.basename(key)
            safe_name = f"item_{idx:06d}_{filename}"
            local_path = os.path.join(local_root, safe_name)
            if download_object(client, bkt, key, local_path):
                local_paths.append(local_path)
            else:
                print(f"Skip tải {key}")

        if not local_paths:
            return {"success": False, "message": "Không tải được file hợp lệ nào"}

        type_str = "FRAME" if is_frame_bucket else "VIDEO/MEDIA"
        source_info = f"prefix:{prefix}" if prefix else "root"

        print(f"✓ Đã tải {len(local_paths)} {type_str} (nguồn: {source_info})")

        # ── Tính đặc trưng ───────────────────────────────────────────────────── 
        data = {}
        features = []
        feature_names_vn = {}

        if type_str.startswith("VIDEO"):
            features = ["duration", "bitrate", "frame_rate", "width", "height", "file_size_mb"]
            feature_names_vn = {
                "duration": "Thời lượng (giây)",
                "bitrate": "Bitrate ước tính (kbps)",
                "frame_rate": "FPS",
                "width": "Chiều rộng (px)",
                "height": "Chiều cao (px)",
                "file_size_mb": "Kích thước file (MB)",
            }
            data = {f: [] for f in features}

            for path in local_paths:
                try:
                    cap = cv2.VideoCapture(path)
                    if not cap.isOpened(): continue
                    fps = cap.get(cv2.CAP_PROP_FPS) or 0
                    frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0
                    duration = frame_count / fps if fps > 0 else 0
                    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
                    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
                    size_mb = os.path.getsize(path) / (1024 * 1024)
                    bitrate = (size_mb * 8192) / duration if duration > 0 else 0

                    data["duration"].append(duration)
                    data["bitrate"].append(bitrate)
                    data["frame_rate"].append(fps)
                    data["width"].append(width)
                    data["height"].append(height)
                    data["file_size_mb"].append(size_mb)
                    cap.release()
                except Exception as e:
                    print(f"Skip video analysis {path}: {e}")
        else:
            features = ["brightness", "contrast", "blur", "noise_level", "edge_density"]
            feature_names_vn = {
                "brightness": "Độ sáng trung bình",
                "contrast": "Độ tương phản",
                "blur": "Độ mờ (Laplacian variance)",
                "noise_level": "Mức nhiễu",
                "edge_density": "Mật độ cạnh",
            }
            data = {f: [] for f in features}

            for path in local_paths:
                try:
                    img = cv2.imread(path)
                    if img is None: continue
                    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

                    data["brightness"].append(float(np.mean(gray)))
                    data["contrast"].append(float(np.std(gray)))
                    data["blur"].append(float(cv2.Laplacian(gray, cv2.CV_64F).var()))
                    blurred = cv2.GaussianBlur(gray, (5,5), 0)
                    data["noise_level"].append(float(np.std(gray - blurred)))
                    edges = cv2.Canny(gray, 100, 200)
                    data["edge_density"].append(float(np.sum(edges > 0) / edges.size if edges.size > 0 else 0))
                except Exception as e:
                    print(f"Skip frame analysis {path}: {e}")

        # ── Chuẩn bị dữ liệu cho Chart.js ─────────────────────────────────────
        boxplot_data = []
        valid_features = [f for f in features if len(data.get(f, [])) >= 3]

        for feat in valid_features:
            values = [v for v in data[feat] if not np.isnan(v) and not np.isinf(v)]
            if len(values) < 3:
                continue

            q1, q3 = np.percentile(values, [25, 75])
            iqr = q3 - q1
            outliers = [v for v in values if v < (q1 - 1.5 * iqr) or v > (q3 + 1.5 * iqr)]

            stats = {
                "min": float(np.min(values)),
                "q1": float(q1),
                "median": float(np.median(values)),
                "q3": float(q3),
                "max": float(np.max(values)),
                "mean": float(np.mean(values)),
                "count": len(values),
                "outliers": outliers
            }

            boxplot_data.append({
                "feature": feat,
                "label": feature_names_vn.get(feat, feat),
                "values": values,
                "stats": stats
            })

        elapsed = time.time() - start_time

        if not boxplot_data:
            return {"success": False, "message": "Không có đặc trưng nào đủ dữ liệu để vẽ boxplot"}

        return {
            "success": True,
            "message": f"Đã xử lý {len(local_paths)} {type_str} – {len(boxplot_data)} boxplot ({elapsed:.1f}s)",
            "type": "frame" if type_str.startswith("FRAME") else "video",
            "boxplot_data": boxplot_data
        }

    except Exception as e:
        traceback.print_exc()
        return {"success": False, "message": f"Lỗi xử lý: {str(e)}"}

    finally:
        if os.path.exists(local_root):
            shutil.rmtree(local_root, ignore_errors=True)