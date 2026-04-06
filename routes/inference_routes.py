import os
import uuid
from flask import Blueprint, request, jsonify
from werkzeug.utils import secure_filename
from datetime import datetime, timezone

import services.database as db_service
from services.kafka_producer import kafka_queue

inference_bp = Blueprint('inference_bp', __name__)

# Absolute paths or relative paths for storage
UPLOAD_FOLDER = os.path.join(os.getcwd(), 'static', 'inference_results', 'input')
OUTPUT_FOLDER = os.path.join(os.getcwd(), 'static', 'inference_results', 'output')

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# Allowed extensions
ALLOWED_EXTENSIONS = {'mp4', 'avi', 'mov', 'mkv'}

# ─── Fake Camera List ─────────────────────────────────────────────────────────
CAMERA_LIST = [
    {"camera_id": "CAM_001", "camera_name": "QL1 - Ngã tư Hàng Xanh",         "location": "TP. Hồ Chí Minh"},
    {"camera_id": "CAM_002", "camera_name": "QL13 - Vòng xoay Bình Phước",     "location": "TP. Hồ Chí Minh"},
    {"camera_id": "CAM_003", "camera_name": "DT743 - Ngã tư An Phú",           "location": "Bình Dương"},
    {"camera_id": "CAM_004", "camera_name": "QL1 - Ngã ba Trung Lương",        "location": "Tiền Giang"},
    {"camera_id": "CAM_005", "camera_name": "QL51 - Cầu Đồng Nai",            "location": "Đồng Nai"},
    {"camera_id": "CAM_006", "camera_name": "QL22 - Ngã tư An Sương",          "location": "TP. Hồ Chí Minh"},
    {"camera_id": "CAM_007", "camera_name": "QL1A - Cầu vượt Bình Điền",      "location": "TP. Hồ Chí Minh"},
    {"camera_id": "CAM_008", "camera_name": "DT747 - Ngã tư Thủ Dầu Một",     "location": "Bình Dương"},
    {"camera_id": "CAM_009", "camera_name": "QL14 - Ngã tư Chơn Thành",       "location": "Bình Phước"},
    {"camera_id": "CAM_010", "camera_name": "QL1A - Cầu Bình Triệu",          "location": "TP. Hồ Chí Minh"},
]
# ─────────────────────────────────────────────────────────────────────────────

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@inference_bp.route('/api/inference/cameras', methods=['GET'])
def get_camera_list():
    """Trả về danh sách camera giả định."""
    return jsonify({"success": True, "cameras": CAMERA_LIST})


@inference_bp.route('/api/inference/upload', methods=['POST'])
def upload_inference_video():
    if 'video' not in request.files:
        return jsonify({"success": False, "error": "No file part"}), 400
        
    file = request.files['video']
    if file.filename == '':
        return jsonify({"success": False, "error": "No selected file"}), 400
        
    if file and allowed_file(file.filename):
        job_id = str(uuid.uuid4())
        filename = secure_filename(file.filename)
        safe_filename = f"{job_id}_{filename}"
        input_path = os.path.join(UPLOAD_FOLDER, safe_filename)
        
        file.save(input_path)
        
        enable_counting = request.form.get('enable_counting', 'false').lower() == 'true'
        line_y = request.form.get('line_y', type=int)

        # ── Camera & Metadata ──────────────────────────────────────────────
        camera_id   = request.form.get('camera_id', 'CAM_UNKNOWN')
        camera_name = request.form.get('camera_name', 'Không rõ')
        location    = request.form.get('location', 'Không rõ')

        record_date_str = request.form.get('record_date', '')
        try:
            record_date = datetime.fromisoformat(record_date_str) if record_date_str else datetime.now()
        except ValueError:
            record_date = datetime.now()
        # ──────────────────────────────────────────────────────────────────

        # Create job record in DB
        db = db_service.get_db_connection()
        if db is not None:
            job_record = {
                "job_id": job_id,
                "original_filename": filename,
                "input_path": input_path,
                "output_dir": OUTPUT_FOLDER,
                "status": "pending",
                "progress": 0,
                "error": None,
                "output_url": None,
                "enable_counting": enable_counting,
                "line_y": line_y,
                "counts": {},
                # Camera metadata
                "camera_id": camera_id,
                "camera_name": camera_name,
                "location": location,
                "record_date": record_date,
                # Live preview fields (populated during processing)
                "preview_url": None,
                "processing_fps": 0,
                "gallery_snapshots": [],
                "frame_count": 0,
                "video_fps": 0,
                "total_frames": 0,
                "created_at": datetime.now(),
                "updated_at": datetime.now()
            }
            db['inference_jobs'].insert_one(job_record)
        
        success = kafka_queue.send_task(source='inference_video', keyword=job_id, priority=1)
        
        if success:
            return jsonify({
                "success": True, 
                "job_id": job_id, 
                "message": "Video uploaded and task queued successfully."
            })
        else:
            return jsonify({"success": False, "error": "Failed to queue task."}), 500

    return jsonify({"success": False, "error": "Invalid file type."}), 400


