from flask import Blueprint
from controllers.keyword_controller import (
    get_keywords,
    create_keyword,
    update_keyword,
    delete_keyword,
    download_by_keyword_id
)

keyword_bp = Blueprint('keyword', __name__)

keyword_bp.route('/api/keywords', methods=['GET'])(get_keywords)
keyword_bp.route('/api/keywords', methods=['POST'])(create_keyword)
keyword_bp.route('/api/keywords/<keyword_id>', methods=['PUT'])(update_keyword)
keyword_bp.route('/api/keywords/<keyword_id>', methods=['DELETE'])(delete_keyword)
keyword_bp.route('/api/keywords/<keyword_id>/download', methods=['POST'])(download_by_keyword_id)
