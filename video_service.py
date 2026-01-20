import os
import cv2
import json
"""
import services.database as db_service
import services.minio_service as minio_service
"""
from datetime import datetime
import numpy as np

from services.image_enhancement import smart_process_image, load_settings

FRAMES_OUTPUT_ROOT = "dataset_extracted"
VALID_VIDEO_EXTENSIONS = ('.mp4', '.avi', '.mov', '.mkv', '.wmv')
VALID_IMAGE_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.webp')

def extract_frames_from_folder(input_folder, output_root=None, progress_file_path=None,
                               interval_seconds=1.0,
                               blur_threshold=100,
                               sim_threshold=0.95,
                               min_brightness=40,
                               max_brightness=220):
    """
    Extract frames from videos.
    - No resizing (Original resolution).
    - Smart Filtering (Blur, Brightness, Similarity).
    - Output: 16-bit PNG (Upscaled from 8-bit).
    """
    try:
        if output_root is None:
            output_root = FRAMES_OUTPUT_ROOT

        if progress_file_path is None:
            progress_file_path = os.path.join(output_root, '.extract_progress.json')

        if not os.path.exists(input_folder):
            return {"success": False, "error": f"Folder '{input_folder}' not found"}

        files = os.listdir(input_folder)
        video_files = [f for f in files if f.lower().endswith(VALID_VIDEO_EXTENSIONS)]

        if not video_files:
            return {"success": False, "error": f"No videos found in '{input_folder}'"}

        total_videos = len(video_files)
        total_frames = 0
        processed_videos = []

        os.makedirs(output_root, exist_ok=True)

        for idx, video_file in enumerate(video_files):
            video_path = os.path.join(input_folder, video_file)
            video_name = os.path.splitext(video_file)[0]
            current_output_dir = os.path.join(output_root, video_name)

            if not os.path.exists(current_output_dir):
                os.makedirs(current_output_dir)

            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                continue

            video_fps = cap.get(cv2.CAP_PROP_FPS)
            if not video_fps or video_fps <= 0:
                video_fps = 30.0

            frame_step = int(video_fps * interval_seconds)
            if frame_step < 1:
                frame_step = 1

            count = 0
            saved_count = 0
            last_saved_hist = None

            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                # 1. LỌC THEO THỜI GIAN (Interval)
                if count % frame_step == 0:
                    try:
                        # Tính toán trên 8-bit cho nhanh
                        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

                        # 2. LỌC ĐỘ SÁNG
                        avg_brightness = np.mean(gray)
                        if avg_brightness < min_brightness or avg_brightness > max_brightness:
                            count += 1
                            continue

                        # 3. LỌC ĐỘ MỜ
                        blur_score = cv2.Laplacian(gray, cv2.CV_64F).var()
                        if blur_score < blur_threshold:
                            count += 1
                            continue

                        # 4. LỌC TRÙNG LẶP
                        curr_hist = cv2.calcHist([frame], [0, 1, 2], None, [8, 8, 8], [0, 256, 0, 256, 0, 256])
                        curr_hist = cv2.normalize(curr_hist, curr_hist).flatten()

                        is_duplicate = False
                        if last_saved_hist is not None:
                            similarity = cv2.compareHist(last_saved_hist, curr_hist, cv2.HISTCMP_CORREL)
                            if similarity > sim_threshold:
                                is_duplicate = True

                        if is_duplicate:
                            count += 1
                            continue

                        # --- LƯU ẢNH (NẾU ĐẠT CHUẨN) ---
                        last_saved_hist = curr_hist

                        # --- APPLY IMAGE ENHANCEMENT (Resize, Denoise, etc) ---
                        enhance_settings = load_settings()
                        if enhance_settings.get('enabled_video', False):
                            # Smart Process (detects scene -> calls process_image)
                            # frame is 8-bit BGR here
                            try:
                                processed_frame, scene_type = smart_process_image(frame, enhance_settings)
                                if processed_frame is not None:
                                    frame = processed_frame
                            except Exception as e:
                                print(f"Error enhancing video frame: {e}")

                        # QUAN TRỌNG: Convert sang 16-bit PNG
                        # frame đang là uint8 (0-255). Nhân 256 để scale lên uint16 (0-65535)
                        frame_16bit = frame.astype(np.uint16) * 256

                        filename = f"{video_name}_fr{saved_count:05d}.png"
                        save_path = os.path.join(current_output_dir, filename)

                        # Lưu file 16-bit
                        cv2.imwrite(save_path, frame_16bit)
                        """
                        # --- MinIO & MongoDB Integration ---
                        try:
                            # Upload file vừa lưu (đã là 16-bit) lên MinIO
                            object_name = f"{video_name}/{filename}"
                            upload_result = minio_service.upload_file(save_path, minio_service.MINIO_BUCKET_FRAMES,
                                                                      object_name)

                            minio_key = None
                            minio_url_path = None

                            if upload_result['success']:
                                minio_key = upload_result['key']
                                minio_url_path = f"{minio_service.MINIO_BUCKET_FRAMES}/{minio_key}"

                            # Save Metadata
                            db = db_service.get_db_connection()
                            if db is not None:
                                doc = {
                                    'video_name': video_name,
                                    'frame_index': saved_count,
                                    'original_video_path': video_path,
                                    'timestamp': datetime.now(),
                                    'file_size': os.path.getsize(save_path),
                                    'bit_depth': 16,  # Ghi chú lại là 16-bit
                                    'created_at': datetime.now(),
                                    'quality_metrics': {
                                        'brightness': float(avg_brightness),
                                        'blur_score': float(blur_score)
                                    }
                                }

                                if minio_key:
                                    doc['storage_refs'] = {
                                        'bucket': minio_service.MINIO_BUCKET_FRAMES,
                                        'key': minio_key
                                    }
                                    doc['minio_url_path'] = minio_url_path

                                db['video_frames'].insert_one(doc)

                        except Exception as e:
                            print(f"Error saving frame metadata: {e}")
                        """
                        saved_count += 1
                    except Exception as e:
                        print(f"Error extracting frame: {e}")
                        pass

                count += 1

            cap.release()
            total_frames += saved_count
            processed_videos.append({"video": video_file, "frames": saved_count})

            # Update progress
            progress = int(((idx + 1) / total_videos) * 100) if total_videos > 0 else 0
            progress_data = {
                "total": total_videos,
                "processed": idx + 1,
                "progress": progress,
                "total_frames": total_frames
            }
            with open(progress_file_path, 'w', encoding='utf-8') as f:
                json.dump(progress_data, f, ensure_ascii=False)

        if os.path.exists(progress_file_path):
            os.remove(progress_file_path)

        return {"success": True, "total_frames": total_frames, "videos": processed_videos}
    except Exception as e:
        return {"success": False, "error": str(e)}


