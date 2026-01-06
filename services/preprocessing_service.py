
import os
import sys
import json
import logging
from pathlib import Path

# Setup logging
logger = logging.getLogger(__name__)

# Add image-preprocessing code to path
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
preprocessing_dir = os.path.join(root_dir, 'image-preprocessing')

if preprocessing_dir not in sys.path:
    sys.path.append(preprocessing_dir)

# Try to import ImageProcessor
try:
    # We explicitly import the class. 
    # Note: ensure that image_processor.py inside image-preprocessing does not have relative imports that fail.
    from image_processor import ImageProcessor
    PROCESSOR_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Could not import ImageProcessor: {e}. Preprocessing will be disabled.")
    PROCESSOR_AVAILABLE = False
except Exception as e:
    logger.error(f"Unexpected error importing ImageProcessor: {e}")
    PROCESSOR_AVAILABLE = False

# Default Configuration
DEFAULT_CONFIG = {
    'apply_crop': True,
    'apply_realesrgan': True,
    'apply_resize': True,
    'apply_clahe': True,
    'apply_sharpen': True,
    'realesrgan_denoise_strength': 0.5,
    'realesrgan_scale': 4,
    'blend_with_original': False,
    'blend_alpha': 0.7,
    'clahe_clip_limit': 2.0,
    'clahe_tile_size': 8,
}

CONFIG_FILE = os.path.join(root_dir, 'preprocessing_config.json')

def get_config():
    """Load configuration from file or return defaults."""
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                saved_config = json.load(f)
                # Merge with defaults to ensure all keys exist
                config = DEFAULT_CONFIG.copy()
                config.update(saved_config)
                return config
    except Exception as e:
        logger.error(f"Error loading config: {e}")
    
    return DEFAULT_CONFIG.copy()

def save_config(new_config):
    """Save configuration to file."""
    try:
        # Validate/clean config locally if needed
        config_to_save = DEFAULT_CONFIG.copy()
        config_to_save.update(new_config)
        
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config_to_save, f, indent=4)
        return True
    except Exception as e:
        logger.error(f"Error saving config: {e}")
        return False

def process_file(input_path, output_path=None, config=None):
    """
    Process an image file using the configured pipeline.
    
    Args:
        input_path: Path to source image
        output_path: Path to save processed image. If None, overwrites input or returns object (depending on implementation).
                     Here we assume we want to save to a file.
        config: Optional override configuration
    
    Returns:
        bool: Success status
        str: Error message (if any)
    """
    if not PROCESSOR_AVAILABLE:
        return False, "Image Processor module not loaded (missing dependencies?)"

    if config is None:
        config = get_config()

    try:
        import cv2
        from image_loader import ImageLoader # import here to avoid top-level failures if missing
        
        # Load image
        # ImageLoader.load_image returns (image, error)
        image, error = ImageLoader.load_image(Path(input_path))
        if error or image is None:
            return False, f"Failed to load image: {error}"

        # Process
        processed_img = ImageProcessor.process_image(
            image,
            apply_crop=config.get('apply_crop', True),
            apply_realesrgan=config.get('apply_realesrgan', True),
            apply_resize=config.get('apply_resize', True),
            apply_clahe=config.get('apply_clahe', True),
            apply_sharpen=config.get('apply_sharpen', True),
            realesrgan_denoise_strength=config.get('realesrgan_denoise_strength', 0.5),
            realesrgan_scale=config.get('realesrgan_scale', 4),
            blend_with_original=config.get('blend_with_original', False),
            blend_alpha=config.get('blend_alpha', 0.7),
            clahe_clip_limit=config.get('clahe_clip_limit', 2.0),
            clahe_tile_size=config.get('clahe_tile_size', 8),
        )

        if processed_img is None:
             return False, "Processing returned None"

        # Save
        target_path = output_path if output_path else input_path
        # Create dir if not exists
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        
        # ImageProcessor.save_image returns (success, error)
        success, save_err = ImageProcessor.save_image(processed_img, Path(target_path))
        
        if success:
            return True, None
        else:
            return False, save_err

    except Exception as e:
        logger.error(f"Error processing image {input_path}: {e}")
        return False, str(e)

def process_cv2_image(image_data, output_path, config=None):
    """
    Process a CV2 image (numpy array) directly.
    """
    if not PROCESSOR_AVAILABLE:
        return False, "Image Processor module not loaded"

    if config is None:
        config = get_config()
        
    try:
        if image_data is None:
             return False, "Input image is None"

        # Process
        processed_img = ImageProcessor.process_image(
            image_data,
            apply_crop=config.get('apply_crop', True),
            apply_realesrgan=config.get('apply_realesrgan', True),
            apply_resize=config.get('apply_resize', True),
            apply_clahe=config.get('apply_clahe', True),
            apply_sharpen=config.get('apply_sharpen', True),
            realesrgan_denoise_strength=config.get('realesrgan_denoise_strength', 0.5),
            realesrgan_scale=config.get('realesrgan_scale', 4),
            blend_with_original=config.get('blend_with_original', False),
            blend_alpha=config.get('blend_alpha', 0.7),
            clahe_clip_limit=config.get('clahe_clip_limit', 2.0),
            clahe_tile_size=config.get('clahe_tile_size', 8),
        )

        if processed_img is None:
             return False, "Processing returned None"

        # Save
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        success, save_err = ImageProcessor.save_image(processed_img, Path(output_path))
        
        if success:
            return True, None
        else:
            return False, save_err

    except Exception as e:
        logger.error(f"Error processing cv2 image: {e}")
        return False, str(e)
