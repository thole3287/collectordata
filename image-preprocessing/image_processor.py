"""
Image Processor Module

This module implements the image preprocessing pipeline using Real-ESRGAN:
- Real-ESRGAN (x2 super resolution)
- Resize to 1280x720
- Light CLAHE (Contrast Limited Adaptive Histogram Equalization)
"""

import cv2
import numpy as np
from typing import Tuple, Optional
from pathlib import Path
import warnings
import os
import urllib.request
import hashlib

# Try to import Real-ESRGAN, fallback if not available
try:
    from realesrgan import RealESRGANer
    from realesrgan.archs.srvgg_arch import SRVGGNetCompact
    from basicsr.archs.rrdbnet_arch import RRDBNet
    REALESRGAN_AVAILABLE = True
except ImportError:
    REALESRGAN_AVAILABLE = False
    warnings.warn(
        "Real-ESRGAN not available. Install with: pip install realesrgan basicsr",
        UserWarning
    )


class ImageProcessor:
    """Handles image preprocessing operations using Real-ESRGAN pipeline."""
    
    # Target dimensions
    TARGET_WIDTH = 1280
    TARGET_HEIGHT = 720
    TARGET_ASPECT_RATIO = 16 / 9
    
    # Real-ESRGAN model (lazy loaded)
    _realesrgan_upsampler = None
    _realesrgan_denoise_strength: float = 0.5
    _realesrgan_scale: int = 4  # 4: realesr-general-x4v3, 2: RealESRGAN_x2plus
    
    @staticmethod
    def _download_model(url: str, local_path: Path) -> Path:
        """
        Download model file from URL if not already exists locally.
        
        Args:
            url: URL to download from
            local_path: Local path to save the model
            
        Returns:
            Path to the local model file
        """
        if local_path.exists():
            return local_path
        
        # Create parent directory if needed
        local_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Download the model
        print(f"Downloading model from {url}...")
        print(f"Saving to {local_path}")
        
        try:
            urllib.request.urlretrieve(url, str(local_path))
            print(f"Model downloaded successfully to {local_path}")
        except Exception as e:
            raise RuntimeError(f"Failed to download model from {url}: {str(e)}")
        
        return local_path
    
    @classmethod
    def _get_realesrgan_upsampler(cls, denoise_strength: float = 0.5, scale: int = 4):
        """
        Get or create Real-ESRGAN upsampler (lazy initialization).
        
        For the generalesr-x4v3 model family, denoise strength works like the `-dn`
        option in the official CLI:
          - 0.0 → keep more original noise/details
          - 1.0 → strong denoising (more aggressive noise removal)
        """
        if not REALESRGAN_AVAILABLE:
            raise RuntimeError(
                "Real-ESRGAN is not available. Please install: pip install realesrgan basicsr"
            )
        
        # Clamp denoise strength to [0, 1]
        try:
            dn = float(denoise_strength)
        except (TypeError, ValueError):
            dn = 0.5
        dn = max(0.0, min(1.0, dn))

        # Normalize scale choice: only 2 or 4 are supported
        try:
            scale = int(scale)
        except (TypeError, ValueError):
            scale = 4
        if scale not in (2, 4):
            scale = 4
        
        # Recreate upsampler if it does not exist or settings changed
        if (
            cls._realesrgan_upsampler is None
            or abs(cls._realesrgan_denoise_strength - dn) > 1e-3
            or cls._realesrgan_scale != scale
        ):
            cls._realesrgan_denoise_strength = dn
            cls._realesrgan_scale = scale

            # Download models to project root models directory
            # Get the directory where this file is located (image_processor.py)
            project_root = Path(__file__).parent.resolve()
            cache_dir = project_root / "models" / "realesrgan"

            if scale == 4:
                # Use realesr-general-x4v3 model family (supports denoise strength)
                base_url = "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0"
                general_model_url = f"{base_url}/realesr-general-x4v3.pth"
                general_wdn_model_url = f"{base_url}/realesr-general-wdn-x4v3.pth"

                general_model_path = cache_dir / "realesr-general-x4v3.pth"
                general_wdn_model_path = cache_dir / "realesr-general-wdn-x4v3.pth"

                # realesr-general-x4v3 uses SRVGGNetCompact architecture
                model = SRVGGNetCompact(
                    num_in_ch=3,
                    num_out_ch=3,
                    num_feat=64,
                    num_conv=32,
                    upscale=4,
                    act_type='prelu'
                )

                # For dn in [0,1), blend general and general-wdn using DNI
                if dn < 1.0:
                    # Download both models
                    cls._download_model(general_model_url, general_model_path)
                    cls._download_model(general_wdn_model_url, general_wdn_model_path)
                    model_path = [str(general_model_path), str(general_wdn_model_path)]
                    dni_weight = [dn, 1 - dn]
                else:
                    # Only download general model
                    cls._download_model(general_model_url, general_model_path)
                    model_path = str(general_model_path)
                    dni_weight = None

                cls._realesrgan_upsampler = RealESRGANer(
                    scale=4,
                    model_path=model_path,
                    dni_weight=dni_weight,
                    model=model,
                    tile=400,  # Use tiling for large images to avoid memory issues
                    tile_pad=10,
                    pre_pad=0,
                    half=False  # Use FP32 for maximum quality (FP16 can reduce quality)
                )
            else:
                # Use RealESRGAN_x2plus model (RRDBNet, scale=2)
                base_url = "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.1"
                x2_model_url = f"{base_url}/RealESRGAN_x2plus.pth"
                x2_model_path = cache_dir / "RealESRGAN_x2plus.pth"

                cls._download_model(x2_model_url, x2_model_path)

                # RealESRGAN_x2plus uses RRDBNet architecture
                model = RRDBNet(
                    num_in_ch=3,
                    num_out_ch=3,
                    num_feat=64,
                    num_block=23,
                    num_grow_ch=32,
                    scale=2,
                )

                cls._realesrgan_upsampler = RealESRGANer(
                    scale=2,
                    model_path=str(x2_model_path),
                    model=model,
                    tile=400,
                    tile_pad=10,
                    pre_pad=0,
                    half=False,
                )
        
        return cls._realesrgan_upsampler
    
    @classmethod
    def get_realesrgan_info(cls) -> dict:
        """
        Get information about the currently loaded Real-ESRGAN model.
        
        Returns:
            Dictionary with model information or None if not available
        """
        if not REALESRGAN_AVAILABLE:
            return {
                'available': False,
                'message': 'Real-ESRGAN is not installed'
            }
        
        try:
            upsampler = cls._get_realesrgan_upsampler(
                cls._realesrgan_denoise_strength,
                cls._realesrgan_scale,
            )
            model_path = str(upsampler.model_path) if hasattr(upsampler, 'model_path') else 'Unknown'
            
            return {
                'available': True,
                'scale': upsampler.scale,
                'model_path': model_path,
                'model_name': 'realesr-general-x4v3' if cls._realesrgan_scale == 4 else 'RealESRGAN_x2plus',
                'tile': upsampler.tile if hasattr(upsampler, 'tile') else None,
                'half': upsampler.half if hasattr(upsampler, 'half') else False,
                # For x4 model we resize 4x output back down to 2x.
                # For x2 model the native output is already 2x.
                'output_scale': 2,
                'denoise_strength': cls._realesrgan_denoise_strength,
            }
        except Exception as e:
            return {
                'available': False,
                'error': str(e)
            }
    
    @staticmethod
    def apply_realesrgan(
        image: np.ndarray,
        denoise_strength: float = 0.5,
        scale: int = 4,
    ) -> np.ndarray:
        """
        Apply Real-ESRGAN x2 super resolution to recover lost details.
        
        Args:
            image: Input image array (BGR format)
            
        Returns:
            Super-resolved image array (2x larger)
        """
        if not REALESRGAN_AVAILABLE:
            # Fallback: use bicubic upsampling if Real-ESRGAN not available
            h, w = image.shape[:2]
            upscaled = cv2.resize(
                image,
                (w * 2, h * 2),
                interpolation=cv2.INTER_CUBIC,
            )
            return upscaled
        
        try:
            upsampler = ImageProcessor._get_realesrgan_upsampler(
                denoise_strength,
                scale,
            )
            
            # Real-ESRGAN expects RGB format
            rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            
            # Apply super resolution:
            # - For x4 model (realesr-general-x4v3): outscale=4 then resize back to 2x
            # - For x2 model (RealESRGAN_x2plus): native 2x (outscale=2)
            if upsampler.scale == 4:
                output, _ = upsampler.enhance(rgb_image, outscale=4)
            else:
                output, _ = upsampler.enhance(rgb_image, outscale=2)
            
            # Convert back to BGR
            bgr_output = cv2.cvtColor(output, cv2.COLOR_RGB2BGR)
            
            # If model is x4, resize from 4x down to 2x for consistency.
            # If model is x2, output is already 2x.
            if upsampler.scale == 4:
                h, w = image.shape[:2]
                bgr_output = cv2.resize(
                    bgr_output,
                    (w * 2, h * 2),
                    interpolation=cv2.INTER_LANCZOS4,
                )
            
            return bgr_output
            
        except Exception as e:
            # Fallback on error
            warnings.warn(f"Real-ESRGAN failed, using bicubic upsampling: {str(e)}")
            h, w = image.shape[:2]
            upscaled = cv2.resize(
                image,
                (w * 2, h * 2),
                interpolation=cv2.INTER_CUBIC,
            )
            return upscaled
    
    @staticmethod
    def center_crop_16_9(image: np.ndarray) -> np.ndarray:
        """
        Center-crop image to 16:9 aspect ratio.
        
        Args:
            image: Input image array (BGR format)
            
        Returns:
            Cropped image array
        """
        h, w = image.shape[:2]
        current_aspect = w / h
        
        if current_aspect > ImageProcessor.TARGET_ASPECT_RATIO:
            # Image is wider than 16:9, crop width
            new_width = int(h * ImageProcessor.TARGET_ASPECT_RATIO)
            x_start = (w - new_width) // 2
            cropped = image[:, x_start:x_start + new_width]
        elif current_aspect < ImageProcessor.TARGET_ASPECT_RATIO:
            # Image is taller than 16:9, crop height
            new_height = int(w / ImageProcessor.TARGET_ASPECT_RATIO)
            y_start = (h - new_height) // 2
            cropped = image[y_start:y_start + new_height, :]
        else:
            # Already 16:9, return as-is
            cropped = image
        
        return cropped
    
    @staticmethod
    def resize_image(image: np.ndarray, width: int = TARGET_WIDTH, 
                     height: int = TARGET_HEIGHT) -> np.ndarray:
        """
        Resize image to target dimensions using high-quality interpolation.
        
        Args:
            image: Input image array
            width: Target width (default: 1280)
            height: Target height (default: 720)
            
        Returns:
            Resized image array
        """
        # Use INTER_LANCZOS4 for high-quality resizing
        resized = cv2.resize(
            image, 
            (width, height), 
            interpolation=cv2.INTER_LANCZOS4
        )
        return resized
    
    @staticmethod
    def denoise_image(image: np.ndarray) -> np.ndarray:
        """
        Apply noise reduction using fastNlMeansDenoisingColored with optimized parameters.
        Uses edge-preserving denoising to maintain sharpness.
        
        Args:
            image: Input image array (BGR format)
            
        Returns:
            Denoised image array
        """
        # Convert BGR to RGB for denoising (OpenCV expects RGB)
        rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        
        # Apply denoising with optimized parameters
        # Reduced h values to preserve more detail while still removing noise
        # h: filter strength (lower = less denoising but preserves edges better)
        # hColor: color component filter strength
        # templateWindowSize: size of template patch (odd number)
        # searchWindowSize: size of search window (odd number)
        denoised_rgb = cv2.fastNlMeansDenoisingColored(
            rgb_image,
            h=6,  # Reduced from 10 to preserve more detail
            hColor=6,  # Reduced from 10
            templateWindowSize=7,
            searchWindowSize=21
        )
        
        # Convert back to BGR
        denoised_bgr = cv2.cvtColor(denoised_rgb, cv2.COLOR_RGB2BGR)
        
        return denoised_bgr
    
    @staticmethod
    def enhance_contrast_light(
        image: np.ndarray,
        clip_limit: float = 2.0,
        tile_grid_size: int = 8
    ) -> np.ndarray:
        """
        Apply light CLAHE (Contrast Limited Adaptive Histogram Equalization).
        Optimized for better quality output.
        
        Args:
            image: Input image array (BGR format)
            clip_limit: CLAHE clip limit (default: 2.0, recommended range: 1.0-2.0)
            tile_grid_size: CLAHE tile grid size (default: 8, e.g., 8x8)
            
        Returns:
            Light contrast-enhanced image array
        """
        # Convert to LAB color space
        lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        
        # Clamp clip_limit to reasonable range [0.5, 5.0]
        clip_limit = max(0.5, min(5.0, float(clip_limit)))
        # Clamp tile_grid_size to reasonable range [4, 32]
        tile_grid_size = max(4, min(32, int(tile_grid_size)))
        
        # Apply light CLAHE with configurable parameters
        clahe = cv2.createCLAHE(
            clipLimit=clip_limit,
            tileGridSize=(tile_grid_size, tile_grid_size)
        )
        l_enhanced = clahe.apply(l)
        
        # Merge channels and convert back to BGR
        lab_enhanced = cv2.merge([l_enhanced, a, b])
        enhanced = cv2.cvtColor(lab_enhanced, cv2.COLOR_LAB2BGR)
        
        return enhanced
    
    @staticmethod
    def apply_light_sharpening(image: np.ndarray) -> np.ndarray:
        """
        Apply light sharpening after Real-ESRGAN to enhance fine details.
        Uses subtle unsharp masking.
        
        Args:
            image: Input image array (BGR format)
            
        Returns:
            Lightly sharpened image array
        """
        # Light Gaussian blur
        gaussian = cv2.GaussianBlur(image, (0, 0), 1.0)
        
        # Subtle unsharp masking
        sharpened = cv2.addWeighted(image, 1.2, gaussian, -0.2, 0)
        sharpened = np.clip(sharpened, 0, 255).astype(np.uint8)
        
        return sharpened
    
    @staticmethod
    def sharpen_image(image: np.ndarray, strength: float = 2.5) -> np.ndarray:
        """
        Apply enhanced unsharp masking for image sharpening.
        Uses multiple passes for better results.
        
        Args:
            image: Input image array
            strength: Sharpening strength (default: 2.5, increased from 1.5)
            
        Returns:
            Sharpened image array
        """
        # First pass: Stronger unsharp masking with smaller blur radius
        gaussian1 = cv2.GaussianBlur(image, (0, 0), 1.5)  # Reduced from 2.0
        sharpened1 = cv2.addWeighted(image, 1.0 + strength, gaussian1, -strength, 0)
        sharpened1 = np.clip(sharpened1, 0, 255).astype(np.uint8)
        
        # Second pass: Subtle additional sharpening for fine details
        gaussian2 = cv2.GaussianBlur(sharpened1, (0, 0), 0.8)
        sharpened2 = cv2.addWeighted(sharpened1, 1.0 + (strength * 0.3), gaussian2, -(strength * 0.3), 0)
        sharpened2 = np.clip(sharpened2, 0, 255).astype(np.uint8)
        
        return sharpened2
    
    @staticmethod
    def apply_edge_preserving_filter(image: np.ndarray) -> np.ndarray:
        """
        Apply edge-preserving filter to reduce noise while maintaining sharp edges.
        This helps prepare the image for better sharpening.
        
        Args:
            image: Input image array (BGR format)
            
        Returns:
            Filtered image array
        """
        # Use bilateral filter for edge-preserving smoothing
        filtered = cv2.bilateralFilter(image, d=9, sigmaColor=75, sigmaSpace=75)
        return filtered
    
    @staticmethod
    def process_image(
        image: np.ndarray,
        apply_crop: bool = True,
        apply_realesrgan: bool = True,
        apply_resize: bool = True,
        apply_clahe: bool = True,
        apply_sharpen: bool = True,
        realesrgan_denoise_strength: float = 0.5,
        realesrgan_scale: int = 4,
        blend_with_original: bool = False,
        blend_alpha: float = 0.7,
        clahe_clip_limit: float = 2.0,
        clahe_tile_size: int = 8,
    ) -> np.ndarray:
        """
        Complete preprocessing pipeline with flexible steps.
        Pipeline: Original → [Crop 16:9] → [Real-ESRGAN (x2)] → [Resize 1280×720] → [Light CLAHE] → [Light Sharpening] → Output
        
        Args:
            image: Input image array (BGR format)
            apply_crop: Whether to apply center-crop to 16:9
            apply_realesrgan: Whether to apply Real-ESRGAN super resolution
            apply_resize: Whether to apply final resize to 1280x720
            apply_clahe: Whether to apply light CLAHE
            apply_sharpen: Whether to apply light sharpening
            
        Returns:
            Processed image array
        """
        processed_image = image.copy()

        # Step 1: Center-crop to 16:9
        if apply_crop:
            processed_image = ImageProcessor.center_crop_16_9(processed_image)
        
        # Prepare original image for optional blending (after upscaling)
        original_for_blend = processed_image.copy()

        # Step 2: Apply Real-ESRGAN x2 super resolution or simple upscale
        if apply_realesrgan:
            upscaled = ImageProcessor.apply_realesrgan(
                processed_image,
                denoise_strength=realesrgan_denoise_strength,
                scale=realesrgan_scale,
            )
        else:
            # If Real-ESRGAN is disabled, perform a simple 2x upscale for consistency
            # This ensures subsequent resize operates on a larger image if needed
            h, w = processed_image.shape[:2]
            upscaled = cv2.resize(
                processed_image,
                (w * 2, h * 2),
                interpolation=cv2.INTER_LANCZOS4
            )

        # Optional Step: Blend enhanced image with original (already resized)
        if blend_with_original:
            try:
                # Clamp alpha to [0, 1]
                try:
                    alpha = float(blend_alpha)
                except (TypeError, ValueError):
                    alpha = 0.7
                alpha = max(0.0, min(1.0, alpha))

                # Resize original to match upscaled size
                oh, ow = original_for_blend.shape[:2]
                uh, uw = upscaled.shape[:2]
                if (oh, ow) != (uh, uw):
                    original_resized = cv2.resize(
                        original_for_blend,
                        (uw, uh),
                        interpolation=cv2.INTER_LANCZOS4,
                    )
                else:
                    original_resized = original_for_blend

                # Blend: Final = alpha * Enhanced + (1 - alpha) * Original
                blended = cv2.addWeighted(
                    upscaled.astype(np.float32),
                    alpha,
                    original_resized.astype(np.float32),
                    1.0 - alpha,
                    0.0,
                )
                upscaled = np.clip(blended, 0, 255).astype(np.uint8)
            except Exception:
                # Nếu blend lỗi thì bỏ qua, dùng upscaled như cũ
                pass

        # Step 3: Resize to target dimensions (1280x720)
        if apply_resize:
            processed_image = ImageProcessor.resize_image(upscaled)
        else:
            # If resize is disabled, use the upscaled image as is
            processed_image = upscaled
        
        # Step 4: Apply light CLAHE for subtle contrast enhancement
        if apply_clahe:
            processed_image = ImageProcessor.enhance_contrast_light(
                processed_image,
                clip_limit=clahe_clip_limit,
                tile_grid_size=clahe_tile_size
            )
        
        # Step 5: Apply light sharpening to enhance fine details
        if apply_sharpen:
            processed_image = ImageProcessor.apply_light_sharpening(processed_image)
        
        return processed_image
    
    @staticmethod
    def save_image(image: np.ndarray, output_path: Path) -> Tuple[bool, Optional[str]]:
        """
        Save processed image to disk as PNG format (lossless).
        
        Args:
            image: Image array to save
            output_path: Path where to save the image (will be converted to .png)
            
        Returns:
            Tuple of (success, error_message)
        """
        try:
            # Ensure output directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Always save as PNG (lossless format)
            # Change extension to .png if it's not already
            if output_path.suffix.lower() != '.png':
                output_path = output_path.with_suffix('.png')
            
            # Save as PNG with optimal compression (lossless)
            # Compression level 3 provides good balance between file size and write speed
            success = cv2.imwrite(
                str(output_path),
                image,
                [cv2.IMWRITE_PNG_COMPRESSION, 3]  # Balanced compression (0-9, 3 is good balance)
            )
            
            if not success:
                return False, f"Failed to save image: {output_path.name}"
            
            return True, None
            
        except Exception as e:
            return False, f"Error saving {output_path.name}: {str(e)}"

