from datetime import datetime, timedelta
import services.database as db_service
import services.minio_service as minio_service

def get_general_stats():
    """Lấy thống kê tổng quan cho dashboard"""
    try:
        db = db_service.get_db_connection()
        if db is None:
            return {'error': 'Không thể kết nối database'}
        
        collection = db['downloaded_videos']
        total_videos = collection.count_documents({})
        
        pipeline_method = [{'$group': {'_id': '$download_method', 'count': {'$sum': 1}}}]
        by_method = {row['_id']: row['count'] for row in collection.aggregate(pipeline_method)}
        
        yesterday = datetime.now() - timedelta(hours=24)
        recent_24h = collection.count_documents({'downloaded_at': {'$gte': yesterday}})
        
        return {
            'total_videos': total_videos,
            'by_method': by_method,
            'recent_24h': recent_24h
        }
    except Exception as e:
        return {'error': str(e)}

def get_visualization_data():
    """Lấy dữ liệu cho các biểu đồ visualize"""
    try:
        db = db_service.get_db_connection()
        if db is None:
            return {'error': 'Không thể kết nối database'}
        
        collection = db['downloaded_videos']
        frames_collection = db['video_frames']
        
        # 1. Platform
        pipeline_platform = [{'$group': {'_id': '$platform', 'count': {'$sum': 1}}}]
        by_platform = [{'platform': row['_id'], 'count': row['count']} for row in collection.aggregate(pipeline_platform)]
        
        # 2. Keywords
        pipeline_keyword = [
            {'$match': {'keyword': {'$ne': None}}},
            {'$group': {'_id': '$keyword', 'count': {'$sum': 1}, 'platforms': {'$addToSet': '$platform'}}},
            {'$sort': {'count': -1}},
            {'$limit': 20}
        ]
        by_keyword = []
        for r in collection.aggregate(pipeline_keyword):
            kw_display = r['_id']
            # Nếu keyword có dạng "Search || Filter", chỉ lấy phần Search
            if '||' in kw_display:
                kw_display = kw_display.split('||')[0].strip()
            
            by_keyword.append({
                'keyword': kw_display, 
                'count': r['count'], 
                'platforms': r['platforms']
            })

        # --- NEW: Calculate Frame Counts per Keyword ---
        try:
            # 1. Aggregate frames count by video_id
            pipeline_frames = [
                {'$group': {'_id': '$video_id', 'count': {'$sum': 1}}}
            ]
            frame_counts_map = {str(r['_id']): r['count'] for r in frames_collection.aggregate(pipeline_frames)}

            # --- NEW: Aggregate LABELED frames count by video_id ---
            pipeline_labeled = [
                {'$match': {'label_status': 'labeled'}},
                {'$group': {'_id': '$video_id', 'count': {'$sum': 1}}}
            ]
            labeled_counts_map = {str(r['_id']): r['count'] for r in frames_collection.aggregate(pipeline_labeled)}
            # -------------------------------------------------------
            
            # 2. Get VideoID -> Keyword mapping
            videos_cursor = collection.find({'keyword': {'$ne': None}}, {'video_id': 1, 'keyword': 1})
            
            keyword_frame_counts = {}
            keyword_labeled_counts = {} # Store labeled counts
            
            for video in videos_cursor:
                vid = str(video.get('video_id'))
                kw_raw = video.get('keyword', '')
                if not kw_raw: continue
                
                # Clean keyword
                kw_clean = kw_raw.split('||')[0].strip() if '||' in kw_raw else kw_raw.strip()
                
                # Get count for this video
                cnt = frame_counts_map.get(vid, 0)
                l_cnt = labeled_counts_map.get(vid, 0) # Labeled count
                
                # Accumulate
                if cnt > 0:
                    keyword_frame_counts[kw_clean] = keyword_frame_counts.get(kw_clean, 0) + cnt
                
                if l_cnt > 0:
                    keyword_labeled_counts[kw_clean] = keyword_labeled_counts.get(kw_clean, 0) + l_cnt
            
            # 3. Update by_keyword list
            for item in by_keyword:
                kw = item['keyword']
                item['frame_count'] = keyword_frame_counts.get(kw, 0)
                item['labeled_count'] = keyword_labeled_counts.get(kw, 0)
                
        except Exception as e:
            print(f"[WARN] Error calculating frame counts for keywords: {e}")
            # Non-critical, continue without frame counts
            pass
        # ---------------------------------------------
        
        # 3. Resolution
        pipeline_res = [
            {'$match': {'metadata.resolution': {'$ne': None}}},
            {'$group': {'_id': '$metadata.resolution', 'count': {'$sum': 1}}},
            {'$sort': {'count': -1}}
        ]
        by_resolution = [{'resolution': r['_id'], 'count': r['count']} for r in collection.aggregate(pipeline_res)]
        
        # 4. Method
        pipeline_meth = [{'$group': {'_id': '$download_method', 'count': {'$sum': 1}}}]
        by_method = [{'method': r['_id'], 'count': r['count']} for r in collection.aggregate(pipeline_meth)]
        
        # 5. Date
        pipeline_date = [
            {'$group': {'_id': {'$dateToString': {'format': '%Y-%m-%d', 'date': '$downloaded_at'}}, 'count': {'$sum': 1}}},
            {'$sort': {'_id': -1}},
            {'$limit': 30}
        ]
        by_date = [{'date': r['_id'], 'count': r['count']} for r in collection.aggregate(pipeline_date)]
        
        # 6. Weather
        pipeline_weather = [
            {'$group': {'_id': {'$ifNull': ['$weather', '$scene_type']}, 'count': {'$sum': 1}}},
            {'$match': {'_id': {'$ne': None}}}
        ]
        by_weather = [{'weather': r['_id'], 'count': r['count']} for r in frames_collection.aggregate(pipeline_weather)]

        # 7. Duration
        pipeline_dur = [
            {'$match': {'metadata.duration': {'$ne': None}}},
            {'$addFields': {'duration_range': {'$switch': {'branches': [
                {'case': {'$lt': ['$metadata.duration', 60]}, 'then': '0-60s'},
                {'case': {'$lt': ['$metadata.duration', 300]}, 'then': '1-5min'},
                {'case': {'$lt': ['$metadata.duration', 600]}, 'then': '5-10min'},
                {'case': {'$lt': ['$metadata.duration', 1800]}, 'then': '10-30min'},
                {'case': {'$gte': ['$metadata.duration', 1800]}, 'then': '30min+'}
            ], 'default': 'unknown'}}}},
            {'$group': {'_id': '$duration_range', 'count': {'$sum': 1}}}
        ]
        by_dur_raw = list(collection.aggregate(pipeline_dur))
        order_map = {'0-60s': 1, '1-5min': 2, '5-10min': 3, '10-30min': 4, '30min+': 5}
        by_duration = sorted([{'range': r['_id'], 'count': r['count']} for r in by_dur_raw], key=lambda x: order_map.get(x['range'], 99))
        
        # 7. Quality
        total = collection.count_documents({})
        has_file = collection.count_documents({'file_path': {'$ne': None}})
        has_dur = collection.count_documents({'metadata.duration': {'$ne': None}})
        has_res = collection.count_documents({'metadata.resolution': {'$ne': None}})
        has_kw = collection.count_documents({'keyword': {'$ne': None}})
        
        quality = {
            'total': total,
            'has_file': has_file,
            'has_duration': has_dur,
            'has_resolution': has_res,
            'has_keyword': has_kw,
            'completeness': {
                'file': round((has_file/total*100) if total else 0, 2),
                'duration': round((has_dur/total*100) if total else 0, 2),
                'resolution': round((has_res/total*100) if total else 0, 2),
                'keyword': round((has_kw/total*100) if total else 0, 2),
            }
        }
        
        return {
            'by_platform': by_platform,
            'by_keyword': by_keyword,
            'by_resolution': by_resolution,
            'by_method': by_method,
            'by_date': by_date,
            'by_duration': by_duration,
            'by_weather': by_weather,
            'quality': quality
        }
    except Exception as e:
        return {'error': str(e)}
