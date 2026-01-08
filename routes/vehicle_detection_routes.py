from flask import Blueprint
from controllers.vehicle_detection_controller import (
    upload_vehicle_detection,
    get_vehicle_detection,
    search_vehicle_detections
)

vehicle_detection_bp = Blueprint('vehicle_detection', __name__)

vehicle_detection_bp.route('/api/vehicle-detection/upload', methods=['POST'])(upload_vehicle_detection)
vehicle_detection_bp.route('/api/vehicle-detection/<event_id>', methods=['GET'])(get_vehicle_detection)
vehicle_detection_bp.route('/api/vehicle-detection/search', methods=['GET'])(search_vehicle_detections)
