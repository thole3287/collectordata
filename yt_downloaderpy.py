import yt_dlp
import json
import os
from datetime import datetime
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, DuplicateKeyError
from bson import ObjectId
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# ==================== CẤU HÌNH DATABASE ====================
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': int(os.getenv('DB_PORT', 27017)),
    'database': os.getenv('DB_NAME', 'data_collection'),
    'username': os.getenv('DB_USER', ''),
    'password': os.getenv('DB_PASSWORD', ''),
}

# ==================== HÀM KẾT NỐI DATABASE ====================
def get_db_connection():
    """Tạo kết nối đến MongoDB database"""
    try:
        if DB_CONFIG['username'] and DB_CONFIG['password']:
            connection_string = f"mongodb://{DB_CONFIG['username']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/"
        else:
            connection_string = f"mongodb://{DB_CONFIG['host']}:{DB_CONFIG['port']}/"
        
        client = MongoClient(connection_string)
        # Test connection
        client.admin.command('ping')
        db = client[DB_CONFIG['database']]
        return db
    except (ConnectionFailure, Exception) as e:
        print(f"Lỗi kết nối database: {e}")
        return None

def save_to_database(video_data, download_method='keyword'):
    """
    Lưu thông tin video vào MongoDB database
    
    :param video_data: Dictionary chứa thông tin video
    :param download_method: 'keyword' hoặc 'url'
    :return: True nếu thành công, False nếu thất bại
    """
    db = get_db_connection()
    if db is None:
        return False
    
    try:
        collection = db['downloaded_videos']
        
        # Kiểm tra xem video đã tồn tại chưa
        existing = collection.find_one({'video_id': video_data['id']})
        
        if existing:
            print(f"  ⚠ Video {video_data['id']} đã tồn tại trong database, bỏ qua...")
            return False
        
        # Parse resolution để lấy width và height
        width = video_data.get('width')
        height = video_data.get('height')
        if not width or not height:
            resolution = video_data.get('resolution', '')
            if resolution and 'x' in resolution:
                try:
                    width, height = map(int, resolution.split('x'))
                except:
                    width = height = None
        
        # Upload video lên MinIO nếu có file_path và MinIO được cấu hình
        minio_key = None
        minio_bucket = None
        file_path = video_data.get('file_path')
        storage_refs_data = {}  # Lưu thông tin frames
        
        # Kiểm tra cấu hình có cho phép upload lên MinIO không
        should_upload_minio = os.getenv('UPLOAD_TO_MINIO', 'true').lower() == 'true'
        
        if file_path and os.path.exists(file_path):
            if should_upload_minio:
                try:
                    import services.minio_service as minio_helper
                    minio_endpoint = os.getenv('MINIO_ENDPOINT', 'localhost')
                    
                    if minio_endpoint:
                        # Tạo object key: platform/video_id.mp4
                        video_id = video_data['id']
                        platform = video_data.get('platform', 'youtube')
                        file_ext = os.path.splitext(file_path)[1] or '.mp4'
                        object_key = f"{platform}/{video_id}{file_ext}"
                        
                        # Upload lên MinIO
                        result = minio_helper.upload_and_get_key(
                            file_path=file_path,
                            bucket_name=minio_helper.MINIO_BUCKET_VIDEOS,
                            custom_path=object_key,
                            content_type='video/mp4'
                        )
                        
                        if result.get('success'):
                            minio_key = result['key']
                            minio_bucket = result['bucket']
                            print(f"  ✓ Đã upload video lên MinIO: {minio_bucket}/{minio_key}")
                            
                            # Extract frames và upload lên MinIO
                            try:
                                # Lấy FPS từ video metadata
                                video_fps = video_data.get('fps')
                                if not video_fps:
                                    # Nếu không có trong metadata, sẽ tự động detect từ video
                                    video_fps = None
                                
                                frames_result = minio_helper.extract_and_upload_frames(
                                    video_path=file_path,
                                    video_id=video_id,
                                    platform=platform,
                                    fps=video_fps,  # FPS của video (tự động tính frame_step)
                                    interval_seconds=None,  # Đọc từ env FRAME_INTERVAL_SECONDS (mặc định 1.0 giây)
                                    target_width=1280,
                                    target_height=720,
                                    db=db  # Truyền db để lưu metadata frames vào MongoDB
                                )
                                
                                if frames_result.get('success'):
                                    print(f"  ✓ Đã extract và upload {frames_result['frames_uploaded']} frames lên MinIO")
                                    # Lưu frame keys vào storage_refs_data
                                    storage_refs_data['frames_bucket'] = frames_result['bucket']
                                    storage_refs_data['frame_keys'] = frames_result['frame_keys']
                                    storage_refs_data['frames_count'] = frames_result['frames_uploaded']
                                    
                                    # --- XÓA FILE LOCAL SAU KHI UPLOAD THÀNH CÔNG ---
                                    # Chỉ xóa khi cả video và frames đều đã lên MinIO an toàn (hoặc ít nhất là video)
                                    # Ở đây chọn phương án: Video lên OK là có thể xóa, frames đã extract xong.
                                    try:
                                        os.remove(file_path)
                                        print(f"  ✓ Đã xóa file local: {file_path}")
                                    except Exception as e:
                                        print(f"  ⚠ Không thể xóa file local: {e}")
                                else:
                                    print(f"  ⚠ Không thể extract frames: {frames_result.get('error')}")
                            except Exception as e:
                                import traceback
                                print(f"  ⚠ Lỗi khi extract frames: {e}")
                                print(f"  ⚠ Traceback: {traceback.format_exc()}")
                except Exception as e:
                    import traceback
                    print(f"  ⚠ Không thể upload lên MinIO: {e}")
                    print(f"  ⚠ Traceback: {traceback.format_exc()}")
            else:
                print(f"  ℹ Upload MinIO đang TẮT (UPLOAD_TO_MINIO={should_upload_minio}). Giữ file tại local.")
        
        # Tạo document theo cấu trúc MongoDB
        document = {
            'video_id': video_data['id'],
            'title': video_data['title'],
            'url': video_data['url'],
            'file_path': file_path,  # Giữ lại local path
            'media_type': 'mp4',  # Mặc định mp4
            'metadata': {
                'duration': video_data.get('duration'),
                'fps': video_data.get('fps'),
                'width': width,
                'height': height,
                'resolution': video_data.get('resolution') or (f"{width}x{height}" if width and height else None)
            },
            'platform': video_data.get('platform', 'youtube'),
            'keyword': video_data.get('keyword'),
            'download_method': download_method,
            'downloaded_at': datetime.now(),
            'created_at': datetime.now()
        }
        
        # Thêm MinIO storage reference nếu có
        if minio_key:
            document['storage_refs'] = {
                'bucket': minio_bucket,
                'key': minio_key
            }
            # Thêm frame references nếu có
            if storage_refs_data.get('frames_bucket'):
                document['storage_refs'].update({
                    'frames_bucket': storage_refs_data['frames_bucket'],
                    'frame_keys': storage_refs_data.get('frame_keys', []),
                    'frames_count': storage_refs_data.get('frames_count', 0)
                })
        
        collection.insert_one(document)
        print(f"  ✓ Đã lưu video {video_data['id']} vào database")
        return True
        
    except DuplicateKeyError:
        print(f"  ⚠ Video {video_data['id']} đã tồn tại trong database, bỏ qua...")
        return False
    except Exception as e:
        print(f"  ✗ Lỗi lưu vào database: {e}")
        return False

