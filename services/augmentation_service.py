
import cv2
import albumentations as A
import services.image_enhancement as image_enhancement

def augment_image(image):
    """
    Generate augmented versions of the input image based on settings.
    Returns a list of tuples: [(image, suffix_name), ...]
    Includes the original image with suffix 'original'.
    """
    settings = image_enhancement.load_settings()
    
    # Global angle setting or default 15
    angle = int(settings.get('rotation_angle', 15))
    
    transforms = [
        # 1. Rotate Left
        (A.Compose([A.Rotate(limit=(angle, angle), p=1.0)]), f"rotate_left_{angle}"), 
        # Note: albumentations Rotate positive is counter-clockwise (Left)? 
        # Let's verify: limit=(15, 15) usually means rotate 15 degrees. 
        # In standard image coords (y down), positive rotation is usually clockwise? 
        # Actually user code said: limit=(-15, -15) is Left, (15, 15) is Right.
        # Let's stick to user's convention if possible, or standard.
        # User code: limit=(-15, -15) # Xoay 15 độ trái.
        # User code: limit=(15, 15)   # Xoay 15 độ phải.
        
        (A.Compose([A.Rotate(limit=(-angle, -angle), p=1.0)]), f"rotate_left_{angle}"),
        (A.Compose([A.Rotate(limit=(angle, angle), p=1.0)]), f"rotate_right_{angle}"),
        
        # 3. Flip + Rotate Left
        (A.Compose([A.HorizontalFlip(p=1.0), A.Rotate(limit=(-angle, -angle), p=1.0)]), f"flip_rotate_left_{angle}"),
        
        # 4. Flip + Rotate Right
        (A.Compose([A.HorizontalFlip(p=1.0), A.Rotate(limit=(angle, angle), p=1.0)]), f"flip_rotate_right_{angle}"),
    ]
    
    # Input is BGR (OpenCV), Albumentations expects RGB
    image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    
    results = []
    
    # 1. Original
    results.append((image, "")) # Empty suffix for original? Or "_original"?
    # User said: "1 thành 4 tổng thành 5".
    # Usually original is just kept as is. Suffix "" means filename remains "video_fr123.png".
    
    # 2. Augmented
    for transform, suffix in transforms:
        try:
            aug = transform(image=image_rgb)["image"]
            aug_bgr = cv2.cvtColor(aug, cv2.COLOR_RGB2BGR)
            results.append((aug_bgr, "_" + suffix))
        except Exception as e:
            print(f"Error augmenting image ({suffix}): {e}")
            
    return results