def extract_frames_from_image_folder(input_folder, output_root=None, progress_file_path=None,
                                     blur_threshold=100,
                                     sim_threshold=0.95,
                                     min_brightness=40,
                                     max_brightness=220):
    """
    Process images from a folder.
    - Input: Folder chứa ảnh (jpg, png...).
    - Logic: Giống video (Lọc độ sáng, độ mờ, trùng lặp).
    - Output: 16-bit PNG tại thư mục output_root.
    """
    try:
        if output_root is None:
            output_root = FRAMES_OUTPUT_ROOT

        if progress_file_path is None:
            progress_file_path = os.path.join(output_root, '.extract_image_progress.json')

        if not os.path.exists(input_folder):
            return {"success": False, "error": f"Folder '{input_folder}' not found"}

        # Lấy danh sách file ảnh và SẮP XẾP (Quan trọng để lọc trùng lặp hoạt động đúng)
        files = sorted(os.listdir(input_folder))
        image_files = [f for f in files if f.lower().endswith(VALID_IMAGE_EXTENSIONS)]

        if not image_files:
            return {"success": False, "error": f"No images found in '{input_folder}'"}

        total_images = len(image_files)
        saved_count = 0

        # Tạo folder output (lấy tên folder input làm tên folder con)
        folder_name = os.path.basename(os.path.normpath(input_folder))
        current_output_dir = os.path.join(output_root, folder_name)
        os.makedirs(current_output_dir, exist_ok=True)

        last_saved_hist = None
        processed_images = []

        for idx, img_file in enumerate(image_files):
            img_path = os.path.join(input_folder, img_file)

            try:
                # Đọc ảnh
                frame = cv2.imread(img_path)
                if frame is None:
                    print(f"Warning: Cannot read file {img_file}")
                    continue

                # --- BẮT ĐẦU CÁC BƯỚC LỌC ---

                # Chuyển xám để tính toán cho nhanh
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

                # 1. LỌC ĐỘ SÁNG (Brightness)
                avg_brightness = np.mean(gray)
                if avg_brightness < min_brightness or avg_brightness > max_brightness:
                    # Bỏ qua nếu quá tối hoặc quá sáng
                    continue

                # 2. LỌC ĐỘ MỜ (Blur)
                blur_score = cv2.Laplacian(gray, cv2.CV_64F).var()
                if blur_score < blur_threshold:
                    # Bỏ qua nếu ảnh mờ
                    continue

                # 3. LỌC TRÙNG LẶP (Similarity)
                # Tính Histogram màu
                curr_hist = cv2.calcHist([frame], [0, 1, 2], None, [8, 8, 8], [0, 256, 0, 256, 0, 256])
                curr_hist = cv2.normalize(curr_hist, curr_hist).flatten()

                is_duplicate = False
                if last_saved_hist is not None:
                    # So sánh với ảnh ĐÃ LƯU gần nhất
                    similarity = cv2.compareHist(last_saved_hist, curr_hist, cv2.HISTCMP_CORREL)
                    if similarity > sim_threshold:
                        is_duplicate = True

                if is_duplicate:
                    # Bỏ qua nếu giống ảnh trước đó
                    continue

                # --- LƯU ẢNH (NẾU ĐẠT CHUẨN) ---
                last_saved_hist = curr_hist

                # Convert sang 16-bit PNG
                frame_16bit = frame.astype(np.uint16) * 256

                # Đặt tên file output (Giữ tên gốc hoặc đánh số lại tùy nhu cầu)
                # Ở đây mình giữ tên gốc nhưng đổi đuôi thành .png
                base_name = os.path.splitext(img_file)[0]
                filename = f"{base_name}_processed.png"
                save_path = os.path.join(current_output_dir, filename)

                cv2.imwrite(save_path, frame_16bit)
                processed_images.append(filename)

                """
                # --- MinIO & MongoDB Integration (Logic tương tự video) ---
                try:
                    # Upload
                    object_name = f"{folder_name}/{filename}"
                    # ... (Code upload MinIO ở đây) ...

                    # Save Metadata DB
                    # ... (Code save DB ở đây, thay video_name bằng folder_name) ...
                    pass
                except Exception as e:
                    print(f"Error saving metadata for {filename}: {e}")
                """

                saved_count += 1

            except Exception as e:
                print(f"Error processing image {img_file}: {e}")
                continue

            # Update progress file
            progress = int(((idx + 1) / total_images) * 100)
            progress_data = {
                "total": total_images,
                "processed": idx + 1,
                "saved": saved_count,
                "progress": progress
            }
            # Ghi file json tiến trình (ghi đè liên tục)
            with open(progress_file_path, 'w', encoding='utf-8') as f:
                json.dump(progress_data, f, ensure_ascii=False)

        # Xóa file progress khi xong
        if os.path.exists(progress_file_path):
            os.remove(progress_file_path)

        return {
            "success": True,
            "total_input": total_images,
            "saved_images": saved_count,
            "output_folder": current_output_dir
        }

    except Exception as e:
        return {"success": False, "error": str(e)}

def extract_frames_from_videos_task(input_folder, output_root=None, result_file=None):
    """Refactored task to run in thread"""
    result = extract_frames_from_folder(input_folder, output_root)
    if result_file:
        os.makedirs(os.path.dirname(result_file), exist_ok=True)
        with open(result_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

if __name__ == '__main__':
    extract_frames_from_folder("test")
    result = extract_frames_from_image_folder("test_images_input")
    print(json.dumps(result, indent=2))