# ==================== HÀM XỬ LÝ VIDEO CHUNG ====================
def extract_video_info(entry, keyword=None):
    """
    Trích xuất thông tin video từ entry của yt-dlp
    
    :param entry: Dictionary chứa thông tin từ yt-dlp
    :param keyword: Từ khóa (nếu có)
    :return: Dictionary chứa thông tin video
    """
    if not entry:
        return None
    
    video_id = entry.get("id")
    title = entry.get("title")
    url = entry.get("webpage_url") or f"https://www.youtube.com/watch?v={video_id}" if video_id else None
    
    # Thông tin file tải về
    file_path = None
    try:
        req_dl = entry.get("requested_downloads") or entry.get("requested_formats")
        if req_dl:
            first = req_dl[0] if isinstance(req_dl, list) else req_dl
            file_path = first.get("filepath") or first.get("_filename")
    except Exception:
        file_path = None
    
    if not file_path:
        file_path = entry.get("filepath") or entry.get("_filename")
    
    if file_path:
        file_path = os.path.abspath(file_path)
    
    duration = entry.get("duration")
    fps = entry.get("fps")
    width = entry.get("width")
    height = entry.get("height")
    resolution = entry.get("resolution") or (
        f"{width}x{height}" if width and height else None
    )
    
    if not video_id or not title or not url:
        return None
    
    return {
        "id": video_id,
        "title": title,
        "url": url,
        "file_path": file_path,
        "duration": duration,
        "fps": fps,
        "width": width,
        "height": height,
        "resolution": resolution,
        "platform": "youtube",
        "downloaded_at": datetime.now().isoformat(),
        "keyword": keyword,
    }

