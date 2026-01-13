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
from services.database import get_db_connection

# Cấu hình
MAX_VIDEOS = 9999                 # max số video xử lý (tăng lên để lấy hết)
MAX_OBJECTS = 9999                # max số frame/object tải về trực tiếp
TEMP_DIR = "downloads/temp_scatter"
MAX_TOTAL_FRAMES = 9999           # giới hạn tổng frame tính feature (tăng để lấy gần hết)

FRAMES_BUCKET_NAMES = ["frames"]  # danh sách bucket chứa frame

def generate_scatter_for_prefix(
    bucket: str,
    prefix: str = "",
    local_root: str = TEMP_DIR,
) -> dict:
    start_time = time.time()
    print(f"🚀 Bắt đầu tạo scatter plots - Bucket: {bucket} | Prefix: '{prefix}'")

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

        if is_frame_bucket:
            # ── TRƯỜNG HỢP BUCKET CHỨA FRAME ────────────────────────────────
            print(f"Chế độ FRAME BUCKET: List trực tiếp object từ {bucket}/{prefix}")

            all_objects = list(minio_client.list_objects(bucket, prefix=prefix, recursive=True))
            if not all_objects:
                return {"success": False, "message": f"Không tìm thấy object trong bucket {bucket}/{prefix.rstrip('/')}"}

            # Lọc chỉ lấy file ảnh hợp lệ
            valid_frames = [
                obj for obj in all_objects
                if not obj.object_name.endswith("/")
                and obj.object_name.lower().endswith(('.png', '.jpg', '.jpeg'))
            ]

            if not valid_frames:
                return {"success": False, "message": "Không tìm thấy file ảnh hợp lệ trong bucket này"}

            # Không random sample nữa → lấy hết (giới hạn bởi MAX_TOTAL_FRAMES)
            valid_frames = valid_frames[:MAX_TOTAL_FRAMES]

            print(f"→ Tìm thấy {len(valid_frames)} frame hợp lệ trong bucket (giới hạn {MAX_TOTAL_FRAMES})")

            # Tải frame về temp
            for idx, obj in enumerate(valid_frames):
                safe_name = f"frame_{idx:06d}_{os.path.basename(obj.object_name)}"
                local_path = os.path.join(local_root, safe_name)
                try:
                    minio_client.fget_object(bucket, obj.object_name, local_path)
                    local_paths.append(local_path)
                except Exception as e:
                    print(f"Skip frame {obj.object_name}: {e}")

            type_str = "FRAME ẢNH (trực tiếp từ bucket)"
            frame_source = "bucket_direct"

        else:
            # ── TRƯỜNG HỢP BUCKET VIDEO ──────────────────────────────────────
            print(f"Chế độ VIDEO BUCKET: Query MongoDB để lấy frame_keys")

            query = {}
            if bucket:
                query["storage_refs.bucket"] = bucket
            if prefix:
                query["storage_refs.key"] = {"$regex": f"^{prefix}", "$options": "i"}

            print("Query chính:", query)

            cursor = db['downloaded_videos'].find(query).limit(MAX_VIDEOS)
            videos = list(cursor)

            # Fallback nếu cần
            if not videos and prefix:
                print("→ Không tìm thấy với key → fallback dùng file_path")
                query_fallback = {}
                if bucket:
                    query_fallback["storage_refs.bucket"] = bucket
                query_fallback["file_path"] = {"$regex": f"^{prefix}", "$options": "i"}
                cursor = db['downloaded_videos'].find(query_fallback).limit(MAX_VIDEOS)
                videos = list(cursor)

            if not videos:
                return {"success": False, "message": f"Không tìm thấy video nào trong MongoDB với bucket={bucket} và prefix={prefix}"}

            print(f"✓ Tìm thấy {len(videos)} video phù hợp")

            # Lấy HẾT tất cả frame_keys (không sample)
            selected_frame_keys = []
            total_frames_available = 0

            for doc in videos:
                try:
                    storage = doc.get("storage_refs", {})
                    frames_bucket = storage.get("frames_bucket")
                    frame_keys = storage.get("frame_keys", [])

                    if not frame_keys or not frames_bucket:
                        print(f"Skip video {doc.get('video_id', 'unknown')}: thiếu frame_keys")
                        continue

                    # Lấy hết frame của video này
                    selected_frame_keys.extend([(frames_bucket, key) for key in frame_keys])
                    total_frames_available += len(frame_keys)

                    # Giới hạn tổng
                    if len(selected_frame_keys) >= MAX_TOTAL_FRAMES:
                        selected_frame_keys = selected_frame_keys[:MAX_TOTAL_FRAMES]
                        print(f"→ Đạt giới hạn {MAX_TOTAL_FRAMES} frame, dừng lấy thêm")
                        break

                except Exception as e:
                    print(f"Lỗi xử lý video {doc.get('video_id', 'unknown')}: {e}")

            if not selected_frame_keys:
                return {"success": False, "message": "Không tìm thấy frame nào trong metadata"}

            print(f"→ Đã chọn {len(selected_frame_keys)} frame (tổng có sẵn: ~{total_frames_available})")

            # Tải frame
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

        # ── Tính feature ─────────────────────────────────────────────────────
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

        # ── Vẽ scatter ───────────────────────────────────────────────────────
        scatter_pairs = [
            ("mean_brightness", "laplacian_variance", "Độ sáng trung bình", "Độ nét (Laplacian variance)"),
            ("laplacian_variance", "edge_density", "Độ nét (Laplacian variance)", "Mật độ cạnh (Canny)"),
            ("frame_index", "frame_diff_energy", "Thứ tự frame", "Năng lượng thay đổi frame"),
            ("mean_brightness", "brightness_flicker", "Độ sáng", "Độ nhấp nháy độ sáng"),
        ]

        images_base64 = []
        feature_labels = []

        for x_key, y_key, x_label, y_label in scatter_pairs:
            fig, ax = plt.subplots(figsize=(9, 7), dpi=130)
            ax.scatter(data[x_key], data[y_key], alpha=0.7, s=55, c='teal', edgecolor='white', linewidth=0.5)

            ax.set_xlabel(x_label, fontsize=13)
            ax.set_ylabel(y_label, fontsize=13)
            ax.set_title(f'{x_label} vs {y_label}  ({type_str})', fontsize=15, pad=15)
            ax.grid(True, linestyle='--', alpha=0.35)
            ax.tick_params(labelsize=11)

            if x_key == "frame_index":
                ax.set_xlim(left=-1)

            buf = BytesIO()
            plt.savefig(buf, format='png', bbox_inches='tight', dpi=130)
            buf.seek(0)
            b64 = base64.b64encode(buf.read()).decode('utf-8')
            images_base64.append(f"data:image/png;base64,{b64}")

            feature_labels.append(f"{x_label} vs {y_label}")
            plt.close(fig)

        elapsed = time.time() - start_time
        return {
            "success": True,
            "message": f"Đã tạo {len(scatter_pairs)} scatter plots từ {len(local_paths)} frame ({frame_source}) ({elapsed:.1f}s)",
            "type": "frame",
            "images_base64": images_base64,
            "feature_labels": feature_labels,
        }

    except Exception as e:
        print("LỖI CHI TIẾT KHI TẠO SCATTER:")
        traceback.print_exc()
        return {"success": False, "message": f"Lỗi xử lý: {str(e)}"}

    finally:
        if os.path.exists(local_root):
            try:
                shutil.rmtree(local_root, ignore_errors=True)
            except:
                pass