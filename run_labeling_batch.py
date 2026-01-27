
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
    print("🚀 Starting Batch Labeling Process...")
    
    # 1. Initialize Service with DB
    db = get_db_connection()
    if db is None:
        print("❌ Failed to connect to MongoDB.")
        return
        
    service = LabelingService(db=db)
    minio_client = get_minio_client()
    
    # 2. List all images từ MinIO (luôn chạy lại từ đầu, không skip ảnh đã labeled)
    prefixes = ["camera", "pexels", "youtube"]
    all_objects = []
    
    print("🔍 Listing objects from MinIO...")
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
    print(f"📦 Found {total_imgs} images total.")
    
    if total_imgs == 0:
        return

    # 4. Process Pool
    # We can use ThreadPool because I/O (MinIO) is significant, 
    # but inference is CPU/GPU bound. 
    # If running on typical CPU, standard loop might be safer or small pool.
    # User said "chạy hết", so let's do sequential or small consistent batch to avoid crashing their machine.
    
    # Let's use simple sequential for safety and clear logging first, 
    # or a small pool (workers=2) to balance I/O and CPU.
    
    processed = 0
    errors = 0
    
    # Chạy FULL tất cả ảnh
    print(f"🔎 Running full batch on {total_imgs} images (re-label all)...")
    with tqdm(total=total_imgs, desc="Labeling Images") as pbar:
        for obj_name in all_objects:
            try:
                # Check if already done? 
                # (Optional optimization: Check if 'visualized/...' key exists. 
                # But user might want to re-run. Let's run all for now.)
                
                result = service.process_single_image(obj_name)
                
                if result.get('success'):
                    # Debug log for success
                    print(f"[OK] Labeled {obj_name} with winner={result.get('winner')} (dets={len(result.get('detections', []))})")
                else:
                    errors += 1
                    print(f"[ERR] Failed to label {obj_name}: {result.get('error')}")
            except Exception as e:
                errors += 1
                print(f"[EXC] Error processing {obj_name}: {e}")
                
            pbar.update(1)
            processed += 1

    print(f"\n✅ Completed: {processed}/{total_imgs}")
    print(f"❌ Errors: {errors}")

if __name__ == "__main__":
    main()
