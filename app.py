from flask import Flask, render_template, jsonify, request, send_from_directory
from flask_cors import CORS
import threading
import yt_downloaderpy as yt
from datetime import datetime, timedelta
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, DuplicateKeyError
from bson import ObjectId
import os
import json
from pathlib import Path
from apscheduler.schedulers.background import BackgroundScheduler
import camera_collector
import camera_config_loader
import requests
import time
import cv2
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Database connection function
def get_db_connection():
    """Get MongoDB database connection."""
    try:
        db_host = os.getenv('DB_HOST', 'localhost')
        db_port = int(os.getenv('DB_PORT', 27017))
        db_name = os.getenv('DB_NAME', 'data_collection')
        db_user = os.getenv('DB_USER', '')
        db_password = os.getenv('DB_PASSWORD', '')
        
        if db_user and db_password:
            connection_string = f"mongodb://{db_user}:{db_password}@{db_host}:{db_port}/"
        else:
            connection_string = f"mongodb://{db_host}:{db_port}/"
        
        client = MongoClient(connection_string)
        # Test connection
        client.admin.command('ping')
        db = client[db_name]
        return db
    except (ConnectionFailure, Exception) as e:
        print(f"Error connecting to MongoDB: {e}")
        return None

def save_pexels_video_to_database(video_data, query, download_method='pexels'):
    """
    Lưu thông tin video Pexels vào MongoDB database
    
    :param video_data: Dictionary chứa thông tin video từ Pexels
    :param query: Từ khóa tìm kiếm
    :param download_method: 'pexels'
    :return: True nếu thành công, False nếu thất bại
    """
    db = get_db_connection()
    if db is None:
        return False
    
    try:
        collection = db['downloaded_videos']
        
        # Kiểm tra xem video đã tồn tại chưa
        existing = collection.find_one({'video_id': str(video_data['id'])})
        
        if existing:
            return False
        
        # Tạo document theo cấu trúc MongoDB
        document = {
            'video_id': str(video_data['id']),
            'title': video_data.get('title', f"Pexels Video {video_data['id']}"),
            'url': video_data.get('url', f"https://www.pexels.com/video/{video_data['id']}/"),
            'file_path': video_data.get('file_path'),
            'media_type': 'mp4',
            'metadata': {
                'duration': video_data.get('duration'),
                'fps': video_data.get('fps'),
                'width': video_data.get('width'),
                'height': video_data.get('height'),
                'resolution': video_data.get('resolution') or (f"{video_data.get('width')}x{video_data.get('height')}" if video_data.get('width') and video_data.get('height') else None)
            },
            'platform': 'pexels',
            'keyword': query,
            'download_method': download_method,
            'downloaded_at': datetime.now(),
            'created_at': datetime.now()
        }
        
        collection.insert_one(document)
        return True
        
    except DuplicateKeyError:
        return False
    except Exception as e:
        print(f"Error saving Pexels video to database: {e}")
        return False

app = Flask(__name__)
CORS(app)

# Camera Collector setup
camera_scheduler = None
camera_collector_instance = None

def init_camera_collector():
    """Initialize camera collector."""
    global camera_collector_instance
    try:
        cameras = camera_config_loader.load_cameras()
        camera_collector_instance = camera_collector.CameraCollector(
            cameras, 
            storage_path="camera_collector_data"
        )
        return True
    except Exception as e:
        print(f"Warning: Could not initialize camera collector: {e}")
        return False

def setup_camera_scheduler():
    """Setup camera collection scheduler."""
    global camera_scheduler, camera_collector_instance
    if camera_collector_instance is None:
        if not init_camera_collector():
            return
    
    camera_scheduler = BackgroundScheduler()
    camera_scheduler.add_job(
        func=camera_collector_instance.collect_all,
        trigger="interval",
        seconds=5,
        id='camera_collection',
        name='Collect camera images',
        replace_existing=True
    )

def start_camera_scheduler():
    """Start camera collection scheduler."""
    global camera_scheduler
    if camera_scheduler is None:
        setup_camera_scheduler()
    if camera_scheduler and not camera_scheduler.running:
        camera_scheduler.start()
        return True
    return False

def stop_camera_scheduler():
    """Stop camera collection scheduler."""
    global camera_scheduler
    if camera_scheduler and camera_scheduler.running:
        camera_scheduler.shutdown(wait=False)
        camera_scheduler = None
        return True
    return False

def is_camera_scheduler_running():
    """Check if camera scheduler is running."""
    global camera_scheduler
    return camera_scheduler is not None and camera_scheduler.running

# Initialize camera collector on startup (don't fail if it doesn't work)
try:
    init_camera_collector()
except Exception as e:
    print(f"Warning: Camera collector initialization failed: {e}")
    print("App will continue without camera collector functionality")

# ==================== API ENDPOINTS ====================

@app.route('/')
def index():
    """Trang chủ admin"""
    return render_template('index.html')

