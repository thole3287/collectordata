from flask import Blueprint
from controllers.dataset_controller import (
    serve_minio_image,
    get_dataset_stats,
    get_frames,
    get_dataset_groups,
    get_frame_image,
    image_proxy
)

dataset_bp = Blueprint('dataset', __name__)

# Legacy route for serving image (kept for compat, or map to get_frame_image)
dataset_bp.route('/api/image/<frame_id>', methods=['GET'])(serve_minio_image)

dataset_bp.route('/api/dataset/stats', methods=['GET'])(get_dataset_stats)
dataset_bp.route('/api/frames', methods=['GET'])(get_frames)
dataset_bp.route('/api/dataset/groups', methods=['GET'])(get_dataset_groups)

# Re-mapped route to match app.py logic where api/image/<frame_id> was both serve_minio_image and get_frame_image? 
# In app.py:
# Line 81: @app.route('/api/image/<frame_id>') -> serve_minio_image
# Line 1267: @app.route('/api/image/<frame_id>') -> get_frame_image (Redefinition!)
# The second one overrides the first one in Flask. 
# serve_minio_image had logic: db lookup -> client.get_object -> generate()
# get_frame_image had logic: db lookup -> reconstruction fallback -> client.get_object -> Response()
# get_frame_image seemed more robust with fallbacks. I used get_frame_image logic as the definitive one but imported serve_minio_image as well?
# Actually in my controller code I included both.
# I should just use one URL map. I will use get_frame_image logic for /api/image/<frame_id>.

# Explicit routes
dataset_bp.route('/api/image-proxy', methods=['GET'])(image_proxy)
