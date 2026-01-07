from flask import Flask, render_template, jsonify, request, send_from_directory
from flask_cors import CORS
import threading
import os
import json
from datetime import datetime, timedelta
import time
from dotenv import load_dotenv

# Services
import services.database as db_service
import services.camera_service as camera_service
import services.pexels_service as pexels_service
import services.video_service as video_service
import services.keyword_service as keyword_service
# MinIO service (rename helper use)
import services.minio_service as minio_service
import services.auto_collector_service as auto_collector_service

import cv2
import numpy as np
from bson import ObjectId

# Load environment variables
load_dotenv()

# App configuration
app = Flask(__name__)
CORS(app)

# --- CONFIGS ---
PEXELS_API_KEY = os.getenv('PEXELS_API_KEY', '')
PEXELS_OUTPUT_FOLDER = "pexels_traffic_dataset"
FRAMES_OUTPUT_ROOT = "dataset_extracted"
VALID_VIDEO_EXTENSIONS = ('.mp4', '.avi', '.mov', '.mkv', '.wmv')

# --- IMPORT OLD LOGIC WRAPPERS (for backward compatibility if needed, or direct use) ---
# We still use yt_downloaderpy for YouTube logic as per plan (it wasn't fully refactored into a service file yet, though it acts like one)
import yt_downloaderpy as yt

# ==================== INITIALIZATION ====================

# Initialize camera collector on startup
try:
    camera_service.init_camera_collector()
except Exception as e:
    print(f"Warning: Camera collector initialization failed: {e}")
    print("App will continue without camera collector functionality")

# Initialize MinIO buckets
try:
    minio_endpoint = os.getenv('MINIO_ENDPOINT')
    if minio_endpoint:
        print("🔧 Initializing MinIO buckets...")
        minio_service.ensure_buckets_exist()
except Exception as e:
    print(f"⚠️ MinIO initialization skipped: {e}")

# Initialize Database Indexes
try:
    print("🔧 Ensuring Database Indexes...")
    db = db_service.get_db_connection()
    if db is not None:
        # Create index for downloaded_videos sorting
        db['downloaded_videos'].create_index([('downloaded_at', -1)])
        print("✓ Database indexes created")
except Exception as e:
    print(f"⚠️ Database index creation skipped: {e}")


# ==================== ROUTES: HOME ====================

@app.route('/')
def index():
    """Trang chủ admin"""
    return render_template('index.html')


# ==================== ROUTES: DATASET & GALLERY ====================

