from flask import Blueprint, jsonify, request, Response
import services.minio_service as minio_service
import services.dataset_service as dataset_service


dataset_bp = Blueprint('dataset', __name__)

@dataset_bp.route('/api/image/<frame_id>')
def serve_minio_image(frame_id):
    """Serve image directly from MinIO via ID lookup"""
    result = dataset_service.serve_image_service(frame_id)
    
    if result.get('error'):
        return jsonify({'error': result['error']}), result.get('status', 500)
    
    # If success, result contains bucket and key to stream
    bucket = result['bucket']
    key = result['key']
    
    try:
        client = minio_service.get_minio_client(internal=True)
        data = client.get_object(bucket, key)
        
        def generate():
            for chunk in data.stream(32*1024):
                yield chunk
            data.close()
            data.release_conn()
            
        return Response(generate(), mimetype='image/png')
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@dataset_bp.route('/api/dataset/stats', methods=['GET'])
def get_dataset_stats():
    """Get aggregated statistics for the dataset dashboard"""
    result = dataset_service.get_dataset_stats_service()
    if 'error' in result:
        return jsonify(result), 500
    return jsonify(result)

@dataset_bp.route('/api/frames', methods=['GET'])
def get_frames():
    """Get list of extracted frames with pagination and filtering"""
    params = {
        'page': request.args.get('page', 1, type=int),
        'per_page': request.args.get('per_page', 24, type=int),
        'platform': request.args.get('platform', '', type=str),
        'search': request.args.get('search', '', type=str),
        'video_id': request.args.get('video_id', '', type=str),
        'label_status': request.args.get('label_status', '', type=str),
    }
    
    result = dataset_service.get_frames_service(params)
    if 'error' in result:
        return jsonify(result), 500
    return jsonify(result)


@dataset_bp.route('/api/dataset/groups', methods=['GET'])
def get_dataset_groups():
    """Lấy danh sách nhóm video (đã extract frames) với thông tin weather dominant - Optimized"""
    params = {
        'page': request.args.get('page', 1, type=int),
        'per_page': request.args.get('per_page', 20, type=int),
        'platform': request.args.get('platform', '', type=str),
        'search': request.args.get('search', '', type=str),
        'label_status': request.args.get('label_status', '', type=str)
    }
    
    result = dataset_service.get_dataset_groups_service(params)
    if 'error' in result:
        return jsonify(result), 500
    return jsonify(result)

@dataset_bp.route('/api/image-proxy')
def image_proxy():
    """
    Proxy image from MinIO to frontend to avoid CORS/Network issues.
    Query params: bucket, key
    """
    bucket = request.args.get('bucket')
    key = request.args.get('key')
    
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

@dataset_bp.route('/api/dataset/label-content', methods=['GET', 'PUT'])
def label_content_api():
    bucket = request.args.get('bucket', 'dataset')
    key = request.args.get('key')
    
    if request.method == 'GET':
        if not key:
            return jsonify({'error': 'Missing key'}), 400
        try:
            client = minio_service.get_minio_client(internal=True)
            response = client.get_object(bucket, key)
            content = response.read().decode('utf-8')
            response.close()
            response.release_conn()
            return jsonify({'content': content})
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    # PUT logic
    from io import BytesIO
    import services.database as db_service
    from bson import ObjectId

    data = request.json or {}
    bucket = data.get('bucket', bucket)
    key = data.get('key', key)
    content = data.get('content', '')
    frame_id = data.get('frame_id', '')
    platform = data.get('platform', '')

    if not bucket or not key:
        return jsonify({'error': 'Missing bucket or key'}), 400

    # YOLO class names mapping (matches labeling_service.py)
    CLASS_NAMES = {
        0: 'person', 1: 'bicycle', 2: 'car', 3: 'motorcycle',
        5: 'bus', 7: 'truck'
    }

    try:
        client = minio_service.get_minio_client(internal=True)
        encoded = content.encode('utf-8')
        client.put_object(bucket, key, BytesIO(encoded), len(encoded), content_type='text/plain')

        # Rebuild label_summary from new content
        label_summary = {}
        for line in content.strip().splitlines():
            parts = line.strip().split()
            if len(parts) >= 5:
                cls_id = int(parts[0])
                cls_name = CLASS_NAMES.get(cls_id, str(cls_id))
                label_summary[cls_name] = label_summary.get(cls_name, 0) + 1

        # Update DB
        if frame_id:
            try:
                db = db_service.get_db_connection()
                if db:
                    collection_name = 'camera_images' if platform == 'camera' else 'video_frames'
                    db[collection_name].update_one(
                        {'_id': ObjectId(frame_id)},
                        {'$set': {'label_summary': label_summary}}
                    )
            except Exception as db_err:
                print(f'DB update label_summary failed: {db_err}')

        return jsonify({'success': True, 'label_summary': label_summary})
    except Exception as e:
        print(f'Label save error {bucket}/{key}: {e}')
        return jsonify({'error': str(e)}), 500


