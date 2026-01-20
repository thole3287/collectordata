import cv2
import numpy as np
import os
import shutil
import time
import traceback

from services.minio_service import get_minio_client
from services.database import get_db_connection

# Cấu hình
MAX_VIDEOS = 9999                 # max số video xử lý
MAX_TOTAL_FRAMES = 9999           # giới hạn tổng frame tính feature

FRAMES_BUCKET_NAMES = ["frames"]  # danh sách bucket chứa frame trực tiếp

def generate_scatter_for_prefix(
    bucket: str,
    prefix: str = "",
    local_root: str = "downloads/temp_scatter",
) -> dict:
    """
    Xử lý frame từ MinIO và trả về dữ liệu đặc trưng thô để vẽ scatter bằng Chart.js
    
    Returns:
        dict chứa dữ liệu scatter_data (các cặp x,y + labels) thay vì ảnh base64
    """
    start_time = time.time()
    print(f"🚀 Bắt đầu xử lý scatter data - Bucket: {bucket} | Prefix: '{prefix}'")

    try:
        os.makedirs(local_root, exist_ok=True)
        minio_client = get_minio_client()
        db = get_db_connection()

        # Chuẩn hóa prefix
        if prefix:
            prefix = prefix.strip().rstrip('/') + '/'

        is_frame_bucket = bucket in FRAMES_BUCKET_NAMES or 'frame' in bucket.lower()

        local_paths = []
        type_str = ""
        frame_source = ""

        # ── 1. Xử lý bucket chứa frame trực tiếp ────────────────────────────────
        if is_frame_bucket:
            print(f"Chế độ FRAME BUCKET: List trực tiếp từ {bucket}/{prefix}")

            all_objects = list(minio_client.list_objects(bucket, prefix=prefix, recursive=True))
            if not all_objects:
                return {"success": False, "message": f"Không tìm thấy object trong bucket {bucket}/{prefix.rstrip('/')}"}

            valid_frames = [
                obj for obj in all_objects
                if not obj.object_name.endswith("/")
                and obj.object_name.lower().endswith(('.png', '.jpg', '.jpeg'))
            ]

            if not valid_frames:
                return {"success": False, "message": "Không tìm thấy file ảnh hợp lệ"}

            valid_frames = valid_frames[:MAX_TOTAL_FRAMES]
            print(f"→ Tìm thấy {len(valid_frames)} frame hợp lệ (giới hạn {MAX_TOTAL_FRAMES})")

            for idx, obj in enumerate(valid_frames):
                safe_name = f"frame_{idx:06d}_{os.path.basename(obj.object_name)}"
                local_path = os.path.join(local_root, safe_name)
                try:
                    minio_client.fget_object(bucket, obj.object_name, local_path)
                    local_paths.append(local_path)
                except Exception as e:
                    print(f"Skip frame {obj.object_name}: {e}")

            type_str = ""
            frame_source = "bucket_direct"

        # ── 2. Xử lý bucket video qua metadata MongoDB ──────────────────────────
        else:
            print(f"Chế độ VIDEO BUCKET: Query MongoDB với prefix '{prefix}'")

            query = {}
            if bucket:
                query["storage_refs.bucket"] = bucket
            if prefix:
                query["storage_refs.key"] = {"$regex": f"^{prefix}", "$options": "i"}

            cursor = db['downloaded_videos'].find(query).limit(MAX_VIDEOS)
            videos = list(cursor)

            # Fallback nếu cần
            if not videos and prefix:
                print("→ Fallback dùng file_path")
                query_fallback = {"file_path": {"$regex": f"^{prefix}", "$options": "i"}}
                if bucket:
                    query_fallback["storage_refs.bucket"] = bucket
                cursor = db['downloaded_videos'].find(query_fallback).limit(MAX_VIDEOS)
                videos = list(cursor)

            if not videos:
                return {"success": False, "message": "Không tìm thấy video nào phù hợp"}

            print(f"✓ Tìm thấy {len(videos)} video")

            selected_frame_keys = []
            total_frames_available = 0

            for doc in videos:
                storage = doc.get("storage_refs", {})
                frames_bucket = storage.get("frames_bucket")
                frame_keys = storage.get("frame_keys", [])

                if not frame_keys or not frames_bucket:
                    continue

                selected_frame_keys.extend([(frames_bucket, key) for key in frame_keys])
                total_frames_available += len(frame_keys)

                if len(selected_frame_keys) >= MAX_TOTAL_FRAMES:
                    selected_frame_keys = selected_frame_keys[:MAX_TOTAL_FRAMES]
                    break

            if not selected_frame_keys:
                return {"success": False, "message": "Không tìm thấy frame nào trong metadata"}

            print(f"→ Đã chọn {len(selected_frame_keys)} frame (tổng có sẵn ~{total_frames_available})")

            for idx, (f_bucket, key) in enumerate(selected_frame_keys):
                safe_name = f"frame_{idx:06d}_{os.path.basename(key)}"
                local_path = os.path.join(local_root, safe_name)
                try:
                    minio_client.fget_object(f_bucket, key, local_path)
                    local_paths.append(local_path)
                except Exception as e:
                    print(f"Skip frame {key}: {e}")

            type_str = "FRAME ẢNH (từ metadata video)"
            frame_source = "metadata"

        if not local_paths:
            return {"success": False, "message": "Không tải được frame nào"}

        print(f"✓ Đã tải thành công {len(local_paths)} frame ({type_str})")

        # ── Tính đặc trưng ──────────────────────────────────────────────────────
        data = {
            "frame_index": [],
            "mean_brightness": [],
            "laplacian_variance": [],
            "edge_density": [],
            "frame_diff_energy": [],
            "brightness_flicker": [],
        }

        prev_gray = None
        prev_brightness = None

        for i, path in enumerate(local_paths):
            img = cv2.imread(path)
            if img is None:
                continue

            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            brightness = float(np.mean(gray))
            lap_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
            edges = cv2.Canny(gray, 100, 200)
            edge_dens = float(np.sum(edges > 0) / edges.size) if edges.size > 0 else 0.0

            diff_energy = 0.0
            flicker = 0.0

            if prev_gray is not None:
                diff = cv2.absdiff(gray, prev_gray)
                diff_energy = float(np.mean(diff)) * 8.0
                flicker = abs(brightness - prev_brightness)

            data["frame_index"].append(i)
            data["mean_brightness"].append(brightness)
            data["laplacian_variance"].append(lap_var)
            data["edge_density"].append(edge_dens)
            data["frame_diff_energy"].append(diff_energy)
            data["brightness_flicker"].append(flicker)

            prev_gray = gray.copy()
            prev_brightness = brightness

        if len(data["frame_index"]) < 5:
            return {"success": False, "message": f"Chỉ xử lý được {len(data['frame_index'])} frame hợp lệ"}

        # ── Chuẩn bị dữ liệu cho Chart.js (không vẽ nữa) ───────────────────────
        scatter_pairs = [
            ("mean_brightness",     "laplacian_variance",  "Độ sáng trung bình",          "Độ nét"),
            ("laplacian_variance",  "edge_density",        "Độ nét", "Mật độ cạnh"),
            ("mean_brightness",     "brightness_flicker",  "Độ sáng",                     "Độ nhấp nháy độ sáng"),
            ("frame_diff_energy",   "edge_density",        "Năng lượng thay đổi frame",   "Mật độ cạnh"),
        ]

        scatter_data = []

        for x_key, y_key, x_label, y_label in scatter_pairs:
            scatter_data.append({
                "x_key": x_key,
                "y_key": y_key,
                "x_label": x_label,
                "y_label": y_label,
                "title": f"{x_label} vs {y_label}  ({type_str})",
                "data": {
                    "x": data[x_key],
                    "y": data[y_key]
                }
            })

        elapsed = time.time() - start_time

        return {
            "success": True,
            "message": f"Đã xử lý {len(local_paths)} frame trong {elapsed:.1f}s ({frame_source})",
            "type": "frame",
            "scatter_data": scatter_data,
            "frame_count": len(local_paths),
            "frame_source": frame_source
        }

    except Exception as e:
        print("LỖI CHI TIẾT KHI XỬ LÝ SCATTER:")
        traceback.print_exc()
        return {"success": False, "message": f"Lỗi xử lý: {str(e)}"}

    finally:
        if os.path.exists(local_root):
            try:
                shutil.rmtree(local_root, ignore_errors=True)
            except:
                pass