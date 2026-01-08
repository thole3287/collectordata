from flask import jsonify, request, send_from_directory
import os
import services.camera_service as camera_service

def camera_status():
    return jsonify(camera_service.get_camera_status()), 200

def camera_start():
    if camera_service.start_camera_scheduler():
        return jsonify({"status": "success", "message": "Camera collector started"}), 200
    return jsonify({"status": "error", "message": "Scheduler already running or not initialized"}), 400

def camera_stop():
    if camera_service.stop_camera_scheduler():
        return jsonify({"status": "success", "message": "Camera collector stopped"}), 200
    return jsonify({"status": "error", "message": "Scheduler not running"}), 400

def camera_list():
    cameras = camera_service.get_cameras_list()
    return jsonify({"status": "success", "cameras": cameras, "total": len(cameras)}), 200

def camera_add():
    camera_id = request.json.get('camera_id')
    if not camera_id:
        return jsonify({"status": "error", "message": "camera_id is required"}), 400
    
    success, message = camera_service.add_camera_to_collection(camera_id)
    if success:
        # Reload collector to reflect changes
        camera_service.init_camera_collector()
        return jsonify({"status": "success", "message": message}), 200
    return jsonify({"status": "error", "message": message}), 500

def camera_remove():
    camera_id = request.json.get('camera_id')
    if not camera_id:
        return jsonify({"status": "error", "message": "camera_id is required"}), 400
        
    success, message = camera_service.remove_camera_from_collection(camera_id)
    if success:
        # Reload collector
        camera_service.init_camera_collector()
        return jsonify({"status": "success", "message": message}), 200
    return jsonify({"status": "error", "message": message}), 500

def camera_recent_images():
    limit = int(request.args.get('limit', 10))
    # Use the new DB-based function which returns MinIO URLs
    images = camera_service.get_recent_images_from_db(limit=limit)
    return jsonify({"images": images}), 200

def camera_serve_image(image_path):
    if not camera_service.camera_collector_instance:
        return jsonify({"error": "Camera collector not initialized"}), 500
    
    data_dir = camera_service.camera_collector_instance.storage_path
    path_parts = image_path.split('/')
    if len(path_parts) < 2:
        return jsonify({"error": "Invalid image path"}), 400
    
    directory = os.path.join(data_dir, '/'.join(path_parts[:-1]))
    filename = path_parts[-1]
    
    if not os.path.exists(os.path.join(directory, filename)):
         return jsonify({"error": "Image not found"}), 404
         
    return send_from_directory(directory, filename)