@app.route('/api/videos', methods=['GET'])
def get_videos():
    """Lấy danh sách tất cả video từ database"""
    try:
        db = yt.get_db_connection()
        if db is None:
            return jsonify({'error': 'Không thể kết nối database'}), 500
        
        collection = db['downloaded_videos']
        
        # Lấy tham số phân trang
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        search = request.args.get('search', '', type=str)
        
        # Xây dựng query
        query = {}
        if search:
            query = {
                '$or': [
                    {'title': {'$regex': search, '$options': 'i'}},
                    {'keyword': {'$regex': search, '$options': 'i'}},
                    {'video_id': {'$regex': search, '$options': 'i'}}
                ]
            }
        
        # Đếm tổng số video
        total = collection.count_documents(query)
        
        # Lấy video với phân trang
        offset = (page - 1) * per_page
        videos = list(collection.find(query)
                     .sort('downloaded_at', -1)
                     .skip(offset)
                     .limit(per_page))
        
        # Convert ObjectId và datetime objects to strings
        for video in videos:
            video['_id'] = str(video['_id'])
            if 'downloaded_at' in video and video['downloaded_at'] and isinstance(video['downloaded_at'], datetime):
                video['downloaded_at'] = video['downloaded_at'].isoformat()
            if 'created_at' in video and video['created_at'] and isinstance(video['created_at'], datetime):
                video['created_at'] = video['created_at'].isoformat()
            if 'updated_at' in video and video['updated_at'] and isinstance(video['updated_at'], datetime):
                video['updated_at'] = video['updated_at'].isoformat()
        
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
    """API để tải video từ URL"""
    data = request.json
    urls = data.get('urls', [])
    
    if not urls:
        return jsonify({'error': 'Vui lòng cung cấp ít nhất một URL'}), 400
    
    # Chạy download trong thread riêng để không block
    def download_thread():
            downloaded_videos = []
            for url in urls:
                try:
                    video = yt.download_by_url(url.strip())
                    if video:
                        downloaded_videos.append(video)
                except Exception as e:
                    print(f"Lỗi khi tải {url}: {e}")
            
            # Tự động extract frames sau khi download xong
            if downloaded_videos:
                downloads_folder = os.path.join(os.getcwd(), 'downloads')
                if os.path.exists(downloads_folder):
                    extract_result = extract_frames_from_folder(
                        downloads_folder, 
                        FRAMES_OUTPUT_ROOT,
                        os.path.join(FRAMES_OUTPUT_ROOT, '.youtube_extract_progress.json')
                    )
                    # Lưu kết quả extract frames
                    extract_result_file = os.path.join(FRAMES_OUTPUT_ROOT, '.youtube_extract_result.json')
                    os.makedirs(FRAMES_OUTPUT_ROOT, exist_ok=True)
                    with open(extract_result_file, 'w', encoding='utf-8') as f:
                        json.dump(extract_result, f, ensure_ascii=False, indent=2)
    
    thread = threading.Thread(target=download_thread)
    thread.daemon = True
    thread.start()
    
    return jsonify({
        'message': f'Đã bắt đầu tải {len(urls)} video(s)',
        'status': 'processing'
    })

