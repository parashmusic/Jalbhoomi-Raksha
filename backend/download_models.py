import os
from ultralytics import YOLO
from pathlib import Path

def download_weights():
    # Ensure the models directory exists
    model_dir = Path("d:/Flood Detection/models")
    model_dir.mkdir(parents=True, exist_ok=True)
    
    target_path = model_dir / "flood_yolov8m.pt"
    
    print(f"🚀 Downloading YOLOv8 weights to {target_path}...")
    
    # This downloads the official YOLOv8 medium model from Ultralytics
    # In a real scenario, you'd replace this with your custom-trained model
    model = YOLO("yolov8m.pt") 
    
    # Save/Rename it to what our app expects
    os.rename("yolov8m.pt", str(target_path))
    
    print(f"✅ Success! Weights ready at {target_path}")

if __name__ == "__main__":
    download_weights()
