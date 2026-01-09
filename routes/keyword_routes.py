from flask import Blueprint, jsonify, request
import services.keyword_service as keyword_service
import services.video_service as video_service
import yt_downloaderpy as yt
import threading
import os
import json
from datetime import datetime

keyword_bp = Blueprint('keyword', __name__)
FRAMES_OUTPUT_ROOT = "dataset_extracted"

@keyword_bp.route('/api/keywords', methods=['GET'])
def get_keywords():
    active_only = request.args.get('active_only', 'false').lower() == 'true'
    result = keyword_service.get_all_keywords(active_only)
    if 'error' in result:
        return jsonify(result), 500
    return jsonify({'keywords': result})

@keyword_bp.route('/api/keywords', methods=['POST'])
def create_keyword():
    response = keyword_service.create_keyword(request.json)
    if 'error' in response:
        return jsonify(response), 400
    return jsonify(response)

@keyword_bp.route('/api/keywords/<keyword_id>', methods=['PUT'])
def update_keyword(keyword_id):
    response = keyword_service.update_keyword(keyword_id, request.json)
    if 'error' in response:
        return jsonify(response), 400 if response['error'] != 'Keyword ID không hợp lệ' else 400
    return jsonify(response), 200

@keyword_bp.route('/api/keywords/<keyword_id>', methods=['DELETE'])
def delete_keyword(keyword_id):
    response = keyword_service.delete_keyword(keyword_id)
    if 'error' in response:
        return jsonify(response), 404
    return jsonify(response)

@keyword_bp.route('/api/keywords/<keyword_id>/download', methods=['POST'])
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
