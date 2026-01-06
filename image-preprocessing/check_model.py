#!/usr/bin/env python3
"""
Script to check which Real-ESRGAN model is being used.
"""

from image_processor import ImageProcessor

def main():
    print("=" * 60)
    print("Real-ESRGAN Model Information")
    print("=" * 60)
    
    model_info = ImageProcessor.get_realesrgan_info()
    
    if not model_info.get('available', False):
        print("❌ Real-ESRGAN is not available")
        if 'error' in model_info:
            print(f"   Error: {model_info['error']}")
        elif 'message' in model_info:
            print(f"   {model_info['message']}")
        print("\nTo install Real-ESRGAN:")
        print("  pip install realesrgan basicsr")
        return
    
    print("✅ Real-ESRGAN is available")
    print()
    print("Model Details:")
    print(f"  Model Name: {model_info.get('model_name', 'Unknown')}")
    print(f"  Model Scale: {model_info.get('scale', 'Unknown')}x")
    print(f"  Output Scale: {model_info.get('output_scale', 'Unknown')}x")
    print(f"  Model Path: {model_info.get('model_path', 'Unknown')}")
    print(f"  Tile Size: {model_info.get('tile', 'Unknown')}")
    print(f"  Precision: {'FP32' if not model_info.get('half', False) else 'FP16'}")
    print()
    
    print("📌 Currently using: RealESRGAN_x4plus (mandatory)")
    print("   Model provides 4x upscaling, then resized to 2x for output")
    
    print("=" * 60)

if __name__ == '__main__':
    main()

