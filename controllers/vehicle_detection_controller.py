from flask import jsonify, request
import cv2
import numpy as np
import os
from datetime import datetime
import services.database as db_service
import services.minio_service as minio_service

def upload_vehicle_detection():
    try:
        db = db_service.get_db_connection()
        if db is None: return jsonify({'error': 'Database connection failed'}), 500
        
        data = request.get_json()
        event_id = data.get('event_id') or f"evt_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
        camera_id = data.get('camera_id', 'unknown')
        
        timestamp = datetime.now()
        if data.get('timestamp'):
            timestamp = datetime.fromisoformat(data['timestamp'])
            
        detection_data = {
            'event_id': event_id,
            'timestamp': timestamp,
            'camera_id': camera_id,
            'location': data.get('location', {}),
            'vehicle_type': data.get('vehicle_type'),
            'license_plate': data.get('license_plate'),
            'color': data.get('color'),
            'confidence': data.get('confidence', 0.0)
        }
        
        storage_refs = {'bucket': minio_service.MINIO_BUCKET_VEHICLE_DETECTION}
        
        # Upload helpers
        def convert_and_upload_png(path, type_):
            if path and os.path.exists(path):
                # Convert to PNG 16-bit
                try:
                    img = cv2.imread(path)
                    if img is not None:
                        # Resize if type is 'full' (Full Frame)
                        if type_ == 'full':
                            img = cv2.resize(img, (1280, 720), interpolation=cv2.INTER_AREA)
                            
                        img_16bit = img.astype(np.uint16) * 256
                        # Use .png extension
                        base_name = os.path.splitext(os.path.basename(path))[0]
                        png_path = os.path.join(os.path.dirname(path), f"{base_name}.png")
                        cv2.imwrite(png_path, img_16bit)
                        
                        # Upload PNG
                        res = minio_service.upload_and_get_key(
                            png_path, 
                            minio_service.MINIO_BUCKET_VEHICLE_DETECTION, 
                            camera_id=camera_id, 
                            event_id=event_id, 
                            file_type=type_, 
                            content_type='image/png'
                        )
                        
                        # Cleanup generated PNG
                        try:
                            os.remove(png_path)
                            # Optionally delete original JPG if needed? keeping it safe for now.
                        except:
                            pass
                            
                        return res['key'] if res['success'] else None
                except Exception as e:
                    print(f"Error converting/uploading PNG: {e}")
                    pass
            return None

        storage_refs['full_frame_key'] = convert_and_upload_png(data.get('full_frame_path'), 'full')
        storage_refs['cropped_vehicle_key'] = convert_and_upload_png(data.get('cropped_vehicle_path'), 'crop')
        storage_refs['cropped_plate_key'] = convert_and_upload_png(data.get('cropped_plate_path'), 'plate')
        
        if data.get('video_clip_path'):
            res = minio_service.upload_and_get_key(data['video_clip_path'], minio_service.MINIO_BUCKET_VEHICLE_DETECTION, camera_id=camera_id, event_id=event_id, file_type='video', content_type='video/mp4')
            if res['success']: storage_refs['video_clip_key'] = res['key']
            
        doc_id = minio_service.save_vehicle_detection_to_mongodb(db, detection_data, storage_refs)
        
        if doc_id:
            return jsonify({'success': True, 'event_id': event_id, 'document_id': str(doc_id), 'storage_refs': storage_refs}), 201
        return jsonify({'error': 'Failed to save to MongoDB'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def get_vehicle_detection(event_id):
    try:
        db = db_service.get_db_connection()
        if db is None: return jsonify({'error': 'Database connection failed'}), 500
        expires = request.args.get('expires', 3600, type=int)
        result = minio_service.get_presigned_urls_for_detection(db, event_id, expires=expires)
        if result: return jsonify(result), 200
        return jsonify({'error': 'Detection not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def search_vehicle_detections():
    try:
        db = db_service.get_db_connection()
        if db is None: return jsonify({'error': 'Database connection failed'}), 500
        collection = db['vehicle_detections']
        
        query = {}
        if request.args.get('license_plate'): query['detection_data.license_plate'] = {'$regex': request.args.get('license_plate'), '$options': 'i'}
        if request.args.get('vehicle_type'): query['detection_data.vehicle_type'] = request.args.get('vehicle_type')
        if request.args.get('camera_id'): query['camera_id'] = request.args.get('camera_id')
        if request.args.get('date_from'): query.setdefault('timestamp', {})['$gte'] = datetime.fromisoformat(request.args.get('date_from'))
        if request.args.get('date_to'): query.setdefault('timestamp', {})['$lte'] = datetime.fromisoformat(request.args.get('date_to'))
        
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        
        total = collection.count_documents(query)
        detections = list(collection.find(query).sort('timestamp', -1).skip((page-1)*per_page).limit(per_page))
        
        for det in detections:
            det['_id'] = str(det['_id'])
            if 'timestamp' in det and isinstance(det['timestamp'], datetime):
                det['timestamp'] = det['timestamp'].isoformat()
            if 'created_at' in det and isinstance(det['created_at'], datetime):
                det['created_at'] = det['created_at'].isoformat()
            if 'updated_at' in det and isinstance(det['updated_at'], datetime):
                det['updated_at'] = det['updated_at'].isoformat()
        
        return jsonify({'total': total, 'page': page, 'per_page': per_page, 'total_pages': (total + per_page - 1) // per_page, 'detections': detections}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
