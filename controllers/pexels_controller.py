from flask import jsonify, request
import threading
import os
import json
import services.pexels_service as pexels_service
import extensions

def pexels_download():
    data = request.json
    query = data.get('query', 'traffic')
    num_videos = int(data.get('num_videos', 10))
    
    def download_task():
        result = pexels_service.download_pexels_videos(query, num_videos, extensions.PEXELS_API_KEY)
        
        # Save results for frontend legacy check
        os.makedirs(extensions.PEXELS_OUTPUT_FOLDER, exist_ok=True)
        result_file = os.path.join(extensions.PEXELS_OUTPUT_FOLDER, '.download_result.json')
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

def pexels_download_result():
    try:
        result_file = os.path.join(extensions.PEXELS_OUTPUT_FOLDER, '.download_result.json')
        if os.path.exists(result_file):
            with open(result_file, 'r', encoding='utf-8') as f:
                result = json.load(f)
            os.remove(result_file)
            return jsonify(result), 200
        return jsonify({"success": False, "message": "Chưa có kết quả"}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