@app.route('/api/download/keyword', methods=['POST'])
def download_by_keyword_api():
    """API để tải video từ keyword"""
    data = request.json
    keyword = data.get('keyword', '').strip()
    num_videos = data.get('num_videos', 1)
    
    if not keyword:
        return jsonify({'error': 'Vui lòng cung cấp từ khóa'}), 400
    
    # Chạy download trong thread riêng
    def download_thread():
        try:
            videos = yt.download_by_keyword(keyword, num_videos)
            # Tự động extract frames sau khi download xong
            if videos:
                downloads_folder = os.path.join(os.getcwd(), 'downloads')
                if os.path.exists(downloads_folder):
                    extract_result = extract_frames_from_folder(
                        downloads_folder, 
                        FRAMES_OUTPUT_ROOT,
                        os.path.join(FRAMES_OUTPUT_ROOT, '.youtube_extract_progress.json')
                    )
                    # Lưu kết quả extract frames
                    extract_result_file = os.path.join(FRAMES_OUTPUT_ROOT, '.youtube_extract_result.json')
                    os.makedirs(FRAMES_OUTPUT_ROOT, exist_ok=True)
                    with open(extract_result_file, 'w', encoding='utf-8') as f:
                        json.dump(extract_result, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Lỗi khi tải từ keyword {keyword}: {e}")
    
    thread = threading.Thread(target=download_thread)
    thread.daemon = True
    thread.start()
    
    return jsonify({
        'message': f'Đã bắt đầu tải video cho từ khóa: {keyword}',
        'status': 'processing'
    })

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Lấy thống kê tổng quan"""
    try:
        db = yt.get_db_connection()
        if db is None:
            return jsonify({'error': 'Không thể kết nối database'}), 500
        
        collection = db['downloaded_videos']
        
        # Tổng số video
        total_videos = collection.count_documents({})
        
        # Video theo method
        pipeline_method = [
            {'$group': {'_id': '$download_method', 'count': {'$sum': 1}}}
        ]
        by_method = {}
        for row in collection.aggregate(pipeline_method):
            by_method[row['_id']] = row['count']
        
        # Video mới nhất trong 24h
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
    """Lấy dữ liệu để visualize"""
    try:
        db = yt.get_db_connection()
        if db is None:
            return jsonify({'error': 'Không thể kết nối database'}), 500
        
        collection = db['downloaded_videos']
        
        # 1. Phân bố theo platform
        pipeline_platform = [
            {'$group': {'_id': '$platform', 'count': {'$sum': 1}}}
        ]
        by_platform = [{'platform': row['_id'], 'count': row['count']} for row in collection.aggregate(pipeline_platform)]
        
        # 2. Phân bố theo keyword (top keywords) với platform
        pipeline_keyword = [
            {'$match': {'keyword': {'$ne': None}}},
            {'$group': {
                '_id': '$keyword',
                'count': {'$sum': 1},
                'platforms': {'$addToSet': '$platform'}
            }},
            {'$sort': {'count': -1}},
            {'$limit': 20}
        ]
        by_keyword = []
        for row in collection.aggregate(pipeline_keyword):
            by_keyword.append({
                'keyword': row['_id'],
                'count': row['count'],
                'platforms': row['platforms']
            })
        
        # 3. Phân bố theo resolution
        pipeline_resolution = [
            {'$match': {'metadata.resolution': {'$ne': None}}},
            {'$group': {'_id': '$metadata.resolution', 'count': {'$sum': 1}}},
            {'$sort': {'count': -1}}
        ]
        by_resolution = [{'resolution': row['_id'], 'count': row['count']} for row in collection.aggregate(pipeline_resolution)]
        
        # 4. Phân bố theo download method
        pipeline_method = [
            {'$group': {'_id': '$download_method', 'count': {'$sum': 1}}}
        ]
        by_method = [{'method': row['_id'], 'count': row['count']} for row in collection.aggregate(pipeline_method)]
        
        # 5. Video theo thời gian (theo ngày)
        pipeline_date = [
            {
                '$group': {
                    '_id': {'$dateToString': {'format': '%Y-%m-%d', 'date': '$downloaded_at'}},
                    'count': {'$sum': 1}
                }
            },
            {'$sort': {'_id': -1}},
            {'$limit': 30}
        ]
        by_date = [{'date': row['_id'], 'count': row['count']} for row in collection.aggregate(pipeline_date)]
        
        # 6. Phân bố theo duration (ranges)
        pipeline_duration = [
            {'$match': {'metadata.duration': {'$ne': None}}},
            {
                '$addFields': {
                    'duration_range': {
                        '$switch': {
                            'branches': [
                                {'case': {'$lt': ['$metadata.duration', 60]}, 'then': '0-60s'},
                                {'case': {'$lt': ['$metadata.duration', 300]}, 'then': '1-5min'},
                                {'case': {'$lt': ['$metadata.duration', 600]}, 'then': '5-10min'},
                                {'case': {'$lt': ['$metadata.duration', 1800]}, 'then': '10-30min'},
                                {'case': {'$gte': ['$metadata.duration', 1800]}, 'then': '30min+'}
                            ],
                            'default': 'unknown'
                        }
                    }
                }
            },
            {'$group': {'_id': '$duration_range', 'count': {'$sum': 1}}}
        ]
        by_duration_raw = list(collection.aggregate(pipeline_duration))
        
        # Sắp xếp theo thứ tự logic
        order_map = {'0-60s': 1, '1-5min': 2, '5-10min': 3, '10-30min': 4, '30min+': 5}
        by_duration = sorted(
            [{'range': row['_id'], 'count': row['count']} for row in by_duration_raw],
            key=lambda x: order_map.get(x['range'], 99)
        )
        
        # 7. Data quality check
        total = collection.count_documents({})
        has_file = collection.count_documents({'file_path': {'$ne': None}})
        has_duration = collection.count_documents({'metadata.duration': {'$ne': None}})
        has_resolution = collection.count_documents({'metadata.resolution': {'$ne': None}})
        has_keyword = collection.count_documents({'keyword': {'$ne': None}})
        
        quality_stats = {
            'total': total,
            'has_file': has_file,
            'has_duration': has_duration,
            'has_resolution': has_resolution,
            'has_keyword': has_keyword,
            'completeness': {
                'file': round((has_file / total * 100) if total > 0 else 0, 2),
                'duration': round((has_duration / total * 100) if total > 0 else 0, 2),
                'resolution': round((has_resolution / total * 100) if total > 0 else 0, 2),
                'keyword': round((has_keyword / total * 100) if total > 0 else 0, 2),
            }
        }
        
        return jsonify({
            'by_platform': by_platform,
            'by_keyword': by_keyword,
            'by_resolution': by_resolution,
            'by_method': by_method,
            'by_date': by_date,
            'by_duration': by_duration,
            'quality': quality_stats
        })
    except Exception as e:
        return jsonify({'error': f'Lỗi: {str(e)}'}), 500

# ==================== API KEYWORDS ====================

@app.route('/api/keywords', methods=['GET'])
def get_keywords():
    """Lấy danh sách keywords"""
    try:
        db = yt.get_db_connection()
        if db is None:
            return jsonify({'error': 'Không thể kết nối database'}), 500
        
        collection = db['keywords']
        
        # Lấy tham số active_only
        active_only = request.args.get('active_only', 'false').lower() == 'true'
        
        # Xây dựng query
        query = {}
        if active_only:
            query['is_active'] = True
        
        keywords = list(collection.find(query).sort('created_at', -1))
        
        # Convert ObjectId và datetime objects to strings
        for kw in keywords:
            kw['_id'] = str(kw['_id'])
            if 'last_downloaded_at' in kw and kw['last_downloaded_at'] and isinstance(kw['last_downloaded_at'], datetime):
                kw['last_downloaded_at'] = kw['last_downloaded_at'].isoformat()
            if 'created_at' in kw and isinstance(kw['created_at'], datetime):
                kw['created_at'] = kw['created_at'].isoformat()
            if 'updated_at' in kw and isinstance(kw['updated_at'], datetime):
                kw['updated_at'] = kw['updated_at'].isoformat()
        
        return jsonify({'keywords': keywords})
    except Exception as e:
        return jsonify({'error': f'Lỗi: {str(e)}'}), 500

@app.route('/api/keywords', methods=['POST'])
def create_keyword():
    """Tạo keyword mới"""
    try:
        data = request.json
        keyword = data.get('keyword', '').strip()
        num_videos = data.get('num_videos', 1)
        description = data.get('description', '')
        
        if not keyword:
            return jsonify({'error': 'Vui lòng nhập từ khóa'}), 400
        
        db = yt.get_db_connection()
        if db is None:
            return jsonify({'error': 'Không thể kết nối database'}), 500
        
        collection = db['keywords']
        try:
            # Kiểm tra keyword đã tồn tại chưa
            existing = collection.find_one({'keyword': keyword})
            if existing:
                return jsonify({'error': 'Keyword đã tồn tại'}), 400
            
            # Tạo document mới
            now = datetime.now()
            document = {
                'keyword': keyword,
                'num_videos': num_videos,
                'status': 'pending',
                'total_downloaded': 0,
                'last_downloaded_at': None,
                'description': description,
                'is_active': True,
                'created_at': now,
                'updated_at': now
            }
            
            result = collection.insert_one(document)
            
            return jsonify({
                'message': 'Đã thêm keyword thành công',
                'id': str(result.inserted_id)
            })
        except DuplicateKeyError:
            return jsonify({'error': 'Keyword đã tồn tại'}), 400
    except Exception as e:
        return jsonify({'error': f'Lỗi: {str(e)}'}), 500

@app.route('/api/keywords/<keyword_id>', methods=['PUT'])
def update_keyword(keyword_id):
    """Cập nhật keyword"""
    try:
        data = request.json
        db = yt.get_db_connection()
        if db is None:
            return jsonify({'error': 'Không thể kết nối database'}), 500
        
        collection = db['keywords']
        
        # Kiểm tra keyword có tồn tại không
        try:
            keyword_obj_id = ObjectId(keyword_id)
        except:
            return jsonify({'error': 'Keyword ID không hợp lệ'}), 400
        
        existing = collection.find_one({'_id': keyword_obj_id})
        if not existing:
            return jsonify({'error': 'Keyword không tồn tại'}), 404
        
        # Xây dựng update document
        update_doc = {'updated_at': datetime.now()}
        
        if 'keyword' in data:
            update_doc['keyword'] = data['keyword']
        
        if 'num_videos' in data:
            update_doc['num_videos'] = int(data['num_videos'])
        
        if 'description' in data:
            update_doc['description'] = data['description']
        
        if 'is_active' in data:
            update_doc['is_active'] = bool(data['is_active'])
        
        if 'status' in data:
            update_doc['status'] = data['status']
        
        if len(update_doc) == 1:  # Chỉ có updated_at
            return jsonify({'error': 'Không có trường nào để cập nhật'}), 400
        
        collection.update_one(
            {'_id': keyword_obj_id},
            {'$set': update_doc}
        )
        
        return jsonify({'message': 'Đã cập nhật keyword thành công'}), 200
    except Exception as e:
        return jsonify({'error': f'Lỗi: {str(e)}'}), 500

@app.route('/api/keywords/<keyword_id>', methods=['DELETE'])
def delete_keyword(keyword_id):
    """Xóa keyword"""
    try:
        db = yt.get_db_connection()
        if db is None:
            return jsonify({'error': 'Không thể kết nối database'}), 500
        
        collection = db['keywords']
        
        try:
            keyword_obj_id = ObjectId(keyword_id)
        except:
            return jsonify({'error': 'Keyword ID không hợp lệ'}), 400
        
        result = collection.delete_one({'_id': keyword_obj_id})
        
        if result.deleted_count == 0:
            return jsonify({'error': 'Keyword không tồn tại'}), 404
        
        return jsonify({'message': 'Đã xóa keyword thành công'})
    except Exception as e:
        return jsonify({'error': f'Lỗi: {str(e)}'}), 500

@app.route('/api/keywords/<keyword_id>/download', methods=['POST'])
def download_by_keyword_id(keyword_id):
    """Tải video từ keyword ID"""
    try:
        db = yt.get_db_connection()
        if db is None:
            return jsonify({'error': 'Không thể kết nối database'}), 500
        
        collection = db['keywords']
        
        try:
            keyword_obj_id = ObjectId(keyword_id)
        except:
            return jsonify({'error': 'Keyword ID không hợp lệ'}), 400
        
        keyword_data = collection.find_one({'_id': keyword_obj_id})
        
        if not keyword_data:
            return jsonify({'error': 'Keyword không tồn tại'}), 404
        
        keyword = keyword_data['keyword']
        num_videos = keyword_data['num_videos']
        
        # Cập nhật status
        collection.update_one(
            {'_id': keyword_obj_id},
            {'$set': {'status': 'processing', 'updated_at': datetime.now()}}
        )
        
        # Chạy download trong thread riêng
        def download_thread():
            try:
                videos = yt.download_by_keyword(keyword, num_videos)
                
                # Tự động extract frames sau khi download xong
                if videos:
                    downloads_folder = os.path.join(os.getcwd(), 'downloads')
                    if os.path.exists(downloads_folder):
                        extract_result = extract_frames_from_folder(
                            downloads_folder, 
                            FRAMES_OUTPUT_ROOT,
                            os.path.join(FRAMES_OUTPUT_ROOT, '.youtube_extract_progress.json')
                        )
                        # Lưu kết quả extract frames
                        extract_result_file = os.path.join(FRAMES_OUTPUT_ROOT, '.youtube_extract_result.json')
                        os.makedirs(FRAMES_OUTPUT_ROOT, exist_ok=True)
                        with open(extract_result_file, 'w', encoding='utf-8') as f:
                            json.dump(extract_result, f, ensure_ascii=False, indent=2)
                
                # Cập nhật status và số lượng đã tải
                db = yt.get_db_connection()
                if db is not None:
                    collection = db['keywords']
                    collection.update_one(
                        {'_id': keyword_obj_id},
                        {
                            '$set': {
                                'status': 'completed',
                                'last_downloaded_at': datetime.now(),
                                'updated_at': datetime.now()
                            },
                            '$inc': {'total_downloaded': len(videos) if videos else 0}
                        }
                    )
            except Exception as e:
                print(f"Lỗi khi tải từ keyword {keyword}: {e}")
                # Cập nhật status failed
                db = yt.get_db_connection()
                if db is not None:
                    collection = db['keywords']
                    collection.update_one(
                        {'_id': keyword_obj_id},
                        {'$set': {'status': 'failed', 'updated_at': datetime.now()}}
                    )
        
        thread = threading.Thread(target=download_thread)
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'message': f'Đã bắt đầu tải video cho từ khóa: {keyword}',
            'status': 'processing'
        })
    except Exception as e:
        return jsonify({'error': f'Lỗi: {str(e)}'}), 500

# ==================== CAMERA COLLECTOR API ENDPOINTS ====================

@app.route('/api/camera/status')
def camera_status():
    """Get camera collector status."""
    try:
        if camera_collector_instance is None:
            return jsonify({
                "status": "ok",
                "scheduler_running": False,
                "cameras": [],
                "last_collection": None,
                "statistics": {
                    "total_attempts": 0,
                    "successful": 0,
                    "failed": 0
                },
                "message": "Camera collector not initialized"
            }), 200
        
        status_info = camera_collector_instance.get_status()
        status_info['scheduler_running'] = is_camera_scheduler_running()
        return jsonify(status_info), 200
    except Exception as e:
        return jsonify({
            "status": "error",
            "scheduler_running": False,
            "cameras": [],
            "last_collection": None,
            "statistics": {
                "total_attempts": 0,
                "successful": 0,
                "failed": 0
            },
            "message": str(e)
        }), 200

@app.route('/api/camera/start', methods=['POST'])
def camera_start():
    """Start camera collection."""
    try:
        if start_camera_scheduler():
            return jsonify({"status": "success", "message": "Camera collector started"}), 200
        else:
            return jsonify({"status": "error", "message": "Scheduler already running or not initialized"}), 400
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/camera/stop', methods=['POST'])
def camera_stop():
    """Stop camera collection."""
    try:
        if stop_camera_scheduler():
            return jsonify({"status": "success", "message": "Camera collector stopped"}), 200
        else:
            return jsonify({"status": "error", "message": "Scheduler not running"}), 400
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/camera/list')
def camera_list():
    """Get list of all available cameras."""
    try:
        # Try multiple possible paths
        possible_paths = [
            Path('camera.json'),
            Path('camera-collector/camera-collector/camera.json'),
            Path('camera-collector/camera.json')
        ]
        
        camera_file = None
        for path in possible_paths:
            if path.exists():
                camera_file = path
                break
        
        if not camera_file:
            return jsonify({
                "status": "error",
                "message": "camera.json file not found. Please ensure camera.json exists.",
                "cameras": []
            }), 200  # Return 200 with empty list instead of 404
        
        with open(camera_file, 'r', encoding='utf-8') as f:
            cameras = json.load(f)
        
        camera_list = []
        for cam in cameras:
            if isinstance(cam, dict) and 'camera_id' in cam:
                camera_list.append({
                    'camera_id': cam.get('camera_id'),
                    'title': cam.get('title') or cam.get('code', ''),
                    'code': cam.get('code', ''),
                    'display_name': cam.get('display_name') or cam.get('address', ''),
                    'address': cam.get('address') or cam.get('display_name', ''),
                })
        
        return jsonify({
            "status": "success",
            "cameras": camera_list,
            "total": len(camera_list)
        }), 200
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Error reading camera.json: {e}"
        }), 500

@app.route('/api/camera/add', methods=['POST'])
def camera_add():
    """Add camera to collection list."""
    try:
        data = request.json
        camera_id = data.get('camera_id')
        
        if not camera_id:
            return jsonify({
                "status": "error",
                "message": "camera_id is required"
            }), 400
        
        # Try multiple possible paths
        possible_paths = [
            Path('camera.json'),
            Path('camera-collector/camera-collector/camera.json'),
            Path('camera-collector/camera.json')
        ]
        
        camera_file = None
        for path in possible_paths:
            if path.exists():
                camera_file = path
                break
        
        if not camera_file:
            return jsonify({
                "status": "error",
                "message": "camera.json file not found"
            }), 404
        
        with open(camera_file, 'r', encoding='utf-8') as f:
            cameras = json.load(f)
        
        # Find the camera
        selected_camera = None
        for cam in cameras:
            if isinstance(cam, dict) and cam.get('camera_id') == camera_id:
                selected_camera = cam
                break
        
        if not selected_camera:
            return jsonify({
                "status": "error",
                "message": f"Camera with ID {camera_id} not found"
            }), 404
        
        # Load current config
        config_file = Path('camera_collector_config/cameras.json')
        if config_file.exists():
            with open(config_file, 'r', encoding='utf-8') as f:
                config_cameras = json.load(f)
        else:
            config_cameras = []
        
        # Check if camera already exists
        if any(cam.get('id') == camera_id for cam in config_cameras):
            return jsonify({
                "status": "success",
                "message": "Camera already in collection list"
            }), 200
        
        # Add camera to config
        config_cameras.append({
            'id': camera_id,
            'name': selected_camera.get('title') or selected_camera.get('code') or selected_camera.get('display_name', 'Unknown')
        })
        
        # Save config
        config_file.parent.mkdir(parents=True, exist_ok=True)
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config_cameras, f, indent=2, ensure_ascii=False)
        
        # Reload collector
        init_camera_collector()
        
        return jsonify({
            "status": "success",
            "message": "Camera added to collection list"
        }), 200
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Error adding camera: {e}"
        }), 500

@app.route('/api/camera/remove', methods=['POST'])
def camera_remove():
    """Remove camera from collection list."""
    try:
        data = request.json
        camera_id = data.get('camera_id')
        
        if not camera_id:
            return jsonify({
                "status": "error",
                "message": "camera_id is required"
            }), 400
        
        config_file = Path('camera_collector_config/cameras.json')
        if not config_file.exists():
            return jsonify({
                "status": "error",
                "message": "config/cameras.json file not found"
            }), 404
        
        with open(config_file, 'r', encoding='utf-8') as f:
            config_cameras = json.load(f)
        
        original_count = len(config_cameras)
        config_cameras = [cam for cam in config_cameras if cam.get('id') != camera_id]
        
        if len(config_cameras) == original_count:
            return jsonify({
                "status": "error",
                "message": f"Camera with ID {camera_id} not found in collection list"
            }), 404
        
        # Save config
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config_cameras, f, indent=2, ensure_ascii=False)
        
        # Reload collector
        init_camera_collector()
        
        return jsonify({
            "status": "success",
            "message": "Camera removed from collection list"
        }), 200
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Error removing camera: {e}"
        }), 500

@app.route('/api/camera/recent-images')
def camera_recent_images():
    """Get recent collected images."""
    try:
        if camera_collector_instance is None:
            return jsonify({"images": []}), 200
        
        limit = int(request.args.get('limit', 10))
        images = camera_collector_instance.get_recent_images(limit=limit)
        return jsonify({"images": images}), 200
    except Exception as e:
        return jsonify({"images": []}), 200

@app.route('/api/camera/images/<path:image_path>')
def camera_serve_image(image_path):
    """Serve camera images."""
    if camera_collector_instance is None:
        return jsonify({"error": "Camera collector not initialized"}), 500
    
    data_dir = camera_collector_instance.storage_path
    path_parts = image_path.split('/')
    if len(path_parts) < 2:
        return jsonify({"error": "Invalid image path"}), 400
    
    directory = os.path.join(data_dir, '/'.join(path_parts[:-1]))
    filename = path_parts[-1]
    
    if not os.path.exists(os.path.join(directory, filename)):
        return jsonify({"error": "Image not found"}), 404
    
    return send_from_directory(directory, filename)

# Pexels API Key (loaded from .env)
PEXELS_API_KEY = os.getenv('PEXELS_API_KEY', '')
PEXELS_OUTPUT_FOLDER = "pexels_traffic_dataset"
FRAMES_OUTPUT_ROOT = "dataset_extracted"
FRAME_STEP = 30
TARGET_WIDTH = 1280
TARGET_HEIGHT = 720
VALID_VIDEO_EXTENSIONS = ('.mp4', '.avi', '.mov', '.mkv', '.wmv')

def download_pexels_videos(query, num_videos):
    """Download videos from Pexels API and save to database."""
    try:
        if not os.path.exists(PEXELS_OUTPUT_FOLDER):
            os.makedirs(PEXELS_OUTPUT_FOLDER)

        headers = {
            "Authorization": PEXELS_API_KEY
        }

        url = f"https://api.pexels.com/videos/search?query={query}&per_page={num_videos}&orientation=landscape"
        response = requests.get(url, headers=headers)
        
        if response.status_code != 200:
            return {"success": False, "error": f"API error: {response.status_code}"}

        data = response.json()
        videos = data.get("videos", [])
        # Chỉ lấy số lượng video được yêu cầu
        videos = videos[:num_videos]
        total_videos = len(videos)

        count = 0
        saved_to_db = 0
        downloaded_files = []
        
        # Lưu progress vào file
        progress_file = os.path.join(PEXELS_OUTPUT_FOLDER, '.download_progress.json')
        
        for idx, video in enumerate(videos):
            video_id = video["id"]
            video_title = video.get("user", {}).get("name", "") + " - " + str(video_id)
            video_duration = video.get("duration", 0)
            video_url = video.get("url", f"https://www.pexels.com/video/{video_id}/")
            video_files = video["video_files"]

            best_link = None
            best_file = None
            min_diff = 99999

            # Tìm file video tốt nhất (gần 1280px nhất)
            for v_file in video_files:
                width = v_file["width"]
                diff = abs(width - TARGET_WIDTH)
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
                
                # Chuẩn bị dữ liệu để lưu vào database
                video_data = {
                    "id": str(video_id),
                    "title": video_title or f"Pexels Video {video_id}",
                    "url": video_url,
                    "file_path": file_path,
                    "duration": video_duration,
                    "fps": best_file.get("fps"),
                    "width": best_file.get("width"),
                    "height": best_file.get("height"),
                    "resolution": f"{best_file.get('width')}x{best_file.get('height')}" if best_file.get("width") and best_file.get("height") else None
                }
                
                # Lưu vào database
                if save_pexels_video_to_database(video_data, query, download_method='pexels'):
                    saved_to_db += 1
                
                count += 1
                
                # Cập nhật progress
                progress = int((count / total_videos) * 100) if total_videos > 0 else 0
                progress_data = {
                    "total": total_videos,
                    "downloaded": count,
                    "progress": progress,
                    "saved_to_db": saved_to_db
                }
                with open(progress_file, 'w', encoding='utf-8') as f:
                    json.dump(progress_data, f, ensure_ascii=False)
                
                time.sleep(1)
        
        # Xóa progress file sau khi hoàn thành
        if os.path.exists(progress_file):
            os.remove(progress_file)

        return {
            "success": True, 
            "count": count, 
            "saved_to_db": saved_to_db,
            "files": downloaded_files
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

def extract_frames_from_folder(input_folder, output_root=None, progress_file_path=None):
    """
    Extract frames from all videos in a folder.
    
    :param input_folder: Folder chứa các video cần extract frames
    :param output_root: Folder output (mặc định sẽ dùng FRAMES_OUTPUT_ROOT)
    :param progress_file_path: Đường dẫn file progress (mặc định sẽ tự động tạo)
    :return: Dictionary chứa kết quả
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
        
        # Tạo output folder nếu chưa có
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

            count = 0
            saved_count = 0

            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                if count % FRAME_STEP == 0:
                    try:
                        resized_frame = cv2.resize(frame, (TARGET_WIDTH, TARGET_HEIGHT), interpolation=cv2.INTER_AREA)
                        filename = f"{video_name}_fr{saved_count:05d}.jpg"
                        save_path = os.path.join(current_output_dir, filename)
                        cv2.imwrite(save_path, resized_frame)
                        saved_count += 1
                    except Exception as e:
                        pass

                count += 1

            cap.release()
            total_frames += saved_count
            processed_videos.append({"video": video_file, "frames": saved_count})
            
            # Cập nhật progress
            progress = int(((idx + 1) / total_videos) * 100) if total_videos > 0 else 0
            progress_data = {
                "total": total_videos,
                "processed": idx + 1,
                "progress": progress,
                "total_frames": total_frames
            }
            with open(progress_file_path, 'w', encoding='utf-8') as f:
                json.dump(progress_data, f, ensure_ascii=False)

        # Xóa progress file sau khi hoàn thành
        if os.path.exists(progress_file_path):
            os.remove(progress_file_path)

        return {"success": True, "total_frames": total_frames, "videos": processed_videos}
    except Exception as e:
        return {"success": False, "error": str(e)}

def extract_frames_from_videos():
    """Extract frames from all videos in PEXELS_OUTPUT_FOLDER."""
    return extract_frames_from_folder(PEXELS_OUTPUT_FOLDER, FRAMES_OUTPUT_ROOT)

@app.route('/api/pexels/download', methods=['POST'])
def pexels_download():
    """Download videos from Pexels."""
    try:
        data = request.json
        query = data.get('query', 'traffic')
        num_videos = int(data.get('num_videos', 10))

        def download_task():
            result = download_pexels_videos(query, num_videos)
            # Lưu kết quả vào file để frontend có thể đọc
            os.makedirs(PEXELS_OUTPUT_FOLDER, exist_ok=True)
            result_file = os.path.join(PEXELS_OUTPUT_FOLDER, '.download_result.json')
            with open(result_file, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            
            # Tự động extract frames sau khi download xong
            if result.get("success") and result.get("count", 0) > 0:
                extract_result = extract_frames_from_folder(PEXELS_OUTPUT_FOLDER, FRAMES_OUTPUT_ROOT)
                # Lưu kết quả extract frames
                extract_result_file = os.path.join(FRAMES_OUTPUT_ROOT, '.extract_result.json')
                os.makedirs(FRAMES_OUTPUT_ROOT, exist_ok=True)
                with open(extract_result_file, 'w', encoding='utf-8') as f:
                    json.dump(extract_result, f, ensure_ascii=False, indent=2)

        thread = threading.Thread(target=download_task)
        thread.daemon = True
        thread.start()

        return jsonify({
            "status": "success",
            "message": f"Đã bắt đầu tải {num_videos} video với từ khóa '{query}'"
        }), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/frames/extract', methods=['POST'])
def extract_frames():
    """Extract frames from videos."""
    try:
        def extract_task():
            result = extract_frames_from_videos()
            # Lưu kết quả vào file để frontend có thể đọc
            result_file = os.path.join(FRAMES_OUTPUT_ROOT, '.extract_result.json')
            os.makedirs(FRAMES_OUTPUT_ROOT, exist_ok=True)
            with open(result_file, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)

        thread = threading.Thread(target=extract_task)
        thread.daemon = True
        thread.start()

        return jsonify({
            "status": "success",
            "message": "Đã bắt đầu tạo frame từ video"
        }), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/pexels/result', methods=['GET'])
def pexels_download_result():
    """Get download result."""
    try:
        result_file = os.path.join(PEXELS_OUTPUT_FOLDER, '.download_result.json')
        if os.path.exists(result_file):
            with open(result_file, 'r', encoding='utf-8') as f:
                result = json.load(f)
            # Xóa file sau khi đọc
            os.remove(result_file)
            return jsonify(result), 200
        return jsonify({"success": False, "message": "Chưa có kết quả"}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/frames/result', methods=['GET'])
def extract_frames_result():
    """Get extract frames result (for Pexels)."""
    try:
        result_file = os.path.join(FRAMES_OUTPUT_ROOT, '.extract_result.json')
        if os.path.exists(result_file):
            with open(result_file, 'r', encoding='utf-8') as f:
                result = json.load(f)
            # Xóa file sau khi đọc
            os.remove(result_file)
            return jsonify(result), 200
        return jsonify({"success": False, "message": "Chưa có kết quả"}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/frames/youtube-result', methods=['GET'])
def youtube_extract_result():
    """Get extract frames result for YouTube videos."""
    try:
        result_file = os.path.join(FRAMES_OUTPUT_ROOT, '.youtube_extract_result.json')
        if os.path.exists(result_file):
            with open(result_file, 'r', encoding='utf-8') as f:
                result = json.load(f)
            # Xóa file sau khi đọc
            os.remove(result_file)
            return jsonify({"exists": True, "result": result}), 200
        return jsonify({"exists": False}), 200
    except Exception as e:
        return jsonify({"exists": False, "error": str(e)}), 500

if __name__ == '__main__':
    # Load Flask config from .env
    flask_host = os.getenv('FLASK_HOST', '127.0.0.1')
    flask_port = int(os.getenv('FLASK_PORT', 5000))
    flask_debug = os.getenv('FLASK_DEBUG', 'True').lower() == 'true'
    
    # Thử các port khác nhau nếu port mặc định bị lỗi
    import socket
    ports_to_try = [flask_port, 5001, 8080, 3000, 8000]
    port = None
    
    for p in ports_to_try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.bind((flask_host, p))
            sock.close()
            port = p
            break
        except OSError:
            continue
    
    if port is None:
        print("❌ Không tìm thấy port trống. Vui lòng đóng các ứng dụng đang sử dụng port hoặc chạy với quyền Administrator.")
        exit(1)
    
    if port != flask_port:
        print(f"⚠️ Port {flask_port} không khả dụng, sử dụng port {port}")
    
    print(f"🚀 Server đang chạy tại: http://{flask_host}:{port}")
    app.run(debug=flask_debug, host=flask_host, port=port)

