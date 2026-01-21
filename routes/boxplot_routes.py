from flask import Blueprint, jsonify, request
from services.boxplot_service import generate_boxplot_for_prefix

boxplot_bp = Blueprint("boxplot", __name__, url_prefix="/api/boxplots")

@boxplot_bp.route("/generate", methods=["POST"])
def generate_boxplots():
    data = request.get_json() or {}
    bucket = data.get("bucket")
    prefix = data.get("prefix", "").strip()

    if not bucket:
        return jsonify({"success": False, "message": "Thiếu bucket"}), 400

    result = generate_boxplot_for_prefix(bucket=bucket, prefix=prefix)
    return jsonify(result)