# ==================== CẤU HÌNH YT-DLP ====================
def get_download_directory():
    """
    Tạo và trả về thư mục để lưu video
    """
    download_dir = os.path.join(os.getcwd(), 'downloads')
    os.makedirs(download_dir, exist_ok=True)
    return download_dir

def get_ydl_options():
    """Trả về cấu hình mặc định cho yt-dlp"""
    download_dir = get_download_directory()
    
    return {
        'format': 'bestvideo[height<=1080]/best[height<=1080]/best',
        'merge_output_format': 'mp4',
        'postprocessors': [
            {'key': 'FFmpegVideoConvertor', 'preferedformat': 'mp4'},
        ],
        'outtmpl': os.path.join(download_dir, '%(title)s.%(ext)s'),
        'noplaylist': True,
        'quiet': False,
        'ignoreerrors': True,
    }

# ==================== KIỂM TRA VIDEO ĐÃ TỒN TẠI ====================
def check_video_exists(video_id):
    """
    Kiểm tra xem video đã tồn tại trong database chưa
    
    :param video_id: ID video YouTube
    :return: True nếu đã tồn tại, False nếu chưa
    """
    db = get_db_connection()
    if db is None:
        return False
    
    try:
        collection = db['downloaded_videos']
        exists = collection.find_one({'video_id': video_id}) is not None
        return exists
    except Exception as e:
        print(f"  ⚠ Lỗi kiểm tra video: {e}")
        return False

# ==================== TẢI VIDEO THEO TỪ KHÓA ====================
def download_by_keyword(keyword, num_videos=1):
    """
    Hàm tìm kiếm và tải video từ YouTube theo từ khóa.
    Tự động bỏ qua video đã tồn tại trong database.
    
    :param keyword: Từ khóa tìm kiếm
    :param num_videos: Số lượng video muốn tải về (mặc định là 1)
    :return: List các video đã tải thành công (không tính video đã tồn tại)
    """
    print(f"\n--> Đang tìm kiếm và chuẩn bị tải {num_videos} video cho từ khóa: '{keyword}'...")
    
    # Tăng số lượng tìm kiếm để bù cho video đã tồn tại
    search_multiplier = 2  # Tìm nhiều hơn để có đủ video mới
    search_count = num_videos * search_multiplier
    
    ydl_opts = get_ydl_options()
    search_query = f"ytsearch{search_count}:{keyword}"
    downloaded_videos = []
    skipped_count = 0
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Lấy thông tin video trước (không tải ngay)
            info = ydl.extract_info(search_query, download=False)
        
        entries = info.get("entries", []) if isinstance(info, dict) else []
        
        for entry in entries:
            if not entry:
                continue
                
            video_id = entry.get("id")
            if not video_id:
                continue
            
            # Kiểm tra video đã tồn tại chưa TRƯỚC KHI TẢI
            if check_video_exists(video_id):
                skipped_count += 1
                print(f"  ⏭ Video {video_id} đã tồn tại, bỏ qua...")
                continue
            
            # Chỉ tải nếu chưa đủ số lượng video cần
            if len(downloaded_videos) >= num_videos:
                break
            
            # Tải video này
            try:
                print(f"  📥 Đang tải video {video_id}...")
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    video_info_dict = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=True)
                
                video_info = extract_video_info(video_info_dict, keyword=keyword)
                if video_info:
                    # Lưu vào database
                    if save_to_database(video_info, download_method='keyword'):
                        downloaded_videos.append(video_info)
                        print(f"  ✓ Đã tải và lưu video {video_id}")
                    else:
                        print(f"  ⚠ Không thể lưu video {video_id}")
            except Exception as e:
                print(f"  ✗ Lỗi khi tải video {video_id}: {e}")
                continue
        
        print(f"\n--> Hoàn tất: Đã tải {len(downloaded_videos)} video mới, bỏ qua {skipped_count} video đã tồn tại")
        return downloaded_videos
        
    except Exception as e:
        print(f"✗ Đã xảy ra lỗi: {e}")
        import traceback
        traceback.print_exc()
        return []

