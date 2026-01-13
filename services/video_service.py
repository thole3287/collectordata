import os
import cv2
import json
import threading
import services.database as db_service
import services.minio_service as minio_service
import services.scene_analysis
from datetime import datetime

import numpy as np

import hashlib

FRAMES_OUTPUT_ROOT = "dataset_extracted"
VALID_VIDEO_EXTENSIONS = ('.mp4', '.avi', '.mov', '.mkv', '.wmv')
# Đọc từ env nếu có, nhưng ở đây cần import os/cv2 nên sẽ xử lý tham số truyền vào
# TARGET_WIDTH = 1280
# TARGET_HEIGHT = 720


def calculate_file_hash(file_path):
    """Calculate SHA256 hash of a file."""
    sha256 = hashlib.sha256()
    try:
        with open(file_path, 'rb') as f:
            while chunk := f.read(8192):
                sha256.update(chunk)
        return sha256.hexdigest()
    except Exception as e:
        print(f"Error calculating hash: {e}")
        return None


def analyze_scene_features(frame):
    # Backward compatibility wrapper if needed, or just remove and update calls
    return services.scene_analysis.analyze_scene_features(frame)


def extract_frames_from_folder(input_folder, output_root=None, progress_file_path=None, interval_seconds=1.0, platform='youtube'):
    """
    Extract frames from all videos in a folder.
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

            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                if count % frame_step == 0:
                    try:
                        # Resize frame REMOVED - Use original size
                        # resized_frame = cv2.resize(frame, (TARGET_WIDTH, TARGET_HEIGHT), interpolation=cv2.INTER_AREA)
                        
                        # Use Original Frame for Scene Analysis & Saving
                        resized_frame = frame
                        
                        # --- Feature Extraction for Scene Classification ---
                        scene_type = analyze_scene_features(resized_frame)
                        
                        # Convert to 16-bit PNG (scale up)
                        frame_16bit = resized_frame.astype(np.uint16) * 256
                        
                        # Save as .png
                        filename = f"{video_name}_fr{saved_count:05d}.png"
                        save_path = os.path.join(current_output_dir, filename)
                        
                        # Use cv2.imwrite for 16-bit PNG
                        cv2.imwrite(save_path, frame_16bit)
                        
                        # --- MinIO & MongoDB Integration ---
                        try:
                            # 1. Upload to MinIO (as PNG)
                            # User requested: dataset - platform - scene - video_name ...
                            object_name = f"{platform}/{scene_type}/{video_name}/{filename}"
                            upload_result = minio_service.upload_file(save_path, minio_service.MINIO_BUCKET_FRAMES, object_name)
                            
                            minio_key = None
                            minio_url_path = None
                            
                            if upload_result['success']:
                                minio_key = object_name
                                minio_url_path = f"{minio_service.MINIO_BUCKET_FRAMES}/{minio_key}"
                            
                            # 2. Save Metadata to MongoDB
                            db = db_service.get_db_connection()
                            if db is not None:
                                doc = {
                                    'video_name': video_name,
                                    'video_id': video_name, # Assuming filename is video_id for folder processing
                                    'platform': platform,
                                    'frame_index': saved_count,
                                    'original_video_path': video_path,
                                    'timestamp': datetime.now(),
                                    'file_size': os.path.getsize(save_path),
                                    'scene_type': scene_type,
                                    'weather': scene_type, # Mirror scene_type
                                    'created_at': datetime.now()
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
                        # -----------------------------------
                        
                        saved_count += 1
                    except Exception as e:
                        print(f"Error extracting frame: {e}")
                        pass

                count += 1

            cap.release()
            total_frames += saved_count
            processed_videos.append({"video": video_file, "frames": saved_count})
            
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

def extract_frames_from_videos_task(input_folder, output_root=None, result_file=None):
    """Refactored task to run in thread"""
    result = extract_frames_from_folder(input_folder, output_root)
    if result_file:
        os.makedirs(os.path.dirname(result_file), exist_ok=True)
        with open(result_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
