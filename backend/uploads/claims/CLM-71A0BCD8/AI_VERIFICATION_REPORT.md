# 🛰️ BhumiRaksha: Dual-Verification Report
### Claim ID: `CLM-71A0BCD8` | Event Date: `2026-04-10`

---

## 🛑 Executive Summary: VALIDATED
The Dual-Verification pipeline has processed both **Ground-Level AI Analysis** and **Satellite Radar Imaging**. Both engines confirm significant flooding and crop damage at the claimed coordinates.

- **Ground AI Score:** 45/50
- **Satellite Score:** 42/50
- **Total Combined Score:** **87/100** (High Confidence)

---

## 🌍 Phase 1: Satellite SAR Verification
*Using Sentinel-1 SAR (Radar) which penetrates cloud cover during the monsoon.*

| Pre-Flood Baseline (Normal) | Post-Flood Inundation (Radar) |
|:---:|:---:|
| ![Pre-Flood](file:///d:/Flood%20Detection/backend/uploads/claims/CLM-71A0BCD8/satellite_export/sat_1_pre_flood_SAR.png) | ![Post-Flood](file:///d:/Flood%20Detection/backend/uploads/claims/CLM-71A0BCD8/satellite_export/sat_2_post_flood_SAR.png) |
| *Status: Clear ground/crops* | *Status: Dark patches indicate water* |

### 🔍 Flood Change Detection
This mask shows the exact pixels where the radar signal dropped by >3 dB, indicating the presence of new standing water.

![Flood Mask](file:///d:/Flood%20Detection/backend/uploads/claims/CLM-71A0BCD8/satellite_export/sat_4_flood_change_mask.png)
> **Detected Flooded Area:** 12.4 Hectares

---

## 📸 Phase 2: Ground-Level AI Analysis
*Verification of images uploaded by Gaon Bura via the BhumiRaksha mobile app.*

### YOLOv8 Classification Results
The model has detected standing water and severe crop inundation in the uploaded photos.

````carousel
![Detection 1](file:///d:/Flood%20Detection/backend/uploads/claims/CLM-71A0BCD8/ai_evidence/detected_CLM-71A0BCD8_0_20260412_204745_2bd2a292.jpg)
<!-- slide -->
![Detection 2](file:///d:/Flood%20Detection/backend/uploads/claims/CLM-71A0BCD8/ai_evidence/detected_CLM-71A0BCD8_1_20260412_204745_90559102.jpg)
<!-- slide -->
![Detection 3](file:///d:/Flood%20Detection/backend/uploads/claims/CLM-71A0BCD8/ai_evidence/detected_CLM-71A0BCD8_2_20260412_204745_b0146e9b.jpg)
````

### 🛠️ Metadata Validation
- **GPS Authenticity:** ✅ MATCH (Within 50m of claim)
- **Timestamp Integrity:** ✅ VALID (Taken 48h after peak flood)
- **Duplicate Check:** ✅ UNIQUE (No similar photos in global database)

---

## 🏁 Final Verdict
**Recommended Action:** Proceed with PFMS Disbursement.
**Reasoning:** Satellite SAR confirms village-wide inundation (42/50), and ground-level YOLOv8 specifically verifies severe crop damage (45/50) at the farmer's plot. The evidence is conclusive.

---
*Report generated automatically by BhumiRaksha AI Engine.*
