import cv2
import numpy as np
import json
import os

SETTINGS_FILE = 'enhance_settings.json'

DEFAULT_SETTINGS = {
    'enabled_camera': False,
    'enabled_video': False,
    'params': {
        'mean_intensity': "",
        'clahe_clip_limit': 1.0, 
        'gamma': 1.0,
        'denoise_strength': 0,
        'hue_shift': 0,
        'saturation_scale': 1.0,
        'contrast_scale': 1.0,
        'resize_640': False  # New setting
    }
}

def load_settings():
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                settings = json.load(f)
                # Ensure new key exists in old files
                if 'resize_640' not in settings.get('params', {}):
                    if 'params' not in settings: settings['params'] = {}
                    settings['params']['resize_640'] = False
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
    """Resize ảnh về kích thước target_size"""
    return cv2.resize(image, target_size, interpolation=cv2.INTER_AREA)

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
