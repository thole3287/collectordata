import os
import services.minio_service as minio_helper
from yt_downloaderpy import get_db_connection

def diagnose():
    print("--- DIAGNOSTIC START ---")
    db = get_db_connection()
    collection = db['downloaded_videos']
    
    # Get one problem video from DB
    # Example: Innovv K6 (Video vfpASuWG-O0)
    target_id = "vfpASuWG-O0" 
    video = collection.find_one({'video_id': target_id})
    
    if not video:
        print(f"Video {target_id} not found in DB")
        return

    db_path = video.get('file_path')
    print(f"DB Raw Path: {repr(db_path)}")
    
    normalized_path = db_path.replace('\\', '/')
    db_filename = normalized_path.split('/')[-1]
    db_basename = os.path.splitext(db_filename)[0]
    
    print(f"DB Filename: {repr(db_filename)}")
    print(f"DB Basename: {repr(db_basename)}")
    
    search_dir = "/app/downloads"
    print(f"\nListing {search_dir} matching 'Innovv K6':")
    
    found_any = False
    if os.path.exists(search_dir):
        for f in os.listdir(search_dir):
            if "Innovv K6" in f:
                found_any = True
                print(f"FS Filename: {repr(f)}")
                
                if f.startswith(db_basename):
                    print("   -> startswith MATCH!")
                else:
                    print("   -> startswith FAIL")
                    
                if db_basename in f:
                    print("   -> 'in' MATCH!")
                else:
                    print("   -> 'in' FAIL")
                    
    if not found_any:
        print("No files found matching 'Innovv K6' in filesystem")

if __name__ == "__main__":
    diagnose()
