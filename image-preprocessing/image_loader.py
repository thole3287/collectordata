"""
Image Loader Module

This module handles loading images from a directory and provides
utilities for discovering and validating image files.
"""

import os
from pathlib import Path
from typing import List, Tuple, Optional
import cv2
import numpy as np


class ImageLoader:
    """Handles loading and discovery of image files."""
    
    # Supported image extensions
    SUPPORTED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.JPG', '.JPEG', '.PNG'}
    
    @staticmethod
    def discover_images(directory: str) -> List[Path]:
        """
        Discover all supported image files in a directory.
        
        Args:
            directory: Path to the directory containing images
            
        Returns:
            List of Path objects for discovered image files
        """
        directory_path = Path(directory)
        
        if not directory_path.exists():
            raise ValueError(f"Directory does not exist: {directory}")
        
        if not directory_path.is_dir():
            raise ValueError(f"Path is not a directory: {directory}")
        
        image_files = []
        for ext in ImageLoader.SUPPORTED_EXTENSIONS:
            image_files.extend(directory_path.glob(f"*{ext}"))
        
        # Sort for consistent processing order
        image_files.sort()
        
        return image_files
    
    @staticmethod
    def load_image(image_path: Path) -> Optional[Tuple[np.ndarray, str]]:
        """
        Load an image from disk.
        
        Args:
            image_path: Path to the image file
            
        Returns:
            Tuple of (image array, error_message) or (image, None) if successful
            Returns None if image cannot be loaded
        """
        try:
            # Read image in BGR format (OpenCV default)
            image = cv2.imread(str(image_path))
            
            if image is None:
                return None, f"Failed to decode image: {image_path.name}"
            
            if image.size == 0:
                return None, f"Image is empty: {image_path.name}"
            
            return image, None
            
        except Exception as e:
            return None, f"Error loading {image_path.name}: {str(e)}"
    
    @staticmethod
    def validate_image(image: np.ndarray) -> Tuple[bool, Optional[str]]:
        """
        Validate that an image array is valid.
        
        Args:
            image: Image array to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if image is None:
            return False, "Image is None"
        
        if not isinstance(image, np.ndarray):
            return False, "Image is not a numpy array"
        
        if len(image.shape) != 3:
            return False, f"Expected 3D array, got {len(image.shape)}D"
        
        if image.shape[2] != 3:
            return False, f"Expected 3 channels, got {image.shape[2]}"
        
        return True, None