@app.route('/api/image/<frame_id>')
def serve_minio_image(frame_id):
    """Serve image directly from MinIO via ID lookup"""
    try:
        db = db_service.get_db_connection()
        if db is None:
            return jsonify({'error': 'Database connection failed'}), 500
            
        # Find frame doc
        frame = db['video_frames'].find_one({'_id': ObjectId(frame_id)})
        if not frame:
            return jsonify({'error': 'Frame not found'}), 404
            
        # Get MinIO details
        storage_refs = frame.get('storage_refs', {})
        bucket = storage_refs.get('bucket')
        key = storage_refs.get('key')
        
        if not bucket or not key:
            return jsonify({'error': 'Image location not valid'}), 404
            
        # Get object from MinIO
        client = minio_service.get_minio_client()
        try:
            # Check if object exists
            try:
                client.stat_object(bucket, key)
            except Exception:
                return jsonify({'error': 'Image file missing in storage'}), 404
                
            # Get object
            data = client.get_object(bucket, key)
            
            # Create a generator to stream the response
            def generate():
                for chunk in data.stream(32*1024):
                    yield chunk
                data.close()
                data.release_conn()
                
            return app.response_class(generate(), mimetype='image/png')
            
        except Exception as e:
            print(f"MinIO fetch error: {e}")
            return jsonify({'error': 'Failed to retrieve image'}), 500
            
    except Exception as e:
        print(f"Error serving image: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/dataset/stats', methods=['GET'])
def get_dataset_stats():
    """Get aggregated statistics for the dataset dashboard"""
    try:
        db = db_service.get_db_connection()
        if db is None:
            return jsonify({'error': 'Database connection failed'}), 500
            
        collection = db['video_frames']
        
        # 1. Total Frames
        total_frames = collection.count_documents({})
        
        # 2. Platform Distribution
        pipeline_platform = [
            {"$group": {"_id": "$platform", "count": {"$sum": 1}}}
        ]
        platform_stats = list(collection.aggregate(pipeline_platform))
        platforms = {item['_id'] or 'unknown': item['count'] for item in platform_stats}
        
        # 3. Collection Timeline (Last 7 days or groupings)
        # Simplified: Group by Date (YYYY-MM-DD)
        pipeline_timeline = [
            {
                "$group": {
                    "_id": {
                        "$dateToString": {
                            "format": "%Y-%m-%d", 
                            "date": { 
                                "$convert": { 
                                    "input": "$created_at", 
                                    "to": "date", 
                                    "onError": None, 
                                    "onNull": None 
                                }
                            }
                        }
                    },
                    "count": {"$sum": 1}
                }
            },
            {"$sort": {"_id": 1}},
            {"$limit": 30} # Last 30 days
        ]
        timeline_stats = list(collection.aggregate(pipeline_timeline))
        timeline = [{"date": item['_id'], "count": item['count']} for item in timeline_stats]
        
        return jsonify({
            'total_frames': total_frames,
            'platforms': platforms,
            'timeline': timeline
        })
    except Exception as e:
        print(f"Error getting stats: {e}")
        return jsonify({'error': str(e)}), 500



@app.route('/api/frames', methods=['GET'])
def get_frames():
    """Get list of extracted frames with pagination and filtering"""
    try:
        db = db_service.get_db_connection()
        if db is None:
            return jsonify({'error': 'Database connection failed'}), 500
        
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 24, type=int)
        platform_filter = request.args.get('platform', '', type=str)
        search_query = request.args.get('search', '', type=str)
        
        video_id_filter = request.args.get('video_id', '', type=str)

        # distinct handling for Camera platform
        if platform_filter == 'camera':
            query = {}
            if search_query:
                query['$or'] = [
                    {'camera_name': {'$regex': search_query, '$options': 'i'}},
                    {'camera_id': {'$regex': search_query, '$options': 'i'}}
                ]
            
            # Count and Sort for Camera
            total_frames = db['camera_images'].count_documents(query)
            total_pages = (total_frames + per_page - 1) // per_page
            
            cursor = db['camera_images'].find(query).sort('timestamp', -1)
            cursor.skip((page - 1) * per_page).limit(per_page)
            
            frames = []
            for doc in cursor:
                # Map camera_images to unified frame structure
                frame_id = str(doc.get('_id', ''))
                
                # storage refs
                storage = doc.get('storage_refs', {})
                bucket = storage.get('bucket', 'dataset')
                key = storage.get('key', '')
                
                # Construct Proxy URL
                image_url = ""
                if bucket and key:
                    image_url = f"/api/image-proxy?bucket={bucket}&key={key}"
                elif 'file_path' in doc:
                     # Fallback for old local files (unlikely to work if not in minio, but kept for compat)
                     image_url = f"/api/camera/images/{os.path.basename(doc['file_path'])}"
                
                frames.append({
                    'id': frame_id,
                    'video_name': doc.get('camera_name', 'Unknown Camera'),
                    'video_id': doc.get('camera_id', ''),
                    'platform': 'camera',
                    'frame_index': 0, # Not applicable for single images
                    'frame_number': 0,
                    'video_frame_number': 0,
                    'file_size': doc.get('file_size', 0), # Might be missing
                    'scene_type': 'day', # TODO: Add scene detection for camera images later
                    'image_url': image_url,
                    'storage_bucket': bucket,
                    'storage_key': key,
                    'created_at': doc.get('timestamp', datetime.now()).isoformat()
                })
                
            return jsonify({
                'frames': frames,
                'total_frames': total_frames,
                'current_page': page,
                'total_pages': total_pages
            })
        
        # Standard Video Frames Logic (Youtube/Pexels)
        # Build Query
        query = {}
        if platform_filter and platform_filter != 'all':
            query['platform'] = platform_filter
            
        if video_id_filter:
            query['video_id'] = video_id_filter
            
        if search_query:
            # Search by video_name or video_id
            query['$or'] = [
                {'video_name': {'$regex': search_query, '$options': 'i'}},
                {'video_id': {'$regex': search_query, '$options': 'i'}}
            ]
        
        # Sort by most recent
        cursor = db['video_frames'].find(query).sort('created_at', -1)
        
        total_frames = db['video_frames'].count_documents(query)
        total_pages = (total_frames + per_page - 1) // per_page
        
        cursor.skip((page - 1) * per_page).limit(per_page)
        
        frames = []
        for doc in cursor:
            frame_id = str(doc.get('_id', ''))
            video_name = doc.get('video_name', '') or str(doc.get('video_id', 'unknown'))
            # Fix: Retrieve platform, defaulting to 'youtube' if missing
            platform = doc.get('platform', 'youtube') 
            
            image_url = f"/api/image/{frame_id}"
            
            # Rich Metadata for Passport View
            frames.append({
                'id': frame_id,
                'video_name': video_name,
                'video_id': doc.get('video_id', ''),
                'platform': platform,
                'frame_index': doc.get('frame_index', 0),
                'frame_number': doc.get('frame_number', ''),
                'video_frame_number': doc.get('video_frame_number', 0),
                'file_size': doc.get('file_size', 0),
                'scene_type': doc.get('scene_type', 'day'), # Detected scene
                'image_url': image_url,
                'storage_bucket': doc.get('storage_refs', {}).get('bucket', ''),
                'storage_key': doc.get('storage_refs', {}).get('key', ''),
                'created_at': doc.get('created_at', datetime.now()).isoformat()
            })
            
        return jsonify({
            'frames': frames,
            'total_frames': total_frames,
            'current_page': page,
            'total_pages': total_pages
        })
    except Exception as e:
        print(f"Error fetching frames: {e}")
        # print(f"Query was: {query}") # Debug
        return jsonify({'error': str(e)}), 500


# ==================== ROUTES: VIDEOS ====================

@app.route('/api/videos', methods=['GET'])
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

@app.route('/api/download/url', methods=['POST'])
def download_by_url_api():
    """API để tải video từ URL (YouTube hoặc Pexels)"""
    data = request.json
    urls = data.get('urls', [])
    platform = data.get('platform', 'youtube') # 'youtube' or 'pexels'
    
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
                    
                video = yt.download_by_url(url.strip())
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

@app.route('/api/download/keyword', methods=['POST'])
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

# ==================== ROUTES: AUTO COLLECTOR ====================

@app.route('/api/auto-collector/start', methods=['POST'])
def start_auto_collector():
    result = auto_collector_service.auto_collector.start()
    return jsonify(result)

