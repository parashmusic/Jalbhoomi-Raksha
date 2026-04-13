BhumiRaksha -- Satellite Evidence Export
=========================================
Claim ID   : CLM-71A0BCD8
Event Date : 2026-04-10
Exported   : 2026-04-13 23:39:16
Source     : Google Earth Engine  (Copernicus / ESA Sentinel)

FILES
-----
sat_1_pre_flood_SAR.png
  Sentinel-1 IW VV-band mean BEFORE the flood (2026-03-11 to 2026-04-07).
  Greyscale: bright = dry land/crops, dark = water/wet soil.

sat_2_post_flood_SAR.png
  Sentinel-1 IW VV-band mean AFTER the flood (2026-04-10 to 2026-04-17).
  Areas that turned dark compared to sat_1 are flooded.

sat_3_SAR_difference.png
  Backscatter change image (VV_pre - VV_post).
  Blue = large drop in backscatter = flooded area.

sat_4_flood_change_mask.png
  Binary flood mask: RED pixels had >3 dB backscatter drop.
  This EXACT mask is used to compute the Satellite Score (0-50 pts).

sat_5_pre_flood_optical.png  (if present)
  Sentinel-2 true-colour RGB before the flood (cloud-free composite).

sat_6_post_flood_optical.png  (if present)
  Sentinel-2 true-colour RGB after the flood (cloud-free composite).

PIPELINE LOGIC
--------------
  1. Sentinel-1 SAR radar penetrates monsoon cloud cover
  2. VV backscatter drops when land is submerged under water
  3. Pixels with >3 dB drop are classified as flooded
  4. Flooded area in hectares -> Satellite Score 0-50
  5. Satellite Score + YOLO Ground Score (0-50) = Total AI Score
