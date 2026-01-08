import unittest
from unittest.mock import MagicMock, patch, mock_open
import numpy as np
import cv2
import os
import sys

# Add project root to path
sys.path.append(os.getcwd())

import services.scene_analysis as scene_analysis
from camera_collector import CameraCollector

class TestCameraChanges(unittest.TestCase):

    def test_scene_analysis_night(self):
        # Create a black image (Night)
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        scene = scene_analysis.analyze_scene_features(img)
        self.assertEqual(scene, 'night')

    def test_scene_analysis_day(self):
        # Create a random image (Day) - High contrast, some saturation
        img = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
        # Ensure high brightness to avoid night
        img = img + 50
        img = np.clip(img, 0, 255)
        
        # This random noise usually has high contrast
        scene = scene_analysis.analyze_scene_features(img)
        # It might be day or rain depending on randomness, but unlikely rain (low contrast) or night (low brightness)
        # Let's force it to be day-like: High Value, High Saturation
        # Create pure red image
        img[:] = [0, 0, 255] # BGR -> Red
        # Hue=0, Sat=255, Val=255
        
        scene = scene_analysis.analyze_scene_features(img)
        self.assertEqual(scene, 'day')

    def test_scene_analysis_rain(self):
         # Create gray image (Rain-like: Low Sat, Low Contrast, Med Brightness)
         img = np.ones((100, 100, 3), dtype=np.uint8) * 100 # Gray 100
         # Brightness 100 (>70 -> Not Night)
         # Saturation 0 (<50 -> Rain candidate)
         # Contrast 0 (<40 -> Rain candidate)
         scene = scene_analysis.analyze_scene_features(img)
         self.assertEqual(scene, 'rain')

    @patch('camera_collector.minio_service')
    @patch('camera_collector.db_service')
    @patch('camera_collector.cv2')
    @patch('camera_collector.requests')
    @patch('camera_collector.os.makedirs')
    @patch('camera_collector.os.path.getsize')
    @patch('camera_collector.os.remove')
    @patch('builtins.open', new_callable=mock_open)
    def test_collect_image_path(self, mock_file, mock_remove, mock_getsize, mock_makedirs, mock_requests, mock_cv2, mock_db, mock_minio):
        # Setup
        # Mock os.path.exists to return True so we don't try to make dirs excessively or fail checks
        with patch('camera_collector.os.path.exists', return_value=True):
            collector = CameraCollector([{'id': 'CAM001', 'name': 'Test Cam'}])
            
            # Mock requests response
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.content = b'fake_image_data'
            mock_requests.Session.return_value.get.return_value = mock_response
            
            # Mock cv2 image decoding and resizing
            # Return a "Day" image (Red)
            mock_img = np.zeros((720, 1280, 3), dtype=np.uint8)
            mock_img[:] = [0, 0, 255]
            
            mock_cv2.imdecode.return_value = mock_img
            mock_cv2.resize.return_value = mock_img
            
            # Mock getsize
            mock_getsize.return_value = 1024
            
            # Mock MinIO
            mock_minio.upload_and_get_key.return_value = {'success': True, 'key': 'fake_key'}
            
            # Run
            collector.collect_image('CAM001')
            
            # Verify MinIO upload arguments
            if mock_minio.upload_and_get_key.call_args:
                args, kwargs = mock_minio.upload_and_get_key.call_args
                custom_path = kwargs.get('custom_path')
                print(f"Generated MinIO Path: {custom_path}")
                
                # Check if 'day' is in the path (since we used Red image)
                self.assertIn('/day/', custom_path)
                self.assertIn('camera/', custom_path)
                self.assertIn('CAM001/', custom_path)
            else:
                self.fail("minio_service.upload_and_get_key was not called")

if __name__ == '__main__':
    unittest.main()
