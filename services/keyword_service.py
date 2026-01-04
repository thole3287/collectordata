from datetime import datetime
from bson import ObjectId
from pymongo.errors import DuplicateKeyError
from services.database import get_db_connection

def get_all_keywords(active_only=False):
    """Lấy danh sách keywords"""
    db = get_db_connection()
    if db is None:
        return {'error': 'Không thể kết nối database'}
    
    collection = db['keywords']
    query = {}
    if active_only:
        query['is_active'] = True
    
    keywords = list(collection.find(query).sort('created_at', -1))
    
    # Convert ObjectId và datetime objects to strings
    for kw in keywords:
        kw['_id'] = str(kw['_id'])
        if 'last_downloaded_at' in kw and kw['last_downloaded_at'] and isinstance(kw['last_downloaded_at'], datetime):
            kw['last_downloaded_at'] = kw['last_downloaded_at'].isoformat()
        if 'created_at' in kw and isinstance(kw['created_at'], datetime):
            kw['created_at'] = kw['created_at'].isoformat()
        if 'updated_at' in kw and isinstance(kw['updated_at'], datetime):
            kw['updated_at'] = kw['updated_at'].isoformat()
            
    return keywords

def create_keyword(data):
    """Tạo keyword mới"""
    keyword = data.get('keyword', '').strip()
    num_videos = data.get('num_videos', 1)
    description = data.get('description', '')
    
    if not keyword:
        return {'error': 'Vui lòng nhập từ khóa'}
    
    db = get_db_connection()
    if db is None:
        return {'error': 'Không thể kết nối database'}
    
    collection = db['keywords']
    try:
        existing = collection.find_one({'keyword': keyword})
        if existing:
            return {'error': 'Keyword đã tồn tại'}
        
        now = datetime.now()
        document = {
            'keyword': keyword,
            'num_videos': num_videos,
            'status': 'pending',
            'total_downloaded': 0,
            'last_downloaded_at': None,
            'description': description,
            'is_active': True,
            'created_at': now,
            'updated_at': now
        }
        
        result = collection.insert_one(document)
        return {'message': 'Đã thêm keyword thành công', 'id': str(result.inserted_id)}
    except DuplicateKeyError:
        return {'error': 'Keyword đã tồn tại'}
    except Exception as e:
        return {'error': f'Lỗi: {str(e)}'}

def update_keyword(keyword_id, data):
    """Cập nhật keyword"""
    db = get_db_connection()
    if db is None:
        return {'error': 'Không thể kết nối database'}
    
    collection = db['keywords']
    
    try:
        keyword_obj_id = ObjectId(keyword_id)
    except:
        return {'error': 'Keyword ID không hợp lệ'}
    
    existing = collection.find_one({'_id': keyword_obj_id})
    if not existing:
        return {'error': 'Keyword không tồn tại'}
    
    update_doc = {'updated_at': datetime.now()}
    
    if 'keyword' in data:
        update_doc['keyword'] = data['keyword']
    if 'num_videos' in data:
        update_doc['num_videos'] = int(data['num_videos'])
    if 'description' in data:
        update_doc['description'] = data['description']
    if 'is_active' in data:
        update_doc['is_active'] = bool(data['is_active'])
    if 'status' in data:
        update_doc['status'] = data['status']
    
    if len(update_doc) == 1:
        return {'error': 'Không có trường nào để cập nhật'}
    
    collection.update_one({'_id': keyword_obj_id}, {'$set': update_doc})
    return {'message': 'Đã cập nhật keyword thành công'}

def delete_keyword(keyword_id):
    """Xóa keyword"""
    db = get_db_connection()
    if db is None:
        return {'error': 'Không thể kết nối database'}
    
    collection = db['keywords']
    try:
        keyword_obj_id = ObjectId(keyword_id)
    except:
        return {'error': 'Keyword ID không hợp lệ'}
    
    result = collection.delete_one({'_id': keyword_obj_id})
    if result.deleted_count == 0:
        return {'error': 'Keyword không tồn tại'}
    
    return {'message': 'Đã xóa keyword thành công'}

def get_keyword_by_id(keyword_id):
    """Lấy thông tin keyword theo ID"""
    db = get_db_connection()
    if db is None:
        return None
    
    try:
        return db['keywords'].find_one({'_id': ObjectId(keyword_id)})
    except:
        return None

def update_keyword_status(keyword_id, status, **kwargs):
    """Cập nhật status của keyword"""
    db = get_db_connection()
    if db is None:
        return False
        
    update_data = {'status': status, 'updated_at': datetime.now()}
    update_data.update(kwargs)
    
    try:
        db['keywords'].update_one(
            {'_id': ObjectId(keyword_id)},
            {
                '$set': update_data,
                '$inc': kwargs.get('inc', {})
            }
        )
        return True
    except:
        return False