@app.route('/api/auto-collector/stop', methods=['POST'])
def stop_auto_collector():
    result = auto_collector_service.auto_collector.stop()
    return jsonify(result)

@app.route('/api/auto-collector/status', methods=['GET'])
def get_auto_collector_status():
    result = auto_collector_service.auto_collector.get_status()
    return jsonify(result)


# ==================== ROUTES: STATS ====================

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Lấy thống kê tổng quan"""
    try:
        db = db_service.get_db_connection()
        if db is None:
            return jsonify({'error': 'Không thể kết nối database'}), 500
        
        collection = db['downloaded_videos']
        total_videos = collection.count_documents({})
        
        pipeline_method = [{'$group': {'_id': '$download_method', 'count': {'$sum': 1}}}]
        by_method = {row['_id']: row['count'] for row in collection.aggregate(pipeline_method)}
        
        yesterday = datetime.now() - timedelta(hours=24)
        recent_24h = collection.count_documents({'downloaded_at': {'$gte': yesterday}})
        
        return jsonify({
            'total_videos': total_videos,
            'by_method': by_method,
            'recent_24h': recent_24h
        })
    except Exception as e:
        return jsonify({'error': f'Lỗi: {str(e)}'}), 500

@app.route('/api/visualization', methods=['GET'])
def get_visualization_data():
    """Lấy dữ liệu visualize (giữ nguyên logic aggregate phức tạp trong controller để dễ đọc)"""
    # Note: Could move to a stats_service if needed, but keeping here is acceptable
    try:
        db = db_service.get_db_connection()
        if db is None:
            return jsonify({'error': 'Không thể kết nối database'}), 500
        
        collection = db['downloaded_videos']
        
        # 1. Platform
        pipeline_platform = [{'$group': {'_id': '$platform', 'count': {'$sum': 1}}}]
        by_platform = [{'platform': row['_id'], 'count': row['count']} for row in collection.aggregate(pipeline_platform)]
        
        # 2. Keywords
        pipeline_keyword = [
            {'$match': {'keyword': {'$ne': None}}},
            {'$group': {'_id': '$keyword', 'count': {'$sum': 1}, 'platforms': {'$addToSet': '$platform'}}},
            {'$sort': {'count': -1}},
            {'$limit': 20}
        ]
        by_keyword = [{'keyword': r['_id'], 'count': r['count'], 'platforms': r['platforms']} for r in collection.aggregate(pipeline_keyword)]
        
        # 3. Resolution
        pipeline_res = [
            {'$match': {'metadata.resolution': {'$ne': None}}},
            {'$group': {'_id': '$metadata.resolution', 'count': {'$sum': 1}}},
            {'$sort': {'count': -1}}
        ]
        by_resolution = [{'resolution': r['_id'], 'count': r['count']} for r in collection.aggregate(pipeline_res)]
        
        # 4. Method
        pipeline_meth = [{'$group': {'_id': '$download_method', 'count': {'$sum': 1}}}]
        by_method = [{'method': r['_id'], 'count': r['count']} for r in collection.aggregate(pipeline_meth)]
        
        # 5. Date
        pipeline_date = [
            {'$group': {'_id': {'$dateToString': {'format': '%Y-%m-%d', 'date': '$downloaded_at'}}, 'count': {'$sum': 1}}},
            {'$sort': {'_id': -1}},
            {'$limit': 30}
        ]
        by_date = [{'date': r['_id'], 'count': r['count']} for r in collection.aggregate(pipeline_date)]
        
        # 6. Weather
        pipeline_weather = [
            {'$group': {'_id': {'$ifNull': ['$weather', '$scene_type']}, 'count': {'$sum': 1}}},
            {'$match': {'_id': {'$ne': None}}}
        ]
        by_weather = [{'weather': r['_id'], 'count': r['count']} for r in db['video_frames'].aggregate(pipeline_weather)]

        # 7. Duration
        pipeline_dur = [
            {'$match': {'metadata.duration': {'$ne': None}}},
            {'$addFields': {'duration_range': {'$switch': {'branches': [
                {'case': {'$lt': ['$metadata.duration', 60]}, 'then': '0-60s'},
                {'case': {'$lt': ['$metadata.duration', 300]}, 'then': '1-5min'},
                {'case': {'$lt': ['$metadata.duration', 600]}, 'then': '5-10min'},
                {'case': {'$lt': ['$metadata.duration', 1800]}, 'then': '10-30min'},
                {'case': {'$gte': ['$metadata.duration', 1800]}, 'then': '30min+'}
            ], 'default': 'unknown'}}}},
            {'$group': {'_id': '$duration_range', 'count': {'$sum': 1}}}
        ]
        by_dur_raw = list(collection.aggregate(pipeline_dur))
        order_map = {'0-60s': 1, '1-5min': 2, '5-10min': 3, '10-30min': 4, '30min+': 5}
        by_duration = sorted([{'range': r['_id'], 'count': r['count']} for r in by_dur_raw], key=lambda x: order_map.get(x['range'], 99))
        
        # 7. Quality
        total = collection.count_documents({})
        has_file = collection.count_documents({'file_path': {'$ne': None}})
        has_dur = collection.count_documents({'metadata.duration': {'$ne': None}})
        has_res = collection.count_documents({'metadata.resolution': {'$ne': None}})
        has_kw = collection.count_documents({'keyword': {'$ne': None}})
        
        quality = {
            'total': total,
            'has_file': has_file,
            'has_duration': has_dur,
            'has_resolution': has_res,
            'has_keyword': has_kw,
            'completeness': {
                'file': round((has_file/total*100) if total else 0, 2),
                'duration': round((has_dur/total*100) if total else 0, 2),
                'resolution': round((has_res/total*100) if total else 0, 2),
                'keyword': round((has_kw/total*100) if total else 0, 2),
            }
        }
        
        return jsonify({
            'by_platform': by_platform,
            'by_keyword': by_keyword,
            'by_resolution': by_resolution,
            'by_method': by_method,
            'by_date': by_date,
            'by_duration': by_duration,
            'by_weather': by_weather,
            'quality': quality
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ==================== ROUTES: KEYWORDS ====================

@app.route('/api/keywords', methods=['GET'])
def get_keywords():
    active_only = request.args.get('active_only', 'false').lower() == 'true'
    result = keyword_service.get_all_keywords(active_only)
    if 'error' in result:
        return jsonify(result), 500
    return jsonify({'keywords': result})

@app.route('/api/keywords', methods=['POST'])
def create_keyword():
    response = keyword_service.create_keyword(request.json)
    if 'error' in response:
        return jsonify(response), 400
    return jsonify(response)

@app.route('/api/keywords/<keyword_id>', methods=['PUT'])
def update_keyword(keyword_id):
    response = keyword_service.update_keyword(keyword_id, request.json)
    if 'error' in response:
        return jsonify(response), 400 if response['error'] != 'Keyword ID không hợp lệ' else 400 # Simplify status codes
    return jsonify(response), 200

@app.route('/api/keywords/<keyword_id>', methods=['DELETE'])
def delete_keyword(keyword_id):
    response = keyword_service.delete_keyword(keyword_id)
    if 'error' in response:
        return jsonify(response), 404
    return jsonify(response)

@app.route('/api/keywords/<keyword_id>/download', methods=['POST'])
def download_by_keyword_id(keyword_id):
    # Retrieve keyword
    kwd = keyword_service.get_keyword_by_id(keyword_id)
    if not kwd:
        return jsonify({'error': 'Keyword không tồn tại'}), 404
    
    keyword = kwd['keyword']
    num_videos = kwd['num_videos']
    
    # Update status processing
    keyword_service.update_keyword_status(keyword_id, 'processing')
    
    def download_thread():
        try:
            videos = yt.download_by_keyword(keyword, num_videos)
            if videos:
                downloads_folder = os.path.join(os.getcwd(), 'downloads')
                if os.path.exists(downloads_folder):
                    result = video_service.extract_frames_from_folder(downloads_folder)
                    extract_result_file = os.path.join(FRAMES_OUTPUT_ROOT, '.youtube_extract_result.json')
                    os.makedirs(FRAMES_OUTPUT_ROOT, exist_ok=True)
                    with open(extract_result_file, 'w', encoding='utf-8') as f:
                        json.dump(result, f, ensure_ascii=False, indent=2)
                
                # Update status completed
                keyword_service.update_keyword_status(
                    keyword_id, 
                    'completed', 
                    last_downloaded_at=datetime.now(),
                    inc={'total_downloaded': len(videos)}
                )
        except Exception as e:
            print(f"Lỗi khi tải từ keyword {keyword}: {e}")
            keyword_service.update_keyword_status(keyword_id, 'failed')

    thread = threading.Thread(target=download_thread)
    thread.daemon = True
    thread.start()
    
    return jsonify({'message': f'Đã bắt đầu tải video cho từ khóa: {keyword}', 'status': 'processing'})


# ==================== ROUTES: CAMERA ====================

@app.route('/api/camera/status')
def camera_status():
    return jsonify(camera_service.get_camera_status()), 200

@app.route('/api/camera/start', methods=['POST'])
def camera_start():
    if camera_service.start_camera_scheduler():
        return jsonify({"status": "success", "message": "Camera collector started"}), 200
    return jsonify({"status": "error", "message": "Scheduler already running or not initialized"}), 400

@app.route('/api/camera/stop', methods=['POST'])
def camera_stop():
    if camera_service.stop_camera_scheduler():
        return jsonify({"status": "success", "message": "Camera collector stopped"}), 200
    return jsonify({"status": "error", "message": "Scheduler not running"}), 400

@app.route('/api/camera/list')
def camera_list():
    cameras = camera_service.get_cameras_list()
    return jsonify({"status": "success", "cameras": cameras, "total": len(cameras)}), 200

@app.route('/api/camera/add', methods=['POST'])
def camera_add():
    camera_id = request.json.get('camera_id')
    if not camera_id:
        return jsonify({"status": "error", "message": "camera_id is required"}), 400
    
    success, message = camera_service.add_camera_to_collection(camera_id)
    if success:
        # Reload collector to reflect changes
        camera_service.init_camera_collector()
        return jsonify({"status": "success", "message": message}), 200
    return jsonify({"status": "error", "message": message}), 500

@app.route('/api/camera/remove', methods=['POST'])
def camera_remove():
    camera_id = request.json.get('camera_id')
    if not camera_id:
        return jsonify({"status": "error", "message": "camera_id is required"}), 400
        
    success, message = camera_service.remove_camera_from_collection(camera_id)
    if success:
        # Reload collector
        camera_service.init_camera_collector()
        return jsonify({"status": "success", "message": message}), 200
    return jsonify({"status": "error", "message": message}), 500

@app.route('/api/camera/recent-images')
def camera_recent_images():
    limit = int(request.args.get('limit', 10))
    # Use the new DB-based function which returns MinIO URLs
    images = camera_service.get_recent_images_from_db(limit=limit)
    return jsonify({"images": images}), 200

@app.route('/api/camera/images/<path:image_path>')
def camera_serve_image(image_path):
    if not camera_service.camera_collector_instance:
        return jsonify({"error": "Camera collector not initialized"}), 500
    
    data_dir = camera_service.camera_collector_instance.storage_path
    path_parts = image_path.split('/')
    if len(path_parts) < 2:
        return jsonify({"error": "Invalid image path"}), 400
    
    directory = os.path.join(data_dir, '/'.join(path_parts[:-1]))
    filename = path_parts[-1]
    
    if not os.path.exists(os.path.join(directory, filename)):
         return jsonify({"error": "Image not found"}), 404
         
    return send_from_directory(directory, filename)


# ==================== ROUTES: PEXELS ====================

@app.route('/api/pexels/download', methods=['POST'])
def pexels_download():
    data = request.json
    query = data.get('query', 'traffic')
    num_videos = int(data.get('num_videos', 10))
    
    def download_task():
        result = pexels_service.download_pexels_videos(query, num_videos, PEXELS_API_KEY)
        
        # Save results for frontend legacy check
        os.makedirs(PEXELS_OUTPUT_FOLDER, exist_ok=True)
        result_file = os.path.join(PEXELS_OUTPUT_FOLDER, '.download_result.json')
        with open(result_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
            
        if result.get("success") and result.get("count", 0) > 0:
            pass
            # video_service.extract_frames_from_videos_task is redundant because 
            # pexels_service.download_pexels_videos -> save_pexels_video_to_database 
            # already handles extraction internally and deletes the file.

    thread = threading.Thread(target=download_task)
    thread.daemon = True
    thread.start()
    
    return jsonify({"status": "success", "message": f"Đã bắt đầu tải {num_videos} video với từ khóa '{query}'"}), 200

@app.route('/api/pexels/result', methods=['GET'])
def pexels_download_result():
    try:
        result_file = os.path.join(PEXELS_OUTPUT_FOLDER, '.download_result.json')
        if os.path.exists(result_file):
            with open(result_file, 'r', encoding='utf-8') as f:
                result = json.load(f)
            os.remove(result_file)
            return jsonify(result), 200
        return jsonify({"success": False, "message": "Chưa có kết quả"}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ==================== ROUTES: FRAMES ====================

@app.route('/api/frames/extract', methods=['POST'])
def extract_frames():
    def extract_task():
        video_service.extract_frames_from_videos_task(
            PEXELS_OUTPUT_FOLDER,
            FRAMES_OUTPUT_ROOT,
            os.path.join(FRAMES_OUTPUT_ROOT, '.extract_result.json')
        )

    thread = threading.Thread(target=extract_task)
    thread.daemon = True
    thread.start()
    return jsonify({"status": "success", "message": "Đã bắt đầu tạo frame từ video"}), 200

@app.route('/api/frames/result', methods=['GET'])
def extract_frames_result():
    # Helper to check result file for Pexels extraction
    try:
        result_file = os.path.join(FRAMES_OUTPUT_ROOT, '.extract_result.json')
        if os.path.exists(result_file):
            with open(result_file, 'r', encoding='utf-8') as f:
                result = json.load(f)
            os.remove(result_file)
            return jsonify(result), 200
        return jsonify({"success": False, "message": "Chưa có kết quả"}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/frames/youtube-result', methods=['GET'])
def youtube_extract_result():
    try:
        result_file = os.path.join(FRAMES_OUTPUT_ROOT, '.youtube_extract_result.json')
        if os.path.exists(result_file):
            with open(result_file, 'r', encoding='utf-8') as f:
                result = json.load(f)
            os.remove(result_file)
            return jsonify({"exists": True, "result": result}), 200
        return jsonify({"exists": False}), 200
    except Exception as e:
        return jsonify({"exists": False, "error": str(e)}), 500

@app.route('/api/frames/<frame_id>/url', methods=['GET'])
def get_frame_presigned_url(frame_id):
    try:
        from bson import ObjectId
        db = db_service.get_db_connection()
        if db is None: return jsonify({'error': 'Database connection failed'}), 500
        
        try:
             frame = db['video_frames'].find_one({'_id': ObjectId(frame_id)})
        except: return jsonify({'error': 'Invalid frame ID'}), 400
        
        if not frame: return jsonify({'error': 'Frame not found'}), 404
        
        if 'storage_refs' in frame and frame['storage_refs']:
            storage_refs = frame['storage_refs']
            bucket = storage_refs.get('bucket')
            key = storage_refs.get('key')
            if bucket and key:
                expires = request.args.get('expires', 3600, type=int)
                presigned_url = minio_service.get_file_url(bucket, key, expires=expires)
                if presigned_url:
                    return jsonify({
                        'frame_id': str(frame['_id']),
                        'video_id': frame.get('video_id'),
                        'url': presigned_url,
                        'expires_in': expires
                    }), 200
        return jsonify({'error': 'Frame has no storage reference'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ==================== ROUTES: VEHICLE DETECTION ====================

@app.route('/api/vehicle-detection/upload', methods=['POST'])
def upload_vehicle_detection():
    try:
        db = db_service.get_db_connection()
        if db is None: return jsonify({'error': 'Database connection failed'}), 500
        
        data = request.get_json()
        event_id = data.get('event_id') or f"evt_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
        camera_id = data.get('camera_id', 'unknown')
        
        timestamp = datetime.now()
        if data.get('timestamp'):
            timestamp = datetime.fromisoformat(data['timestamp'])
            
        detection_data = {
            'event_id': event_id,
            'timestamp': timestamp,
            'camera_id': camera_id,
            'location': data.get('location', {}),
            'vehicle_type': data.get('vehicle_type'),
            'license_plate': data.get('license_plate'),
            'color': data.get('color'),
            'confidence': data.get('confidence', 0.0)
        }
        
        storage_refs = {'bucket': minio_service.MINIO_BUCKET_VEHICLE_DETECTION}
        
        # Upload helpers
        # Upload helpers
        def convert_and_upload_png(path, type_):
            if path and os.path.exists(path):
                # Convert to PNG 16-bit
                try:
                    img = cv2.imread(path)
                    if img is not None:
                        # Resize if type is 'full' (Full Frame)
                        if type_ == 'full':
                            img = cv2.resize(img, (1280, 720), interpolation=cv2.INTER_AREA)
                            
                        img_16bit = img.astype(np.uint16) * 256
                        # Use .png extension
                        base_name = os.path.splitext(os.path.basename(path))[0]
                        png_path = os.path.join(os.path.dirname(path), f"{base_name}.png")
                        cv2.imwrite(png_path, img_16bit)
                        
                        # Upload PNG
                        res = minio_service.upload_and_get_key(
                            png_path, 
                            minio_service.MINIO_BUCKET_VEHICLE_DETECTION, 
                            camera_id=camera_id, 
                            event_id=event_id, 
                            file_type=type_, 
                            content_type='image/png'
                        )
                        
                        # Cleanup generated PNG
                        try:
                            os.remove(png_path)
                            # Optionally delete original JPG if needed? keeping it safe for now.
                        except:
                            pass
                            
                        return res['key'] if res['success'] else None
                except Exception as e:
                    print(f"Error converting/uploading PNG: {e}")
                    pass
            return None

        storage_refs['full_frame_key'] = convert_and_upload_png(data.get('full_frame_path'), 'full')
        storage_refs['cropped_vehicle_key'] = convert_and_upload_png(data.get('cropped_vehicle_path'), 'crop')
        storage_refs['cropped_plate_key'] = convert_and_upload_png(data.get('cropped_plate_path'), 'plate')
        
        if data.get('video_clip_path'):
            res = minio_service.upload_and_get_key(data['video_clip_path'], minio_service.MINIO_BUCKET_VEHICLE_DETECTION, camera_id=camera_id, event_id=event_id, file_type='video', content_type='video/mp4')
            if res['success']: storage_refs['video_clip_key'] = res['key']
            
        doc_id = minio_service.save_vehicle_detection_to_mongodb(db, detection_data, storage_refs)
        
        if doc_id:
            return jsonify({'success': True, 'event_id': event_id, 'document_id': str(doc_id), 'storage_refs': storage_refs}), 201
        return jsonify({'error': 'Failed to save to MongoDB'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/vehicle-detection/<event_id>', methods=['GET'])
def get_vehicle_detection(event_id):
    try:
        db = db_service.get_db_connection()
        if db is None: return jsonify({'error': 'Database connection failed'}), 500
        expires = request.args.get('expires', 3600, type=int)
        result = minio_service.get_presigned_urls_for_detection(db, event_id, expires=expires)
        if result: return jsonify(result), 200
        return jsonify({'error': 'Detection not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/vehicle-detection/search', methods=['GET'])
def search_vehicle_detections():
    # Logic remains similar, access DB directly via service
    try:
        db = db_service.get_db_connection()
        if db is None: return jsonify({'error': 'Database connection failed'}), 500
        collection = db['vehicle_detections']
        
        query = {}
        if request.args.get('license_plate'): query['detection_data.license_plate'] = {'$regex': request.args.get('license_plate'), '$options': 'i'}
        if request.args.get('vehicle_type'): query['detection_data.vehicle_type'] = request.args.get('vehicle_type')
        if request.args.get('camera_id'): query['camera_id'] = request.args.get('camera_id')
        if request.args.get('date_from'): query.setdefault('timestamp', {})['$gte'] = datetime.fromisoformat(request.args.get('date_from'))
        if request.args.get('date_to'): query.setdefault('timestamp', {})['$lte'] = datetime.fromisoformat(request.args.get('date_to'))
        
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        
        total = collection.count_documents(query)
        detections = list(collection.find(query).sort('timestamp', -1).skip((page-1)*per_page).limit(per_page))
        
        for det in detections:
            det['_id'] = str(det['_id'])
            if 'timestamp' in det and isinstance(det['timestamp'], datetime):
                det['timestamp'] = det['timestamp'].isoformat()
            if 'created_at' in det and isinstance(det['created_at'], datetime):
                det['created_at'] = det['created_at'].isoformat()
            if 'updated_at' in det and isinstance(det['updated_at'], datetime):
                det['updated_at'] = det['updated_at'].isoformat()
        
        return jsonify({'total': total, 'page': page, 'per_page': per_page, 'total_pages': (total + per_page - 1) // per_page, 'detections': detections}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/minio/create-buckets', methods=['POST'])
def create_minio_buckets():
    try:
        if not os.getenv('MINIO_ENDPOINT'): return jsonify({'error': 'MinIO not configured'}), 400
        if minio_service.ensure_buckets_exist():
            buckets = [minio_service.MINIO_BUCKET_VIDEOS, minio_service.MINIO_BUCKET_IMAGES, minio_service.MINIO_BUCKET_FRAMES, minio_service.MINIO_BUCKET_CAMERA, minio_service.MINIO_BUCKET_VEHICLE_DETECTION]
            return jsonify({'success': True, 'message': 'Buckets created successfully', 'buckets': buckets}), 200
        return jsonify({'success': False, 'error': 'Failed to create buckets'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500




# ==================== ROUTES: DATASET ====================

@app.route('/api/dataset/groups', methods=['GET'])
def get_dataset_groups():
    """Lấy danh sách nhóm video (đã extract frames) với thông tin weather dominant - Optimized"""
    try:
        db = db_service.get_db_connection()
        if db is None: return jsonify({'error': 'Kết nối DB thất bại'}), 500
        
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        platform_filter = request.args.get('platform', '', type=str)
        search_query = request.args.get('search', '', type=str)

        # --- CAMERA PLATFORM HANDLING ---
        if platform_filter == 'camera':
             # Aggregate camera_images to mimic groups
            match_stage = {}
            if search_query:
                match_stage['$or'] = [
                    {'camera_name': {'$regex': search_query, '$options': 'i'}},
                    {'camera_id': {'$regex': search_query, '$options': 'i'}}
                ]
            
            # Aggregation Pipeline
            # 1. Match filters
            # 2. Sort by timestamp desc (to get latest first)
            # 3. Group by camera_id
            # 4. Count frames
            # 5. Get latest image for preview
            
            pipeline = []
            if match_stage:
                pipeline.append({'$match': match_stage})
                
            pipeline.extend([
                {'$sort': {'timestamp': -1}},
                {'$group': {
                    '_id': '$camera_id',
                    'camera_name': {'$first': '$camera_name'},
                    'total_frames': {'$sum': 1},
                    'last_updated': {'$first': '$timestamp'},
                    'preview_doc': {'$first': '$$ROOT'}
                }},
                {'$sort': {'last_updated': -1}},
                {'$skip': (page - 1) * per_page},
                {'$limit': per_page}
            ])

            # Count total groups (cameras)
            # Need separate count query or facet. Count distinct camera_ids matching query.
            distinct_query = match_stage
            total_groups = len(db['camera_images'].distinct('camera_id', distinct_query))
            
            cursor = db['camera_images'].aggregate(pipeline)
            
            groups = []
            for doc in cursor:
                c_id = doc['_id']
                last_up = doc['last_updated']
                preview = doc.get('preview_doc', {})
                
                # storage refs for preview
                storage = preview.get('storage_refs', {})
                bucket = storage.get('bucket', 'dataset')
                key = storage.get('key', '')
                
                preview_url = "/static/img/no-image.png"
                if bucket and key:
                    preview_url = f"/api/image-proxy?bucket={bucket}&key={key}"
                elif 'file_path' in preview:
                     preview_url = f"/api/camera/images/{os.path.basename(preview['file_path'])}"

                groups.append({
                    'video_id': c_id, # Use camera_id as video_id
                    'title': doc.get('camera_name', c_id),
                    'platform': 'camera',
                    'total_frames': doc['total_frames'],
                    'last_updated': last_up.isoformat() if isinstance(last_up, datetime) else str(last_up),
                    'weather': 'day', # TODO: Detect
                    'preview_image': preview_url
                })
                
            return jsonify({
                'groups': groups,
                'total_groups': total_groups,
                'page': page,
                'per_page': per_page,
                'total_pages': (total_groups + per_page - 1) // per_page if per_page > 0 else 1
            })

        # --- STANDARD VIDEO HANDLING (Youtube/Pexels/All) ---
        
        videos_collection = db['downloaded_videos']
        frames_collection = db['video_frames']
        
        # Build Query
        query = {}
        if platform_filter and platform_filter != 'all':
            query['platform'] = platform_filter
            
        if search_query:
            query['$or'] = [
                {'title': {'$regex': search_query, '$options': 'i'}},
                {'video_id': {'$regex': search_query, '$options': 'i'}}
            ]
        
        total_groups = videos_collection.count_documents(query)
        cursor = videos_collection.find(query).sort([('updated_at', -1), ('created_at', -1)]).skip((page - 1) * per_page).limit(per_page)
        
        videos = list(cursor)
        groups = []
        
        for v in videos:
            video_id = v.get('video_id', str(v.get('_id')))
            
            # 2. Get Frame Stats for this video
            total_frames = frames_collection.count_documents({'video_id': video_id})
            
            dominant_weather = 'unknown'
            preview_image = "/static/img/no-image.png"
            last_updated = v.get('updated_at') or v.get('created_at') or datetime.now()
            
            if total_frames > 0:
                # Get latest frame for preview and info
                latest_frame = frames_collection.find_one(
                    {'video_id': video_id},
                    sort=[('created_at', -1)]
                )
                
                if latest_frame:
                    if 'created_at' in latest_frame:
                         last_updated = latest_frame['created_at']
                    
                    if latest_frame.get('_id'):
                        preview_image = f"/api/image/{str(latest_frame['_id'])}"
                    
                    try:
                        pipeline = [
                            {'$match': {'video_id': video_id}},
                            {'$group': {'_id': {'$ifNull': ['$weather', '$scene_type']}, 'count': {'$sum': 1}}},
                            {'$sort': {'count': -1}},
                            {'$limit': 1}
                        ]
                        w_res = list(frames_collection.aggregate(pipeline))
                        if w_res:
                            dominant_weather = w_res[0]['_id']
                    except Exception:
                        dominant_weather = latest_frame.get('weather') or latest_frame.get('scene_type', 'unknown')

            groups.append({
                'video_id': video_id,
                'title': v.get('title', video_id),
                'platform': v.get('platform', 'unknown'),
                'total_frames': total_frames,
                'last_updated': last_updated.isoformat() if isinstance(last_updated, datetime) else str(last_updated),
                'weather': dominant_weather,
                'preview_image': preview_image
            })

        return jsonify({
            'groups': groups,
            'total_groups': total_groups,
            'page': page,
            'per_page': per_page,
            'total_pages': (total_groups + per_page - 1) // per_page
        })
    except Exception as e:
        print(f"Error getting dataset groups: {e}")
        return jsonify({'error': str(e)}), 500


# ==================== MAIN ====================


# ==================== PROXY ROUTE ====================

@app.route('/api/image/<frame_id>')
def get_frame_image(frame_id):
    """
    Get image content by Frame ID (Proxy from MinIO)
    """
    try:
        from bson import ObjectId
        db = db_service.get_db_connection()
        if db is None: return jsonify({'error': 'Database connection failed'}), 500
        
        try:
             frame = db['video_frames'].find_one({'_id': ObjectId(frame_id)})
        except: return jsonify({'error': 'Invalid frame ID'}), 400
        
        if not frame: return jsonify({'error': 'Frame not found'}), 404
        
        bucket = None
        key = None
        
        # 1. Try storage_refs (New format)
        if 'storage_refs' in frame and frame['storage_refs']:
            bucket = frame['storage_refs'].get('bucket')
            key = frame['storage_refs'].get('key')
            
        # 2. Try legacy fields (Old format fallback)
        if not bucket or not key:
             # Try reconstructing from Platform/VideoID
             # This is a best-effort fallback for old data without storage_refs
             if frame.get('platform') == 'youtube' and frame.get('frame_number'):
                  bucket = minio_service.MINIO_BUCKET_VIDEOS
                  # Assumption: videos/youtube/{video_id}/{frame_number}.jpg ?? No, structure wasn't this clean.
                  # It was videos/youtube/{filename}.
                  # Frames are in MINIO_BUCKET_FRAMES (dataset)
                  bucket = minio_service.MINIO_BUCKET_FRAMES
                  # dataset/youtube/{video_id}/{frame_number}.jpg
                  key = f"youtube/{frame.get('video_id')}/{frame.get('frame_number')}.jpg"

             elif frame.get('platform') == 'pexels':
                  bucket = minio_service.MINIO_BUCKET_FRAMES
                  key = f"pexels/{frame.get('video_id')}/{frame.get('frame_number')}.jpg"

        if not bucket or not key:
            return jsonify({'error': 'Image storage info not found'}), 404

        # Proxy from MinIO
        try:
            client = minio_service.get_minio_client(internal=True)
            response = client.get_object(bucket, key)
            
            from flask import Response, stream_with_context
            return Response(
                stream_with_context(response.stream(32*1024)),
                headers={
                    "Content-Type": response.headers.get("Content-Type", "image/jpeg"),
                    "Content-Length": response.headers.get("Content-Length"),
                    "Cache-Control": "public, max-age=3600"
                }
            )
        except Exception as minio_e:
            print(f"MinIO Proxy Error for {frame_id}: {minio_e}")
            return jsonify({'error': 'Image not found in storage'}), 404
            
    except Exception as e:
        print(f"Error serving image {frame_id}: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/image-proxy')
def image_proxy():
    """
    Proxy image from MinIO to frontend to avoid CORS/Network issues.
    Query params: bucket, key
    """
    bucket = request.args.get('bucket')
    key = request.args.get('key')
    
    # print(f"DEBUG PROXY REQUEST: bucket={bucket}, key={key}")

    if not bucket or not key:
        return jsonify({"error": "Missing bucket or key"}), 400
        
    try:
        # Get internal client (uses minio:9000 inside docker)
        client = minio_service.get_minio_client(internal=True)
        
        # Get object
        response = client.get_object(bucket, key)
        
        # Stream the response
        from flask import Response, stream_with_context
        
        return Response(
            stream_with_context(response.stream(32*1024)),
            headers={
                "Content-Type": response.headers.get("Content-Type", "image/jpeg"),
                "Content-Length": response.headers.get("Content-Length"),
                "Cache-Control": "public, max-age=3600"
            }
        )
    except Exception as e:
        print(f"Proxy error for {bucket}/{key}: {e}")
        return jsonify({"error": str(e)}), 404

if __name__ == '__main__':
    flask_host = os.getenv('FLASK_HOST', '127.0.0.1')
    flask_port = int(os.getenv('FLASK_PORT', 5000))
    flask_debug = os.getenv('FLASK_DEBUG', 'True').lower() == 'true'
    
    import socket
    ports_to_try = [flask_port, 5001, 8080, 3000, 8000]
    port = None
    for p in ports_to_try:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.bind((flask_host, p))
            sock.close()
            port = p
            break
        except OSError: continue
    
    if port is None:
        print("❌ Không tìm thấy port trống.")
        exit(1)
        
    print(f"🚀 Server đang chạy tại: http://{flask_host}:{port}")
    app.run(debug=flask_debug, host=flask_host, port=port)
