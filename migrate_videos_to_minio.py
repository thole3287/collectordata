"""
Script để migrate video và frames cũ lên MinIO
Chạy script này để upload các video đã download trước đó lên MinIO
"""
import os
from dotenv import load_dotenv

load_dotenv()

def migrate_videos():
    """Migrate videos từ local lên MinIO"""
    try:
        import services.minio_service as minio_helper
        from yt_downloaderpy import get_db_connection
        from pymongo import MongoClient
        
        db = get_db_connection()
        if db is None:
            print("❌ Không thể kết nối database")
            return
        
        collection = db['downloaded_videos']
        
        # Tìm các video chưa có storage_refs
        videos_without_minio = collection.find({
            'file_path': {'$exists': True, '$ne': None},
            '$or': [
                {'storage_refs': {'$exists': False}},
                {'storage_refs': None}
            ]
        })
        
        total = collection.count_documents({
            'file_path': {'$exists': True, '$ne': None},
            '$or': [
                {'storage_refs': {'$exists': False}},
                {'storage_refs': None}
            ]
        })
        
        print(f"📦 Tìm thấy {total} video chưa có trong MinIO")
        
        if total == 0:
            print("✅ Tất cả video đã có trong MinIO!")
            return
        
        migrated = 0
        skipped = 0
        errors = 0
        
        for video in videos_without_minio:
            video_id = video.get('video_id')
            file_path = video.get('file_path')
            platform = video.get('platform', 'youtube')
            
            if not file_path:
                print(f"  ⚠ Video {video_id}: Không có đường dẫn file")
                skipped += 1
                continue

            # --- PATH CORRECTION LOGIC ---
            # Nếu path không tồn tại (do đường dẫn Windows v.s Linux Docker), thử fix
            if not os.path.exists(file_path):
                # Handle Windows paths on Linux (os.path.basename won't split backslashes)
                normalized_path = file_path.replace('\\', '/')
                filename = normalized_path.split('/')[-1]
                
                # Check 1: Relative 'downloads' folder
                alt_path_1 = os.path.join("downloads", filename)
                
                # Check 2: Absolute '/app/downloads' (Docker standard)
                alt_path_2 = os.path.join("/app/downloads", filename)
                
                # Check 3: Current directory
                alt_path_3 = filename
                
                if os.path.exists(alt_path_1):
                    file_path = alt_path_1
                elif os.path.exists(alt_path_2):
                    file_path = alt_path_2
                elif os.path.exists(alt_path_3):
                    file_path = alt_path_3
                else:
                    # CHECK FOR PARTIAL/UNMERGED FILES (Fix for missing FFmpeg issue)
                    # DB expects 'Video.mp4', disk has 'Video.f137.mp4' or 'Video.mp4.part'
                    found_partial = None
                    search_dir = "/app/downloads"
                    base_name = os.path.splitext(filename)[0]
                    
                    if os.path.exists(search_dir):
                        try:
                            for f in os.listdir(search_dir):
                                # Check if file starts with the base name and looks like a video part
                                # DEBUG:
                                # if "Hanoi" in f: print(f"DEBUG: Checking {f} against {base_name}")
                                
                                if f.startswith(base_name) and ('.f' in f or '.part' in f) and f.endswith(('.mp4', '.webm')):
                                    # Prioritize mp4 over webm, and larger files (higher res)
                                    candidate = os.path.join(search_dir, f)
                                    if not found_partial:
                                        found_partial = candidate
                                    else:
                                        # Simple heuristic: pick larger file
                                        if os.path.getsize(candidate) > os.path.getsize(found_partial):
                                            found_partial = candidate
                                            
                                # FALLBACK: If explicit startswith fails (due to unicode/encoding?), try loose match
                                elif base_name in f and ('.f' in f or '.part' in f) and f.endswith(('.mp4', '.webm')):
                                     candidate = os.path.join(search_dir, f)
                                     if not found_partial: found_partial = candidate
                        except Exception as e:
                            print(f"  ⚠ Error searching partials: {e}")

                    if found_partial:
                        print(f"  ⚠ Found partial/unmerged file, using: {os.path.basename(found_partial)}")
                        file_path = found_partial
                    else:
                        print(f"  ⚠ Video {video_id}: File không tồn tại - {file_path}")
                        skipped += 1
                        continue
            
            # Additional check for missing 'storage_refs' but file exists
            
            print(f"\n📹 Đang migrate video: {video_id}")
            print(f"   File: {file_path}")
            
            try:
                # Upload video lên MinIO
                file_ext = os.path.splitext(file_path)[1] or '.mp4'
                object_key = f"{platform}/{video_id}{file_ext}"
                
                result = minio_helper.upload_and_get_key(
                    file_path=file_path,
                    bucket_name=minio_helper.MINIO_BUCKET_VIDEOS,
                    custom_path=object_key,
                    content_type='video/mp4'
                )
                
                if not result.get('success'):
                    print(f"   ❌ Lỗi upload video: {result.get('error')}")
                    errors += 1
                    continue
                
                print(f"   ✓ Đã upload video: {result['bucket']}/{result['key']}")
                
                # Extract và upload frames
                storage_refs = {
                    'bucket': result['bucket'],
                    'key': result['key']
                }
                
                try:
                    # Lấy FPS từ metadata
                    fps = video.get('metadata', {}).get('fps') if video.get('metadata') else None
                    
                    frames_result = minio_helper.extract_and_upload_frames(
                        video_path=file_path,
                        video_id=video_id,
                        platform=platform,
                        fps=fps,
                        interval_seconds=None,
                        target_width=1280,
                        target_height=720,
                        db=db
                    )
                    
                    if frames_result.get('success'):
                        print(f"   ✓ Đã extract và upload {frames_result['frames_uploaded']} frames")
                        storage_refs.update({
                            'frames_bucket': frames_result['bucket'],
                            'frame_keys': frames_result.get('frame_keys', []),
                            'frames_count': frames_result.get('frames_uploaded', 0)
                        })
                    else:
                        print(f"   ⚠ Không thể extract frames: {frames_result.get('error')}")
                except Exception as e:
                    print(f"   ⚠ Lỗi khi extract frames: {e}")
                
                # Cập nhật MongoDB
                collection.update_one(
                    {'_id': video['_id']},
                    {'$set': {'storage_refs': storage_refs}}
                )
                
                migrated += 1
                migrated += 1
                print(f"   ✅ Hoàn thành video {video_id} ({migrated}/{total})")
                
                # --- AUTO DELETE LOCAL FILE ---
                try:
                    if os.path.exists(file_path):
                        os.remove(file_path)
                        print(f"   🗑 Đã xóa file local: {file_path}")
                except Exception as e:
                    print(f"   ⚠ Lỗi xóa file: {e}")
                
            except Exception as e:
                print(f"   ❌ Lỗi: {e}")
                errors += 1
        
        print(f"\n📊 Kết quả Migrate:")
        print(f"   ✅ Đã migrate: {migrated}")
        print(f"   ⚠ Bỏ qua: {skipped}")
        print(f"   ❌ Lỗi: {errors}")
        
        # --- PHASE 2: CLEANUP OLD MIGRATED FILES ---
        print("\n🧹 Bắt đầu dọn dẹp các video đã migrate trước đó...")
        
        migrated_videos = collection.find({
            'storage_refs': {'$exists': True},
            'file_path': {'$exists': True}
        })
        
        cleaned = 0
        search_dirs = ["/app/downloads", "downloads"]
        
        for vid in migrated_videos:
             # Logic tương tự để tìm file và xóa
             raw_path = vid.get('file_path', '')
             if not raw_path: continue
             
             # Check if path is NOT a MinIO path (bucket/key) -> MinIO paths don't start with / or C: usually, but let's be safe
             # Actually, if it was migrated, the DB 'file_path' MIGHT have been updated to 'bucket/key' in newer logic,
             # BUT in this script (line 172), we only updated 'storage_refs', NOT 'file_path'.
             # Wait, `yt_downloaderpy` updates `file_path` to MinIO path.
             # This script currently DOES NOT update `file_path`.
             # So `file_path` is still the local path. Perfect.
             
             # Try to find the file locally
             vid_id = vid.get('video_id')
             paths_to_check = []
             
             # 1. Exact raw path
             paths_to_check.append(raw_path)
             
             # 2. Normalized path (Docker)
             normalized = raw_path.replace('\\', '/')
             filename = normalized.split('/')[-1]
             for d in search_dirs:
                 paths_to_check.append(os.path.join(d, filename))
                 
             # 3. Partial files (re-use logic roughly)
             base = os.path.splitext(filename)[0]
             
             # Scan folders for partial matches if specific files don't exist
             # (Simplified for cleanup: just check known paths first)
             
             deleted = False
             
             # Direct check
             for p in paths_to_check:
                 if os.path.exists(p) and os.path.isfile(p):
                     try:
                         os.remove(p)
                         print(f"  🗑 [Cleanup] Đã xóa: {p}")
                         cleaned += 1
                         deleted = True
                         break # Delete once
                     except: pass
            
             if not deleted:
                 # Try partial scan in /app/downloads
                 c_dir = "/app/downloads"
                 if os.path.exists(c_dir):
                     try:
                         for f in os.listdir(c_dir):
                             if (base in f) and ('.f' in f or '.part' in f) and f.endswith(('.mp4', '.webm')):
                                 full_p = os.path.join(c_dir, f)
                                 try:
                                     os.remove(full_p)
                                     print(f"  🗑 [Cleanup Partial] Đã xóa: {full_p}")
                                     cleaned += 1
                                 except: pass
                     except: pass

        print(f"✨ Đã dọn dẹp thêm {cleaned} file cũ.")
        
    except Exception as e:
        print(f"❌ Lỗi: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("🚀 Bắt đầu migrate videos lên MinIO...")
    migrate_videos()






