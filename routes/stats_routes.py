from flask import Blueprint, jsonify
import services.stats_service as stats_service

stats_bp = Blueprint('stats', __name__)

@stats_bp.route('/api/stats', methods=['GET'])
def get_stats():
    """Lấy thống kê tổng quan"""
    result = stats_service.get_general_stats()
    if 'error' in result:
        return jsonify(result), 500
    return jsonify(result)

@stats_bp.route('/api/visualization', methods=['GET'])
def get_visualization_data():
    """Lấy dữ liệu visualize"""
    result = stats_service.get_visualization_data()
    if 'error' in result:
        return jsonify(result), 500
    return jsonify(result)