# ==================== TẢI VIDEO THEO URL ====================
def download_by_url(url):
    """
    Tải video trực tiếp từ URL YouTube
    
    :param url: URL video YouTube (vd: https://www.youtube.com/watch?v=...)
    :return: Dictionary chứa thông tin video đã tải
    """
    print(f"\n--> Đang tải video từ URL: {url}...")
    
    ydl_opts = get_ydl_options()
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Lấy thông tin video trước
            info = ydl.extract_info(url, download=False)
            
            # Kiểm tra xem video đã tồn tại chưa
            video_id = info.get("id")
            if check_video_exists(video_id):
                print(f"  ⚠ Video {video_id} đã tồn tại trong database!")
                return None
            
            # Tải video
            print("  --> Đang tải video...")
            info = ydl.extract_info(url, download=True)
            
            # Trích xuất thông tin
            video_info = extract_video_info(info, keyword=None)
            
            if video_info:
                # Lưu vào database
                save_to_database(video_info, download_method='url')
                print(f"\n--> Hoàn tất tải xuống video: {video_info['title']}")
                return video_info
            else:
                print("✗ Không thể trích xuất thông tin video")
                return None
                
    except Exception as e:
        print(f"✗ Đã xảy ra lỗi: {e}")
        import traceback
        traceback.print_exc()
        return None

# ==================== TẢI NHIỀU VIDEO TỪ DANH SÁCH URL ====================
def download_by_urls(urls):
    """
    Tải nhiều video từ danh sách URL
    
    :param urls: List các URL video
    :return: List các video đã tải thành công
    """
    downloaded = []
    for url in urls:
        video = download_by_url(url)
        if video:
            downloaded.append(video)
    return downloaded

# ==================== TRA CỨU VIDEO THEO TỪ KHÓA ====================
def search_videos_by_keyword(keyword):
    """
    Tìm kiếm video trong database theo từ khóa
    
    :param keyword: Từ khóa cần tìm
    :return: List các video tìm được
    """
    db = get_db_connection()
    if db is None:
        return []
    
    try:
        collection = db['downloaded_videos']
        # Tìm kiếm với regex không phân biệt hoa thường
        query = {'keyword': {'$regex': keyword, '$options': 'i'}}
        results = list(collection.find(query).sort('downloaded_at', -1))
        
        # Chuyển đổi ObjectId thành string và xử lý datetime
        for result in results:
            result['_id'] = str(result['_id'])
            if 'downloaded_at' in result and isinstance(result['downloaded_at'], datetime):
                result['downloaded_at'] = result['downloaded_at'].isoformat()
            if 'created_at' in result and isinstance(result['created_at'], datetime):
                result['created_at'] = result['created_at'].isoformat()
        
        return results
    except Exception as e:
        print(f"Lỗi tìm kiếm: {e}")
        return []

# ==================== LẤY KEYWORDS TỪ DATABASE ====================
def get_keywords_from_db(active_only=True, status_filter=None):
    """
    Lấy danh sách keywords từ database
    
    :param active_only: Chỉ lấy keywords đang active
    :param status_filter: Lọc theo status ('pending', 'processing', 'completed', 'failed', None = tất cả)
    :return: List các keywords
    """
    db = get_db_connection()
    if db is None:
        print("✗ Không thể kết nối database")
        return []
    
    try:
        collection = db['keywords']
        
        # Xây dựng query
        query = {}
        if active_only:
            query['is_active'] = True
        
        if status_filter:
            query['status'] = status_filter
        
        keywords = list(collection.find(query).sort('created_at', 1))
        
        # Chuyển đổi ObjectId thành string và xử lý datetime
        for kw in keywords:
            kw['_id'] = str(kw['_id'])
            if 'last_downloaded_at' in kw and kw['last_downloaded_at'] and isinstance(kw['last_downloaded_at'], datetime):
                kw['last_downloaded_at'] = kw['last_downloaded_at'].isoformat()
            if 'created_at' in kw and isinstance(kw['created_at'], datetime):
                kw['created_at'] = kw['created_at'].isoformat()
            if 'updated_at' in kw and isinstance(kw['updated_at'], datetime):
                kw['updated_at'] = kw['updated_at'].isoformat()
        
        return keywords
    except Exception as e:
        print(f"✗ Lỗi khi lấy keywords từ database: {e}")
        return []

