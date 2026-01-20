import cv2
import numpy as np
import json
import os
from services.scene_analysis import analyze_scene_features

SETTINGS_FILE = 'enhance_settings.json'

DEFAULT_PARAMS = {
    'mean_intensity': "",
    'clahe_clip_limit': 1.0, 
    'gamma': 1.0,
    'denoise_strength': 0,
    'hue_shift': 0,
    'saturation_scale': 1.0,
    'contrast_scale': 1.0,
    'resize_640': False
}

DEFAULT_SETTINGS = {
    'enabled_camera': False,
    'enabled_video': False,
    'profiles': {
        'day': DEFAULT_PARAMS.copy(),
        'night': {**DEFAULT_PARAMS, 'gamma': 1.2, 'denoise_strength': 3.0, 'contrast_scale': 1.1}, # Night defaults
        'rain': {**DEFAULT_PARAMS, 'clahe_clip_limit': 2.0, 'contrast_scale': 1.2, 'saturation_scale': 1.1}, # Rain defaults
    }
}

def load_settings():
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                settings = json.load(f)
                
                # MIGRATION: Old flat params -> New Profiles
                if 'profiles' not in settings:
                    old_params = settings.get('params', DEFAULT_PARAMS.copy())
                    # Ensure new keys exist in old params
                    if 'resize_640' not in old_params: old_params['resize_640'] = False
                    
                    settings['profiles'] = {
                        'day': old_params,
                        'night': {**old_params, 'gamma': 1.2, 'denoise_strength': 3.0}, # Inherit + modify
                        'rain': {**old_params, 'clahe_clip_limit': 2.0}
                    }
                    if 'params' in settings: del settings['params']
                
                return settings
        except:
            return DEFAULT_SETTINGS
    return DEFAULT_SETTINGS

def save_settings(settings):
    try:
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(settings, f, indent=2)
        return True
    except Exception as e:
        print(f"Error saving settings: {e}")
        return False

# Copied and adapted from image_processor/app.py

def calculate_mean_intensity(image):
    """Tính độ sáng trung bình (Mean intensity)"""
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image
    return float(np.mean(gray))

def calculate_var_laplacian(image):
    """Tính độ mờ (Blur score) - Variance of Laplacian"""
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())

def resize_image(image, target_size=(640, 640)):
    """
    Resize ảnh về kích thước target_size giữ nguyên tỷ lệ và thêm padding (letterbox)
    """
    h, w = image.shape[:2]
    target_w, target_h = target_size
    
    # Calculate scale
    scale = min(target_w/w, target_h/h)
    new_w = int(w * scale)
    new_h = int(h * scale)
    
    # Resize keeping aspect ratio
    resized = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_AREA)
    
    # Create blank canvas
    canvas = np.full((target_h, target_w, 3), 0, dtype=np.uint8)
    
    # Center placement
    x_offset = (target_w - new_w) // 2
    y_offset = (target_h - new_h) // 2
    
    canvas[y_offset:y_offset+new_h, x_offset:x_offset+new_w] = resized
    
    return canvas

def apply_clahe(image, clip_limit=2.0, tile_grid_size=(8, 8)):
    """Áp dụng CLAHE (Contrast Limited Adaptive Histogram Equalization)"""
    if len(image.shape) == 3:
        lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=tile_grid_size)
        l = clahe.apply(l)
        enhanced = cv2.merge([l, a, b])
        return cv2.cvtColor(enhanced, cv2.COLOR_LAB2BGR)
    else:
        clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=tile_grid_size)
        return clahe.apply(image)

def apply_gamma_correction(image, gamma=1.0):
    """Áp dụng hiệu chỉnh Gamma"""
    if gamma == 1.0:
        return image
    inv_gamma = 1.0 / gamma
    table = np.array([((i / 255.0) ** inv_gamma) * 255 for i in np.arange(0, 256)]).astype("uint8")
    return cv2.LUT(image, table)

def apply_denoising(image, strength=0):
    """
    Áp dụng khử noise sử dụng Bilateral Filter
    strength: 0 = không khử, 1-10 = mức độ khử noise
    """
    if strength <= 0:
        return image
    
    # Bilateral filter parameters
    d = int(5 + strength)  # 5-15
    sigma_color = int(30 + strength * 5)  # 30-80
    sigma_space = int(30 + strength * 5)  # 30-80
    
    denoised = cv2.bilateralFilter(image, d, sigma_color, sigma_space)
    return denoised

