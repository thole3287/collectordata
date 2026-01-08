import cv2
import numpy as np

def analyze_scene_features(frame):
    """
    Analyze frame features to classify as 'day', 'night', or 'rain'.
    Returns: scene_type (str)
    """
    try:
        # 1. Convert to HSV for Brightness and Saturation
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        h, s, v = cv2.split(hsv)
        
        mean_brightness = np.mean(v)
        mean_saturation = np.mean(s)
        
        # 2. Convert to Grayscale for Contrast
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        std_contrast = np.std(gray)
        
        # 3. Heuristics
        # Night: Low brightness
        # Ban đêm (night): Nếu độ sáng trung bình (mean_brightness) < 70.
        if mean_brightness < 70: # Threshold for night
            return 'night'
            
        # Rain: Low saturation (grayish), Low contrast (foggy/rainy), 
        # distinct from just "Cloudy" but "Rain" often implies overcast/low contrast.
        # This is a basic heuristic.
        # Mưa (rain): Nếu độ bão hòa màu thấp (mean_saturation < 50) VÀ độ tương phản thấp (std_contrast < 40). Giả định là mưa thường làm cảnh vật xám xịt và mờ đi.
        if mean_saturation < 50 and std_contrast < 40:
             return 'rain'
             
        # Optional: Check for vertical streaks (Rain) - Advanced, maybe skip for now 
        # to ensure performance.
        # Ban ngày (day): Các trường hợp còn lại.
        return 'day'
        
    except Exception as e:
        print(f"Error analyzing scene: {e}")
        return 'day' # Default
