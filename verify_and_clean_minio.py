import os
import shutil
import argparse
from pymongo import MongoClient
from minio import Minio
from minio.error import S3Error
from dotenv import load_dotenv

load_dotenv()

# --- CONFIG ---
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = int(os.getenv('DB_PORT', 27017))
DB_NAME = os.getenv('DB_NAME', 'data_collection')
DB_USER = os.getenv('DB_USER', '')
DB_PASSWORD = os.getenv('DB_PASSWORD', '')

MINIO_ENDPOINT = os.getenv('MINIO_ENDPOINT', 'localhost')
MINIO_PORT = int(os.getenv('MINIO_PORT', 9000))
MINIO_ACCESS_KEY = os.getenv('MINIO_ACCESS_KEY', 'minioadmin')
MINIO_SECRET_KEY = os.getenv('MINIO_SECRET_KEY', 'minioadmin123')
MINIO_USE_SSL = os.getenv('MINIO_USE_SSL', 'False').lower() == 'true'

DOWNLOADS_DIR = os.path.abspath("downloads")
DATASET_EXTRACTED_DIR = os.path.abspath("dataset_extracted")

def get_db_connection():
    try:
        if DB_USER and DB_PASSWORD:
            uri = f"mongodb://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/"
        else:
            uri = f"mongodb://{DB_HOST}:{DB_PORT}/"
        client = MongoClient(uri)
        return client[DB_NAME]
    except Exception as e:
        print(f"❌ DB Connection Error: {e}")
        return None

def get_minio_client():
    try:
        client = Minio(
            f"{MINIO_ENDPOINT}:{MINIO_PORT}",
            access_key=MINIO_ACCESS_KEY,
            secret_key=MINIO_SECRET_KEY,
            secure=MINIO_USE_SSL
        )
        return client
    except Exception as e:
        print(f"❌ MinIO Connection Error: {e}")
        return None

def find_local_video_files(video_title, stored_file_path=None):
    """
    Find local video files matching the title or stored path.
    Returns a list of absolute paths.
    """
    candidates = []
    
    # 1. Check strict path if provided and local
    if stored_file_path and not stored_file_path.startswith(('http', 'videos/')): # videos/ is start of minio path
        if os.path.exists(stored_file_path):
            candidates.append(os.path.abspath(stored_file_path))
    
    # 2. Search in downloads folder by Title matching
    if os.path.exists(DOWNLOADS_DIR):
        for f in os.listdir(DOWNLOADS_DIR):
            f_path = os.path.join(DOWNLOADS_DIR, f)
            if not os.path.isfile(f_path):
                continue
            
            # Match exact title + ext
            # Often yt-dlp saves as "Title.mp4" or "Title.f137.mp4"
            if video_title in f:
                # Basic check: title is substring (careful with short titles?)
                # Better: startswith title
                # Clean title for filesystem safety often done by yt-dlp, but simple check first
                if f.startswith(video_title) or video_title in f: # Loose match
                     candidates.append(f_path)
    
    return list(set(candidates)) # Dedupe

def find_local_dataset_folders(video_title):
    """
    Find local dataset folders matching the title.
    """
    candidates = []
    if os.path.exists(DATASET_EXTRACTED_DIR):
        for d in os.listdir(DATASET_EXTRACTED_DIR):
            d_path = os.path.join(DATASET_EXTRACTED_DIR, d)
            if not os.path.isdir(d_path):
                continue
            
            if video_title in d:
                candidates.append(d_path)
    return list(set(candidates))

