from flask import Blueprint
from controllers.collector_controller import (
    start_auto_collector,
    stop_auto_collector,
    get_auto_collector_status
)

collector_bp = Blueprint('collector', __name__)

collector_bp.route('/api/auto-collector/start', methods=['POST'])(start_auto_collector)
collector_bp.route('/api/auto-collector/stop', methods=['POST'])(stop_auto_collector)
collector_bp.route('/api/auto-collector/status', methods=['GET'])(get_auto_collector_status)
