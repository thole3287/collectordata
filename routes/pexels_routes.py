from flask import Blueprint
from controllers.pexels_controller import (
    pexels_download,
    pexels_download_result
)

pexels_bp = Blueprint('pexels', __name__)

pexels_bp.route('/api/pexels/download', methods=['POST'])(pexels_download)
pexels_bp.route('/api/pexels/result', methods=['GET'])(pexels_download_result)
