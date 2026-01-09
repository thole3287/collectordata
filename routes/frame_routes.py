from flask import Blueprint, jsonify, request
import services.minio_service as minio_service
import services.video_service as video_service
import services.database as db_service
import threading
import os
import json
from bson import ObjectId

frame_bp = Blueprint('frame', __name__)

FRAMES_OUTPUT_ROOT = "dataset_extracted"
PEXELS_OUTPUT_FOLDER = "pexels_traffic_dataset"

@frame_bp.route('/api/frames/extract', methods=['POST'])
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

@frame_bp.route('/api/frames/result', methods=['GET'])
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

@frame_bp.route('/api/frames/youtube-result', methods=['GET'])
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

@frame_bp.route('/api/frames/<frame_id>/url', methods=['GET'])
def get_frame_presigned_url(frame_id):
    try:

        
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
