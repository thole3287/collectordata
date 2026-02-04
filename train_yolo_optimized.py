import os
import torch
from ultralytics import YOLO

# Optimizing memory for low-VRAM GPUs (4GB)
# This helps reduce fragmentation
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"

def train():
    # Use the same model as user
    model = YOLO("yolo26n.pt")

    print("🚀 Starting training with optimized settings for 4GB GPU...")
    
    # Replicating user's command but with optimized settings
    # Original: yolo task=detect mode=train model=yolo26n.pt data=... epochs=20 imgsz=640 batch=32 ...
    results = model.train(
        data="C:/laragon/www/collectordata/vehicle_dataset/vehicle_dataset/data.yaml",
        epochs=20,
        imgsz=640,
        batch=8,           # REDUCED from 32 to 8 to avoid OOM
        workers=4,         # Reduced workers slightly to save RAM
        device=0,
        name="vehicle_yolo26_gpu_optimized",
        plots=True,
        amp=False,         # Disabled AMP to avoid NaN/stability issues on GTX 1650
        exist_ok=True,
        project="C:/laragon/www/collectordata/runs/detect"
    )
    
    print("✅ Training complete!")

if __name__ == "__main__":
    train()
