import sys
import os
import cv2
import numpy as np
import logging
import time

# Add current dir to path
sys.path.append(os.getcwd())

# Setup basic logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("VerifyPipeline")

def create_dummy_image(width=640, height=480):
    """Create a dummy image with some shapes"""
    img = np.zeros((height, width, 3), dtype=np.uint8)
    # Background
    img[:] = (50, 50, 50)
    # Rectangle
    cv2.rectangle(img, (50, 50), (200, 200), (255, 0, 0), -1)
    # Circle
    cv2.circle(img, (400, 240), 100, (0, 255, 0), -1)
    # Text
    cv2.putText(img, "TEST INPUT", (100, 400), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
    return img

def verify_preprocessing():
    logger.info("="*50)
    logger.info("VERIFYING IMAGE PREPROCESSING PIPELINE")
    logger.info("="*50)

    try:
        # Import service
        from services.preprocessing_service import PreprocessingService
        logger.info("Successfully imported PreprocessingService")
    except ImportError as e:
        logger.error(f"Failed to import PreprocessingService: {e}")
        return False
    except Exception as e:
        logger.error(f"Error during import: {e}")
        return False

    # Create test input
    input_img = create_dummy_image()
    logger.info(f"Created dummy input image: {input_img.shape}")

    # Test Case 1: Basic Pipeline (Resize, CLAHE, Sharpen)
    config_basic = {
        'apply_crop': True,
        'apply_resize': True,
        'apply_clahe': True,
        'apply_sharpen': True,
        'apply_realesrgan': False,
        'clahe_clip_limit': 2.0,
        'clahe_tile_size': 8
    }
    
    logger.info("-" * 30)
    logger.info("Test 1: Basic Pipeline (No AI)")
    try:
        start_time = time.time()
        processed_img = PreprocessingService.process_cv2_image(input_img, config_basic)
        # metadata = {} 
        duration = time.time() - start_time
        
        logger.info(f"Processing time: {duration:.4f}s")
        logger.info(f"Output shape: {processed_img.shape}")
        # logger.info(f"Metadata: {metadata}")
        
        if processed_img.shape[1] == 1280 and processed_img.shape[0] == 720:
             logger.info("✅ Resize verification PASSED")
        else:
             logger.error(f"❌ Resize verification FAILED (Expected 1280x720)")
             
        # if metadata.get('pipeline_success'):
        #      logger.info("✅ Pipeline Success Flag PASSED")
        # else:
        #      logger.error("❌ Pipeline Success Flag FAILED")

    except Exception as e:
        logger.error(f"Test 1 FAILED with error: {e}")
        import traceback
        traceback.print_exc()

    # Test Case 2: AI Pipeline (Real-ESRGAN) - if dependencies exist
    logger.info("-" * 30)
    logger.info("Test 2: AI Pipeline (Real-ESRGAN)")
    config_ai = {
        'apply_crop': False,
        'apply_resize': False, # Let ESRGAN resize
        'apply_realesrgan': True,
        'realesrgan_denoise_strength': 0.5,
        'realesrgan_scale': 4
    }
    
    try:
        # Check if we should skip AI test (long time)
        input("Press Enter to run AI test (might take time/download models) or Ctrl+C to skip...")
        
        start_time = time.time()
        processed_img = PreprocessingService.process_cv2_image(input_img, config_ai)
        duration = time.time() - start_time
        
        logger.info(f"Processing time: {duration:.4f}s")
        logger.info(f"Output shape: {processed_img.shape}")
        
        # if metadata.get('ai_upscale_applied'):
        #      logger.info("✅ AI Upscale Flag PASSED")
        # else:
        #      logger.warning("⚠️ AI Upscale NOT applied (Check logs for fallback)")

    except KeyboardInterrupt:
        logger.info("Skipped AI Test")
    except Exception as e:
        logger.error(f"Test 2 FAILED with error: {e}")
    
    logger.info("="*50)
    logger.info("VERIFICATION COMPLETED")

if __name__ == "__main__":
    verify_preprocessing()
