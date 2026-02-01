import cv2
import numpy as np
import os
import shutil
import time
import traceback
from datetime import datetime

from services.minio_service import get_minio_client
from services.database import get_db_connection
from services.image_enhancement import resize_image

# Cấu hình
MAX_VIDEOS = 9999
MAX_TOTAL_FRAMES = 2000

FRAMES_BUCKET_NAMES = ["dataset", "frames", "camera_frames"]


def generate_scatter_for_prefix(
    bucket: str,
    prefix: str = "",
    local_root: str = "downloads/temp_scatter",
) -> dict:
    start_time = time.time()
    print(f"🚀 Bắt đầu xử lý scatter - Bucket: {bucket} | Prefix: '{prefix}'")

    try:
        os.makedirs(local_root, exist_ok=True)
        minio_client = get_minio_client()
        db = get_db_connection()

        if prefix:
            prefix = prefix.strip().rstrip("/") + "/"

        is_frame_bucket = bucket.lower() in [n.lower() for n in FRAMES_BUCKET_NAMES] or "frame" in bucket.lower()

        local_paths = []
        metadata_list = []
        type_str = ""
        frame_source = ""

        # 1. FRAME BUCKET (dataset, frames, ...)
        if is_frame_bucket:
            print(f"Chế độ FRAME BUCKET: List từ {bucket}/{prefix}")
            all_objects = list(minio_client.list_objects(bucket, prefix=prefix, recursive=True))

            if not all_objects:
                return {"success": False, "message": f"Không tìm thấy object trong {bucket}/{prefix.rstrip('/')}"}

            valid_frames = [
                obj for obj in all_objects
                if not obj.object_name.endswith("/") and obj.object_name.lower().endswith((".png", ".jpg", ".jpeg"))
            ]

            if not valid_frames:
                return {"success": False, "message": "Không tìm thấy file ảnh hợp lệ"}

            valid_frames = valid_frames[:MAX_TOTAL_FRAMES]
            print(f"→ Tìm thấy {len(valid_frames)} frame hợp lệ")

            for idx, obj in enumerate(valid_frames):
                full_key = obj.object_name

                try:
                    stat = minio_client.stat_object(bucket, full_key)
                    file_size = stat.size
                    created_at = stat.last_modified.isoformat() if stat.last_modified else datetime.utcnow().isoformat()
                except Exception as e:
                    print(f"Không stat được {full_key}: {e}")
                    file_size = 0
                    created_at = datetime.utcnow().isoformat()

                platform = "pexels" if "pexels" in full_key.lower() else "youtube" if "youtube" in full_key.lower() else "camera"
                scene_type = "day"

                metadata_list.append({
                    "object_name": full_key,
                    "bucket": bucket,  # bucket frame thật
                    "platform": platform,
                    "scene_type": scene_type,
                    "file_size": file_size,
                    "created_at": created_at,
                    "video_id": full_key.split("_")[0].split("/")[-1] if "_" in full_key else "unknown",
                })

                safe_name = f"frame_{idx:06d}_{os.path.basename(full_key)}"
                local_path = os.path.join(local_root, safe_name)
                try:
                    minio_client.fget_object(bucket, full_key, local_path)
                    local_paths.append(local_path)
                except Exception as e:
                    print(f"Skip {full_key}: {e}")
                    metadata_list.pop()

            type_str = ""
            frame_source = "bucket_direct"

        # 2. VIDEO BUCKET (từ metadata MongoDB)
        else:
            print(f"Chế độ VIDEO BUCKET: Query MongoDB với prefix '{prefix}'")
            query = {"storage_refs.bucket": bucket}
            if prefix:
                query["storage_refs.key"] = {"$regex": f"^{prefix}", "$options": "i"}

            cursor = db["downloaded_videos"].find(query).limit(MAX_VIDEOS)
            videos = list(cursor)

            if not videos and prefix:
                query_fallback = {"file_path": {"$regex": f"^{prefix}", "$options": "i"}}
                if bucket:
                    query_fallback["storage_refs.bucket"] = bucket
                cursor = db["downloaded_videos"].find(query_fallback).limit(MAX_VIDEOS)
                videos = list(cursor)

            if not videos:
                return {"success": False, "message": "Không tìm thấy video nào phù hợp"}

            selected_frame_keys = []
            for doc in videos:
                storage = doc.get("storage_refs", {})
                frames_bucket = storage.get("frames_bucket")
                frame_keys = storage.get("frame_keys", [])
                if frame_keys and frames_bucket:
                    selected_frame_keys.extend([(frames_bucket, key) for key in frame_keys])

            selected_frame_keys = selected_frame_keys[:MAX_TOTAL_FRAMES]

            for idx, (f_bucket, full_key) in enumerate(selected_frame_keys):
                try:
                    stat = minio_client.stat_object(f_bucket, full_key)
                    file_size = stat.size
                    created_at = stat.last_modified.isoformat() if stat.last_modified else datetime.utcnow().isoformat()
                except:
                    file_size = 0
                    created_at = datetime.utcnow().isoformat()

                platform = doc.get("platform", "youtube")
                scene_type = "day"

                metadata_list.append({
                    "object_name": full_key,
                    "bucket": f_bucket,  # bucket frame thật (dataset/frames)
                    "platform": platform,
                    "scene_type": scene_type,
                    "file_size": file_size,
                    "created_at": created_at,
                    "video_id": doc.get("video_id", full_key.split("_")[0].split("/")[-1] if "_" in full_key else "unknown"),
                })

                safe_name = f"frame_{idx:06d}_{os.path.basename(full_key)}"
                local_path = os.path.join(local_root, safe_name)
                try:
                    minio_client.fget_object(f_bucket, full_key, local_path)
                    local_paths.append(local_path)
                except Exception as e:
                    print(f"Skip {full_key} in {f_bucket}: {e}")
                    metadata_list.pop()

            type_str = "FRAME ẢNH (từ metadata video)"
            frame_source = "metadata"

        if not local_paths:
            return {"success": False, "message": "Không tải được frame nào"}

        print(f"✓ Đã tải thành công {len(local_paths)} frame ({type_str})")

        # Tính đặc trưng
        data = {
            "frame_index": [],
            "mean_brightness": [],
            "laplacian_variance": [],
            "edge_density": [],
            "frame_diff_energy": [],
            "brightness_flicker": [],
            "object_name": [],
            "platform": [],
            "scene_type": [],
            "file_size": [],
            "created_at": [],
            "video_id": [],
            "bucket": [],
        }

        prev_gray = None
        prev_brightness = None

        for i, path in enumerate(local_paths):
            img = cv2.imread(path)
            if img is None:
                continue

            # Fix OpenCV error: Ensure all images are uniform size (640x640)
            # This prevents "Sizes of input arguments do not match" in cv2.absdiff
            img = resize_image(img, target_size=(640, 640))

            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            brightness = float(np.mean(gray))
            lap_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
            edges = cv2.Canny(gray, 100, 200)
            edge_dens = float(np.sum(edges > 0) / edges.size) if edges.size > 0 else 0.0

            diff_energy = 0.0
            flicker = 0.0
            if prev_gray is not None:
                # diff will work because both are 640x640
                diff = cv2.absdiff(gray, prev_gray)
                diff_energy = float(np.mean(diff)) * 8.0
                flicker = abs(brightness - prev_brightness)

            data["frame_index"].append(i)
            data["mean_brightness"].append(brightness)
            data["laplacian_variance"].append(lap_var)
            data["edge_density"].append(edge_dens)
            data["frame_diff_energy"].append(diff_energy)
            data["brightness_flicker"].append(flicker)

            meta = metadata_list[i] if i < len(metadata_list) else {}
            data["object_name"].append(meta.get("object_name", f"frame_{i:06d}.png"))
            data["platform"].append(meta.get("platform", "unknown"))
            data["scene_type"].append(meta.get("scene_type", "day"))
            data["file_size"].append(meta.get("file_size", 0))
            data["created_at"].append(meta.get("created_at", datetime.utcnow().isoformat()))
            data["video_id"].append(meta.get("video_id", "unknown"))
            data["bucket"].append(meta.get("bucket", bucket))  # bucket frame thật

            prev_gray = gray.copy()
            prev_brightness = brightness

        if len(data["frame_index"]) < 5:
            return {"success": False, "message": f"Chỉ xử lý được {len(data['frame_index'])} frame hợp lệ"}

        # Chuẩn bị scatter_data
        scatter_pairs = [
            ("mean_brightness", "laplacian_variance", "Độ sáng trung bình", "Độ nét"),
            ("laplacian_variance", "edge_density", "Độ nét", "Mật độ cạnh"),
            ("mean_brightness", "brightness_flicker", "Độ sáng", "Độ nhấp nháy độ sáng"),
            ("frame_diff_energy", "edge_density", "Năng lượng thay đổi frame", "Mật độ cạnh"),
        ]

        scatter_data = []
        for x_key, y_key, x_label, y_label in scatter_pairs:
            scatter_data.append({
                "x_key": x_key,
                "y_key": y_key,
                "x_label": x_label,
                "y_label": y_label,
                "title": f"{x_label} vs {y_label} ({type_str})",
                "data": {
                    "x": data[x_key],
                    "y": data[y_key],
                    "frame_index": data["frame_index"],
                    "object_name": data["object_name"],
                    "mean_brightness": data["mean_brightness"],
                    "laplacian_variance": data["laplacian_variance"],
                    "platform": data["platform"],
                    "scene_type": data["scene_type"],
                    "file_size": data["file_size"],
                    "created_at": data["created_at"],
                    "video_id": data["video_id"],
                    "bucket": data["bucket"],  # trả bucket frame thật cho từng frame
                },
            })

        elapsed = time.time() - start_time

        return {
            "success": True,
            "message": f"Đã xử lý {len(local_paths)} frame trong {elapsed:.1f}s ({frame_source})",
            "type": "frame",
            "scatter_data": scatter_data,
            "frame_count": len(local_paths),
            "frame_source": frame_source,
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