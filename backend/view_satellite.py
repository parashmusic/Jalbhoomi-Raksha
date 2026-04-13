# backend/view_satellite.py
import ee
from config import settings
from api.dependencies import get_sar_mapper
import json

def get_visuals():
    # 1. Initialize
    print("🛰️ Connecting to Google Earth Engine...")
    ee.Initialize(project=settings.GEE_PROJECT)
    
    # 2. Village Geometry (The one we seeded)
    village_geom = {
        'type': 'Polygon',
        'coordinates': [[[91.70, 26.10], [91.80, 26.10], [91.80, 26.20], [91.70, 26.20], [91.70, 26.10]]]
    }
    aoi = ee.Geometry.Polygon(village_geom['coordinates'])
    
    # 3. Fetch SAR Data (Same logic as our backend)
    event_date = '2026-04-10'
    s1 = ee.ImageCollection('COPERNICUS/S1_GRD').filterBounds(aoi)
    
    pre_flood = s1.filterDate('2026-03-01', '2026-04-01').mean().clip(aoi)
    post_flood = s1.filterDate('2026-04-10', '2026-04-17').mean().clip(aoi)
    
    # Simple Threshold for Visual
    diff = pre_flood.select('VV').subtract(post_flood.select('VV'))
    flood_mask = diff.gt(3).updateMask(diff.gt(3))
    
    # 4. Generate Thumbnail URLs
    vis_params = {'min': -25, 'max': 0} # SAR backscatter range
    
    pre_url = pre_flood.select('VV').getThumbURL({
        'params': vis_params, 'region': aoi, 'dimensions': 512, 'format': 'png'
    })
    
    post_url = post_flood.select('VV').getThumbURL({
        'params': vis_params, 'region': aoi, 'dimensions': 512, 'format': 'png'
    })
    
    mask_url = flood_mask.getThumbURL({
        'params': {'palette': 'FF0000'}, 'region': aoi, 'dimensions': 512, 'format': 'png'
    })
    
    print("\n--- VISUAL CLOUD LINKS ---")
    print(f"1. Before Flood (Radar): {pre_url}")
    print(f"2. After Flood (Radar):  {post_url}")
    print(f"3. Flood Mask (Detected): {mask_url}")
    print("\n💡 Copy and paste these into your browser to see the satellite view!")

if __name__ == "__main__":
    get_visuals()
