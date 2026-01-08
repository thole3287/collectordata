"""Camera configuration loader module."""
import json
import os
import logging
import sys

# Perform absolute import hack or ensure path is in sys.path if needed, 
# but usually Flask adds root. 
# Since this moved to config/, we might need to adjust imports if run standalone,
# but for App execution it should be fine if root is in path.
# However, to be safe and clean:
import extensions

logger = logging.getLogger(__name__)


def load_cameras(config_path=extensions.CAMERA_COLLECTOR_CONFIG_FILE):
    """
    Load camera configuration from JSON file.
    
    Args:
        config_path: Path to the cameras.json configuration file
        
    Returns:
        List of camera dictionaries with 'id' and 'name' keys
        
    Raises:
        FileNotFoundError: If config file doesn't exist
        ValueError: If config file is invalid or malformed
    """
    if not os.path.exists(config_path):
        error_msg = f"Configuration file not found: {config_path}"
        logger.error(error_msg)
        raise FileNotFoundError(error_msg)
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            cameras = json.load(f)
    except json.JSONDecodeError as e:
        error_msg = f"Invalid JSON in configuration file: {e}"
        logger.error(error_msg)
        raise ValueError(error_msg) from e
    except Exception as e:
        error_msg = f"Error reading configuration file: {e}"
        logger.error(error_msg)
        raise ValueError(error_msg) from e
    
    # Validate structure
    if not isinstance(cameras, list):
        error_msg = "Configuration must be a list of camera objects"
        logger.error(error_msg)
        raise ValueError(error_msg)
    
    # Validate each camera object
    for idx, camera in enumerate(cameras):
        if not isinstance(camera, dict):
            error_msg = f"Camera at index {idx} must be a dictionary"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        if 'id' not in camera or 'name' not in camera:
            error_msg = f"Camera at index {idx} must have 'id' and 'name' fields"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        if not isinstance(camera['id'], str) or not isinstance(camera['name'], str):
            error_msg = f"Camera at index {idx} must have string 'id' and 'name' fields"
            logger.error(error_msg)
            raise ValueError(error_msg)
    
    logger.info(f"Loaded {len(cameras)} camera(s) from {config_path}")
    return cameras



