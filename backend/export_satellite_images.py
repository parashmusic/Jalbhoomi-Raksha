"""
export_satellite_images.py
--------------------------
Downloads the Sentinel-1 SAR + Sentinel-2 optical satellite images used by
BhumiRaksha during flood analysis for a given claim.

Exported PNGs (saved locally):
  sat_1_pre_flood_SAR.png         Sentinel-1 VV before flood (greyscale)
  sat_2_post_flood_SAR.png        Sentinel-1 VV after flood  (greyscale)
  sat_3_flood_change_mask.png     Flood mask derived at 3 dB threshold (red)
  sat_4_pre_flood_optical.png     Sentinel-2 RGB before flood (if cloud-free)
  sat_5_post_flood_optical.png    Sentinel-2 RGB after flood  (if cloud-free)
  README.txt                      Explanation of each file

Usage:
  cd backend
  .\\venv\\Scripts\\python export_satellite_images.py
  .\\venv\\Scripts\\python export_satellite_images.py --claim CLM-XXXXXXXX
  .\\venv\\Scripts\\python export_satellite_images.py --claim CLM-71A0BCD8 --event-date 2026-04-10
"""

import sys
import argparse
import urllib.request
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent))
from config import settings

try:
    import ee
    EE_AVAILABLE = True
except ImportError:
    EE_AVAILABLE = False

# ---------------------------------------------------------------------------
DEFAULT_CLAIM_ID = "CLM-71A0BCD8"
EVENT_DATE       = "2026-04-10"
IMAGE_DIM        = 512   # exported thumbnail width/height in pixels

# Village AOI — same coordinates as the seeded database entry
VILLAGE_COORDS = [
    [91.70, 26.10],
    [91.80, 26.10],
    [91.80, 26.20],
    [91.70, 26.20],
    [91.70, 26.10],
]
# ---------------------------------------------------------------------------


def offset_date(date_str: str, days: int) -> str:
    dt = datetime.strptime(date_str, "%Y-%m-%d") + timedelta(days=days)
    return dt.strftime("%Y-%m-%d")


def download_thumb(image, vis_params: dict, region, dimensions: int,
                   dest: Path, label: str) -> bool:
    """
    Download an Earth Engine image as a PNG thumbnail.

    IMPORTANT: vis_params must be passed FLAT inside the getThumbURL dict —
    NOT nested under a 'params' key (common mistake that causes the
    'Must specify visualization parameters' error).
    """
    print(f"  >> [{label}]")
    try:
        # Correct format: merge vis_params directly with the request dict
        thumb_params = {
            **vis_params,        # min, max, palette / bands go here FLAT
            "region":     region,
            "dimensions": dimensions,
            "format":     "png",
        }
        url = image.getThumbURL(thumb_params)
        urllib.request.urlretrieve(url, dest)
        kb = dest.stat().st_size // 1024
        print(f"     [OK] {dest.name}  ({kb} KB)")
        return True
    except Exception as e:
        print(f"     [FAIL] {e}")
        return False