@inference_bp.route('/api/inference/status/<job_id>', methods=['GET'])
def get_inference_status(job_id):
    db = db_service.get_db_connection()
    if db is None:
        return jsonify({"success": False, "error": "Database connection error"}), 500
        
    job = db['inference_jobs'].find_one({"job_id": job_id}, {"_id": 0})
    if not job:
        return jsonify({"success": False, "error": "Job not found"}), 404

    # Serialize datetime fields
    record_date = job.get("record_date")
    if record_date and isinstance(record_date, datetime):
        record_date = record_date.replace(tzinfo=timezone.utc).isoformat()
        
    return jsonify({
        "success": True,
        "job_id": job["job_id"],
        "status": job["status"],
        "progress": job.get("progress", 0),
        "output_url": job.get("output_url"),
        "error": job.get("error"),
        "counts": job.get("counts", {}),
        # Live preview
        "preview_url": job.get("preview_url"),
        "processing_fps": job.get("processing_fps", 0),
        "gallery_snapshots": job.get("gallery_snapshots", []),
        "frame_count": job.get("frame_count", 0),
        "video_fps": job.get("video_fps", 0),
        "total_frames": job.get("total_frames", 0),
        # Camera metadata
        "camera_id": job.get("camera_id", ""),
        "camera_name": job.get("camera_name", ""),
        "location": job.get("location", ""),
        "record_date": record_date,
    })

import time, os
from flask import Response

@inference_bp.route('/api/inference/stream/<job_id>', methods=['GET'])
def stream_inference(job_id):
    """Phát luồng Video Live dạng MJPEG liên tục cho trình duyệt."""
    import os, time
    static_folder = os.path.join(os.getcwd(), 'static')
    
    def generate():
        preview_path = os.path.join(static_folder, 'inference_results', 'previews', str(job_id), 'preview.jpg')
        last_mtime = 0
        
        while True:
            if not os.path.exists(preview_path):
                time.sleep(0.05)
                continue
                
            try:
                mtime = os.path.getmtime(preview_path)
                if mtime != last_mtime:
                    last_mtime = mtime
                    with open(preview_path, "rb") as f:
                        frame = f.read()
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
            except Exception:
                pass
                
            time.sleep(0.01)

    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')


