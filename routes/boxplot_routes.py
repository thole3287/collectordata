# routes/boxplot_routes.py

from flask import Blueprint, jsonify, request
from services.boxplot_service import generate_boxplot_for_prefix

boxplot_bp = Blueprint("boxplot", __name__, url_prefix="/api/boxplots")


@boxplot_bp.route("/generate", methods=["POST"])
def generate_boxplots():
    data = request.get_json() or {}
    prefix = data.get("prefix", "").strip()  # Ví dụ: "pexels/" hoặc ""
    bucket = data.get("bucket")  # Bắt buộc phải gửi bucket từ frontend

    if not bucket:
        return jsonify({"success": False, "message": "Thiếu bucket"}), 400

    result = generate_boxplot_for_prefix(bucket=bucket, prefix=prefix)
    return jsonify(result)


# Thêm route để lấy danh sách các thư mục có dữ liệu
@boxplot_bp.route("/sources", methods=["GET"])
def get_sources():
    from services.minio_service import get_minio_client, MINIO_BUCKET_FRAMES

    try:
        client = get_minio_client()
        bucket = MINIO_BUCKET_FRAMES

        print("🔍 Đang quét toàn bộ bucket frames để tìm thư mục cấp 1 chứa ảnh...")

        # Lấy tất cả objects trong bucket (recursive)
        all_objects = list(client.list_objects(bucket, recursive=True))

        root_folders = set()

        image_count = 0

        for obj in all_objects:
            key = obj.object_name

            # Bỏ qua các folder marker
            if key.endswith("/"):
                continue

            # Chỉ xét các file ảnh
            if not key.lower().endswith((".png", ".jpg", ".jpeg", ".bmp", ".tiff")):
                continue

            image_count += 1

            # Tách đường dẫn và lấy phần cấp 1
            parts = key.split("/")
            if len(parts) >= 2:  # ít nhất có thư mục cấp 1
                root_folder = parts[0] + "/"
                root_folders.add(root_folder)

        print(f"📸 Tìm thấy {image_count} file ảnh trong bucket")
        print(f"📂 Các thư mục cấp 1 chứa ảnh: {sorted(root_folders)}")

        valid_prefixes = sorted(list(root_folders))

        # Fallback nếu không tìm thấy gì (không nên xảy ra nếu có ảnh)
        if not valid_prefixes:
            valid_prefixes = ["pexels/"]

        return jsonify(
            {
                "success": True,
                "sources": valid_prefixes,
                "debug_info": {
                    "total_images_found": image_count,
                    "root_folders": sorted(root_folders),
                },
            }
        )

    except Exception as e:
        import traceback

        traceback.print_exc()
        print(f"❌ Lỗi khi quét sources: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


@boxplot_bp.route("/buckets", methods=["GET"])
def get_buckets():
    try:
        from services.minio_service import get_minio_client

        print("=== BẮT ĐẦU GỌI /api/boxplots/buckets ===")

        # Thử tạo client trước để bắt lỗi sớm
        try:
            client = get_minio_client()
            print("✓ get_minio_client() thành công")
        except Exception as client_err:
            print("✗ LỖI TẠO MINIO CLIENT:")
            import traceback

            traceback.print_exc()
            return (
                jsonify(
                    {
                        "success": False,
                        "message": f"Lỗi kết nối MinIO: {str(client_err)}",
                    }
                ),
                500,
            )

        # Lấy danh sách bucket
        try:
            buckets = list(client.list_buckets())
            all_bucket_names = [b.name for b in buckets]
            print(f"✓ Tìm thấy {len(all_bucket_names)} bucket: {all_bucket_names}")
        except Exception as list_err:
            print("✗ LỖI KHI LIST BUCKETS:")
            import traceback

            traceback.print_exc()
            return (
                jsonify(
                    {"success": False, "message": f"Lỗi list buckets: {str(list_err)}"}
                ),
                500,
            )

        valid_buckets = []
        media_extensions = {
            ".png",
            ".jpg",
            ".jpeg",
            ".bmp",
            ".tiff",
            ".mp4",
            ".avi",
            ".mov",
            ".mkv",
            ".webm",
        }

        for bucket_name in all_bucket_names:
            try:
                objects = list(client.list_objects(bucket_name, recursive=True))
                print(f"Bucket '{bucket_name}': {len(objects)} objects (mẫu)")

                has_media = False
                for obj in objects:
                    if obj.object_name.endswith("/"):
                        continue
                    print(f"  - {obj.object_name}")
                    if any(
                        obj.object_name.lower().endswith(ext)
                        for ext in media_extensions
                    ):
                        has_media = True
                        break

                if has_media:
                    valid_buckets.append(bucket_name)
                    print(f"  → Có media → thêm vào danh sách")
                else:
                    print(f"  → Không có media hợp lệ")

            except Exception as e:
                print(f"✗ Lỗi quét bucket {bucket_name}: {e}")
                import traceback

                traceback.print_exc()

        # Ưu tiên
        priority = [
            "frames",
            "videos",
            "vehicle-detection",
            "raw_videos",
            "youtube_videos",
        ]
        prioritized = [b for b in priority if b in valid_buckets]
        others = sorted([b for b in valid_buckets if b not in priority])
        final_order = prioritized + others

        print(f"✓ Trả về buckets: {final_order}")
        print("=== KẾT THÚC GỌI /api/boxplots/buckets ===")

        return jsonify({"success": True, "buckets": final_order or ["frames"]})

    except Exception as e:
        print("✗ LỖI NGHIÊM TRỌNG TRONG get_buckets():")
        import traceback

        traceback.print_exc()
        return jsonify({"success": False, "message": f"Lỗi server: {str(e)}"}), 500


@boxplot_bp.route("/subprefixes", methods=["GET"])
def get_subprefixes():
    bucket = request.args.get("bucket")
    if not bucket:
        return jsonify({"success": False, "message": "Thiếu tham số bucket"}), 400

    try:
        from services.minio_service import get_minio_client

        client = get_minio_client()

        media_extensions = {
            ".png",
            ".jpg",
            ".jpeg",
            ".bmp",
            ".tiff",
            ".mp4",
            ".avi",
            ".mov",
            ".mkv",
            ".webm",
        }
        root_prefixes = set()

        for obj in client.list_objects(bucket, recursive=True):
            if obj.object_name.endswith("/"):
                continue
            if not any(
                obj.object_name.lower().endswith(ext) for ext in media_extensions
            ):
                continue

            parts = obj.object_name.split("/")
            if len(parts) >= 2:
                root_prefix = (
                    parts[0] + "/"
                )  # chỉ lấy cấp 1: pexels/, camera/, youtube/
                root_prefixes.add(root_prefix)

        sorted_prefixes = sorted(list(root_prefixes))
        print(f"Subprefixes cho bucket {bucket}: {sorted_prefixes}")

        return jsonify({"success": True, "subprefixes": sorted_prefixes})
    except Exception as e:
        import traceback

        traceback.print_exc()
        return jsonify({"success": False, "message": str(e)}), 500
