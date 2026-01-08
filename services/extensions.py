import os
from dotenv import load_dotenv

load_dotenv()

# --- CONFIGURATION & PATHS ---
BASE_DIR = os.getcwd()
STORAGE_DIR = os.path.join(BASE_DIR, "storage")
CONFIG_DIR = os.path.join(BASE_DIR, "config")

# Data Directories
PEXELS_OUTPUT_FOLDER = os.path.join(STORAGE_DIR, "pexels_traffic_dataset")
FRAMES_OUTPUT_ROOT = os.path.join(STORAGE_DIR, "dataset_extracted")
DOWNLOADS_FOLDER = os.path.join(STORAGE_DIR, "downloads")
CAMERA_DATA_FOLDER = os.path.join(STORAGE_DIR, "camera_collector_data")

# Config Files
CAMERA_CONFIG_FILE = os.path.join(CONFIG_DIR, "camera.json")
CAMERA_COLLECTOR_CONFIG_FILE = os.path.join(CONFIG_DIR, "camera_collector_config", "cameras.json")

# Application Config
PEXELS_API_KEY = os.getenv('PEXELS_API_KEY', '')
VALID_VIDEO_EXTENSIONS = ('.mp4', '.avi', '.mov', '.mkv', '.wmv')
MINIO_ENDPOINT = os.getenv('MINIO_ENDPOINT', 'localhost:9000')

# Shared Global Instances (to be initialized in app.py or here)
# For now, services manage their own singletons, but we define constants here.
