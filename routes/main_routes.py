from flask import Blueprint
from controllers.main_controller import index

main_bp = Blueprint('main', __name__)

main_bp.route('/', methods=['GET'])(index)
