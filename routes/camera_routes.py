from flask import Blueprint
from controllers.camera_controller import (
    camera_status,
    camera_start,
    camera_stop,
    camera_list,
    camera_add,
    camera_remove,
    camera_recent_images,
    camera_serve_image
)

camera_bp = Blueprint('camera', __name__)

camera_bp.route('/api/camera/status')(camera_status)
camera_bp.route('/api/camera/start', methods=['POST'])(camera_start)
camera_bp.route('/api/camera/stop', methods=['POST'])(camera_stop)
camera_bp.route('/api/camera/list')(camera_list)
camera_bp.route('/api/camera/add', methods=['POST'])(camera_add)
camera_bp.route('/api/camera/remove', methods=['POST'])(camera_remove)
camera_bp.route('/api/camera/recent-images')(camera_recent_images)
camera_bp.route('/api/camera/images/<path:image_path>')(camera_serve_image)
