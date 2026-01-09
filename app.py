from flask import Flask, render_template, jsonify, request, send_from_directory
from flask_cors import CORS
import threading
import os
import json
from datetime import datetime, timedelta
import time
from dotenv import load_dotenv

# Services
import services.database as db_service
import services.camera_service as camera_service
import services.minio_service as minio_service

# Blueprints
from routes.main_routes import main_bp
from routes.dataset_routes import dataset_bp
from routes.video_routes import video_bp
from routes.auto_collector_routes import auto_collector_bp
from routes.stats_routes import stats_bp
from routes.keyword_routes import keyword_bp
from routes.camera_routes import camera_bp
from routes.pexels_routes import pexels_bp
from routes.frame_routes import frame_bp
from routes.vehicle_routes import vehicle_bp
from routes.minio_routes import minio_bp

# Load environment variables
load_dotenv()

# App configuration
app = Flask(__name__)
CORS(app)

# ==================== INITIALIZATION ====================

# Initialize camera collector on startup
try:
    print("📷 Initializing Camera Collector...")
    camera_service.init_camera_collector()
except Exception as e:
    print(f"Warning: Camera collector initialization failed: {e}")
    print("App will continue without camera collector functionality")

# Initialize MinIO buckets
try:
    minio_endpoint = os.getenv('MINIO_ENDPOINT')
    if minio_endpoint:
        print("🔧 Initializing MinIO buckets...")
        minio_service.ensure_buckets_exist()
except Exception as e:
    print(f"⚠️ MinIO initialization skipped: {e}")

# Initialize Database Indexes
try:
    print("🔧 Ensuring Database Indexes...")
    db = db_service.get_db_connection()
    if db is not None:
        # Create index for downloaded_videos sorting
        db['downloaded_videos'].create_index([('downloaded_at', -1)])
        print("✓ Database indexes created")
except Exception as e:
    print(f"⚠️ Database index creation skipped: {e}")


# ==================== REGISTER BLUEPRINTS ====================

app.register_blueprint(main_bp)
app.register_blueprint(dataset_bp)
app.register_blueprint(video_bp)
app.register_blueprint(auto_collector_bp)
app.register_blueprint(stats_bp)
app.register_blueprint(keyword_bp)
app.register_blueprint(camera_bp)
app.register_blueprint(pexels_bp)
app.register_blueprint(frame_bp)
app.register_blueprint(vehicle_bp)
app.register_blueprint(minio_bp)

# ==================== MAIN ====================

if __name__ == '__main__':
    flask_host = os.getenv('FLASK_HOST', '127.0.0.1')
    flask_port = int(os.getenv('FLASK_PORT', 5000))
    flask_debug = os.getenv('FLASK_DEBUG', 'True').lower() == 'true'
    
    import socket
    ports_to_try = [flask_port, 5001, 8080, 3000, 8000]
    port = None
    for p in ports_to_try:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.bind((flask_host, p))
            sock.close()
            port = p
            break
        except OSError: continue
    
    if port is None:
        print("❌ Không tìm thấy port trống.")
        exit(1)
        
    print(f"🚀 Server đang chạy tại: http://{flask_host}:{port}")
    app.run(debug=flask_debug, host=flask_host, port=port)
