# routes/scatter_routes.py
from flask import Blueprint, jsonify, request
from services.scatter_service import generate_scatter_for_prefix

scatter_bp = Blueprint("scatter", __name__, url_prefix="/api/scatters")


@scatter_bp.route("/generate", methods=["POST"])
def generate_scatters():
    """
    API tạo scatter plot từ bucket và prefix.
    Body JSON: {"bucket": "dataset", "prefix": "pexels/"}
    """
    try:
        data = request.get_json() or {}
        bucket = data.get("bucket")
        prefix = data.get("prefix", "").strip()

        if not bucket:
            return jsonify({"success": False, "message": "Thiếu tham số bucket"}), 400

        result = generate_scatter_for_prefix(bucket=bucket, prefix=prefix)
        return jsonify(result)

    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"Lỗi server: {str(e)}"
        }), 500


# Nếu bạn muốn thêm route phụ (tương tự boxplot_routes.py)
@scatter_bp.route("/buckets", methods=["GET"])
def get_buckets():
    from services.minio_service import get_minio_client
    try:
        client = get_minio_client()
        buckets = [b.name for b in client.list_buckets()]
        return jsonify({"success": True, "buckets": buckets})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@scatter_bp.route("/subprefixes", methods=["GET"])
def get_subprefixes():
    bucket = request.args.get("bucket")
    prefix = request.args.get("prefix", "").strip()

    if not bucket:
        return jsonify({"success": False, "message": "Thiếu bucket"}), 400

    from services.minio_service import get_minio_client
    try:
        client = get_minio_client()
        if prefix and not prefix.endswith("/"):
            prefix += "/"

        objects = client.list_objects(bucket, prefix=prefix, recursive=False)
        folders = set()
        files_count = 0

        for obj in objects:
            name = obj.object_name
            if name == prefix:
                continue
            if name.endswith("/"):
                relative = name[len(prefix):]
                folder_name = relative.split("/")[0]
                if folder_name:
                    folders.add(folder_name + "/")
            elif name.lower().endswith((".jpg", ".jpeg", ".png")):
                files_count += 1

        return jsonify({
            "success": True,
            "subprefixes": sorted(folders),
            "file_count_in_current": files_count,
            "current_prefix": prefix,
        })
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500