def export_satellite_images(claim_id: str, event_date: str):
    print(f"\n{'='*60}")
    print(f"  BhumiRaksha -- Satellite Image Export")
    print(f"  Claim      : {claim_id}")
    print(f"  Event date : {event_date}")
    print(f"{'='*60}\n")

    if not EE_AVAILABLE:
        print("[ERROR] earthengine-api not installed.")
        print("        Run: pip install earthengine-api")
        return

    # ---- 1. GEE Init -------------------------------------------------------
    print("[GEE] Connecting ...")
    try:
        sa  = settings.GEE_SERVICE_ACCOUNT
        key = settings.GEE_KEY_FILE
        if sa and key and Path(key).exists():
            creds = ee.ServiceAccountCredentials(sa, key)
            ee.Initialize(creds, project=settings.GEE_PROJECT)
        else:
            ee.Initialize(project=settings.GEE_PROJECT)
        print("[GEE] Connected OK\n")
    except Exception as e:
        print(f"[ERROR] GEE init failed: {e}")
        return

    # ---- 2. Date windows (same logic as sar_processor.py) -----------------
    pre_start = offset_date(event_date, -30)  # 2026-03-11
    pre_end   = offset_date(event_date, -3)   # 2026-04-07
    post_end  = offset_date(event_date,  7)   # 2026-04-17

    print(f"  Pre-flood  : {pre_start}  to  {pre_end}")
    print(f"  Post-flood : {event_date}  to  {post_end}\n")

    aoi = ee.Geometry.Polygon([VILLAGE_COORDS])

    # ---- 3. Build Sentinel-1 SAR images ------------------------------------
    s1_col = (ee.ImageCollection("COPERNICUS/S1_GRD")
                .filterBounds(aoi)
                .filter(ee.Filter.eq("instrumentMode", "IW"))
                .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VV")))

    s1_pre  = s1_col.filterDate(pre_start, pre_end).select("VV").mean().clip(aoi)
    s1_post = s1_col.filterDate(event_date, post_end).select("VV").mean().clip(aoi)

    # Flood mask: VV backscatter drops >3 dB when land is flooded
    diff        = s1_pre.subtract(s1_post)
    flood_mask  = diff.gt(3).selfMask()   # mask out non-flood pixels

    # ---- 4. Build Sentinel-2 optical images --------------------------------
    s2_col = (ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
                .filterBounds(aoi)
                .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 30)))

    s2_pre  = s2_col.filterDate(pre_start, pre_end).median().clip(aoi)
    s2_post = s2_col.filterDate(event_date, post_end).median().clip(aoi)

    # ---- 5. Visualisation parameters (passed FLAT to getThumbURL) ----------
    # SAR backscatter: -25 dB (dark/water) to 0 dB (bright/land)
    sar_vis  = {"min": -25, "max": 0,   "palette": ["000000", "ffffff"]}

    # Flood change difference image (for context, blue-white palette)
    diff_vis = {"min": 0,   "max": 8,   "palette": ["ffffff", "0000ff"]}

    # Flood mask: red for flooded pixels
    mask_vis = {"min": 0,   "max": 1,   "palette": ["FF4444"]}

    # Sentinel-2 true colour: B4=Red, B3=Green, B2=Blue
    s2_vis   = {"bands": ["B4", "B3", "B2"], "min": 0, "max": 3000}

    # ---- 6. Output directory -----------------------------------------------
    output_dir = Path(f"uploads/claims/{claim_id}/satellite_export")
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"[INFO] Saving to: {output_dir.absolute()}\n")

    # ---- 7. Download images ------------------------------------------------
    ok = 0
    total = 0

    layers = [
        (s1_pre,    sar_vis,  "sat_1_pre_flood_SAR.png",       "Pre-flood Sentinel-1 SAR (VV)"),
        (s1_post,   sar_vis,  "sat_2_post_flood_SAR.png",      "Post-flood Sentinel-1 SAR (VV)"),
        (diff,      diff_vis, "sat_3_SAR_difference.png",      "Change image (pre minus post VV)"),
        (flood_mask,mask_vis, "sat_4_flood_change_mask.png",   "Flood mask (>3 dB change = flooded)"),
    ]

    for img, vis, fname, label in layers:
        total += 1
        if download_thumb(img, vis, aoi, IMAGE_DIM, output_dir / fname, label):
            ok += 1

    # Sentinel-2 optical — only if cloud-free data exists in window
    print("  >> [Checking Sentinel-2 cloud-free availability ...]")
    try:
        n_pre_s2  = s2_col.filterDate(pre_start, pre_end).size().getInfo()
        n_post_s2 = s2_col.filterDate(event_date, post_end).size().getInfo()
        print(f"     S2 pre-flood scenes available : {n_pre_s2}")
        print(f"     S2 post-flood scenes available: {n_post_s2}")

        if n_pre_s2 > 0:
            total += 1
            if download_thumb(s2_pre, s2_vis, aoi, IMAGE_DIM,
                              output_dir / "sat_5_pre_flood_optical.png",
                              "Pre-flood Sentinel-2 optical RGB"):
                ok += 1
        else:
            print("     [SKIP] No cloud-free S2 imagery in pre-flood window")

        if n_post_s2 > 0:
            total += 1
            if download_thumb(s2_post, s2_vis, aoi, IMAGE_DIM,
                              output_dir / "sat_6_post_flood_optical.png",
                              "Post-flood Sentinel-2 optical RGB"):
                ok += 1
        else:
            print("     [SKIP] No cloud-free S2 imagery in post-flood window")

    except Exception as e:
        print(f"     [WARN] Sentinel-2 check failed: {e}")

    # ---- 8. Write README ---------------------------------------------------
    readme = (
        "BhumiRaksha -- Satellite Evidence Export\n"
        "=========================================\n"
        f"Claim ID   : {claim_id}\n"
        f"Event Date : {event_date}\n"
        f"Exported   : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        "Source     : Google Earth Engine  (Copernicus / ESA Sentinel)\n\n"
        "FILES\n"
        "-----\n"
        "sat_1_pre_flood_SAR.png\n"
        f"  Sentinel-1 IW VV-band mean BEFORE the flood ({pre_start} to {pre_end}).\n"
        "  Greyscale: bright = dry land/crops, dark = water/wet soil.\n\n"
        "sat_2_post_flood_SAR.png\n"
        f"  Sentinel-1 IW VV-band mean AFTER the flood ({event_date} to {post_end}).\n"
        "  Areas that turned dark compared to sat_1 are flooded.\n\n"
        "sat_3_SAR_difference.png\n"
        "  Backscatter change image (VV_pre - VV_post).\n"
        "  Blue = large drop in backscatter = flooded area.\n\n"
        "sat_4_flood_change_mask.png\n"
        "  Binary flood mask: RED pixels had >3 dB backscatter drop.\n"
        "  This EXACT mask is used to compute the Satellite Score (0-50 pts).\n\n"
        "sat_5_pre_flood_optical.png  (if present)\n"
        "  Sentinel-2 true-colour RGB before the flood (cloud-free composite).\n\n"
        "sat_6_post_flood_optical.png  (if present)\n"
        "  Sentinel-2 true-colour RGB after the flood (cloud-free composite).\n\n"
        "PIPELINE LOGIC\n"
        "--------------\n"
        "  1. Sentinel-1 SAR radar penetrates monsoon cloud cover\n"
        "  2. VV backscatter drops when land is submerged under water\n"
        "  3. Pixels with >3 dB drop are classified as flooded\n"
        "  4. Flooded area in hectares -> Satellite Score 0-50\n"
        "  5. Satellite Score + YOLO Ground Score (0-50) = Total AI Score\n"
    )
    (output_dir / "README.txt").write_text(readme, encoding="utf-8")

    # ---- 9. Summary --------------------------------------------------------
    print(f"\n{'='*60}")
    if ok == total:
        print(f"  All {ok} satellite images saved successfully!")
    else:
        print(f"  {ok}/{total} images saved  ({total - ok} failed)")
    print(f"  Folder: {output_dir.absolute()}")
    print(f"{'='*60}\n")


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Export satellite images used by the BhumiRaksha pipeline for a claim"
    )
    parser.add_argument("--claim",      default=DEFAULT_CLAIM_ID,
                        help="Claim ID  e.g. CLM-71A0BCD8")
    parser.add_argument("--event-date", default=EVENT_DATE,
                        help="Event date YYYY-MM-DD  (default: 2026-04-10)")
    args = parser.parse_args()
    export_satellite_images(args.claim, args.event_date)
