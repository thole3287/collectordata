import os
import sys
import json
import logging
import cv2
import numpy as np
from pathlib import Path
from typing import Optional, Dict, Any, Tuple

# Configure logging
logger = logging.getLogger(__name__)

# Add image-preprocessing directory to sys.path to allow imports
# This is necessary because image-preprocessing is at the root level
PROJECT_ROOT = Path(__file__).parent.parent
IMAGE_PREPROCESSING_DIR = PROJECT_ROOT / "image-preprocessing"

if str(IMAGE_PREPROCESSING_DIR) not in sys.path:
    sys.path.append(str(IMAGE_PREPROCESSING_DIR))

# Dynamic import to handle cases where the module might be missing
try:
    from image_processor import ImageProcessor
    INITIALIZED = True
except ImportError as e:
    logger.error(f"Failed to import ImageProcessor: {e}")
    INITIALIZED = False

class PreprocessingService:
    """
    Service wrapper for the image-preprocessing module.
    Handles configuration management and provides a unified interface for other services.
    """
    
    CONFIG_FILE = PROJECT_ROOT / "preprocessing_config.json"
    
    # Default configuration
    DEFAULT_CONFIG = {
        "apply_crop": True,
        "apply_realesrgan": False,  # Default off for performance
        "apply_resize": True,
        "apply_clahe": True,
        "apply_sharpen": True,
        "realesrgan_denoise_strength": 0.5,
        "realesrgan_scale": 4,
        "blend_with_original": False,
        "blend_alpha": 0.7,
        "clahe_clip_limit": 2.0,
        "clahe_tile_size": 8
    }

    @classmethod
    def load_config(cls) -> Dict[str, Any]:
        """Load configuration from JSON file or return defaults."""
        if not cls.CONFIG_FILE.exists():
            return cls.DEFAULT_CONFIG.copy()
        
        try:
            with open(cls.CONFIG_FILE, 'r') as f:
                config = json.load(f)
                # Merge with defaults to ensure all keys exist
                merged_config = cls.DEFAULT_CONFIG.copy()
                merged_config.update(config)
                return merged_config
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            return cls.DEFAULT_CONFIG.copy()

    @classmethod
    def save_config(cls, config: Dict[str, Any]) -> bool:
        """Save configuration to JSON file."""
        try:
            # Validate/Sanitize inputs
            clean_config = {k: v for k, v in config.items() if k in cls.DEFAULT_CONFIG}
            
            with open(cls.CONFIG_FILE, 'w') as f:
                json.dump(clean_config, f, indent=4)
            return True
        except Exception as e:
            logger.error(f"Error saving config: {e}")
            return False

    @staticmethod
    def process_cv2_image(image: np.ndarray, config: Optional[Dict[str, Any]] = None) -> np.ndarray:
        """
        Process an OpenCV image (numpy array) using the configured pipeline.
        
        Args:
            image: BGR numpy array
            config: Optional configuration dictionary. If None, loads from file.
            
        Returns:
            Processed BGR numpy array
        """
        if not INITIALIZED:
            logger.warning("Preprocessing module not initialized. Returning original image.")
            # Fallback: simple resize if needed, or just return
            return image

        if config is None:
            config = PreprocessingService.load_config()

        try:
            processed = ImageProcessor.process_image(
                image,
                apply_crop=config.get("apply_crop", True),
                apply_realesrgan=config.get("apply_realesrgan", False),
                apply_resize=config.get("apply_resize", True),
                apply_clahe=config.get("apply_clahe", True),
                apply_sharpen=config.get("apply_sharpen", True),
                realesrgan_denoise_strength=float(config.get("realesrgan_denoise_strength", 0.5)),
                realesrgan_scale=int(config.get("realesrgan_scale", 4)),
                blend_with_original=config.get("blend_with_original", False),
                blend_alpha=float(config.get("blend_alpha", 0.7)),
                clahe_clip_limit=float(config.get("clahe_clip_limit", 2.0)),
                clahe_tile_size=int(config.get("clahe_tile_size", 8))
            )
            return processed
        except Exception as e:
            logger.error(f"Error during image processing: {e}")
            # Fallback to simple resize if processing fails but we expect 1280x720
            try:
                if config.get("apply_resize", True):
                    return cv2.resize(image, (1280, 720), interpolation=cv2.INTER_LANCZOS4)
            except:
                pass
            return image
