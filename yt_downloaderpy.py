import yt_dlp
import json
import os
from datetime import datetime
import mysql.connector
from mysql.connector import Error

# ==================== CẤU HÌNH DATABASE ====================
DB_CONFIG = {
    'host': 'localhost',
    'database': 'data_collection',
    'user': 'root',
    'password': '',  # Thay đổi mật khẩu MySQL của bạn ở đây
    'charset': 'utf8mb4',
    'collation': 'utf8mb4_unicode_ci'
}

# ==================== HÀM KẾT NỐI DATABASE ====================
def get_db_connection():
    """Tạo kết nối đến MySQL database"""
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        if connection.is_connected():
            return connection
    except Error as e:
        print(f"Lỗi kết nối database: {e}")
        return None

def save_to_database(video_data, download_method='keyword'):
    """
    Lưu thông tin video vào MySQL database
    
    :param video_data: Dictionary chứa thông tin video
    :param download_method: 'keyword' hoặc 'url'
    :return: True nếu thành công, False nếu thất bại
    """
    connection = get_db_connection()
    if not connection:
        return False
    
    try:
        cursor = connection.cursor()
        
        # Kiểm tra xem video đã tồn tại chưa
        check_query = "SELECT id FROM downloaded_videos WHERE video_id = %s"
        cursor.execute(check_query, (video_data['id'],))
        existing = cursor.fetchone()
        
        if existing:
            print(f"  ⚠ Video {video_data['id']} đã tồn tại trong database, bỏ qua...")
            return False
        
        # Insert video mới
        insert_query = """
        INSERT INTO downloaded_videos 
        (video_id, title, url, file_path, duration, fps, width, height, 
         resolution, platform, keyword, download_method, downloaded_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        
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
        
        values = (
            video_data['id'],
            video_data['title'],
            video_data['url'],
            video_data.get('file_path'),
            video_data.get('duration'),
            video_data.get('fps'),
            width,
            height,
            video_data.get('resolution'),
            video_data.get('platform', 'youtube'),
            video_data.get('keyword'),
            download_method,
            datetime.now()
        )
        
        cursor.execute(insert_query, values)
        connection.commit()
        print(f"  ✓ Đã lưu video {video_data['id']} vào database")
        return True
        
    except Error as e:
        print(f"  ✗ Lỗi lưu vào database: {e}")
        connection.rollback()
        return False
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

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
    connection = get_db_connection()
    if not connection:
        return False
    
    try:
        cursor = connection.cursor()
        check_query = "SELECT id FROM downloaded_videos WHERE video_id = %s"
        cursor.execute(check_query, (video_id,))
        exists = cursor.fetchone() is not None
        cursor.close()
        connection.close()
        return exists
    except Error as e:
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
            connection = get_db_connection()
            if connection:
                cursor = connection.cursor()
                check_query = "SELECT id FROM downloaded_videos WHERE video_id = %s"
                cursor.execute(check_query, (video_id,))
                if cursor.fetchone():
                    print(f"  ⚠ Video {video_id} đã tồn tại trong database!")
                    cursor.close()
                    connection.close()
                    return None
                cursor.close()
                connection.close()
            
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
    connection = get_db_connection()
    if not connection:
        return []
    
    try:
        cursor = connection.cursor(dictionary=True)
        query = "SELECT * FROM downloaded_videos WHERE keyword LIKE %s ORDER BY downloaded_at DESC"
        cursor.execute(query, (f'%{keyword}%',))
        results = cursor.fetchall()
        return results
    except Error as e:
        print(f"Lỗi tìm kiếm: {e}")
        return []
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

# ==================== LẤY KEYWORDS TỪ DATABASE ====================
def get_keywords_from_db(active_only=True, status_filter=None):
    """
    Lấy danh sách keywords từ database
    
    :param active_only: Chỉ lấy keywords đang active
    :param status_filter: Lọc theo status ('pending', 'processing', 'completed', 'failed', None = tất cả)
    :return: List các keywords
    """
    connection = get_db_connection()
    if not connection:
        print("✗ Không thể kết nối database")
        return []
    
    try:
        cursor = connection.cursor(dictionary=True)
        
        query = "SELECT * FROM keywords WHERE 1=1"
        params = []
        
        if active_only:
            query += " AND is_active = TRUE"
        
        if status_filter:
            query += " AND status = %s"
            params.append(status_filter)
        
        query += " ORDER BY created_at ASC"
        
        cursor.execute(query, params)
        keywords = cursor.fetchall()
        
        cursor.close()
        connection.close()
        
        return keywords
    except Error as e:
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
        keyword_id = kw['id']
        
        print(f"\n  📥 Đang xử lý: {keyword}")
        
        # Cập nhật status thành processing
        connection = get_db_connection()
        if connection:
            try:
                cursor = connection.cursor()
                cursor.execute("UPDATE keywords SET status = 'processing' WHERE id = %s", (keyword_id,))
                connection.commit()
                cursor.close()
                connection.close()
            except:
                pass
        
        try:
            # Tải video
            videos = download_by_keyword(keyword, num_videos)
            
            if videos:
                # Cập nhật status và số lượng đã tải
                connection = get_db_connection()
                if connection:
                    try:
                        cursor = connection.cursor()
                        cursor.execute("""
                            UPDATE keywords 
                            SET status = 'completed', 
                                total_downloaded = total_downloaded + %s,
                                last_downloaded_at = NOW()
                            WHERE id = %s
                        """, (len(videos), keyword_id))
                        connection.commit()
                        cursor.close()
                        connection.close()
                        success_count += 1
                        print(f"  ✓ Hoàn thành: {len(videos)} video(s) đã tải")
                    except Exception as e:
                        print(f"  ⚠ Lỗi cập nhật database: {e}")
            else:
                # Không tải được video nào
                connection = get_db_connection()
                if connection:
                    try:
                        cursor = connection.cursor()
                        cursor.execute("UPDATE keywords SET status = 'failed' WHERE id = %s", (keyword_id,))
                        connection.commit()
                        cursor.close()
                        connection.close()
                        failed_count += 1
                        print(f"  ✗ Không tải được video nào")
                    except:
                        pass
        except Exception as e:
            print(f"  ✗ Lỗi: {e}")
            # Cập nhật status failed
            connection = get_db_connection()
            if connection:
                try:
                    cursor = connection.cursor()
                    cursor.execute("UPDATE keywords SET status = 'failed' WHERE id = %s", (keyword_id,))
                    connection.commit()
                    cursor.close()
                    connection.close()
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
