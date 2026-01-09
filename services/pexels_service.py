import os
import requests
import json
import time
import threading
import random
from datetime import datetime
from pymongo.errors import DuplicateKeyError
import logging
from services.database import get_db_connection
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Setup logger
logger = logging.getLogger(__name__)

PEXELS_OUTPUT_FOLDER = "pexels_traffic_dataset"
TARGET_WIDTH = 1280
TARGET_HEIGHT = 720

from services.video_service import calculate_file_hash

def extract_title_from_url(url, video_id):
    """
    Extracts a title from the Pexels video URL.
    Example: https://www.pexels.com/video/stunning-4k-aerial-view-of-jonkoping-cityscape-35124638/
    Returns: "Stunning 4k Aerial View Of Jonkoping Cityscape"
    """
    if not url:
        return f"Pexels Video {video_id}"
    
    try:
        # Url usually ends with '...-video_id/' or '...-video_id'
        parts = url.strip('/').split('/')
        slug = parts[-1] 
        
        # Remove video_id from end of slug if present
        if slug.endswith(str(video_id)):
            slug = slug.replace(f"-{video_id}", "")
            
        # Replace hyphens with spaces and title case
        title = slug.replace('-', ' ').title()
        
        if not title.strip():
             return f"Pexels Video {video_id}"
             
        return title
    except Exception:
        return f"Pexels Video {video_id}"

def save_pexels_video_to_database(video_data, query, download_method='pexels'):
    """Lưu thông tin video Pexels vào Database"""
    db = get_db_connection()
    if db is None:
        print("[ERROR] No database connection")
        return False
    
    try:
        collection = db['downloaded_videos']
        # User requested Hash check instead of ID check
        # existing = collection.find_one({'video_id': str(video_data['id'])})
        # if existing:
        #     print(f"[INFO] Video {video_data['id']} already exists in DB")
        #     return False
        
        file_path = video_data.get('file_path')
        file_hash = None
        
        if file_path and os.path.exists(file_path):
             # Calculate hash
            file_hash = calculate_file_hash(file_path)
            if file_hash:
                existing_hash = collection.find_one({'file_hash': file_hash})
                if existing_hash:
                    logger.info(f"Video content duplicate (Hash: {file_hash}). Skipping.")
                    try:
                        os.remove(file_path)
                    except:
                        pass
                    return False
        
        # Upload MinIO Logic
        minio_key = None
        minio_bucket = None
        file_path = video_data.get('file_path')
        storage_refs_data = {}
        
        # Check toggle
        should_upload_minio = os.getenv('UPLOAD_TO_MINIO', 'true').lower() == 'true'
        print(f"[INFO] Upload to MinIO: {should_upload_minio}, File: {file_path}")
        
        if file_path and os.path.exists(file_path) and should_upload_minio:
            try:
                import services.minio_service as minio_service
                minio_endpoint = os.getenv('MINIO_ENDPOINT')
                
                if minio_endpoint:
                    video_id = str(video_data['id'])
                    file_ext = os.path.splitext(file_path)[1] or '.mp4'
                    object_key = f"pexels/{video_id}{file_ext}"
                    
                    print(f"[INFO] Uploading to MinIO: {object_key}")
                    result = minio_service.upload_and_get_key(
                        file_path=file_path,
                        bucket_name=minio_service.MINIO_BUCKET_VIDEOS,
                        custom_path=object_key,
                        content_type='video/mp4'
                    )
                    
                    if result.get('success'):
                        minio_key = result['key']
                        minio_bucket = result['bucket']
                        print(f"[OK] Uploaded video to MinIO: {minio_key}")
                        
                        # Extract frames
                        try:
                            video_fps = video_data.get('fps')
                            print(f"[INFO] Extracting frames for {video_id}...")
                            frames_result = minio_service.extract_and_upload_frames(
                                video_path=file_path,
                                video_id=video_id,
                                platform='pexels',
                                fps=video_fps,
                                target_width=1280,
                                target_height=720,
                                db=db
                            )
                            if frames_result.get('success'):
                                storage_refs_data['frames_bucket'] = frames_result['bucket']
                                storage_refs_data['frame_keys'] = frames_result['frame_keys']
                                storage_refs_data['frames_count'] = frames_result['frames_uploaded']
                                print(f"[OK] Extracted and uploaded {frames_result['frames_uploaded']} frames")
                                
                                # Delete local file
                                try:
                                    os.remove(file_path)
                                    print(f"[INFO] Deleted local file: {file_path}")
                                except Exception as e:
                                    print(f"[WARN] Error deleting file: {e}")
                            else:
                                print(f"[ERROR] Frame extraction failed: {frames_result.get('error')}")
                        except Exception as e:
                            print(f"Error extracting frames: {e}")
            except Exception as e:
                print(f"Error uploading to MinIO: {e}")

        # Update file_path to MinIO Path (bucket/key) if upload succeeded
        if minio_key and minio_bucket:
             file_path = f"{minio_bucket}/{minio_key}"

        # Create Document
        document = {
            'video_id': str(video_data['id']),
            'title': video_data.get('title', f"Pexels Video {video_data['id']}"),
            'url': video_data.get('url', f"https://www.pexels.com/video/{video_data['id']}/"),
            'file_path': file_path,
            'file_hash': file_hash,
            'media_type': 'mp4',
            'metadata': {
                'duration': video_data.get('duration'),
                'fps': video_data.get('fps'),
                'width': video_data.get('width'),
                'height': video_data.get('height'),
                'resolution': video_data.get('resolution') or (f"{video_data.get('width')}x{video_data.get('height')}" if video_data.get('width') else None)
            },
            'platform': 'pexels',
            'keyword': query,
            'download_method': download_method,
            'downloaded_at': datetime.now(),
            'created_at': datetime.now()
        }
        
        if minio_key:
            document['storage_refs'] = {
                'bucket': minio_bucket,
                'key': minio_key
            }
            if storage_refs_data.get('frames_bucket'):
                document['storage_refs'].update({
                    'frames_bucket': storage_refs_data['frames_bucket'],
                    'frame_keys': storage_refs_data.get('frame_keys', []),
                    'frames_count': storage_refs_data.get('frames_count', 0)
                })
        
        collection.insert_one(document)
        print(f"[OK] Saved video info to DB: {video_data['id']}")
        return True
    except DuplicateKeyError:
        return False
    except Exception as e:
        print(f"Error saving Pexels video: {e}")
        return False

