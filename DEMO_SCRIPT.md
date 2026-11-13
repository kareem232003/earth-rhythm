# 3-Minute Judging Demo Script (`DEMO_SCRIPT.md`)

**Project:** EARTH RHYTHM — NISAR Surface Change Storyteller  
**Challenge:** NASA Space Apps 2026 (*"Dancing with the SARs"*)  
**Target Duration:** `3:00` (`180 seconds`)  
**Live URL:** `http://127.0.0.1:8000`

---

## Pre-Flight Setup (Before Starting the 3-Minute Timer)
1. Start the server in a terminal:
   ```powershell
   .\.venv\Scripts\python.exe -m uvicorn nisar_pipeline.api_server:app --app-dir src --host 127.0.0.1 --port 8000
   ```
2. Open `http://127.0.0.1:8000` in Chrome/Edge at full screen (`F11`).
3. Ensure **Step 1 (`The Oasis & The Desert Noise Floor`)** is selected in the right-hand `Story Mode (6)` panel.

---

## Timed Walkthrough (`0:00 – 3:00`)

### `0:00 – 0:30` | The Hook & The Desert Noise Reference (Chapter 1)
- **On Screen:** Dual-Pol False-Color RGB Composite (`2026-08-10`) over Fayoum Oasis, Lake Qarun, and the Western Desert.
- **What to Do:** Point to the sharp boundary between the emerald-green irrigated oasis (`HV = -15.32 dB`) and the dark purple hyper-arid Western Desert (`HV = -24.16 dB`).
- **What to Say:**
  > *"Welcome to **Earth Rhythm**. You are looking at 10 real 12-day repeat acquisitions from the **NASA-ISRO SAR (NISAR)** L-band radar (`24 cm` wavelength, `Track 129 / Frame 016`, `PROVISIONAL CRID P05023`) over Egypt's Fayoum Oasis between June and October 2026. Before claiming any surface change is real, we filtered all 10 dates strictly in linear power (`ENL` verified from `4.9` to `>150` looks) and measured `218,705` stable desert pixels (`350 km²`) across `1.97 million` 12-day pairs to lock in our statistical change thresholds: **`2.73 dB` in `HH`** and **`2.03 dB` in `HV`**."*

---

### `0:30 – 1:10` | Summer Canopy Growth & Split-Screen Swipe (Chapter 2)
- **What to Do:**
  1. Click **Step 2 (`Summer Canopy Growth: Jun 23 → Aug 10`)** in the Story Mode bar.
  2. Drag the **vertical split-screen swipe handle** left and right across the central Fayoum cropland (`ROI_01`).
  3. Toggle **`+ Sentinel-2 NDVI (Rule 2)`** on the SVG time-series chart.
- **What to Say:**
  > *"Swiping between June 23 and August 10 in `HV` cross-polarization reveals **`763.88 km²` (`39.5%` of the oasis)** surging by more than `+2.03 dB` as summer maize, sorghum, and cotton canopies thicken (`+4.04 dB` at `ROI_01`). Why `HV`? Because `24 cm` L-band waves penetrate the upper leaves and depolarize through volume scattering inside stems and branches. Overlaying independent **Copernicus Sentinel-2 NDVI** (explicitly badged as optical context) confirms a **`0.93` Pearson correlation** during the summer growth phase — while **`NASA POWER`** records **`0.00 mm` of rain** on all 10 passes, proving 100% of this water comes from the **Bahr Youssef** Nile canal."*

---

### `1:10 – 2:00` | The Core Discovery: When `HH` and `HV` Disagree (Chapters 3 & 4)
- **What to Do:**
  1. Click **Step 3 (`Late-Summer Harvest vs. Autumn Planting`)** to show the **7-Class Dual-Pol Change & Disagreement Map** (`594.8 km²` harvested in orange vs. `174.2 km²` autumn planting in green).
  2. Immediately click **Step 4 (`When HH and HV Disagree: Harvest + Flood Irrigation`)** (`ROI_03`).
- **What to Say:**
  > *"Here is why dual-polarization NISAR is transformative. Between August and October, farmers harvest `595 km²` of summer crops while planting `174 km²` of autumn crops. Look at the magenta pixels at `ROI_03`: if you only had single-polarization `HH`, you would see a **`+4.98 dB` backscatter increase** and falsely conclude vegetation grew. In reality, **`HV` plummeted by `-4.67 dB`** (`-9.64 dB` in the `HV/HH` ratio)! Farmers harvested the crop — removing the canopy volume (`-HV`) — and immediately flood-irrigated the bare furrows for the autumn season, spiking soil dielectric constant (`+HH`). Across the basin, **`440.7 km²`** exhibits single-channel or opposite-sign polarization disagreement."*

---

### `2:00 – 2:35` | Specular Water vs. Wind Waves & Live Pixel Inspection (Chapter 5 + Inspector)
- **What to Do:**
  1. Click **Step 5 (`Lake Qarun: Specular Water vs. Wind-Wave Bragg Scattering`)** and point to the `ROI_05` chart (`HH` swings `11.17 dB` while `HV` stays flat at `-24.9 dB`).
  2. Click any agricultural parcel on the map and switch to the **`Pixel Inspector`** tab (`~26 ms` live query).
- **What to Say:**
  > *"Over Lake Qarun (`Step 5`), `HV` stays pinned near the `-25 dB` thermal noise floor (`1.22 dB` range), whereas `HH` swings by **`11.17 dB`** due to Bragg capillary waves on windy mornings (`4.95 m/s` on Oct 09). And clicking any coordinate on the map queries our calibrated 10-date linear-power cube in **26 milliseconds**, returning the exact 10-date `HH`/`HV` trajectory, `[P25, P75]` interquartile ribbon, and physical regime."*

---

### `2:35 – 3:00` | Exploratory `L2_GUNW` InSAR, Rule 3 Provenance & Honest Limits (Chapter 6 + Metadata)
- **What to Do:**
  1. Click **Step 6 (`Exploratory InSAR: L2_GUNW Coherence & Limits`)** to show the coherence-masked ($\gamma \ge 0.50$) `L2_GUNW` phase screen.
  2. Click the **`Rule 3 Metadata & Download`** tab to show the 11 mandatory provenance fields and the **Download Cloud-Optimized GeoTIFF (`.tif`)** button.
- **What to Say:**
  > *"Finally, in `Step 6`, we evaluated NISAR `L2_GUNW` unwrapped interferograms, strictly masking coherence below `0.50`. While desert (`0.81`) and urban (`0.73`) targets stay coherent, we explicitly show that a single 12-day pair contains a `2.5 cm` regional tropospheric phase ramp — so we refuse to overclaim subsidence without a multi-pair stack. Every single layer exposes all **11 Rule 3 & Rule 5 provenance fields** and is downloadable as a verified Cloud-Optimized GeoTIFF. Thank you!"*

