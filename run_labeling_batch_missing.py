
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.getcwd())

load_dotenv()

from services.labeling_service import LabelingService
from services.minio_service import get_minio_client, MINIO_BUCKET_FRAMES
from services.database import get_db_connection

def main():
    print("🚀 Starting Batch Labeling Process (MISSING ONLY)...")
    
    # 1. Initialize Service with DB
    db = get_db_connection()
    if db is None:
        print("❌ Failed to connect to MongoDB.")
        return
        
    service = LabelingService(db=db)
    minio_client = get_minio_client()
    
    # 2. Optimization: Get set of ALREADY VISUALIZED files
    # Output key logic in service: visualized/{base_name}.jpg
    # Source: camera/folder/base_name.png
    
    print("🔍 Fetching existing labeled data (visualized/*)...")
    existing_visualized = set()
    try:
        # Recursive list of 'visualized' folder
        objects = minio_client.list_objects(MINIO_BUCKET_FRAMES, prefix="visualized", recursive=True)
        for obj in objects:
            # Store just the filename (base_name.jpg) or full path?
            # Service logic: vis_key = f"visualized/{base_name}.jpg"
            # We can store the 'base_name' for easier matching if filenames are unique enough
            # OR better: iterate source, construct expected vis_key, check existence.
            # Storing full key in set is safest.
            existing_visualized.add(obj.object_name)
    except Exception as e:
        print(f"Error listing visualized objects: {e}")
        
    print(f"📦 Found {len(existing_visualized)} existing visualized files.")

    # 3. List Source Images
    prefixes = ["camera", "pexels", "youtube"]
    all_objects = []
    
    print("🔍 Listing source images from MinIO...")
    for prefix in prefixes:
        try:
            objects = minio_client.list_objects(MINIO_BUCKET_FRAMES, prefix=prefix, recursive=True)
            for obj in objects:
                if obj.is_dir: continue
                if obj.object_name.lower().endswith(('.jpg', '.jpeg', '.png')):
                    all_objects.append(obj.object_name)
        except Exception as e:
            print(f"Error listing {prefix}: {e}")
            
    total_imgs = len(all_objects)
    print(f"📦 Found {total_imgs} source images total.")
    
    # 4. Filter for MISSING items
    missing_objects = []
    for obj_name in all_objects:
        # Construct expected output key
        # base_name = os.path.splitext(obj_name)[0] -> This keeps the path! e.g. camera/subdir/image
        # But wait, logic in service:
        # base_name = os.path.splitext(object_name)[0] (includes path 'camera/...')
        # vis_key = f"visualized/{base_name}.jpg" -> "visualized/camera/subdir/image.jpg"
        
        base_name_with_path = os.path.splitext(obj_name)[0]
        
        # Check if jpg or png output exists (Service currently outputs .jpg for visualized)
        expected_vis_key = f"visualized/{base_name_with_path}.jpg"
        
        if expected_vis_key not in existing_visualized:
            missing_objects.append(obj_name)
            
    print(f"⚠️  Found {len(missing_objects)} images NOT yet labeled.")
    
    if len(missing_objects) == 0:
        print("✅ Everything is already labeled! Exiting.")
        return

    # 5. Process Missing
    processed = 0
    errors = 0
    
    print(f"▶️  Processing {len(missing_objects)} missing images...")
    with tqdm(total=len(missing_objects), desc="Labeling Missing") as pbar:
        for obj_name in missing_objects:
            try:
                result = service.process_single_image(obj_name)
                
                if result.get('success'):
                    # concise log
                    pass 
                else:
                    errors += 1
                    tqdm.write(f"[ERR] Failed {obj_name}: {result.get('error')}")
            except Exception as e:
                errors += 1
                tqdm.write(f"[EXC] Error {obj_name}: {e}")
                
            pbar.update(1)
            processed += 1

    print(f"\n✅ Completed: {processed}/{len(missing_objects)}")
    if errors > 0:
        print(f"❌ Errors: {errors}")

if __name__ == "__main__":
    main()
