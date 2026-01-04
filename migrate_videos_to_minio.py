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
            
            if not file_path or not os.path.exists(file_path):
                print(f"  ⚠ Video {video_id}: File không tồn tại - {file_path}")
                skipped += 1
                continue
            
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
                print(f"   ✅ Hoàn thành video {video_id} ({migrated}/{total})")
                
            except Exception as e:
                print(f"   ❌ Lỗi: {e}")
                errors += 1
        
        print(f"\n📊 Kết quả:")
        print(f"   ✅ Đã migrate: {migrated}")
        print(f"   ⚠ Bỏ qua: {skipped}")
        print(f"   ❌ Lỗi: {errors}")
        
    except Exception as e:
        print(f"❌ Lỗi: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("🚀 Bắt đầu migrate videos lên MinIO...")
    migrate_videos()





