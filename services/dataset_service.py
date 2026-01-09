import services.database as db_service
import services.minio_service as minio_service
from bson import ObjectId
from datetime import datetime
import os
from flask import Response

def get_frames_service(params):
    """Get list of extracted frames with pagination and filtering"""
    try:
        db = db_service.get_db_connection()
        if db is None:
            return {'error': 'Database connection failed'}
        
        page = params.get('page', 1)
        per_page = params.get('per_page', 24)
        platform_filter = params.get('platform', '')
        search_query = params.get('search', '')
        video_id_filter = params.get('video_id', '')

        # distinct handling for Camera platform
        if platform_filter == 'camera':
            query = {}
            if search_query:
                query['$or'] = [
                    {'camera_name': {'$regex': search_query, '$options': 'i'}},
                    {'camera_id': {'$regex': search_query, '$options': 'i'}}
                ]
            
            # Filter by specific camera (video_id context)
            if video_id_filter:
                query['camera_id'] = video_id_filter
            
            # Count and Sort for Camera
            total_frames = db['camera_images'].count_documents(query)
            total_pages = (total_frames + per_page - 1) // per_page
            
            cursor = db['camera_images'].find(query).sort('timestamp', -1)
            cursor.skip((page - 1) * per_page).limit(per_page)
            
            frames = []
            for doc in cursor:
                # Map camera_images to unified frame structure
                frame_id = str(doc.get('_id', ''))
                
                # storage refs
                storage = doc.get('storage_refs', {})
                bucket = storage.get('bucket', 'dataset')
                key = storage.get('key', '')
                
                # Construct Proxy URL
                image_url = ""
                if bucket and key:
                    image_url = f"/api/image-proxy?bucket={bucket}&key={key}"
                elif 'file_path' in doc:
                     # Fallback for old local files (unlikely to work if not in minio, but kept for compat)
                     image_url = f"/api/camera/images/{os.path.basename(doc['file_path'])}"
                
                frames.append({
                    'id': frame_id,
                    'video_name': doc.get('camera_name', 'Unknown Camera'),
                    'video_id': doc.get('camera_id', ''),
                    'platform': 'camera',
                    'frame_index': 0, # Not applicable for single images
                    'frame_number': 0,
                    'video_frame_number': 0,
                    'file_size': doc.get('file_size', 0), # Might be missing
                    'scene_type': 'day', # TODO: Add scene detection for camera images later
                    'image_url': image_url,
                    'storage_bucket': bucket,
                    'storage_key': key,
                    'created_at': doc.get('timestamp', datetime.now()).isoformat()
                })
                
            return {
                'frames': frames,
                'total_frames': total_frames,
                'current_page': page,
                'total_pages': total_pages
            }
        
        # Standard Video Frames Logic (Youtube/Pexels)
        # Build Query
        query = {}
        if platform_filter and platform_filter != 'all':
            query['platform'] = platform_filter
            
        if video_id_filter:
            query['video_id'] = video_id_filter
            
        if search_query:
            # Search by video_name or video_id
            query['$or'] = [
                {'video_name': {'$regex': search_query, '$options': 'i'}},
                {'video_id': {'$regex': search_query, '$options': 'i'}}
            ]
        
        # Sort by most recent
        cursor = db['video_frames'].find(query).sort('created_at', -1)
        
        total_frames = db['video_frames'].count_documents(query)
        total_pages = (total_frames + per_page - 1) // per_page
        
        cursor.skip((page - 1) * per_page).limit(per_page)
        
        frames = []
        for doc in cursor:
            frame_id = str(doc.get('_id', ''))
            video_name = doc.get('video_name', '') or str(doc.get('video_id', 'unknown'))
            # Fix: Retrieve platform, defaulting to 'youtube' if missing
            platform = doc.get('platform', 'youtube') 
            
            image_url = f"/api/image/{frame_id}"
            
            # Rich Metadata for Passport View
            frames.append({
                'id': frame_id,
                'video_name': video_name,
                'video_id': doc.get('video_id', ''),
                'platform': platform,
                'frame_index': doc.get('frame_index', 0),
                'frame_number': doc.get('frame_number', ''),
                'video_frame_number': doc.get('video_frame_number', 0),
                'file_size': doc.get('file_size', 0),
                'scene_type': doc.get('scene_type', 'day'), # Detected scene
                'image_url': image_url,
                'storage_bucket': doc.get('storage_refs', {}).get('bucket', ''),
                'storage_key': doc.get('storage_refs', {}).get('key', ''),
                'created_at': doc.get('created_at', datetime.now()).isoformat()
            })
            
        return {
            'frames': frames,
            'total_frames': total_frames,
            'current_page': page,
            'total_pages': total_pages
        }
    except Exception as e:
        print(f"Error fetching frames: {e}")
        return {'error': str(e)}