def adjust_mean_intensity(image, target_mean):
    """
    Điều chỉnh độ sáng trung bình về giá trị target
    """
    current_mean = calculate_mean_intensity(image)
    if current_mean == 0:
        return image
    
    ratio = target_mean / current_mean
    adjusted = image.astype(np.float32) * ratio
    adjusted = np.clip(adjusted, 0, 255).astype(np.uint8)
    return adjusted

def adjust_hue_saturation(image, hue_shift=0, saturation_scale=1.0):
    """
    Điều chỉnh màu sắc (Hue) và độ bão hòa (Saturation)
    hue_shift: -180 đến 180
    saturation_scale: 0.0 đến 2.0
    """
    if hue_shift == 0 and saturation_scale == 1.0:
        return image
    
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV).astype(np.float32)
    h, s, v = cv2.split(hsv)
    
    if hue_shift != 0:
        h = (h + hue_shift / 2.0) % 180
    
    if saturation_scale != 1.0:
        s = s * saturation_scale
        s = np.clip(s, 0, 255)
    
    hsv = cv2.merge([h, s, v]).astype(np.uint8)
    adjusted = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
    return adjusted

def adjust_contrast(image, contrast_scale=1.0):
    """
    Điều chỉnh độ tương phản (Contrast)
    contrast_scale: 0.5 đến 2.0
    """
    if contrast_scale == 1.0:
        return image
    
    adjusted = image.astype(np.float32)
    adjusted = (adjusted - 128) * contrast_scale + 128
    adjusted = np.clip(adjusted, 0, 255).astype(np.uint8)
    return adjusted

def process_image(image, settings):
    """
    Hàm lợp chính áp dụng các bộ lọc theo settings
    settings: dict chứa config (contrast, gamma, clahe...)
    """
    if image is None:
        return None

    # Params
    denoise_strength = float(settings.get('denoise_strength', 0))
    hue_shift = float(settings.get('hue_shift', 0))
    saturation_scale = float(settings.get('saturation_scale', 1.0))
    contrast_scale = float(settings.get('contrast_scale', 1.0))
    mean_intensity = settings.get('mean_intensity') # Optional
    gamma = float(settings.get('gamma', 1.0))
    clahe_clip_limit = float(settings.get('clahe_clip_limit', 0))
    resize_640 = settings.get('resize_640', False) # New setting

    adjusted_image = image.copy()

    # 1. Denoise
    if denoise_strength > 0:
        adjusted_image = apply_denoising(adjusted_image, denoise_strength)

    # 2. Hue / Saturation
    if hue_shift != 0 or saturation_scale != 1.0:
        adjusted_image = adjust_hue_saturation(adjusted_image, hue_shift, saturation_scale)

    # 3. Contrast
    if contrast_scale != 1.0:
        adjusted_image = adjust_contrast(adjusted_image, contrast_scale)

    # 4. Mean Intensity
    if mean_intensity is not None and str(mean_intensity).strip() != "":
        try:
            target_mean = float(mean_intensity)
            adjusted_image = adjust_mean_intensity(adjusted_image, target_mean)
        except:
            pass

    # 5. Gamma
    if gamma != 1.0:
        adjusted_image = apply_gamma_correction(adjusted_image, gamma)

    # 6. CLAHE
    if clahe_clip_limit > 0.01:
        adjusted_image = apply_clahe(adjusted_image, clip_limit=clahe_clip_limit)

    # 7. Resize (Last step to retain details during processing)
    if resize_640:
        adjusted_image = resize_image(adjusted_image, (640, 640))

    return adjusted_image

def smart_process_image(image, global_settings):
    """
    Tự động nhận diện ngữ cảnh (Ngày/Đêm/Mưa) và áp dụng Profile phù hợp
    """
    if image is None: return None
    
    # 1. Detect Scene
    scene_type = analyze_scene_features(image)
    
    # 2. Select Profile
    profiles = global_settings.get('profiles', DEFAULT_SETTINGS['profiles'])
    profile_name = scene_type if scene_type in profiles else 'day'
    params = profiles.get(profile_name, profiles['day'])
    
    # 3. Process
    # print(f"DEBUG: Smart Process | Scene: {scene_type} | Profile: {profile_name}")
    processed = process_image(image, params)
    return processed, scene_type
