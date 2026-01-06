"""
Flask Routes Module

This module defines all Flask routes for the image preprocessing web application.
"""

import threading
import os
import tempfile
import shutil
import gc
from pathlib import Path
from flask import render_template, request, jsonify, send_file
from werkzeug.utils import secure_filename
import cv2
import base64

from image_loader import ImageLoader
from image_processor import ImageProcessor


# Global state for processing (simple approach for single-user app)
processing_state = {
    'is_processing': False,
    'current_image': 0,
    'total_images': 0,
    'errors': [],
    'input_dir': None,
    'output_dir': None,
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


def register_routes(app):
    """
    Register all routes with the Flask app.
    
    Args:
        app: Flask application instance
    """
    
    @app.route('/')
    def index():
        """Render the main page."""
        return render_template('index.html')
    
    @app.route('/api/upload', methods=['POST'])
    def upload_folder():
        """
        Handle folder upload (via file picker) or path input.
        Can receive either:
        - JSON with 'folder_path' field (for path input)
        - Multipart form data with files (for folder upload)
        """
        try:
            # Check if this is a file upload (folder picker) or path input
            if 'files[]' in request.files or len(request.files) > 0:
                # Handle folder upload via file picker
                files = request.files.getlist('files[]')
                if not files or len(files) == 0:
                    # Try alternative field name
                    files = []
                    for key in request.files:
                        files.extend(request.files.getlist(key))
                
                if not files or len(files) == 0:
                    return jsonify({
                        'success': False,
                        'error': 'No files uploaded'
                    }), 400
                
                # Filter image files
                image_extensions = {'.jpg', '.jpeg', '.png', '.JPG', '.JPEG', '.PNG'}
                image_files = [f for f in files if any(f.filename.lower().endswith(ext.lower()) for ext in image_extensions)]
                
                if len(image_files) == 0:
                    return jsonify({
                        'success': False,
                        'error': 'No supported images found in uploaded files (.jpg, .png)'
                    }), 400
                
                # Create temporary directory to store uploaded files
                temp_dir = Path(tempfile.mkdtemp(prefix='image_preprocessing_'))
                
                # Save uploaded files to temp directory
                saved_files = []
                for file in image_files:
                    if file.filename:
                        # Get just the filename (remove any path)
                        filename = secure_filename(os.path.basename(file.filename))
                        file_path = temp_dir / filename
                        file.save(str(file_path))
                        saved_files.append(file_path)
                
                # Set up output directory
                output_dir = temp_dir.parent / f"{temp_dir.name}_processed"
                output_dir.mkdir(exist_ok=True)
                
                # Update global state
                processing_state['input_dir'] = str(temp_dir)
                processing_state['output_dir'] = str(output_dir)
                processing_state['total_images'] = len(saved_files)
                processing_state['current_image'] = 0
                processing_state['errors'] = []
                processing_state['is_processing'] = False
                
                return jsonify({
                    'success': True,
                    'image_count': len(saved_files),
                    'output_dir': str(output_dir),
                    'uploaded': True
                })
            
            else:
                # Handle path input (original method)
                data = request.get_json()
                if not data:
                    return jsonify({
                        'success': False,
                        'error': 'No data provided'
                    }), 400
                
                folder_path = (data.get('folder_path') or '').strip()
                output_folder_path = (data.get('output_folder_path') or '').strip()
                
                if not folder_path:
                    return jsonify({
                        'success': False,
                        'error': 'No folder path provided'
                    }), 400
                
                # Validate folder exists
                folder_path = Path(folder_path)
                if not folder_path.exists():
                    return jsonify({
                        'success': False,
                        'error': f'Folder does not exist: {folder_path}'
                    }), 400
                
                if not folder_path.is_dir():
                    return jsonify({
                        'success': False,
                        'error': f'Path is not a directory: {folder_path}'
                    }), 400
                
                # Discover images
                try:
                    image_files = ImageLoader.discover_images(str(folder_path))
                except ValueError as e:
                    return jsonify({
                        'success': False,
                        'error': str(e)
                    }), 400
                
                if len(image_files) == 0:
                    return jsonify({
                        'success': False,
                        'error': 'No supported images found in folder (.jpg, .png)'
                    }), 400
                
                # Set up output directory
                if output_folder_path:
                    # User specified output folder
                    output_dir = Path(output_folder_path)
                    # Create directory if it doesn't exist
                    output_dir.mkdir(parents=True, exist_ok=True)
                else:
                    # Default: create output directory next to input folder
                    output_dir = folder_path.parent / f"{folder_path.name}_processed"
                    output_dir.mkdir(exist_ok=True)
                
                # Update global state
                processing_state['input_dir'] = str(folder_path)
                processing_state['output_dir'] = str(output_dir)
                processing_state['total_images'] = len(image_files)
                processing_state['current_image'] = 0
                processing_state['errors'] = []
                processing_state['is_processing'] = False
                
                return jsonify({
                    'success': True,
                    'image_count': len(image_files),
                    'output_dir': str(output_dir),
                    'uploaded': False
                })
            
        except Exception as e:
            return jsonify({
                'success': False,
                'error': f'Server error: {str(e)}'
            }), 500
    
    def process_images_background():
        """
        Background thread function to process images.
        Optimized for large datasets (10,000+ images) with memory management.
        """
        try:
            # Discover images
            image_files = ImageLoader.discover_images(processing_state['input_dir'])
            processing_state['total_images'] = len(image_files)
            
            # Process images
            output_dir = Path(processing_state['output_dir'])
            # Ensure output directory exists
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Process in batches to manage memory better
            batch_size = 100  # Process 100 images, then cleanup memory
            
            for batch_start in range(0, len(image_files), batch_size):
                batch_end = min(batch_start + batch_size, len(image_files))
                batch_files = image_files[batch_start:batch_end]
                
                for idx, image_path in enumerate(batch_files):
                    global_idx = batch_start + idx + 1
                    processing_state['current_image'] = global_idx
                    
                    # Load image
                    image = None
                    try:
                        image, error = ImageLoader.load_image(image_path)
                        if error or image is None:
                            processing_state['errors'].append({
                                'file': image_path.name,
                                'error': error or 'Failed to load image'
                            })
                            continue
                        
                        # Validate image
                        is_valid, validation_error = ImageLoader.validate_image(image)
                        if not is_valid:
                            processing_state['errors'].append({
                                'file': image_path.name,
                                'error': validation_error or 'Invalid image format'
                            })
                            # Explicitly delete image to free memory
                            del image
                            image = None
                            continue
                        
                        # Process image
                        processed = None
                        try:
                            processed = ImageProcessor.process_image(
                                image,
                                apply_crop=processing_state['apply_crop'],
                                apply_realesrgan=processing_state['apply_realesrgan'],
                                apply_resize=processing_state['apply_resize'],
                                apply_clahe=processing_state['apply_clahe'],
                                apply_sharpen=processing_state['apply_sharpen'],
                                realesrgan_denoise_strength=processing_state.get('realesrgan_denoise_strength', 0.5),
                                realesrgan_scale=processing_state.get('realesrgan_scale', 4),
                                blend_with_original=processing_state.get('blend_with_original', False),
                                blend_alpha=processing_state.get('blend_alpha', 0.7),
                                clahe_clip_limit=processing_state.get('clahe_clip_limit', 2.0),
                                clahe_tile_size=processing_state.get('clahe_tile_size', 8),
                            )
                            
                            # Free original image memory immediately
                            del image
                            image = None
                            
                            # Save processed image
                            output_path = output_dir / image_path.name
                            success, save_error = ImageProcessor.save_image(processed, output_path)
                            
                            # Free processed image memory immediately
                            del processed
                            processed = None
                            
                            if not success:
                                processing_state['errors'].append({
                                    'file': image_path.name,
                                    'error': save_error or 'Failed to save image'
                                })
                                
                        except Exception as e:
                            processing_state['errors'].append({
                                'file': image_path.name,
                                'error': f'Processing error: {str(e)}'
                            })
                            # Cleanup on error
                            if image is not None:
                                del image
                            if processed is not None:
                                del processed
                    
                    except Exception as e:
                        processing_state['errors'].append({
                            'file': image_path.name if image_path else 'Unknown',
                            'error': f'Unexpected error: {str(e)}'
                        })
                        # Cleanup on error
                        if image is not None:
                            del image
                    
                    finally:
                        # Force garbage collection every 50 images to free memory
                        if global_idx % 50 == 0:
                            gc.collect()
                
                # Force garbage collection after each batch
                gc.collect()
            
            processing_state['is_processing'] = False
            
        except Exception as e:
            processing_state['is_processing'] = False
            processing_state['errors'].append({
                'file': 'System',
                'error': f'Processing thread error: {str(e)}'
            })
    
    @app.route('/api/process', methods=['POST'])
    def start_processing():
        """
        Start processing images in background thread.
        Expects JSON with 'apply_denoise' and 'apply_sharpen' flags.
        """
        try:
            if processing_state['is_processing']:
                return jsonify({
                    'success': False,
                    'error': 'Processing already in progress'
                }), 400
            
            if not processing_state['input_dir']:
                return jsonify({
                    'success': False,
                    'error': 'No input folder selected'
                }), 400
            
            data = request.get_json()
            processing_state['apply_crop'] = data.get('apply_crop', True)
            processing_state['apply_realesrgan'] = data.get('apply_realesrgan', True)
            processing_state['apply_resize'] = data.get('apply_resize', True)
            processing_state['apply_clahe'] = data.get('apply_clahe', True)
            processing_state['apply_sharpen'] = data.get('apply_sharpen', True)
            processing_state['realesrgan_denoise_strength'] = float(data.get('realesrgan_denoise_strength', 0.5))
            processing_state['clahe_clip_limit'] = float(data.get('clahe_clip_limit', 2.0))
            processing_state['clahe_tile_size'] = int(data.get('clahe_tile_size', 8))
            processing_state['realesrgan_scale'] = int(data.get('realesrgan_scale', 4))
            processing_state['blend_with_original'] = bool(data.get('blend_with_original', False))
            processing_state['blend_alpha'] = float(data.get('blend_alpha', 0.7))
            
            # Reset state
            processing_state['is_processing'] = True
            processing_state['current_image'] = 0
            processing_state['errors'] = []
            
            # Start processing in background thread
            thread = threading.Thread(target=process_images_background, daemon=True)
            thread.start()
            
            return jsonify({
                'success': True,
                'message': 'Processing started'
            })
            
        except Exception as e:
            processing_state['is_processing'] = False
            return jsonify({
                'success': False,
                'error': f'Server error: {str(e)}'
            }), 500
    
    @app.route('/api/status', methods=['GET'])
    def get_status():
        """Get current processing status."""
        return jsonify({
            'is_processing': processing_state['is_processing'],
            'current_image': processing_state['current_image'],
            'total_images': processing_state['total_images'],
            'errors': processing_state['errors'],
            'input_dir': processing_state['input_dir'],
            'output_dir': processing_state['output_dir']
        })
    
    @app.route('/api/image/original/<path:filename>', methods=['GET'])
    def serve_original_image(filename):
        """
        Serve original image from input directory.
        """
        try:
            if not processing_state['input_dir']:
                return jsonify({
                    'success': False,
                    'error': 'No input folder selected'
                }), 400
            
            image_path = Path(processing_state['input_dir']) / filename
            
            if not image_path.exists():
                return jsonify({
                    'success': False,
                    'error': f'Image not found: {filename}'
                }), 404
            
            return send_file(str(image_path))
            
        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    @app.route('/api/image/processed/<path:filename>', methods=['GET'])
    def serve_processed_image(filename):
        """
        Serve processed image from output directory.
        """
        try:
            if not processing_state['output_dir']:
                return jsonify({
                    'success': False,
                    'error': 'No output folder selected'
                }), 400
            
            image_path = Path(processing_state['output_dir']) / filename
            
            if not image_path.exists():
                return jsonify({
                    'success': False,
                    'error': f'Image not found: {filename}'
                }), 404
            
            return send_file(str(image_path))
            
        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    @app.route('/api/preview', methods=['GET'])
    def get_preview():
        """
        Get preview paths of original and processed images.
        Expects 'image_name' query parameter.
        Returns paths instead of base64 encoded images.
        """
        try:
            image_name = request.args.get('image_name')
            if not image_name:
                return jsonify({
                    'success': False,
                    'error': 'No image name provided'
                }), 400
            
            if not processing_state['input_dir'] or not processing_state['output_dir']:
                return jsonify({
                    'success': False,
                    'error': 'No folder selected'
                }), 400
            
            input_path = Path(processing_state['input_dir']) / image_name
            output_path = Path(processing_state['output_dir']) / image_name
            
            if not input_path.exists():
                return jsonify({
                    'success': False,
                    'error': f'Original image not found: {image_name}'
                }), 404
            
            if not output_path.exists():
                return jsonify({
                    'success': False,
                    'error': f'Processed image not found: {image_name}'
                }), 404
            
            # Return paths instead of base64
            return jsonify({
                'success': True,
                'original': f'/api/image/original/{image_name}',
                'processed': f'/api/image/processed/{image_name}',
                'original_path': str(input_path),
                'processed_path': str(output_path)
            })
            
        except Exception as e:
            return jsonify({
                'success': False,
                'error': f'Server error: {str(e)}'
            }), 500
    
    @app.route('/api/list-images', methods=['GET'])
    def list_images():
        """List all images in the input directory."""
        try:
            if not processing_state['input_dir']:
                return jsonify({
                    'success': False,
                    'error': 'No folder selected'
                }), 400
            
            image_files = ImageLoader.discover_images(processing_state['input_dir'])
            image_names = [f.name for f in image_files]
            
            return jsonify({
                'success': True,
                'images': image_names
            })
            
        except Exception as e:
            return jsonify({
                'success': False,
                'error': f'Server error: {str(e)}'
            }), 500
    
    @app.route('/api/model-info', methods=['GET'])
    def get_model_info():
        """Get information about the Real-ESRGAN model being used."""
        try:
            model_info = ImageProcessor.get_realesrgan_info()
            return jsonify({
                'success': True,
                'model_info': model_info
            })
        except Exception as e:
            return jsonify({
                'success': False,
                'error': f'Server error: {str(e)}'
            }), 500

