from services.database import get_db_connection
from datetime import datetime, timedelta

def check_recent_activity():
    db = get_db_connection()
    if db is None:
        print("Cannot connect to DB")
        return

    print("Checking recent Pexels activity (last 24h)...")
    
    # Check Videos
    videos_coll = db['downloaded_videos']
    recent_videos = list(videos_coll.find({
        'platform': 'pexels',
        'created_at': {'$gte': datetime.now() - timedelta(hours=24)}
    }).limit(5))
    
    print(f"Recent Pexels Videos: {len(recent_videos)}")
    for v in recent_videos:
        print(f" - {v.get('title')} ({v.get('created_at')})")
        
    # Check Frames
    frames_coll = db['video_frames']
    recent_frames = list(frames_coll.find({
        'platform': 'pexels',
        'created_at': {'$gte': datetime.now() - timedelta(hours=24)}
    }).limit(5))
    
    print(f"Recent Pexels Frames: {len(recent_frames)}")
    for f in recent_frames:
        print(f" - {f.get('video_id')} frame {f.get('frame_number')} ({f.get('created_at')})")

if __name__ == "__main__":
    check_recent_activity()
