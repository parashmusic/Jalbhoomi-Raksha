# backend/export_detections.py
import os
from ultralytics import YOLO
from PIL import Image
from pathlib import Path
from config import settings

def export_visual_evidence(claim_id: str):
    print(f"🧐 Generating Visual AI Evidence for Claim: {claim_id}...")
    
    # 1. Load Model
    model = YOLO(settings.YOLO_MODEL_PATH)
    
    # 2. Find Photos
    claim_dir = Path(f"uploads/claims/{claim_id}")
    if not claim_dir.exists():
        print(f"❌ Claim folder {claim_dir} not found!")
        return
    
    # 3. Process each photo
    output_dir = claim_dir / "ai_evidence"
    output_dir.mkdir(exist_ok=True)
    
    photos = list(claim_dir.glob("*.jpg")) + list(claim_dir.glob("*.jpeg"))
    
    for photo in photos:
        print(f"📸 Processing {photo.name}...")
        results = model.predict(str(photo), conf=0.25, verbose=False)
        
        # This saves the image WITH the bounding boxes and labels
        # we save it with a 'detected_' prefix
        result = results[0]
        output_path = output_dir / f"detected_{photo.name}"
        
        # results[0].plot() returns a BGR numpy array (OpenCV style)
        # we convert it to RGB and save via PIL
        plot_bgr = result.plot()
        plot_rgb = plot_bgr[:, :, ::-1] # BGR to RGB
        Image.fromarray(plot_rgb).save(output_path)
        
        print(f"✅ Saved evidence to: {output_path}")

    print(f"\n🚀 DONE! Check your folder at: {output_dir.absolute()}")

if __name__ == "__main__":
    # Using the Claim ID from your last log
    export_visual_evidence("CLM-71A0BCD8")
