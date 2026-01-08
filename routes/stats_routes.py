from flask import Blueprint
from controllers.stats_controller import (
    get_stats,
    get_visualization_data
)

stats_bp = Blueprint('stats', __name__)

stats_bp.route('/api/stats', methods=['GET'])(get_stats)
stats_bp.route('/api/visualization', methods=['GET'])(get_visualization_data)
