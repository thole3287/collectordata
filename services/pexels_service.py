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

# Setup logger
logger = logging.getLogger(__name__)

PEXELS_OUTPUT_FOLDER = "pexels_traffic_dataset"
TARGET_WIDTH = 1280
TARGET_HEIGHT = 720

def save_pexels_video_to_database(video_data, query, download_method='pexels'):
    """Lưu thông tin video Pexels vào Database"""
    db = get_db_connection()
    if db is None:
        return False
    
    try:
        collection = db['downloaded_videos']
        existing = collection.find_one({'video_id': str(video_data['id'])})
        if existing:
            return False
        
        # Upload MinIO Logic
        minio_key = None
        minio_bucket = None
        file_path = video_data.get('file_path')
        storage_refs_data = {}
        
        # Check toggle
        should_upload_minio = os.getenv('UPLOAD_TO_MINIO', 'true').lower() == 'true'
        
        if file_path and os.path.exists(file_path) and should_upload_minio:
            try:
                import services.minio_service as minio_service
                minio_endpoint = os.getenv('MINIO_ENDPOINT')
                # Strict check logic or relaxed? using same logic as yt_downloaderpy update
                if minio_endpoint or True: # Assuming defaults work if env not set
                    video_id = str(video_data['id'])
                    file_ext = os.path.splitext(file_path)[1] or '.mp4'
                    object_key = f"pexels/{video_id}{file_ext}"
                    
                    result = minio_service.upload_and_get_key(
                        file_path=file_path,
                        bucket_name=minio_service.MINIO_BUCKET_VIDEOS,
                        custom_path=object_key,
                        content_type='video/mp4'
                    )
                    
                    if result.get('success'):
                        minio_key = result['key']
                        minio_bucket = result['bucket']
                        
                        # Extract frames
                        try:
                            video_fps = video_data.get('fps')
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
                                
                                # Delete local file
                                try:
                                    os.remove(file_path)
                                except:
                                    pass
                        except Exception as e:
                            logger.error(f"Error extracting frames: {e}")
            except Exception as e:
                logger.error(f"Error uploading to MinIO: {e}")

        # Create Document
        document = {
            'video_id': str(video_data['id']),
            'title': video_data.get('title', f"Pexels Video {video_data['id']}"),
            'url': video_data.get('url', f"https://www.pexels.com/video/{video_data['id']}/"),
            'file_path': file_path,
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
        return True
    except DuplicateKeyError:
        return False
    except Exception as e:
        logger.error(f"Error saving Pexels video: {e}")
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
                    "title": video.get("user", {}).get("name", "") + " - " + str(video_id),
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