@dataset_bp.route('/api/dataset/regenerate-visualized', methods=['POST'])
def regenerate_visualized():
    """
    Re-draw bounding boxes from a label .txt file onto the original image
    and save back as visualized image in MinIO.
    Body JSON: { bucket, image_key, label_key, vis_key }
    """
    import cv2
    import numpy as np
    from io import BytesIO

    data = request.json or {}
    bucket = data.get('bucket')
    image_key = data.get('image_key')    # original image key
    label_key = data.get('label_key')    # label .txt key
    vis_key = data.get('vis_key')        # visualized image key to overwrite

    if not all([bucket, image_key, label_key, vis_key]):
        return jsonify({'error': 'Missing required fields'}), 400

    # Color map (BGR) – matches labeling_service.py
    CLASS_NAMES = {
        0: 'person', 1: 'bicycle', 2: 'car', 3: 'motorcycle',
        5: 'bus', 7: 'truck'
    }
    COLOR_MAP = {
        'bus':        (0, 255, 255),
        'car':        (255, 255, 0),
        'truck':      (10, 10, 235),
        'motorcycle': (255, 255, 255),
        'bicycle':    (200, 200, 200),
        'person':     (0, 165, 255),
    }

    try:
        client = minio_service.get_minio_client(internal=True)

        # 1. Download original image
        img_resp = client.get_object(bucket, image_key)
        img_bytes = np.frombuffer(img_resp.read(), dtype=np.uint8)
        img_resp.close()
        img_resp.release_conn()
        img = cv2.imdecode(img_bytes, cv2.IMREAD_COLOR)
        if img is None:
            return jsonify({'error': 'Cannot decode image'}), 500

        h, w = img.shape[:2]

        # 2. Download label txt
        lbl_resp = client.get_object(bucket, label_key)
        label_content = lbl_resp.read().decode('utf-8')
        lbl_resp.close()
        lbl_resp.release_conn()

        # 3. Draw boxes
        vis_img = img.copy()
        for line in label_content.strip().splitlines():
            parts = line.strip().split()
            if len(parts) < 5:
                continue
            cls_id = int(parts[0])
            cx, cy, bw, bh = float(parts[1]), float(parts[2]), float(parts[3]), float(parts[4])
            cls_name = CLASS_NAMES.get(cls_id, str(cls_id))
            color = COLOR_MAP.get(cls_name.lower(), (0, 255, 0))

            x1 = int((cx - bw / 2) * w)
            y1 = int((cy - bh / 2) * h)
            x2 = int((cx + bw / 2) * w)
            y2 = int((cy + bh / 2) * h)

            cv2.rectangle(vis_img, (x1, y1), (x2, y2), color, 2)
            conf_str = f' {float(parts[5]):.2f}' if len(parts) >= 6 else ''
            label_text = f'{cls_name}{conf_str}'
            cv2.putText(vis_img, label_text, (x1, max(0, y1 - 5)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1, cv2.LINE_AA)

        # 4. Upload visualized
        _, encoded = cv2.imencode('.jpg', vis_img)
        vis_bytes = encoded.tobytes()
        client.put_object(bucket, vis_key, BytesIO(vis_bytes), len(vis_bytes), content_type='image/jpeg')

        return jsonify({'success': True, 'vis_key': vis_key})
    except Exception as e:
        print(f'Regenerate visualized error: {e}')
        return jsonify({'error': str(e)}), 500