def download_pexels_videos(query, num_videos, api_key):
    """Download videos from Pexels API."""
    try:
        if not os.path.exists(PEXELS_OUTPUT_FOLDER):
            os.makedirs(PEXELS_OUTPUT_FOLDER)

        headers = {"Authorization": api_key}
        # Random page to get different videos each time
        random_page = random.randint(1, 100) 
        logger.info(f"Checking Pexels page {random_page} for query '{query}'")
        
        url = f"https://api.pexels.com/videos/search?query={query}&per_page={num_videos}&orientation=landscape&page={random_page}"
        response = requests.get(url, headers=headers)
        
        if response.status_code != 200:
            logger.error(f"Pexels API Error: {response.status_code} - {response.text}")
            return {"success": False, "error": f"API error: {response.status_code}"}

        data = response.json()
        videos = data.get("videos", [])[:num_videos]
        total = len(videos)
        logger.info(f"Pexels API found {len(data.get('videos', []))} videos for query '{query}', downloading {total}")
        
        count = 0
        saved_to_db = 0
        downloaded_files = []
        progress_file = os.path.join(PEXELS_OUTPUT_FOLDER, '.download_progress.json')
        
        for idx, video in enumerate(videos):
            video_id = video["id"]
            
            # [OPTIMIZATION] Check DB before downloading (DISABLED per user request to check content hash)
            # db = get_db_connection()
            # if db:
            #     existing_video = db['downloaded_videos'].find_one({'video_id': str(video_id)})
            #     if existing_video:
            #         logger.info(f"Video {video_id} already exists in DB. Skipping.")
            #         continue

            video_files = video["video_files"]
            
            # Find best file ~1280px width
            best_link = None
            best_file = None
            min_diff = 99999
            for v_file in video_files:
                diff = abs(v_file["width"] - TARGET_WIDTH)
                if diff < min_diff:
                    min_diff = diff
                    best_link = v_file["link"]
                    best_file = v_file
            
            if best_link and best_file:
                vid_content = requests.get(best_link).content
                filename = os.path.join(PEXELS_OUTPUT_FOLDER, f"pexels_{query}_{video_id}.mp4")
                file_path = os.path.abspath(filename)
                
                with open(filename, "wb") as f:
                    f.write(vid_content)
                
                downloaded_files.append(filename)
                
                video_data = {
                    "id": str(video_id),
                    "title": extract_title_from_url(video.get("url"), video_id),
                    "url": video.get("url"),
                    "file_path": file_path,
                    "duration": video.get("duration"),
                    "fps": best_file.get("fps"),
                    "width": best_file.get("width"),
                    "height": best_file.get("height")
                }
                
                if save_pexels_video_to_database(video_data, query):
                    saved_to_db += 1
                    logger.info(f"Successfully processed video {video_id}")
                else:
                    logger.warning(f"Failed to save video {video_id} to DB (duplicate or error)")
                
                # Cleanup: Ensure local file is removed regardless of result (success/duplicate/error)
                # save_pexels_video_to_database attempts delete on success, but we double check here
                try:
                    if os.path.exists(filename):
                        os.remove(filename)
                        print(f"[INFO] Deleted local file (cleanup): {filename}")
                except Exception as e:
                    print(f"[WARN] Failed to delete local file {filename}: {e}")
                
                count += 1
                
                # Update progress
                progress = int((count / total) * 100) if total > 0 else 0
                progress_data = {
                    "total": total,
                    "downloaded": count,
                    "progress": progress,
                    "saved_to_db": saved_to_db
                }
                with open(progress_file, 'w', encoding='utf-8') as f:
                    json.dump(progress_data, f, ensure_ascii=False)
                
                time.sleep(1)
        
        if os.path.exists(progress_file):
            os.remove(progress_file)
            
        return {"success": True, "count": count, "saved_to_db": saved_to_db, "files": downloaded_files}
    except Exception as e:
        return {"success": False, "error": str(e)}

