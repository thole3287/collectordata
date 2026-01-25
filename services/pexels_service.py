import os
import re
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
# TARGET_WIDTH = 1280 (Removed to keep original size)
TARGET_WIDTH = 1280 # Keeping for logic download best quality, but not for resize
TARGET_HEIGHT = 720
MIN_RESOLUTION = 512


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
                                target_width=None, # Use original size
                                target_height=None,
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

        # Xử lý Keyword: Hỗ trợ format "Search Query || Regex Filter"
        search_query = query
        regex_filter = query

        if '||' in query:
            parts = query.split('||')
            if len(parts) >= 2:
                search_query = parts[0].strip()
                regex_filter = parts[1].strip()
                logger.info(f"Processing Advanced Pexels Query: Search='{search_query}', Filter='{regex_filter}'")

        headers = {"Authorization": api_key}
        # Random page to get different videos each time
        random_page = random.randint(1, 100) 
        logger.info(f"Checking Pexels page {random_page} for query '{search_query}'")
        
        url = f"https://api.pexels.com/videos/search?query={search_query}&per_page={num_videos}&orientation=landscape&page={random_page}"
        response = requests.get(url, headers=headers)
        
        if response.status_code != 200:
            logger.error(f"Pexels API Error: {response.status_code} - {response.text}")
            return {"success": False, "error": f"API error: {response.status_code}"}

        data = response.json()
        videos = data.get("videos", [])[:num_videos]
        total = len(videos)
        logger.info(f"Pexels API found {len(data.get('videos', []))} videos for query '{search_query}', filtering with '{regex_filter}'")
        
        saved_to_db = 0
        downloaded_files = []
        progress_file = os.path.join(PEXELS_OUTPUT_FOLDER, '.download_progress.json')
        
        # Determine starting page (randomize to vary results, but allow sequential fetching)
        # If we really want "new" data every time, random is okay, but for "filling quota", we need sequence.
        # Let's start random, then increment.
        current_page = random.randint(1, 50) 
        
        attempts = 0
        max_attempts = 20 # Avoid infinite loops
        
        while saved_to_db < num_videos and attempts < max_attempts:
            attempts += 1
            remaining = num_videos - saved_to_db
            
            # Fetch slightly more than needed to account for filtering
            per_page = max(min(remaining * 2, 80), 15)
            
            logger.info(f"Pexels Search: Query='{search_query}', Page={current_page}, Need={remaining}, Fetching={per_page}")
            
            url = f"https://api.pexels.com/videos/search?query={search_query}&per_page={per_page}&orientation=landscape&page={current_page}"
            response = requests.get(url, headers=headers)
            
            if response.status_code != 200:
                logger.error(f"Pexels API Error: {response.status_code} - {response.text}")
                # If rate limited, maybe wait? For now just break to be safe/not hang.
                break

            data = response.json()
            videos = data.get("videos", [])
            
            if not videos:
                logger.info("No more videos found on Pexels.")
                break
                
            logger.info(f"  -> Found {len(videos)} videos on page {current_page}")
            
            for video in videos:
                if saved_to_db >= num_videos:
                    break
                    
                video_id = video["id"]
                
                # --- REGEX CHECK TITLE ---
                video_title = extract_title_from_url(video.get("url"), video_id)
                if regex_filter:
                    try:
                        if not re.search(regex_filter, video_title, re.IGNORECASE):
                            # logger.info(f"Skipping '{video_title}' (Regex mismatch)")
                            continue
                    except Exception:
                        pass

                video_files = video.get("video_files", [])
                
                # Find best file ~1280px width
                best_link = None
                best_file = None
                min_diff = 99999
                
                for v_file in video_files:
                    # CHECK RESOLUTION
                    if v_file.get("width", 0) < MIN_RESOLUTION or v_file.get("height", 0) < MIN_RESOLUTION:
                        continue
                        
                    diff = abs(v_file.get("width", 0) - TARGET_WIDTH)
                    if diff < min_diff:
                        min_diff = diff
                        best_link = v_file.get("link")
                        best_file = v_file
                
                if best_link and best_file:
                    filename = os.path.join(PEXELS_OUTPUT_FOLDER, f"pexels_{query}_{video_id}.mp4")
                    file_path = os.path.abspath(filename)
                    
                    # Download
                    try:
                        vid_content = requests.get(best_link).content
                        with open(filename, "wb") as f:
                            f.write(vid_content)
                    except Exception as e:
                        logger.error(f"Download failed: {e}")
                        continue
                    
                    downloaded_files.append(filename)
                    
                    video_data = {
                        "id": str(video_id),
                        "title": video_title,
                        "url": video.get("url"),
                        "file_path": file_path,
                        "duration": video.get("duration"),
                        "fps": best_file.get("fps"),
                        "width": best_file.get("width"),
                        "height": best_file.get("height")
                    }
                    
                    if save_pexels_video_to_database(video_data, query):
                        saved_to_db += 1
                        logger.info(f"[SUCCESS] Saved Pexels video {video_id} ({saved_to_db}/{num_videos})")
                        
                        # Cleanup local file immediately
                        try:
                            if os.path.exists(filename):
                                os.remove(filename)
                        except:
                            pass
                    else:
                        # Duplicate or error, cleanup anyway
                        try:
                            if os.path.exists(filename):
                                os.remove(filename)
                        except:
                            pass
                    
                    # Update progress
                    progress_data = {
                        "total": num_videos,
                        "downloaded": saved_to_db,
                        "status": f"Page {current_page}"
                    }
                    with open(progress_file, 'w', encoding='utf-8') as f:
                        json.dump(progress_data, f, ensure_ascii=False)
                else:
                    # logger.info(f"Skipping video {video_id}: No file meets criteria (>= {MIN_RESOLUTION}px)")
                    pass
            
            # Move to next page for next iteration
            current_page += 1
            # Random delay to be nice to API
            time.sleep(1)
        
        if os.path.exists(progress_file):
            os.remove(progress_file)
            
        return {"success": True, "count": saved_to_db, "saved_to_db": saved_to_db, "files": downloaded_files}
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
            # CHECK RESOLUTION
            if v_file.get("width", 0) < MIN_RESOLUTION or v_file.get("height", 0) < MIN_RESOLUTION:
                continue

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
            return {"success": False, "error": f"No video file meets resolution criteria (>={MIN_RESOLUTION}px)"}

    except Exception as e:
        logger.error(f"Error downloading video {video_id}: {e}")
        return {"success": False, "error": str(e)}
