import cv2
import numpy as np
import os
import shutil
import time
import random
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from io import BytesIO
import base64
import traceback

from services.minio_service import get_minio_client
from services.database import get_db_connection  # ← Thêm import này

# Cấu hình
MAX_SAMPLES = 9999                # max số file tải về (tăng để lấy gần hết)
TEMP_DIR = "downloads/temp_boxplot"

FEATURE_COLORS = [
    '#1f77b4',  # blue
    '#ff7f0e',  # orange
    '#2ca02c',  # green
    '#d62728',  # red
    '#9467bd',  # purple
    '#8c564b',  # brown
]

FRAMES_BUCKET_NAMES = ["frames"]  # bucket chứa frame

def generate_boxplot_for_prefix(
    bucket: str,
    prefix: str = "",
    local_root: str = TEMP_DIR,
) -> dict:
    start_time = time.time()
    print(f"🚀 Bắt đầu tạo boxplot - Bucket: {bucket} | Prefix: '{prefix}'")

    try:
        os.makedirs(local_root, exist_ok=True)
        client = get_minio_client()
        db = get_db_connection()

        if prefix:
            prefix = prefix.strip().rstrip('/') + '/'

        is_frame_bucket = bucket in FRAMES_BUCKET_NAMES or 'frame' in bucket.lower()

        local_paths = []
        type_str = ""
        source_info = ""

        if is_frame_bucket:
            # ── TRƯỜNG HỢP BUCKET FRAME ─────────────────────────────────────
            print(f"Chế độ FRAME BUCKET: xử lý bucket frames")

            if not prefix:
                # Prefix rỗng → fallback dùng MongoDB để lấy đúng frame theo video
                print("→ Prefix rỗng → fallback dùng MongoDB lấy frame_keys")
                query = {"storage_refs.frames_bucket": bucket}
                cursor = db['downloaded_videos'].find(query).limit(MAX_SAMPLES)
                videos = list(cursor)

                if not videos:
                    return {"success": False, "message": f"Không tìm thấy video nào trong MongoDB cho bucket frames '{bucket}'"}

                selected_keys = []
                for doc in videos:
                    storage = doc.get("storage_refs", {})
                    frame_keys = storage.get("frame_keys", [])
                    if frame_keys:
                        selected_keys.extend(frame_keys)

                if not selected_keys:
                    return {"success": False, "message": "Không tìm thấy frame nào trong metadata"}

                print(f"→ Lấy {len(selected_keys)} frame từ metadata video")

                # Tải frame
                for idx, key in enumerate(selected_keys):
                    safe_name = f"frame_{idx:06d}_{os.path.basename(key)}"
                    local_path = os.path.join(local_root, safe_name)
                    try:
                        client.fget_object(bucket, key, local_path)
                        local_paths.append(local_path)
                    except Exception as e:
                        print(f"Skip {key}: {e}")

                type_str = "FRAME ẢNH (từ metadata)"
                source_info = "metadata_fallback"

            else:
                # Prefix có → list trực tiếp
                print(f"List trực tiếp object từ {bucket}/{prefix}")
                all_objects = list(client.list_objects(bucket, prefix=prefix, recursive=True))
                if not all_objects:
                    return {"success": False, "message": f"Không tìm thấy object trong {bucket}/{prefix.rstrip('/')}"}

                valid_frames = [
                    obj for obj in all_objects
                    if not obj.object_name.endswith("/") 
                    and obj.object_name.lower().endswith(('.png', '.jpg', '.jpeg'))
                ]

                if not valid_frames:
                    return {"success": False, "message": "Không tìm thấy file ảnh hợp lệ"}

                # Lấy hết (giới hạn MAX_SAMPLES nếu cần)
                valid_frames = valid_frames[:MAX_SAMPLES]

                print(f"→ Tìm thấy {len(valid_frames)} frame trong prefix")

                for idx, obj in enumerate(valid_frames):
                    safe_name = f"frame_{idx:06d}_{os.path.basename(obj.object_name)}"
                    local_path = os.path.join(local_root, safe_name)
                    try:
                        client.fget_object(bucket, obj.object_name, local_path)
                        local_paths.append(local_path)
                    except Exception as e:
                        print(f"Skip {obj.object_name}: {e}")

                type_str = "FRAME ẢNH (từ bucket trực tiếp)"
                source_info = "bucket_direct"

        else:
            # ── TRƯỜNG HỢP BUCKET VIDEO ─────────────────────────────────────
            # Giữ nguyên code cũ của bạn cho bucket video (tải video và tính metadata)
            print(f"Chế độ VIDEO BUCKET: xử lý như video gốc")

            all_objects = list(client.list_objects(bucket, prefix=prefix, recursive=True))
            if not all_objects:
                return {"success": False, "message": f"Không tìm thấy object trong {bucket}/{prefix.rstrip('/')}"}

            valid_objects = [obj for obj in all_objects if not obj.object_name.endswith("/") and "." in obj.object_name]
            if not valid_objects:
                return {"success": False, "message": "Không tìm thấy file media hợp lệ"}

            if len(valid_objects) > MAX_SAMPLES:
                valid_objects = random.sample(valid_objects, MAX_SAMPLES)

            is_video = any(obj.object_name.lower().endswith(('.mp4','.avi','.mov','.mkv','.webm','.mpg'))
                           for obj in valid_objects)

            type_str = "VIDEO" if is_video else "FRAME ẢNH"

            for obj in valid_objects:
                filename = os.path.basename(obj.object_name)
                safe_name = f"{bucket}_{prefix.replace('/', '_')}_{filename}"
                local_path = os.path.join(local_root, safe_name)
                try:
                    client.fget_object(bucket, obj.object_name, local_path)
                    local_paths.append(local_path)
                except Exception as e:
                    print(f"Skip {obj.object_name}: {e}")

            source_info = "direct_list"

        if not local_paths:
            return {"success": False, "message": "Không tải được file nào"}

        print(f"✓ Đã tải {len(local_paths)} file ({type_str}) - nguồn: {source_info}")

        # ── Trích xuất đặc trưng (giữ nguyên code cũ của bạn) ────────────────
        if "VIDEO" in type_str.upper():
            features = ["duration", "bitrate", "frame_rate", "width", "height", "file_size_mb"]
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
                except:
                    pass
        else:
            # Frame-based features
            features = ["brightness", "contrast", "blur", "noise_level", "edge_density"]
            feature_names_vn = {
                "brightness": "Độ sáng",
                "contrast": "Độ tương phản",
                "blur": "Độ nét (Laplacian var)",
                "noise_level": "Độ nhiễu",
                "edge_density": "Mật độ cạnh",
            }
            data = {f: [] for f in features}

            for path in local_paths:
                try:
                    img = cv2.imread(path)
                    if img is None: continue
                    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

                    data["brightness"].append(np.mean(gray))
                    data["contrast"].append(np.std(gray))
                    data["blur"].append(cv2.Laplacian(gray, cv2.CV_64F).var())
                    blurred = cv2.GaussianBlur(gray, (5,5), 0)
                    data["noise_level"].append(np.std(gray - blurred))
                    edges = cv2.Canny(gray, 100, 200)
                    data["edge_density"].append(np.sum(edges > 0) / edges.size)
                except:
                    pass

        valid_features = [f for f in features if len(data[f]) >= 3]
        if not valid_features:
            return {"success": False, "message": "Không đủ dữ liệu (cần ít nhất 3 mẫu mỗi đặc trưng)"}

        # ── Vẽ từng boxplot riêng lẻ ────────────────────────────────────────
        images_base64 = []
        feature_labels = []

        for i, feat in enumerate(valid_features):
            values = [v for v in data[feat] if not np.isnan(v) and not np.isinf(v)]
            if len(values) < 3:
                continue

            fig, ax = plt.subplots(figsize=(7.5, 5.2), dpi=110)

            bp = ax.boxplot(
                values,
                patch_artist=True,
                notch=False,
                whis=1.5,
                showfliers=True,
                flierprops=dict(marker='o', markerfacecolor='red', markersize=5, alpha=0.7)
            )

            color = FEATURE_COLORS[i % len(FEATURE_COLORS)]
            for patch in bp['boxes']:
                patch.set_facecolor(color)
                patch.set_alpha(0.58)

            for median in bp['medians']:
                median.set(color='black', linewidth=2.2)

            ax.set_title(f"{feature_names_vn.get(feat, feat)}", fontsize=15, pad=12)
            ax.set_ylabel("Giá trị", fontsize=12)
            ax.grid(axis='y', linestyle='--', alpha=0.35, zorder=0)
            ax.tick_params(axis='both', labelsize=10.5)

            stats_text = (
                f"n = {len(values)}\n"
                f"Median: {np.median(values):.2f}\n"
                f"Mean: {np.mean(values):.2f}"
            )
            ax.text(0.02, 0.98, stats_text, transform=ax.transAxes,
                    fontsize=10, verticalalignment='top',
                    bbox=dict(facecolor='white', alpha=0.7, edgecolor='none'))

            buf = BytesIO()
            plt.savefig(buf, format='png', bbox_inches='tight', dpi=130)
            buf.seek(0)
            b64 = base64.b64encode(buf.read()).decode('utf-8')
            images_base64.append(f"data:image/png;base64,{b64}")

            feature_labels.append(feature_names_vn.get(feat, feat))

            plt.close(fig)

        if not images_base64:
            return {"success": False, "message": "Không tạo được boxplot nào"}

        elapsed = time.time() - start_time
        return {
            "success": True,
            "message": f"Đã phân tích {len(local_paths)} {type_str.lower()} – {len(images_base64)} boxplot riêng lẻ (nguồn: {source_info}) ({elapsed:.1f}s)",
            "type": "video" if "VIDEO" in type_str.upper() else "frame",
            "images_base64": images_base64,
            "feature_labels": feature_labels,
        }

    except Exception as e:
        traceback.print_exc()
        return {"success": False, "message": f"Lỗi xử lý: {str(e)}"}

    finally:
        if os.path.exists(local_root):
            shutil.rmtree(local_root, ignore_errors=True)