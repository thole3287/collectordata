from flask import jsonify, request
import threading
import os
import json
import base64
from datetime import datetime
import services.database as db_service
import services.keyword_service as keyword_service
import services.video_service as video_service
import services.yt_service as yt
import extensions

def get_keywords():
    active_only = request.args.get('active_only', 'false').lower() == 'true'
    result = keyword_service.get_all_keywords(active_only)
    if 'error' in result:
        return jsonify(result), 500
    return jsonify({'keywords': result})

def create_keyword():
    response = keyword_service.create_keyword(request.json)
    if 'error' in response:
        return jsonify(response), 400
    return jsonify(response)

def update_keyword(keyword_id):
    response = keyword_service.update_keyword(keyword_id, request.json)
    if 'error' in response:
        return jsonify(response), 400 if response['error'] != 'Keyword ID không hợp lệ' else 400
    return jsonify(response), 200

def delete_keyword(keyword_id):
    response = keyword_service.delete_keyword(keyword_id)
    if 'error' in response:
        return jsonify(response), 404
    return jsonify(response)

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
                downloads_folder = extensions.DOWNLOADS_FOLDER
                if os.path.exists(downloads_folder):
                    result = video_service.extract_frames_from_folder(downloads_folder)
                    extract_result_file = os.path.join(extensions.FRAMES_OUTPUT_ROOT, '.youtube_extract_result.json')
                    os.makedirs(extensions.FRAMES_OUTPUT_ROOT, exist_ok=True)
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