def get_dataset_groups_service(params):
    """Lấy danh sách nhóm video"""
    try:
        db = db_service.get_db_connection()
        if db is None: return {'error': 'Kết nối DB thất bại'}
        
        page = params.get('page', 1)
        per_page = params.get('per_page', 20)
        platform_filter = params.get('platform', '')
        search_query = params.get('search', '')

        # --- CAMERA PLATFORM HANDLING ---
        if platform_filter == 'camera':
             # Aggregate camera_images to mimic groups
            match_stage = {}
            if search_query:
                match_stage['$or'] = [
                    {'camera_name': {'$regex': search_query, '$options': 'i'}},
                    {'camera_id': {'$regex': search_query, '$options': 'i'}}
                ]
            
            # Aggregation Pipeline
            pipeline = []
            if match_stage:
                pipeline.append({'$match': match_stage})
                
            pipeline.extend([
                {'$sort': {'timestamp': -1}},
                {'$group': {
                    '_id': '$camera_id',
                    'camera_name': {'$first': '$camera_name'},
                    'total_frames': {'$sum': 1},
                    'last_updated': {'$first': '$timestamp'},
                    'preview_doc': {'$first': '$$ROOT'}
                }},
                {'$sort': {'last_updated': -1}},
                {'$skip': (page - 1) * per_page},
                {'$limit': per_page}
            ])

            # Count total groups (cameras)
            distinct_query = match_stage
            total_groups = len(db['camera_images'].distinct('camera_id', distinct_query))
            
            cursor = db['camera_images'].aggregate(pipeline)
            
            groups = []
            for doc in cursor:
                c_id = doc['_id']
                last_up = doc['last_updated']
                preview = doc.get('preview_doc', {})
                
                # storage refs for preview
                storage = preview.get('storage_refs', {})
                bucket = storage.get('bucket', 'dataset')
                key = storage.get('key', '')
                
                preview_url = "/static/img/no-image.png"
                if bucket and key:
                    preview_url = f"/api/image-proxy?bucket={bucket}&key={key}"
                elif 'file_path' in preview:
                     preview_url = f"/api/camera/images/{os.path.basename(preview['file_path'])}"

                groups.append({
                    'video_id': c_id, # Use camera_id as video_id
                    'title': doc.get('camera_name', c_id),
                    'platform': 'camera',
                    'total_frames': doc['total_frames'],
                    'last_updated': last_up.isoformat() if isinstance(last_up, datetime) else str(last_up),
                    'weather': 'day', # TODO: Detect
                    'preview_image': preview_url
                })
                
            return {
                'groups': groups,
                'total_groups': total_groups,
                'page': page,
                'per_page': per_page,
                'total_pages': (total_groups + per_page - 1) // per_page if per_page > 0 else 1
            }

        # --- STANDARD VIDEO HANDLING (Youtube/Pexels/All) ---
        
        videos_collection = db['downloaded_videos']
        frames_collection = db['video_frames']
        
        # Build Query
        query = {}
        if platform_filter and platform_filter != 'all':
            query['platform'] = platform_filter
            
        if search_query:
            query['$or'] = [
                {'title': {'$regex': search_query, '$options': 'i'}},
                {'video_id': {'$regex': search_query, '$options': 'i'}}
            ]
        
        total_groups = videos_collection.count_documents(query)
        cursor = videos_collection.find(query).sort([('updated_at', -1), ('created_at', -1)]).skip((page - 1) * per_page).limit(per_page)
        
        videos = list(cursor)
        groups = []
        
        for v in videos:
            video_id = v.get('video_id', str(v.get('_id')))
            
            # 2. Get Frame Stats for this video
            total_frames = frames_collection.count_documents({'video_id': video_id})
            
            dominant_weather = 'unknown'
            preview_image = "/static/img/no-image.png"
            last_updated = v.get('updated_at') or v.get('created_at') or datetime.now()
            
            if total_frames > 0:
                # Get latest frame for preview and info
                latest_frame = frames_collection.find_one(
                    {'video_id': video_id},
                    sort=[('created_at', -1)]
                )
                
                if latest_frame:
                    if 'created_at' in latest_frame:
                         last_updated = latest_frame['created_at']
                    
                    if latest_frame.get('_id'):
                        preview_image = f"/api/image/{str(latest_frame['_id'])}"
                    
                    try:
                        pipeline = [
                            {'$match': {'video_id': video_id}},
                            {'$group': {'_id': {'$ifNull': ['$weather', '$scene_type']}, 'count': {'$sum': 1}}},
                            {'$sort': {'count': -1}},
                            {'$limit': 1}
                        ]
                        w_res = list(frames_collection.aggregate(pipeline))
                        if w_res:
                            dominant_weather = w_res[0]['_id']
                    except Exception:
                        dominant_weather = latest_frame.get('weather') or latest_frame.get('scene_type', 'unknown')

            groups.append({
                'video_id': video_id,
                'title': v.get('title', video_id),
                'platform': v.get('platform', 'unknown'),
                'total_frames': total_frames,
                'last_updated': last_updated.isoformat() if isinstance(last_updated, datetime) else str(last_updated),
                'weather': dominant_weather,
                'preview_image': preview_image
            })

        return {
            'groups': groups,
            'total_groups': total_groups,
            'page': page,
            'per_page': per_page,
            'total_pages': (total_groups + per_page - 1) // per_page
        }
    except Exception as e:
        print(f"Error getting dataset groups: {e}")
        return {'error': str(e)}

