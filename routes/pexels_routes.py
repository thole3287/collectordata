from flask import Blueprint, jsonify, request
import services.pexels_service as pexels_service
import services.video_service as video_service
import threading
import os
import json

pexels_bp = Blueprint('pexels', __name__)

PEXELS_OUTPUT_FOLDER = "pexels_traffic_dataset"

@pexels_bp.route('/api/pexels/download', methods=['POST'])
def pexels_download():
    # Note: PEXELS_API_KEY needs to be available. We can get it from env here.
    PEXELS_API_KEY = os.getenv('PEXELS_API_KEY', '')
    
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

@pexels_bp.route('/api/pexels/result', methods=['GET'])
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
