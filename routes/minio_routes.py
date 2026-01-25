from flask import Blueprint, jsonify
import services.minio_service as minio_service
import os

minio_bp = Blueprint('minio', __name__)

@minio_bp.route('/api/minio/create-buckets', methods=['POST'])
def create_minio_buckets():
    try:
        if not os.getenv('MINIO_ENDPOINT'): return jsonify({'error': 'MinIO not configured'}), 400
        if minio_service.ensure_buckets_exist():
            buckets = [minio_service.MINIO_BUCKET_VIDEOS, minio_service.MINIO_BUCKET_IMAGES, minio_service.MINIO_BUCKET_FRAMES, minio_service.MINIO_BUCKET_CAMERA, minio_service.MINIO_BUCKET_VEHICLE_DETECTION]
            return jsonify({'success': True, 'message': 'Buckets created successfully', 'buckets': buckets}), 200
        return jsonify({'success': False, 'error': 'Failed to create buckets'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500