def get_dataset_stats_service():
    """Get aggregated statistics for the dataset dashboard"""
    try:
        db = db_service.get_db_connection()
        if db is None:
            return {'error': 'Database connection failed'}
            
        collection = db['video_frames']
        camera_collection = db['camera_images']
        
        # 1. Total Frames (Video + Camera)
        video_count = collection.count_documents({})
        camera_count = camera_collection.count_documents({})
        total_frames = video_count + camera_count
        
        # 2. Platform Distribution
        pipeline_platform = [
            {"$group": {"_id": "$platform", "count": {"$sum": 1}}}
        ]
        platform_stats = list(collection.aggregate(pipeline_platform))
        platforms = {item['_id'] or 'unknown': item['count'] for item in platform_stats}
        # Add Camera platform
        if camera_count > 0:
            platforms['camera'] = camera_count
        
        # 3. Collection Timeline (Last 7 days or groupings)
        # Helper to get timeline from a collection
        def get_timeline(coll, date_field):
            pipeline = [
                {
                    "$group": {
                        "_id": {
                            "$dateToString": {
                                "format": "%Y-%m-%d", 
                                "date": { 
                                    "$convert": { 
                                        "input": f"${date_field}", 
                                        "to": "date", 
                                        "onError": None, 
                                        "onNull": None 
                                    }
                                }
                            }
                        },
                        "count": {"$sum": 1}
                    }
                },
                {"$sort": {"_id": 1}},
                {"$limit": 30}
            ]
            return list(coll.aggregate(pipeline))

        video_timeline = get_timeline(collection, 'created_at')
        camera_timeline = get_timeline(camera_collection, 'timestamp')
        
        # Merge Timelines
        timeline_map = {}
        for item in video_timeline:
            date = item['_id']
            if date: timeline_map[date] = timeline_map.get(date, 0) + item['count']
            
        for item in camera_timeline:
            date = item['_id']
            if date: timeline_map[date] = timeline_map.get(date, 0) + item['count']
            
        # Convert back to list and sort
        timeline = [{"date": k, "count": v} for k, v in sorted(timeline_map.items())]
        
        return {
            'total_frames': total_frames,
            'platforms': platforms,
            'timeline': timeline
        }
    except Exception as e:
        print(f"Error getting stats: {e}")
        return {'error': str(e)}

def serve_image_service(frame_id):
    """Logic to serve MinIO image by frame ID"""
    try:
        db = db_service.get_db_connection()
        if db is None:
            return {'error': 'Database connection failed', 'status': 500}
            
        # Find frame doc
        frame = db['video_frames'].find_one({'_id': ObjectId(frame_id)})
        if not frame:
            return {'error': 'Frame not found', 'status': 404}
            
        # Get MinIO details
        storage_refs = frame.get('storage_refs', {})
        bucket = storage_refs.get('bucket')
        key = storage_refs.get('key')
        
        # Fallback mechanism
        if not bucket or not key:
             if frame.get('platform') == 'youtube' and frame.get('frame_number'):
                  bucket = minio_service.MINIO_BUCKET_FRAMES
                  key = f"youtube/{frame.get('video_id')}/{frame.get('frame_number')}.jpg"

             elif frame.get('platform') == 'pexels':
                  bucket = minio_service.MINIO_BUCKET_FRAMES
                  key = f"pexels/{frame.get('video_id')}/{frame.get('frame_number')}.jpg"

        if not bucket or not key:
            return {'error': 'Image location not valid', 'status': 404}
            
        # Get object from MinIO
        client = minio_service.get_minio_client()
        try:
            # Check if object exists
            try:
                client.stat_object(bucket, key)
            except Exception:
                return {'error': 'Image file missing in storage', 'status': 404}
                
            # Return valid data context for streaming in controller
            return {
                'bucket': bucket,
                'key': key,
                'status': 200
            }
            
        except Exception as e:
            print(f"MinIO fetch error: {e}")
            return {'error': 'Failed to retrieve image', 'status': 500}
            
    except Exception as e:
        print(f"Error serving image: {e}")
        return {'error': str(e), 'status': 500}
