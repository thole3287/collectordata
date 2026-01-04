import json
from pathlib import Path
from apscheduler.schedulers.background import BackgroundScheduler
import camera_collector
import camera_config_loader
import os

# Camera Collector setup
camera_scheduler = None
camera_collector_instance = None

def init_camera_collector():
    """Initialize camera collector."""
    global camera_collector_instance
    try:
        cameras = camera_config_loader.load_cameras()
        # Fix: Ensure storage path is relative to root or absolute
        storage_path = os.path.join(os.getcwd(), "camera_collector_data")
        camera_collector_instance = camera_collector.CameraCollector(
            cameras, 
            storage_path=storage_path
        )
        return True
    except Exception as e:
        print(f"Warning: Could not initialize camera collector: {e}")
        return False

def setup_camera_scheduler():
    """Setup camera collection scheduler."""
    global camera_scheduler, camera_collector_instance
    if camera_collector_instance is None:
        if not init_camera_collector():
            return
    
    camera_scheduler = BackgroundScheduler()
    camera_scheduler.add_job(
        func=camera_collector_instance.collect_all,
        trigger="interval",
        seconds=5,
        id='camera_collection',
        name='Collect camera images',
        replace_existing=True
    )

def start_camera_scheduler():
    """Start camera collection scheduler."""
    global camera_scheduler
    if camera_scheduler is None:
        setup_camera_scheduler()
    if camera_scheduler and not camera_scheduler.running:
        camera_scheduler.start()
        return True
    return False

def stop_camera_scheduler():
    """Stop camera collection scheduler."""
    global camera_scheduler
    if camera_scheduler and camera_scheduler.running:
        camera_scheduler.shutdown(wait=False)
        camera_scheduler = None
        return True
    return False

def is_camera_scheduler_running():
    """Check if camera scheduler is running."""
    global camera_scheduler
    return camera_scheduler is not None and camera_scheduler.running

def get_camera_status():
    """Get status of camera collector."""
    try:
        if camera_collector_instance is None:
            return {
                "status": "ok",
                "scheduler_running": False,
                "cameras": [],
                "last_collection": None,
                "statistics": {
                    "total_attempts": 0,
                    "successful": 0,
                    "failed": 0
                },
                "message": "Camera collector not initialized"
            }
        
        status_info = camera_collector_instance.get_status()
        status_info['scheduler_running'] = is_camera_scheduler_running()
        return status_info
    except Exception as e:
        return {
            "status": "error",
            "scheduler_running": False,
            "cameras": [],
            "last_collection": None,
            "statistics": {
                "total_attempts": 0,
                "successful": 0,
                "failed": 0
            },
            "message": str(e)
        }

def get_cameras_list():
    """Get list of available cameras from config file."""
    try:
        # Try multiple possible paths to be safe
        possible_paths = [
            Path('camera.json'),
            Path('camera-collector/camera-collector/camera.json'),
            Path('camera-collector/camera.json')
        ]
        
        camera_file = None
        for path in possible_paths:
            if path.exists():
                camera_file = path
                break
        
        if not camera_file:
            return []
        
        with open(camera_file, 'r', encoding='utf-8') as f:
            cameras = json.load(f)
        
        camera_list = []
        for cam in cameras:
            if isinstance(cam, dict) and 'camera_id' in cam:
                camera_list.append({
                    'camera_id': cam.get('camera_id'),
                    'title': cam.get('title') or cam.get('code', ''),
                    'code': cam.get('code', ''),
                    'display_name': cam.get('display_name') or cam.get('address', ''),
                    'address': cam.get('address') or cam.get('display_name', ''),
                })
        return camera_list
    except Exception as e:
        print(f"Error reading camera list: {e}")
        return []

def add_camera_to_collection(camera_id):
    """Add camera to active collection list."""
    try:
        # Find camera in master list
        all_cameras = get_cameras_list()
        # This is a simplified lookup since get_cameras_list returns processed dicts
        # Detailed lookup might need re-reading file or passing full object
        
        # Re-read raw file for full details
        possible_paths = [
            Path('camera.json'),
            Path('camera-collector/camera-collector/camera.json'),
            Path('camera-collector/camera.json')
        ]
        camera_file = None
        for path in possible_paths:
            if path.exists():
                camera_file = path
                break
                
        if not camera_file:
            return False, "Master camera file not found"

        with open(camera_file, 'r', encoding='utf-8') as f:
            cameras = json.load(f)

        selected_camera = None
        for cam in cameras:
            if isinstance(cam, dict) and cam.get('camera_id') == camera_id:
                selected_camera = cam
                break
        
        if not selected_camera:
            return False, f"Camera with ID {camera_id} not found"

        # Load current config
        config_file = Path('camera_collector_config/cameras.json')
        if config_file.exists():
            with open(config_file, 'r', encoding='utf-8') as f:
                config_cameras = json.load(f)
        else:
            config_cameras = []
        
        if any(cam.get('id') == camera_id for cam in config_cameras):
            return True, "Camera already in collection list"
        
        config_cameras.append({
            'id': camera_id,
            'name': selected_camera.get('title') or selected_camera.get('code') or selected_camera.get('display_name', 'Unknown')
        })
        
        config_file.parent.mkdir(parents=True, exist_ok=True)
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config_cameras, f, indent=2, ensure_ascii=False)
        
        return True, "Camera added successfully"
    except Exception as e:
        return False, str(e)

def remove_camera_from_collection(camera_id):
    """Remove camera from active collection list."""
    try:
        config_file = Path('camera_collector_config/cameras.json')
        if not config_file.exists():
            return False, "Config file not found"
        
        with open(config_file, 'r', encoding='utf-8') as f:
            config_cameras = json.load(f)
        
        original_count = len(config_cameras)
        config_cameras = [cam for cam in config_cameras if cam.get('id') != camera_id]
        
        if len(config_cameras) == original_count:
            return False, "Camera not found in collection"
        
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config_cameras, f, indent=2, ensure_ascii=False)
            
        return True, "Camera removed successfully"
    except Exception as e:
        return False, str(e)
