from flask import Blueprint, jsonify, request
import json
import os
import io
import cv2
import base64
import numpy as np
from services.image_enhancement import process_image, calculate_mean_intensity, calculate_var_laplacian, load_settings, save_settings

settings_bp = Blueprint('settings', __name__, url_prefix='/api/settings')

# Removed local load_settings/save_settings definitions to reuse service

@settings_bp.route('/', methods=['GET'])
def get_settings():
    return jsonify(load_settings())

@settings_bp.route('/', methods=['POST'])
def update_settings():
    try:
        data = request.json
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400
        
        # Validate/Merge with defaults if needed
        current = load_settings()
        
        # Merge
        if 'enabled_camera' in data: current['enabled_camera'] = data['enabled_camera']
        if 'enabled_video' in data: current['enabled_video'] = data['enabled_video']
        if 'params' in data:
            current['params'].update(data['params'])
        
        if save_settings(current):
            return jsonify({'success': True, 'settings': current})
        else:
            return jsonify({'success': False, 'error': 'Failed to save file'}), 500
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@settings_bp.route('/preview', methods=['POST'])
def preview_settings():
    """
    Apply settings to an uploaded image and return the result + metrics.
    Used for the Live Preview in the Settings Tab.
    """
    try:
        file = request.files.get('image')
        if not file:
            return jsonify({'error': 'No image provided'}), 400
            
        settings_json = request.form.get('settings')
        if not settings_json:
            return jsonify({'error': 'No settings provided'}), 400
        settings = json.loads(settings_json)
        
        # Read image
        np_img = np.frombuffer(file.read(), np.uint8)
        img = cv2.imdecode(np_img, cv2.IMREAD_COLOR)
        
        if img is None:
             return jsonify({'error': 'Invalid image'}), 400

        # Calculate metrics before
        metrics_before = {
            'mean_intensity': calculate_mean_intensity(img),
            'var_laplacian': calculate_var_laplacian(img)
        }
        
        # Process
        processed_img = process_image(img, settings)
        
        # Calculate metrics after
        metrics_after = {
            'mean_intensity': calculate_mean_intensity(processed_img),
            'var_laplacian': calculate_var_laplacian(processed_img)
        }
        
        # Convert to base64
        success, buffer = cv2.imencode('.jpg', processed_img)
        if not success:
             return jsonify({'error': 'Failed to encode image'}), 500
             
        img_str = base64.b64encode(buffer).decode('utf-8')
        
        return jsonify({
            'success': True,
            'image': f"data:image/jpeg;base64,{img_str}",
            'metrics_before': metrics_before,
            'metrics_after': metrics_after
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
