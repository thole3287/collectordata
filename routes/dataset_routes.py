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

@dataset_bp.route('/api/dataset/label-content')
def get_label_content():
    """
    Fetch raw text content of a label file from MinIO.
    Query params: bucket, key
    """
    bucket = request.args.get('bucket')
    key = request.args.get('key')
    
    if not bucket or not key:
        return jsonify({"error": "Missing bucket or key"}), 400
        
    try:
        client = minio_service.get_minio_client(internal=True)
        response = client.get_object(bucket, key)
        content = response.read().decode('utf-8')
        response.close()
        response.release_conn()
        
        return jsonify({"content": content})
    except Exception as e:
        print(f"Label fetch error for {bucket}/{key}: {e}")
        return jsonify({"error": str(e)}), 404
