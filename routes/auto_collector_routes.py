from flask import Blueprint, jsonify
import services.auto_collector_service as auto_collector_service

auto_collector_bp = Blueprint('auto_collector', __name__)

@auto_collector_bp.route('/api/auto-collector/start', methods=['POST'])
def start_auto_collector():
    result = auto_collector_service.auto_collector.start()
    return jsonify(result)

@auto_collector_bp.route('/api/auto-collector/stop', methods=['POST'])
def stop_auto_collector():
    result = auto_collector_service.auto_collector.stop()
    return jsonify(result)

@auto_collector_bp.route('/api/auto-collector/status', methods=['GET'])
def get_auto_collector_status():
    result = auto_collector_service.auto_collector.get_status()
    return jsonify(result)
