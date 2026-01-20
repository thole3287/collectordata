from flask import Blueprint, jsonify, request
import services.minio_service as minio_service
import os

minio_bp = Blueprint('minio', __name__, url_prefix='/api/minio')

# ── Tạo buckets (giữ nguyên) ────────────────────────────────────────────────
@minio_bp.route('/create-buckets', methods=['POST'])
def create_minio_buckets():
    try:
        if not os.getenv('MINIO_ENDPOINT'):
            return jsonify({'success': False, 'error': 'MinIO not configured'}), 400

        if minio_service.ensure_buckets_exist():
            buckets = [
                minio_service.MINIO_BUCKET_VIDEOS,
                minio_service.MINIO_BUCKET_IMAGES,
                minio_service.MINIO_BUCKET_FRAMES,
                minio_service.MINIO_BUCKET_CAMERA,
                minio_service.MINIO_BUCKET_VEHICLE_DETECTION
            ]
            return jsonify({
                'success': True,
                'message': 'Buckets created successfully',
                'buckets': buckets
            }), 200

        return jsonify({'success': False, 'error': 'Failed to create buckets'}), 500

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ── Lấy danh sách bucket ────────────────────────────────────────────────────
@minio_bp.route('/buckets', methods=['GET'])
def get_buckets():
    """
    Trả về danh sách tất cả bucket có trong MinIO
    """
    try:
        client = minio_service.get_minio_client()
        buckets = client.list_buckets()
        bucket_names = [b.name for b in buckets]
        return jsonify({
            'success': True,
            'buckets': bucket_names
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ── Lấy danh sách prefix con trực tiếp (hỗ trợ duyệt cây thư mục) ───────────
@minio_bp.route('/subprefixes', methods=['GET'])
def get_subprefixes():
    """
    Lấy danh sách các thư mục con (prefix cấp tiếp theo) của một prefix bất kỳ
    Query params:
    - bucket (bắt buộc)
    - prefix (tùy chọn, mặc định rỗng)
    """
    bucket = request.args.get('bucket')
    prefix = request.args.get('prefix', '').strip()

    if not bucket:
        return jsonify({'success': False, 'message': 'Thiếu tham số bucket'}), 400

    try:
        client = minio_service.get_minio_client()

        # Chuẩn hóa prefix
        if prefix and not prefix.endswith('/'):
            prefix += '/'

        # List objects không recursive → chỉ lấy cấp trực tiếp
        objects = client.list_objects(bucket, prefix=prefix, recursive=False)

        folders = set()
        files_count = 0

        for obj in objects:
            name = obj.object_name

            # Bỏ qua chính prefix hiện tại
            if name == prefix:
                continue

            # Nếu là thư mục (kết thúc bằng /)
            if name.endswith('/'):
                # Lấy tên thư mục con trực tiếp
                relative_path = name[len(prefix):]
                folder_name = relative_path.split('/')[0]
                if folder_name:
                    folders.add(folder_name + '/')  # giữ dấu / để biết là folder

            # Đếm file (không phải folder) để biết có dữ liệu thật hay không
            elif name.lower().endswith(('.jpg', '.jpeg', '.png')):
                files_count += 1

        return jsonify({
            'success': True,
            'subprefixes': sorted(list(folders)),
            'file_count_in_current': files_count,
            'current_prefix': prefix,
            'message': f'Tìm thấy {len(folders)} thư mục con và {files_count} file ảnh trực tiếp'
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500