#!/usr/bin/env python3
"""
Command-Line Interface for Image Preprocessing

This script allows batch processing of images via command line.
"""

import argparse
import sys
import gc
from pathlib import Path
from tqdm import tqdm

from image_loader import ImageLoader
from image_processor import ImageProcessor


def process_directory(
    input_dir: str,
    output_dir: str,
    apply_crop: bool = True,
    apply_realesrgan: bool = True,
    apply_resize: bool = True,
    apply_clahe: bool = True,
    apply_sharpen: bool = True,
    verbose: bool = False
):
    """
    Process all images in a directory with configurable pipeline steps.
    
    Args:
        input_dir: Path to input directory
        output_dir: Path to output directory
        apply_crop: Whether to apply center-crop to 16:9
        apply_realesrgan: Whether to apply Real-ESRGAN x2 super resolution
        apply_resize: Whether to resize to 1280×720
        apply_clahe: Whether to apply light CLAHE contrast enhancement
        apply_sharpen: Whether to apply light sharpening
        verbose: Whether to print detailed progress
    """
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    
    # Validate input directory
    if not input_path.exists():
        print(f"Error: Input directory does not exist: {input_dir}", file=sys.stderr)
        sys.exit(1)
    
    if not input_path.is_dir():
        print(f"Error: Input path is not a directory: {input_dir}", file=sys.stderr)
        sys.exit(1)
    
    # Create output directory
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Discover images
    try:
        image_files = ImageLoader.discover_images(str(input_path))
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    
    if len(image_files) == 0:
        print(f"Error: No supported images found in {input_dir}", file=sys.stderr)
        sys.exit(1)
    
    print(f"Found {len(image_files)} images")
    print(f"Output directory: {output_dir}")
    print(f"Crop 16:9: {'Enabled' if apply_crop else 'Disabled'}")
    print(f"Real-ESRGAN (x2): {'Enabled' if apply_realesrgan else 'Disabled'}")
    print(f"Resize 1280×720: {'Enabled' if apply_resize else 'Disabled'}")
    print(f"Light CLAHE: {'Enabled' if apply_clahe else 'Disabled'}")
    print(f"Light Sharpening: {'Enabled' if apply_sharpen else 'Disabled'}")
    print("-" * 50)
    
    # Process images
    processed_count = 0
    error_count = 0
    errors = []
    
    # Use tqdm for progress bar if available, otherwise simple counter
    try:
        iterator = tqdm(image_files, desc="Processing", unit="image")
    except ImportError:
        iterator = image_files
        print("Tip: Install 'tqdm' for progress bar: pip install tqdm")
    
    image = None
    processed = None
    
    for idx, image_path in enumerate(iterator):
        try:
            # Load image
            image, error = ImageLoader.load_image(image_path)
            if error or image is None:
                error_msg = error or "Failed to load image"
                errors.append((image_path.name, error_msg))
                error_count += 1
                if verbose:
                    print(f"Error loading {image_path.name}: {error_msg}", file=sys.stderr)
                continue
            
            # Validate image
            is_valid, validation_error = ImageLoader.validate_image(image)
            if not is_valid:
                error_msg = validation_error or "Invalid image format"
                errors.append((image_path.name, error_msg))
                error_count += 1
                if verbose:
                    print(f"Error validating {image_path.name}: {error_msg}", file=sys.stderr)
                # Free memory
                del image
                image = None
                continue
            
            # Process image
            try:
                processed = ImageProcessor.process_image(
                    image,
                    apply_crop=apply_crop,
                    apply_realesrgan=apply_realesrgan,
                    apply_resize=apply_resize,
                    apply_clahe=apply_clahe,
                    apply_sharpen=apply_sharpen
                )
                
                # Free original image memory immediately
                del image
                image = None
                
                # Save processed image
                output_file = output_path / image_path.name
                success, save_error = ImageProcessor.save_image(processed, output_file)
                
                # Free processed image memory immediately
                del processed
                processed = None
                
                if success:
                    processed_count += 1
                    if verbose:
                        print(f"Processed: {image_path.name}")
                else:
                    error_msg = save_error or "Failed to save image"
                    errors.append((image_path.name, error_msg))
                    error_count += 1
                    if verbose:
                        print(f"Error saving {image_path.name}: {error_msg}", file=sys.stderr)
                        
            except Exception as e:
                error_msg = f"Processing error: {str(e)}"
                errors.append((image_path.name, error_msg))
                error_count += 1
                if verbose:
                    print(f"Error processing {image_path.name}: {error_msg}", file=sys.stderr)
                # Cleanup on error
                if image is not None:
                    del image
                    image = None
                if processed is not None:
                    del processed
                    processed = None
        
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            errors.append((image_path.name, error_msg))
            error_count += 1
            if verbose:
                print(f"Error with {image_path.name}: {error_msg}", file=sys.stderr)
            # Cleanup on error
            if image is not None:
                del image
                image = None
            if processed is not None:
                del processed
                processed = None
        
        finally:
            # Force garbage collection every 100 images to free memory
            if (idx + 1) % 100 == 0:
                gc.collect()
    
    # Print summary
    print("-" * 50)
    print(f"Processing complete!")
    print(f"  Successfully processed: {processed_count}")
    print(f"  Errors: {error_count}")
    
    if errors and verbose:
        print("\nErrors encountered:")
        for filename, error in errors:
            print(f"  {filename}: {error}")
    
    if error_count > 0:
        sys.exit(1)


