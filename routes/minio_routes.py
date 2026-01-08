from flask import Blueprint
from controllers.minio_controller import create_minio_buckets

minio_bp = Blueprint('minio', __name__)

minio_bp.route('/api/minio/create-buckets', methods=['POST'])(create_minio_buckets)