def download_video_by_id(video_id, api_key):
    """Download a single video from Pexels by ID"""
    try:
        if not os.path.exists(PEXELS_OUTPUT_FOLDER):
            os.makedirs(PEXELS_OUTPUT_FOLDER)

        headers = {"Authorization": api_key}
        logger.info(f"Fetching Pexels video {video_id} details...")
        
        url = f"https://api.pexels.com/videos/videos/{video_id}"
        response = requests.get(url, headers=headers)
        
        if response.status_code != 200:
            logger.error(f"Pexels API Error: {response.status_code} - {response.text}")
            return {"success": False, "error": f"API error: {response.status_code}"}

        video = response.json()
        video_files = video.get("video_files", [])
        
        if not video_files:
             return {"success": False, "error": "No video files found"}

        # Find best file ~1280px width
        best_link = None
        best_file = None
        min_diff = 99999
        for v_file in video_files:
            diff = abs(v_file["width"] - TARGET_WIDTH)
            if diff < min_diff:
                min_diff = diff
                best_link = v_file["link"]
                best_file = v_file
        
        if best_link and best_file:
            vid_content = requests.get(best_link).content
            filename = os.path.join(PEXELS_OUTPUT_FOLDER, f"pexels_id_{video_id}.mp4")
            file_path = os.path.abspath(filename)
            
            with open(filename, "wb") as f:
                f.write(vid_content)
            
            video_data = {
                "id": str(video_id),
                "title": extract_title_from_url(video.get("url"), video_id),
                "url": video.get("url"),
                "file_path": file_path,
                "duration": video.get("duration"),
                "fps": best_file.get("fps"),
                "width": best_file.get("width"),
                "height": best_file.get("height")
            }
            
            # Save to DB
            saved = save_pexels_video_to_database(video_data, "id_download", download_method="url")
            
            # Cleanup local file if saved successfully (logic inside save function handles upload to minio)
            # But we double check cleanup
            try:
                 if os.path.exists(filename):
                    os.remove(filename)
            except:
                pass

            if saved:
                return {"success": True, "message": f"Downloaded and saved video {video_id}"}
            else:
                return {"success": False, "error": "Failed to save to database (duplicate?)"}
        else:
            return {"success": False, "error": "Could not determine best quality video link"}

    except Exception as e:
        logger.error(f"Error downloading video {video_id}: {e}")
        return {"success": False, "error": str(e)}