def main():
    """Main entry point for CLI."""
    parser = argparse.ArgumentParser(
        description='Preprocess images for object detection (YOLO-compatible)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process with all options enabled (default)
  python preprocess.py --input ./raw --output ./processed
  
  # Process without Real-ESRGAN
  python preprocess.py --input ./raw --output ./processed --no-realesrgan
  
  # Process without CLAHE
  python preprocess.py --input ./raw --output ./processed --no-clahe
  
  # Process with verbose output
  python preprocess.py --input ./raw --output ./processed --verbose
        """
    )
    
    parser.add_argument(
        '--input',
        '-i',
        required=True,
        help='Input directory containing images'
    )
    
    parser.add_argument(
        '--output',
        '-o',
        required=True,
        help='Output directory for processed images'
    )
    
    parser.add_argument(
        '--crop',
        action='store_true',
        default=True,
        help='Apply center-crop to 16:9 (default: enabled)'
    )
    
    parser.add_argument(
        '--no-crop',
        dest='crop',
        action='store_false',
        help='Disable center-crop'
    )
    
    parser.add_argument(
        '--realesrgan',
        action='store_true',
        default=True,
        help='Apply Real-ESRGAN x2 super resolution (default: enabled)'
    )
    
    parser.add_argument(
        '--no-realesrgan',
        dest='realesrgan',
        action='store_false',
        help='Disable Real-ESRGAN super resolution'
    )
    
    parser.add_argument(
        '--resize',
        action='store_true',
        default=True,
        help='Resize to 1280×720 (default: enabled)'
    )
    
    parser.add_argument(
        '--no-resize',
        dest='resize',
        action='store_false',
        help='Disable resize'
    )
    
    parser.add_argument(
        '--clahe',
        action='store_true',
        default=True,
        help='Apply light CLAHE contrast enhancement (default: enabled)'
    )
    
    parser.add_argument(
        '--no-clahe',
        dest='clahe',
        action='store_false',
        help='Disable light CLAHE'
    )
    
    parser.add_argument(
        '--sharpen',
        action='store_true',
        default=True,
        help='Apply light sharpening (default: enabled)'
    )
    
    parser.add_argument(
        '--no-sharpen',
        dest='sharpen',
        action='store_false',
        help='Disable light sharpening'
    )
    
    parser.add_argument(
        '--verbose',
        '-v',
        action='store_true',
        help='Print detailed progress information'
    )
    
    args = parser.parse_args()
    
    process_directory(
        args.input,
        args.output,
        apply_crop=args.crop,
        apply_realesrgan=args.realesrgan,
        apply_resize=args.resize,
        apply_clahe=args.clahe,
        apply_sharpen=args.sharpen,
        verbose=args.verbose
    )


if __name__ == '__main__':
    main()