# ==================== TỰ ĐỘNG TẢI VIDEO TỪ KEYWORDS ====================
def auto_download_from_keywords(active_only=True, status_filter='pending'):
    """
    Tự động tải video từ tất cả keywords trong database
    
    :param active_only: Chỉ tải keywords đang active
    :param status_filter: Chỉ tải keywords có status này (None = tất cả)
    """
    print("=" * 60)
    print("  YOUTUBE DOWNLOADER - Auto Download từ Keywords")
    print("=" * 60)
    
    # Lấy keywords từ database
    keywords = get_keywords_from_db(active_only=active_only, status_filter=status_filter)
    
    if not keywords:
        print("\n  ⚠ Không tìm thấy keyword nào để tải!")
        print("  Hãy thêm keywords vào database hoặc kiểm tra filter")
        print("=" * 60)
        return
    
    print(f"\n  📋 Tìm thấy {len(keywords)} keyword(s) để tải:")
    for kw in keywords:
        print(f"     - {kw['keyword']} (Số video: {kw['num_videos']}, Status: {kw['status']})")
    
    print("\n  🚀 Bắt đầu tải video...")
    print("-" * 60)
    
    success_count = 0
    failed_count = 0
    
    for kw in keywords:
        keyword = kw['keyword']
        num_videos = kw['num_videos']
        keyword_id = kw['_id']  # MongoDB sử dụng _id thay vì id
        
        # Chuyển đổi keyword_id thành ObjectId nếu là string
        if isinstance(keyword_id, str):
            keyword_obj_id = ObjectId(keyword_id)
        else:
            keyword_obj_id = keyword_id
        
        print(f"\n  📥 Đang xử lý: {keyword}")
        
        # Cập nhật status thành processing
        db = get_db_connection()
        if db is not None:
            try:
                collection = db['keywords']
                collection.update_one(
                    {'_id': keyword_obj_id},
                    {'$set': {'status': 'processing', 'updated_at': datetime.now()}}
                )
            except:
                pass
        
        try:
            # Tải video
            videos = download_by_keyword(keyword, num_videos)
            
            if videos:
                # Cập nhật status và số lượng đã tải
                db = get_db_connection()
                if db is not None:
                    try:
                        collection = db['keywords']
                        collection.update_one(
                            {'_id': keyword_obj_id},
                            {
                                '$set': {
                                    'status': 'completed',
                                    'last_downloaded_at': datetime.now(),
                                    'updated_at': datetime.now()
                                },
                                '$inc': {'total_downloaded': len(videos)}
                            }
                        )
                        success_count += 1
                        print(f"  ✓ Hoàn thành: {len(videos)} video(s) đã tải")
                    except Exception as e:
                        print(f"  ⚠ Lỗi cập nhật database: {e}")
            else:
                # Không tải được video nào
                db = get_db_connection()
                if db is not None:
                    try:
                        collection = db['keywords']
                        collection.update_one(
                            {'_id': keyword_obj_id},
                            {'$set': {'status': 'failed', 'updated_at': datetime.now()}}
                        )
                        failed_count += 1
                        print(f"  ✗ Không tải được video nào")
                    except:
                        pass
        except Exception as e:
            print(f"  ✗ Lỗi: {e}")
            # Cập nhật status failed
            db = get_db_connection()
            if db is not None:
                try:
                    collection = db['keywords']
                    collection.update_one(
                        {'_id': keyword_obj_id},
                        {'$set': {'status': 'failed', 'updated_at': datetime.now()}}
                    )
                    failed_count += 1
                except:
                    pass
    
    print("\n" + "=" * 60)
    print(f"  📊 Tổng kết:")
    print(f"     ✓ Thành công: {success_count}")
    print(f"     ✗ Thất bại: {failed_count}")
    print(f"     📋 Tổng cộng: {len(keywords)}")
    print("=" * 60)

# ==================== PHẦN CHẠY CHƯƠNG TRÌNH ====================
# Lưu ý: Để sử dụng với giao diện web, chạy file app.py
# Phần này dùng để chạy tự động từ command line hoặc cronjob
if __name__ == "__main__":
    import sys
    
    # Kiểm tra tham số command line
    active_only = True
    status_filter = 'pending'  # Mặc định chỉ tải keywords pending
    
    if len(sys.argv) > 1:
        if '--all-status' in sys.argv:
            status_filter = None  # Tải tất cả status
        if '--include-inactive' in sys.argv:
            active_only = False  # Bao gồm cả keywords không active
    
    # Chạy tự động tải từ keywords
    auto_download_from_keywords(active_only=active_only, status_filter=status_filter)
    
    print("\n  💡 Mẹo:")
    print("     - Chạy với --all-status để tải tất cả keywords (không chỉ pending)")
    print("     - Chạy với --include-inactive để bao gồm keywords không active")
    print("     - Có thể setup cronjob để tự động chạy định kỳ")
    print("=" * 60)
