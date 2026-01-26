from flask import Blueprint, jsonify, request
import services.database as db_service
import services.video_service as video_service
import services.minio_service as minio_service
import services.pexels_service as pexels_service
import yt_downloaderpy as yt
import threading
import os
import json
from datetime import datetime

video_bp = Blueprint('video', __name__)

FRAMES_OUTPUT_ROOT = "dataset_extracted"

@video_bp.route('/api/videos', methods=['GET'])
def get_videos():
    """Lấy danh sách tất cả video từ database"""
    try:
        db = db_service.get_db_connection()
        if db is None:
            return jsonify({'error': 'Không thể kết nối database'}), 500
        
        collection = db['downloaded_videos']
        
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        search = request.args.get('search', '', type=str)
        
        query = {}
        if search:
            query = {
                '$or': [
                    {'title': {'$regex': search, '$options': 'i'}},
                    {'keyword': {'$regex': search, '$options': 'i'}},
                    {'video_id': {'$regex': search, '$options': 'i'}}
                ]
            }
        
        total = collection.count_documents(query)
        offset = (page - 1) * per_page
        videos = list(collection.find(query).sort('downloaded_at', -1).skip(offset).limit(per_page))
        
        for video in videos:
            video['_id'] = str(video['_id'])
            if 'downloaded_at' in video and isinstance(video['downloaded_at'], datetime):
                video['downloaded_at'] = video['downloaded_at'].isoformat()
            if 'created_at' in video and isinstance(video['created_at'], datetime):
                video['created_at'] = video['created_at'].isoformat()
            if 'updated_at' in video and isinstance(video['updated_at'], datetime):
                video['updated_at'] = video['updated_at'].isoformat()
            
            # Add Media Type (Extension)
            video['media_type'] = 'video/mp4' # Default
            if 'file_path' in video and video['file_path']:
                _, ext = os.path.splitext(video['file_path'])
                if ext:
                    video['media_type'] = ext.lower().replace('.', '')
            elif 'storage_refs' in video and video['storage_refs'].get('key'):
                _, ext = os.path.splitext(video['storage_refs']['key'])
                if ext:
                    video['media_type'] = ext.lower().replace('.', '')
            
            # Presigned URL from MinIO service
            if 'storage_refs' in video and video['storage_refs']:
                try:
                    bucket = video['storage_refs'].get('bucket')
                    key = video['storage_refs'].get('key')
                    if bucket and key:
                        presigned_url = minio_service.get_file_url(bucket, key, expires=3600)
                        if presigned_url:
                            video['minio_url'] = presigned_url
                except Exception as e:
                    print(f"Error generating presigned URL: {e}")
        
        return jsonify({
            'videos': videos,
            'total': total,
            'page': page,
            'per_page': per_page,
            'total_pages': (total + per_page - 1) // per_page
        })
    except Exception as e:
        return jsonify({'error': f'Lỗi: {str(e)}'}), 500

@video_bp.route('/api/download/url', methods=['POST'])
def download_by_url_api():
    """API để tải video từ URL (YouTube hoặc Pexels)"""
    data = request.json
    urls = data.get('urls', [])
    platform = data.get('platform', 'youtube') # 'youtube' or 'pexels'
    bypass_keyword_check = data.get('bypass_keyword_check', False)
    
    if not urls:
        return jsonify({'error': 'Vui lòng cung cấp ít nhất một URL'}), 400
    
    def download_thread():
        # Pexels Logic
        if platform == 'pexels':
            api_key = os.getenv('PEXELS_API_KEY')
            if not api_key:
                print("Error: No Pexels API Key found")
                return

            for url in urls:
                try:
                    # Extract ID from URL (e.g., https://www.pexels.com/video/traffic-flow-12345/)
                    # Matches /video/xxxxx/ or /video/xxxxx
                    import re
                    match = re.search(r'video\/.*?(\d+)\/?', url)
                    if match:
                        video_id = match.group(1)
                        print(f"Downloading Pexels ID: {video_id}")
                        # Pexels validation is already strict on resolution
                        pexels_service.download_video_by_id(video_id, api_key)
                    else:
                        print(f"Could not extract Pexels ID from {url}")
                except Exception as e:
                    print(f"Error downloading Pexels URL {url}: {e}")
            return

        # YouTube Logic (Default)
        downloaded_videos = []
        for url in urls:
            try:
                # Basic check to avoid passing Pexels URL to YouTube downloader if user forgot to switch toggle
                if 'pexels.com' in url:
                    print(f"Skipping Pexels URL in YouTube mode: {url}")
                    continue
                    
                video = yt.download_by_url(url.strip(), bypass_keyword_check=bypass_keyword_check)
                if video:
                    downloaded_videos.append(video)
            except Exception as e:
                print(f"Lỗi khi tải {url}: {e}")
        
        if downloaded_videos:
            downloads_folder = os.path.join(os.getcwd(), 'downloads')
            if os.path.exists(downloads_folder):
                result = video_service.extract_frames_from_folder(downloads_folder)
                extract_result_file = os.path.join(FRAMES_OUTPUT_ROOT, '.youtube_extract_result.json')
                os.makedirs(FRAMES_OUTPUT_ROOT, exist_ok=True)
                with open(extract_result_file, 'w', encoding='utf-8') as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)

    thread = threading.Thread(target=download_thread)
    thread.daemon = True
    thread.start()
    
    return jsonify({
        'message': f'Đã bắt đầu tải {len(urls)} video(s) từ {platform}',
        'status': 'processing'
    })

@video_bp.route('/api/download/keyword', methods=['POST'])
def download_by_keyword_api():
    """API để tải video từ keyword (YouTube hoặc Pexels)"""
    data = request.json
    keyword = data.get('keyword', '').strip()
    num_videos = data.get('num_videos', 1)
    platform = data.get('platform', 'youtube')
    
    if not keyword:
        return jsonify({'error': 'Vui lòng cung cấp từ khóa'}), 400
    
    def download_thread():
        try:
            if platform == 'pexels':
                api_key = os.getenv('PEXELS_API_KEY')
                if api_key:
                    pexels_service.download_pexels_videos(keyword, num_videos, api_key)
                else:
                    print("Error: No Pexels API Key configured")
            else:
                # YouTube (Default)
                videos = yt.download_by_keyword(keyword, num_videos)
                if videos:
                    downloads_folder = os.path.join(os.getcwd(), 'downloads')
                    if os.path.exists(downloads_folder):
                        result = video_service.extract_frames_from_folder(downloads_folder)
                        extract_result_file = os.path.join(FRAMES_OUTPUT_ROOT, '.youtube_extract_result.json')
                        os.makedirs(FRAMES_OUTPUT_ROOT, exist_ok=True)
                        with open(extract_result_file, 'w', encoding='utf-8') as f:
                            json.dump(result, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Lỗi khi tải từ keyword {keyword} ({platform}): {e}")
    
    thread = threading.Thread(target=download_thread)
    thread.daemon = True
    thread.start()
    
    return jsonify({
        'message': f'Đã bắt đầu tải video cho từ khóa: {keyword} trên {platform}',
        'status': 'processing'
    })
