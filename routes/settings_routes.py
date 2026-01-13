from flask import Blueprint, jsonify, request
import json
import os
import io
import cv2
import base64
import numpy as np
from services.image_enhancement import process_image, smart_process_image, calculate_mean_intensity, calculate_var_laplacian, load_settings, save_settings

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
        
        # Load existing
        current = load_settings()
        
        # Merge Top Level
        if 'enabled_camera' in data: current['enabled_camera'] = data['enabled_camera']
        if 'enabled_video' in data: current['enabled_video'] = data['enabled_video']
        
        # Merge Profiles
        if 'profiles' in data:
            if 'profiles' not in current: current['profiles'] = {}
            for profile_name, prf_params in data['profiles'].items():
                if profile_name in current['profiles']:
                    current['profiles'][profile_name].update(prf_params)
                else:
                    current['profiles'][profile_name] = prf_params

        # Fallback for old single-profile updates (optional backwards compat)
        if 'params' in data:
             # If "params" is sent, assume it updates 'day' or all? 
             # Let's assume it updates 'day' as default if profiles not specified
             if 'day' in current['profiles']:
                 current['profiles']['day'].update(data['params'])

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
        
        # Specific profile to preview (optional)
        preview_profile = request.form.get('preview_profile') 
        
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
        if preview_profile and 'profiles' in settings and preview_profile in settings['profiles']:
             # Use specific profile params directly
             # print(f"Previewing specific profile: {preview_profile}")
             processed_img = process_image(img, settings['profiles'][preview_profile])
             used_profile = preview_profile
        else:
             # Use smart detection
             # We need to construct a fake "global settings" object if only params were sent?
             # Actually the frontend sends the full settings object now.
             processed_img, used_profile = smart_process_image(img, settings)
        
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
            'metrics_after': metrics_after,
            'detected_profile': used_profile
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
