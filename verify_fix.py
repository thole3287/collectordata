import os
import shutil
import torch
import gc
import cv2
import numpy as np
from ultralytics import YOLO, RTDETR

# Optimizing memory for low-VRAM GPUs
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"

# Use local dataset for verification
images_folder = r"c:/laragon/www/collectordata/vehicle_dataset/vehicle_dataset/images/train"
# Check if folder exists
if not os.path.exists(images_folder):
    print(f"Error: {images_folder} does not exist.")
    exit(1)

# Limit usage to the first 10 images to be quick but prove it works
# We can't easily limit 'predict' source folder unless we pass a list of files.
# So we will list directory and pass first 10 files.
all_files = [os.path.join(images_folder, f) for f in os.listdir(images_folder) if f.lower().endswith(('.jpg', '.png', '.jpeg'))]
if not all_files:
    print("No images found for verification.")
    exit(1)
    
test_files = all_files[:20] # Test on 20 images
print(f"Testing on {len(test_files)} images.")

base_results_folder = os.path.abspath("verification_results")
if os.path.exists(base_results_folder):
    shutil.rmtree(base_results_folder)
os.makedirs(base_results_folder, exist_ok=True)

yolo26_results = os.path.join(base_results_folder, "yolo26")
rtdetr_results = os.path.join(base_results_folder, "rtdetr")

vehicle_classes = [1, 2, 3, 5, 7]

print("Predicting with YOLO26...")
model_yolo26 = YOLO("yolo26n.pt")
results_yolo26 = model_yolo26.predict(
    source=test_files,
    conf=0.25,
    iou=0.45,
    imgsz=640,
    batch=1,
    classes=vehicle_classes,
    save=False, 
    project=yolo26_results, name="predict", exist_ok=True
)
del model_yolo26
gc.collect()
torch.cuda.empty_cache()

print("Predicting with RT-DETR...")
model_rtdetr = RTDETR("rtdetr-l.pt")
results_rtdetr = model_rtdetr.predict(
    source=test_files,
    conf=0.25,
    iou=0.45,
    imgsz=640,
    batch=1,
    classes=vehicle_classes,
    save=False,
    project=rtdetr_results, name="predict", exist_ok=True
)
del model_rtdetr
gc.collect()
torch.cuda.empty_cache()

print("Verification script finished successfully! No OOM error.")