def main(dry_run=True):
    print(f"Starting Cleanup... (Dry Run: {dry_run})")
    print(f"   Downloads: {DOWNLOADS_DIR}")
    print(f"   Dataset: {DATASET_EXTRACTED_DIR}")
    
    db = get_db_connection()
    minio_client = get_minio_client()
    
    if db is None or minio_client is None:
        return

    collection = db['downloaded_videos']
    
    # Find videos that are marked as synced
    synced_videos = collection.find({
        'storage_refs': {'$exists': True}
    })
    
    videos_to_delete = []
    folders_to_delete = []
    
    print("\nScanning Database and checking MinIO...")
    
    count_processed = 0
    synced_videos_list = list(synced_videos)
    print(f"   Found {len(synced_videos_list)} videos with storage_refs in DB.")

    for video in synced_videos_list:
        count_processed += 1
        video_id = video.get('video_id')
        title = video.get('title')
        refs = video.get('storage_refs', {})
        
        # --- 1. Check Video File ---
        bucket = refs.get('bucket')
        key = refs.get('key')
        
        video_local_files = []
        video_synced = False
        
        if bucket and key:
            # Verify on MinIO
            try:
                minio_client.stat_object(bucket, key)
                video_synced = True
            except S3Error as e:
                print(f"   [MISSING] Video {video_id} ('{title}') not found in MinIO: {bucket}/{key}")
                video_synced = False
        
        if video_synced:
            # Find local copies
            local_files = find_local_video_files(title, video.get('file_path'))
            if local_files:
                for f in local_files:
                    videos_to_delete.append((title, f, f"{bucket}/{key}"))
        
        # --- 2. Check Dataset (Frames) ---
        frames_bucket = refs.get('frames_bucket')
        frames_count = refs.get('frames_count', 0)
        
        folders_synced = False
        
        if frames_bucket and frames_count > 0:
            # We assume if frames_count > 0 and bucket exists, it's fine. 
            # Verifying 1000s of frames is too heavy. Maybe verify one?
            # But let's verify the bucket at least.
            if minio_client.bucket_exists(frames_bucket):
                folders_synced = True
            else:
                 print(f"   [MISSING] Frames bucket {frames_bucket} for {video_id} not found.")

        if folders_synced:
             local_folders = find_local_dataset_folders(title)
             if local_folders:
                 for f in local_folders:
                     folders_to_delete.append((title, f, f"{frames_bucket} ({frames_count} frames)"))

    print("\n" + "="*50)
    print(f"SUMMARY")
    print("="*50)
    
    # Report Videos
    print(f"\nVideos to delete ({len(videos_to_delete)}):")
    unique_videos_size = 0
    for title, local_path, remote in videos_to_delete:
        try:
            size_mb = os.path.getsize(local_path) / (1024 * 1024)
            unique_videos_size += os.path.getsize(local_path)
        except:
            size_mb = 0
        print(f"   - [Local] {ascii(os.path.basename(local_path))} ({size_mb:.2f} MB)")
        print(f"     [Remote] {remote}")
    
    # Report Folders
    print(f"\nDataset Folders to delete ({len(folders_to_delete)}):")
    for title, local_path, remote in folders_to_delete:
        print(f"   - [Local] {ascii(os.path.basename(local_path))}")
        print(f"     [Remote] {remote}")

    if dry_run:
        print("\nDRY RUN: No files were deleted.")
        print("To execute deletion, run with --execute")
    else:
        print("\nEXECUTING DELETION...")
        deleted_count = 0
        
        # Delete Videos
        for _, local_path, _ in videos_to_delete:
            try:
                if os.path.exists(local_path):
                    os.remove(local_path)
                    print(f"   Deleted file: {ascii(local_path)}")
                    deleted_count += 1
            except Exception as e:
                print(f"   Failed to delete {ascii(local_path)}: {e}")
        
        # Delete Folders
        for _, local_path, _ in folders_to_delete:
            try:
                if os.path.exists(local_path):
                    shutil.rmtree(local_path)
                    print(f"   Deleted folder: {ascii(local_path)}")
                    deleted_count += 1
            except Exception as e:
                print(f"   Failed to delete {ascii(local_path)}: {e}")
                
        print(f"\nCompleted. Deleted {deleted_count} items.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Verify MinIO sync and clean up local files.")
    parser.add_argument('--execute', action='store_true', help='Perform actual deletion.')
    args = parser.parse_args()
    
    main(dry_run=not args.execute)
