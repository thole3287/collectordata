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

MAX_SAMPLES = 400          # max số file tải về (frame hoặc video)
TEMP_DIR = "downloads/temp_scatter"
MAX_FRAMES_PER_VIDEO = 300  # giới hạn số frame trích xuất từ mỗi video để tránh quá tải

def generate_scatter_for_prefix(
    bucket: str,
    prefix: str = "",
    local_root: str = TEMP_DIR,
) -> dict:
    start_time = time.time()
    print(f"🚀 Bắt đầu tạo scatter plots - Bucket: {bucket} | Prefix: {prefix}")

    try:
        os.makedirs(local_root, exist_ok=True)
        client = get_minio_client()

        if prefix and not prefix.endswith("/"):
            prefix += "/"

        all_objects = list(client.list_objects(bucket, prefix=prefix, recursive=True))
        if not all_objects:
            return {"success": False, "message": f"Không tìm thấy object trong {bucket}/{prefix.rstrip('/')}"}

        valid_objects = [obj for obj in all_objects if not obj.object_name.endswith("/") and "." in obj.object_name]
        if not valid_objects:
            return {"success": False, "message": "Không tìm thấy file media hợp lệ"}

        # Lấy mẫu ngẫu nhiên nếu quá nhiều
        if len(valid_objects) > MAX_SAMPLES:
            valid_objects = random.sample(valid_objects, MAX_SAMPLES)

        # Xác định loại dữ liệu chính (ưu tiên video nếu có ít nhất 1 video)
        has_video = any(obj.object_name.lower().endswith(('.mp4','.avi','.mov','.mkv','.webm','.mpg'))
                        for obj in valid_objects)
        is_video_mode = has_video

        type_str = "VIDEO" if is_video_mode else "FRAME ẢNH"
        print(f"Chế độ xử lý: {type_str}")

        local_paths = []
        for obj in valid_objects:
            filename = os.path.basename(obj.object_name)
            safe_name = f"{bucket}_{prefix.replace('/', '_')}_{filename}"
            local_path = os.path.join(local_root, safe_name)
            try:
                client.fget_object(bucket, obj.object_name, local_path)
                local_paths.append(local_path)
            except Exception as e:
                print(f"Skip {obj.object_name}: {e}")

        if not local_paths:
            return {"success": False, "message": "Không tải được file nào"}

        print(f"Đã tải {len(local_paths)} file {type_str.lower()}")

        # ───────────────────────────────────────────────────────────────
        # Chuẩn bị dữ liệu scatter
        # ───────────────────────────────────────────────────────────────
        data = {
            "frame_index": [],
            "mean_brightness": [],
            "laplacian_variance": [],
            "edge_density": [],
            "frame_diff_energy": [],
            "global_motion_magnitude": [],
            "brightness_flicker": [],
            "edge_density_bg": [],  # edge density ở vùng nền (sau khi loại bỏ đối tượng chuyển động)
        }

        prev_gray = None
        prev_brightness = None
        prev_flow = None
        frame_counter = 0

        if not is_video_mode:
            # ─── XỬ LÝ FRAME ẢNH ────────────────────────────────────────
            sorted_paths = sorted(
                local_paths,
                key=lambda p: int(''.join(filter(str.isdigit, os.path.basename(p)))) or 999999
            )

            for path in sorted_paths:
                img = cv2.imread(path)
                if img is None:
                    continue

                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                brightness = float(np.mean(gray))
                lap_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
                edges = cv2.Canny(gray, 100, 200)
                edge_dens = float(np.sum(edges > 0) / edges.size) if edges.size > 0 else 0.0

                diff_energy = 0.0
                motion_mag = 0.0
                flicker = 0.0
                edge_dens_bg = edge_dens

                if prev_gray is not None:
                    diff = cv2.absdiff(gray, prev_gray)
                    diff_energy = float(np.mean(diff)) * 8.0

                    # Optical flow đơn giản
                    flow = cv2.calcOpticalFlowFarneback(prev_flow, gray, None, 0.5, 3, 15, 3, 5, 1.2, 0)
                    mag, _ = cv2.cartToPolar(flow[..., 0], flow[..., 1])
                    motion_mag = float(np.mean(mag))

                    flicker = abs(brightness - prev_brightness)

                data["frame_index"].append(frame_counter)
                data["mean_brightness"].append(brightness)
                data["laplacian_variance"].append(lap_var)
                data["edge_density"].append(edge_dens)
                data["frame_diff_energy"].append(diff_energy)
                data["global_motion_magnitude"].append(motion_mag)
                data["brightness_flicker"].append(flicker)
                data["edge_density_bg"].append(edge_dens_bg)

                prev_gray = gray.copy()
                prev_flow = gray.copy()
                prev_brightness = brightness
                frame_counter += 1

        else:
            # ─── XỬ LÝ VIDEO ────────────────────────────────────────────────
            all_frame_data = []

            for video_path in local_paths:
                cap = cv2.VideoCapture(video_path)
                if not cap.isOpened():
                    print(f"Không mở được video: {video_path}")
                    continue

                frame_idx_in_video = 0
                prev_gray_video = None
                prev_brightness_video = None
                prev_flow_video = None

                while cap.isOpened():
                    ret, frame = cap.read()
                    if not ret:
                        break
                    if frame_idx_in_video >= MAX_FRAMES_PER_VIDEO:
                        break

                    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    brightness = float(np.mean(gray))
                    lap_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())

                    edges = cv2.Canny(gray, 100, 200)
                    edge_dens = float(np.sum(edges > 0) / edges.size) if edges.size > 0 else 0.0

                    diff_energy = 0.0
                    motion_mag = 0.0
                    flicker = 0.0
                    edge_dens_bg = edge_dens  # default cho frame đầu

                    if prev_gray_video is not None:
                        diff = cv2.absdiff(gray, prev_gray_video)
                        diff_energy = float(np.mean(diff)) * 8.0

                        # ── SỬA LỖI Ở ĐÂY ──
                        # Sử dụng cách an toàn: lấy phần tử thứ 1 của tuple trả về
                        motion_mask_bin = cv2.threshold(diff, 30, 255, cv2.THRESH_BINARY)[1]
                        motion_mask = motion_mask_bin.astype(bool)

                        bg_edges = edges.copy()
                        bg_edges[motion_mask] = 0
                        edge_dens_bg = float(np.sum(bg_edges > 0) / edges.size) if edges.size > 0 else 0.0

                        # Optical flow cho global motion
                        flow = cv2.calcOpticalFlowFarneback(prev_flow_video, gray, None, 0.5, 3, 15, 3, 5, 1.2, 0)
                        mag, _ = cv2.cartToPolar(flow[..., 0], flow[..., 1])
                        motion_mag = float(np.mean(mag))

                        flicker = abs(brightness - prev_brightness_video)

                    all_frame_data.append({
                        "frame_index": frame_counter,
                        "mean_brightness": brightness,
                        "laplacian_variance": lap_var,
                        "edge_density": edge_dens,
                        "frame_diff_energy": diff_energy,
                        "global_motion_magnitude": motion_mag,
                        "brightness_flicker": flicker,
                        "edge_density_bg": edge_dens_bg,
                    })

                    # Cập nhật trạng thái trước
                    prev_gray_video = gray.copy()
                    prev_flow_video = gray.copy()
                    prev_brightness_video = brightness
                    frame_counter += 1
                    frame_idx_in_video += 1

                cap.release()

            # Gộp dữ liệu từ tất cả video
            if all_frame_data:
                for k in data:
                    data[k] = [d[k] for d in all_frame_data]

        # ────────────────────────────────────────────────────────────────
        # Kiểm tra dữ liệu
        # ────────────────────────────────────────────────────────────────
        if len(data["frame_index"]) < 5:
            return {"success": False, "message": f"Chỉ trích xuất được {len(data['frame_index'])} frame hợp lệ. Cần ít nhất 5 frame."}

        # ─── Định nghĩa scatter plots theo chế độ ───────────────────────
        if not is_video_mode:
            scatter_pairs = [
                ("mean_brightness", "laplacian_variance", "Độ sáng trung bình", "Độ nét (Laplacian variance)"),
                ("laplacian_variance", "edge_density", "Độ nét (Laplacian variance)", "Mật độ cạnh (Canny)"),
                ("frame_index", "frame_diff_energy", "Thứ tự frame", "Năng lượng thay đổi frame"),
            ]
        else:
            scatter_pairs = [
                ("frame_index", "global_motion_magnitude", "Thứ tự frame", "Độ lớn chuyển động toàn cục"),
                ("frame_diff_energy", "brightness_flicker", "Năng lượng thay đổi frame", "Độ nhấp nháy độ sáng"),
                ("global_motion_magnitude", "laplacian_variance", "Độ lớn chuyển động toàn cục", "Độ nét (Laplacian variance)"),
                ("edge_density_bg", "frame_diff_energy", "Mật độ cạnh vùng nền", "Năng lượng thay đổi frame"),
            ]

        # ─── Vẽ biểu đồ ─────────────────────────────────────────────────
        images_base64 = []
        feature_labels = []

        for x_key, y_key, x_label, y_label in scatter_pairs:
            x_values = data[x_key]
            y_values = data[y_key]

            fig, ax = plt.subplots(figsize=(9, 7), dpi=130)
            ax.scatter(x_values, y_values, alpha=0.7, s=55, c='teal', edgecolor='white', linewidth=0.5)

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
            "message": f"Đã tạo {len(scatter_pairs)} scatter plots ({type_str}) ({elapsed:.1f}s)",
            "type": "video" if is_video_mode else "frame",
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