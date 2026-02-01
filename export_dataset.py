import os
import zipfile
import shutil
from tqdm import tqdm
from services.minio_service import get_minio_client, MINIO_BUCKET_FRAMES

# Configuration
EXPORT_DIR = "export_dataset"
ZIP_FILENAME = "dataset_images.zip"
BUCKET_NAME = MINIO_BUCKET_FRAMES # Should be 'dataset'

def export_images():
    print(f"🚀 Starting export from bucket: {BUCKET_NAME}")
    
    client = get_minio_client()
    
    # 1. Ensure export directory exists
    if os.path.exists(EXPORT_DIR):
        shutil.rmtree(EXPORT_DIR)
    os.makedirs(EXPORT_DIR)
    
    # 2. List all objects
    print("📋 Listing files...")
    try:
        objects = client.list_objects(BUCKET_NAME, recursive=True)
        # Convert to list to get total count (might take a moment for huge buckets)
        object_list = list(objects)
        total_files = len(object_list)
        print(f"📦 Found {total_files} files.")
    except Exception as e:
        print(f"❌ Error listing objects: {e}")
        return

    if total_files == 0:
        print("⚠ Bucket is empty.")
        return

    # 3. Download files
    print("⬇ Downloading files...")
    count = 0
    errors = 0
    
    for obj in tqdm(object_list, total=total_files, unit="file"):
        try:
            # Construct local path (preserve structure)
            # obj.object_name might be "youtube/day/vid123/frame.png"
            # We want export_dataset/youtube/day/vid123/frame.png
            
            # Windows path handling
            safe_name = obj.object_name.replace('/', os.sep)
            local_path = os.path.join(EXPORT_DIR, safe_name)
            
            # Ensure parent dir exists
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            
            client.fget_object(BUCKET_NAME, obj.object_name, local_path)
            count += 1
        except Exception as e:
            # print(f"  ❌ Error downloading {obj.object_name}: {e}")
            errors += 1

    print(f"\n✅ Downloaded {count} files. Errors: {errors}")

    # 4. Zip the directory
    print(f"🤐 Zipping to {ZIP_FILENAME}...")
    try:
        with zipfile.ZipFile(ZIP_FILENAME, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(EXPORT_DIR):
                for file in files:
                    file_path = os.path.join(root, file)
                    # Archive name should be relative to EXPORT_DIR
                    arcname = os.path.relpath(file_path, EXPORT_DIR)
                    zipf.write(file_path, arcname)
        print(f"🎉 Created {ZIP_FILENAME} successfully!")
        
        # Optional: Ask to cleanup raw folder
        # shutil.rmtree(EXPORT_DIR) 
        # print("🧹 Cleaned up temporary export folder.")
        
    except Exception as e:
        print(f"❌ Error zipping: {e}")

if __name__ == "__main__":
    export_images()