@inference_bp.route('/api/inference/history', methods=['GET'])
def get_inference_history():
    """Trả về lịch sử thống kê lưu lượng xe đã hoàn tất."""
    db = db_service.get_db_connection()
    if db is None:
        return jsonify({"success": False, "error": "Database connection error"}), 500

    page     = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    date_str = request.args.get('date') # YYYY-MM-DD
    skip     = (page - 1) * per_page

    query = {"incremental_batch": {"$ne": True}}
    if date_str:
        try:
            from dateutil import parser
            from datetime import timedelta
            date_obj = parser.isoparse(date_str)
            start_of_day = date_obj.replace(hour=0, minute=0, second=0, microsecond=0)
            end_of_day   = start_of_day + timedelta(days=1)
            query["record_date"] = {"$gte": start_of_day, "$lt": end_of_day}
        except:
            pass

    total = db['traffic_stats'].count_documents(query)
    cursor = db['traffic_stats'].find(query, {"_id": 0}) \
                                .sort("processed_at", -1) \
                                .skip(skip).limit(per_page)

    records = []
    for doc in cursor:
        # Serialize datetimes
        for field in ('record_date', 'processed_at'):
            if doc.get(field) and isinstance(doc[field], datetime):
                doc[field] = doc[field].replace(tzinfo=timezone.utc).isoformat()
        records.append(doc)

    return jsonify({
        "success": True,
        "records": records,
        "total": total,
        "total_pages": max(1, (total + per_page - 1) // per_page),
        "current_page": page,
    })


@inference_bp.route('/api/inference/analytics', methods=['GET'])
def get_inference_analytics():
    """
    Aggregate dữ liệu traffic_stats để vẽ biểu đồ:
    - by_hour: tổng xe theo giờ trong ngày (0-23)
    - by_camera: top camera đông xe nhất
    - by_city: phân bố theo thành phố
    - congestion_threshold: ngưỡng ước tính tắc đường
    """
    db = db_service.get_db_connection()
    if db is None:
        return jsonify({"success": False, "error": "Database connection error"}), 500

    try:
        camera_id = request.args.get('camera_id')
        start_str = request.args.get('start')
        end_str   = request.args.get('end')

        match_stage = {"record_date": {"$exists": True, "$ne": None}}
        if camera_id:
            match_stage["camera_id"] = camera_id
        
        if start_str or end_str:
            date_filter = {}
            if start_str:
                from dateutil import parser
                date_filter["$gte"] = parser.isoparse(start_str)
            if end_str:
                from dateutil import parser
                date_filter["$lte"] = parser.isoparse(end_str)
            match_stage["record_date"].update(date_filter)
            
        use_30m = bool(start_str or end_str)

        # ── 1. Tổng xe theo khung giờ ─────────────────────────────────────────────
        if use_30m:
            group_id = {
                "$dateFromParts": {
                    "year": {"$year": "$record_date"},
                    "month": {"$month": "$record_date"},
                    "day": {"$dayOfMonth": "$record_date"},
                    "hour": {"$hour": "$record_date"},
                    "minute": {"$subtract": [{"$minute": "$record_date"}, {"$mod": [{"$minute": "$record_date"}, 30]}]}
                }
            }
        else:
            group_id = {"$hour": "$record_date"}

        pipeline_time = [
            {"$match": match_stage},
            {"$group": {
                "_id":        group_id,
                "total":      {"$sum": "$total_vehicles"},
                "car":        {"$sum": "$counts.car"},
                "motorcycle": {"$sum": "$counts.motorcycle"},
                "bus":        {"$sum": "$counts.bus"},
                "truck":      {"$sum": "$counts.truck"},
            }},
            {"$sort": {"_id": 1}}
        ]
        
        by_hour = []
        if use_30m:
            hour_map = {f"{r['_id'].hour:02d}:{r['_id'].minute:02d}": r for r in db['traffic_stats'].aggregate(pipeline_time)}
            for h in range(24):
                for m in [0, 30]:
                    label = f"{h:02d}:{m:02d}"
                    r = hour_map.get(label, {})
                    by_hour.append({
                        "hour": label, "label": label,
                        "total": r.get("total", 0), "car": r.get("car", 0),
                        "motorcycle": r.get("motorcycle", 0), "bus": r.get("bus", 0), "truck": r.get("truck", 0),
                    })
        else:
            hour_map = {r["_id"]: r for r in db['traffic_stats'].aggregate(pipeline_time)}
            for h in range(24):
                r = hour_map.get(h, {})
                by_hour.append({
                    "hour": h, "label": f"{h:02d}:00",
                    "total": r.get("total", 0), "car": r.get("car", 0),
                    "motorcycle": r.get("motorcycle", 0), "bus": r.get("bus", 0), "truck": r.get("truck", 0),
                })

        # ── 2. Top camera đông xe nhất ───────────────────────────────────────
        cam_date_str = request.args.get('cam_date')
        cam_match_stage = dict(match_stage)
        
        if cam_date_str: # Input YYYY-MM-DD
            from datetime import timedelta
            from dateutil import parser
            date_obj = parser.isoparse(cam_date_str)
            start_of_day = date_obj.replace(hour=0, minute=0, second=0, microsecond=0)
            end_of_day   = start_of_day + timedelta(days=1)
            # Ghi đè bộ lọc date để filter đúng ngày được chọn
            cam_match_stage["record_date"] = {"$gte": start_of_day, "$lt": end_of_day}

        pipeline_cam = [
            {"$match": cam_match_stage},
            {"$group": {
                "_id":         "$camera_id",
                "camera_name": {"$last": "$camera_name"},
                "location":    {"$last": "$location"},
                "total":       {"$sum": "$total_vehicles"},
                "car":         {"$sum": "$counts.car"},
                "motorcycle":  {"$sum": "$counts.motorcycle"},
                "bus":         {"$sum": "$counts.bus"},
                "truck":       {"$sum": "$counts.truck"},
            }},
            {"$sort": {"total": -1}},
            {"$limit": 10}
        ]
        by_camera = [{
            "camera_id":   r["_id"],
            "camera_name": r.get("camera_name", r["_id"]),
            "location":    r.get("location", ""),
            "total":       r.get("total", 0),
            "car":         r.get("car", 0),
            "motorcycle":  r.get("motorcycle", 0),
            "bus":         r.get("bus", 0),
            "truck":       r.get("truck", 0),
        } for r in db['traffic_stats'].aggregate(pipeline_cam)]

        # ── 3. Phân bố theo thành phố ────────────────────────────────────────
        pipeline_city = [
            {"$match": match_stage},
            {"$group": {
                "_id":   "$location",
                "total": {"$sum": "$total_vehicles"},
                "count": {"$sum": 1},
            }},
            {"$sort": {"total": -1}}
        ]
        by_city = [{
            "city":  r["_id"] or "Không rõ",
            "total": r.get("total", 0),
            "count": r.get("count", 0),
        } for r in db['traffic_stats'].aggregate(pipeline_city)]

        # ── 4. Ngưỡng tắc đường = trung bình + 1 std của tổng xe theo giờ ───
        all_totals = [r["total"] for r in by_hour if r["total"] > 0]
        if len(all_totals) >= 2:
            avg = sum(all_totals) / len(all_totals)
            std = (sum((x - avg) ** 2 for x in all_totals) / len(all_totals)) ** 0.5
            congestion_threshold = round(avg + std)
        else:
            congestion_threshold = 100

        return jsonify({
            "success": True,
            "by_hour":  by_hour,
            "by_camera": by_camera,
            "by_city":  by_city,
            "congestion_threshold": congestion_threshold,
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
