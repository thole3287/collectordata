# Image Preprocessing Tool

A complete Python application for preprocessing image datasets for object detection (YOLO-compatible). This tool provides both a web-based interface and command-line interface for batch processing images.

## Features

- **16:9 Aspect Ratio Center-Crop**: Automatically crops images to maintain 16:9 aspect ratio (no padding)
- **High-Quality Resizing**: Resizes images to exactly 1280x720 using LANCZOS4 interpolation
- **Noise Reduction**: Optional fastNlMeansDenoisingColored for cleaner images
- **Sharpening**: Optional unsharp masking for enhanced image clarity
- **Web Interface**: Beautiful, modern UI with real-time progress tracking
- **CLI Support**: Batch process images from command line
- **Error Handling**: Gracefully skips unreadable images and logs errors
- **Preview**: Side-by-side comparison of original and processed images

## Requirements

- Python 3.8 or higher
- OpenCV (opencv-python)
- NumPy
- Flask (for web interface)

## Installation

1. Clone or download this repository

2. Install dependencies:

```bash
pip install -r requirements.txt
```

## Usage

### Web Interface

1. Start the Flask application:

```bash
python app.py
```

2. Open your web browser and navigate to:

```
http://localhost:5000
```

3. Follow these steps:
   - Enter the path to your input folder containing images
   - Click "Load Folder" to discover images
   - Toggle denoising and sharpening options as needed
   - Click "Start Processing" to begin
   - Monitor progress in real-time
   - Select images from the dropdown to preview results

### Command-Line Interface

Process images from the command line:

```bash
# Basic usage (denoising and sharpening enabled by default)
python preprocess.py --input ./raw --output ./processed

# With explicit flags
python preprocess.py --input ./raw --output ./processed --denoise --sharpen

# Without denoising
python preprocess.py --input ./raw --output ./processed --sharpen

# Without sharpening
python preprocess.py --input ./raw --output ./processed --denoise

# With verbose output
python preprocess.py --input ./raw --output ./processed --denoise --sharpen --verbose
```

#### CLI Options

- `--input`, `-i`: Input directory containing images (required)
- `--output`, `-o`: Output directory for processed images (required)
- `--denoise`: Apply noise reduction
- `--sharpen`: Apply sharpening
- `--verbose`, `-v`: Print detailed progress information

**Note**: If neither `--denoise` nor `--sharpen` is specified, both are enabled by default.

## Image Processing Pipeline

For each image, the following steps are applied:

1. **Load**: Image is loaded from disk (supports .jpg, .jpeg, .png)
2. **Center-Crop**: Image is cropped to 16:9 aspect ratio (no padding)
3. **Resize**: Image is resized to exactly 1280x720 pixels using high-quality interpolation
4. **Denoise** (optional): Noise reduction using fastNlMeansDenoisingColored
5. **Sharpen** (optional): Unsharp masking for enhanced clarity
6. **Save**: Processed image is saved to output directory with original filename

## Project Structure

```
image-preprocessing/
├── app.py                 # Flask application entry point
├── routes.py              # Flask routes and API endpoints
├── image_loader.py        # Image loading and discovery utilities
├── image_processor.py     # Image preprocessing pipeline
├── preprocess.py          # CLI script for batch processing
├── requirements.txt       # Python dependencies
├── README.md             # This file
└── templates/
    └── index.html        # Web interface HTML template
```

## Supported Image Formats

- JPEG (.jpg, .jpeg)
- PNG (.png)

Both uppercase and lowercase extensions are supported.

## Performance

- Processes at least 1 image per second on 1080p images
- Stable for large datasets (1000+ images)
- CPU-only processing (no GPU required)
- Graceful error handling for corrupted or unreadable files

## Example Folder Structure

```
project/
├── raw_images/           # Input folder
│   ├── image1.jpg
│   ├── image2.png
│   └── image3.jpg
└── processed_images/     # Output folder (created automatically)
    ├── image1.jpg
    ├── image2.png
    └── image3.jpg
```

## Technical Details

### Center-Crop Algorithm

The center-crop maintains a 16:9 aspect ratio by:

- If image is wider than 16:9: crops width from sides
- If image is taller than 16:9: crops height from top/bottom
- If image is already 16:9: no cropping needed

### Resizing

Uses `cv2.INTER_LANCZOS4` interpolation for high-quality resizing to 1280x720.

### Denoising

Uses OpenCV's `fastNlMeansDenoisingColored` with optimized parameters:

- Filter strength: 10
- Color component filter strength: 10
- Template window size: 7x7
- Search window size: 21x21

### Sharpening

Implements unsharp masking:

- Gaussian blur kernel with sigma=2.0
- Sharpening strength: 1.5x
- Formula: `original + (original - blurred) * strength`

## Error Handling

The application gracefully handles:

- Missing or invalid directories
- Corrupted image files
- Unsupported file formats
- Empty images
- File I/O errors

All errors are logged and displayed in the UI or CLI output without crashing the application.

## Notes

- **No YOLO Model**: This tool does NOT use YOLO or any detection model. It only preprocesses images.
- **No Letterbox Padding**: Images are center-cropped, not padded. This tool prepares images BEFORE labeling.
- **Preserves Filenames**: Original filenames are preserved in the output directory.

## License

This project is provided as-is for image preprocessing tasks.

## Contributing

Feel free to submit issues or pull requests for improvements.
