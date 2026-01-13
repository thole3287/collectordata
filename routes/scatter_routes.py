# routes/scatter_routes.py (tạo file mới tương tự boxplot_routes.py)

from flask import Blueprint, jsonify, request
from services.scatter_service import generate_scatter_for_prefix

scatter_bp = Blueprint("scatter", __name__, url_prefix="/api/scatters")

@scatter_bp.route("/generate", methods=["POST"])
def generate_scatters():
    data = request.get_json() or {}
    prefix = data.get("prefix", "").strip()
    bucket = data.get("bucket")

    if not bucket:
        return jsonify({"success": False, "message": "Thiếu bucket"}), 400

    result = generate_scatter_for_prefix(bucket=bucket, prefix=prefix)
    return jsonify(result)

# Sao chép các route khác như buckets, subprefixes từ boxplot_routes.py nếu cần, hoặc dùng chung