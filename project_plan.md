# Project Plan: EARTH RHYTHM — NISAR Surface Change Storyteller

**Challenge:** NASA Space Apps 2026 — "Dancing with the SARs"  
**Version:** 0.1.0 (Phase 0 Initialization)  
**Date:** 2026-11-13

---

## 1. Ultimate Goal & Scope
Use real NISAR L-band SAR data to track, quantify, and visualize 1–2 types of surface change in a single well-covered study area (evaluating Nile Delta, Fayoum Oasis, and Lake Nasser / Toshka Lakes / East Owainat in Phase 0, or proposing a global fallback if Egyptian coverage is insufficient), communicating a clear physical story for scientists, resource managers, educators, and the public.

### In Scope
- **Change Type A (Primary):** NISAR L2 GCOV backscatter time series (HH vs HV comparison) over agricultural, water, or flooded/irrigated surfaces.
- **Change Type B (Exploratory Only):** Line-of-sight (LOS) surface displacement from NISAR L2 GUNW with strict coherence masking and reference point disclosure, included **only** if sufficient interferometric pairs exist and the signal is separable from atmospheric/ionospheric noise.
- **External Context Layers (Explicitly Labelled):** Optical basemap, Sentinel-2 NDVI, land cover, DEM, and rainfall/irrigation context.
- **Interactive Web Application:** React + TypeScript + Vite + MapLibre GL JS frontend displaying precomputed Cloud-Optimized GeoTIFFs (COGs)/tiles and JSON time series, with before/after swipe, date slider, pixel/polygon time-series inspector, 4–6 step Story Mode, full Rule-3 Layer Metadata Panel, Method & Limits Panel, and Future NISAR Applications section.

### Out of Scope
- Synthetic or fabricated satellite data in the application (synthetic data allowed strictly in unit tests and labelled `synthetic`).
- Machine learning forecasting, SHAP, deep-learning atmospheric correction, or arbitrary multi-hazard risk scores.
- Mixing product versions (e.g., BETA/pre-calibration vs PROVISIONAL) or differing viewing geometries (track, frame, orbit direction) within a single quantitative time series or change map.

---

## 2. High-Level Architecture

```
[NASA Earthdata / ASF DAAC]
         │ (earthaccess / asf_search, ranged HDF5 or granule download)
         ▼
[Phase 1–3: Scientific Python Pipeline]
  ├── HDF5 Inspector & Metadata Validator (h5py, Rule 3/7/8 guards)
  ├── Radiometric & Geometric Processor (rasterio, CRS alignment, masks)
  ├── Speckle Filter & ENL Estimator (multilooking, linear-power math)
  └── Change Detection & Noise Thresholding (dB log-ratio, statistical threshold)
         │
         ▼
[Phase 4: Precomputed Assets & Thin API / Static Server]
  ├── Precomputed COGs / XYZ Tiles & JSON Time Series
  └── FastAPI Backend (or static asset server)
         │
         ▼
[Phase 5: React + TypeScript + Vite + MapLibre Frontend]
  ├── Interactive Swipe & Time-Slider Map
  ├── Pixel / Polygon Time-Series Inspector (dB, N dates)
  ├── 4–6 Step Physical Story Mode (HH vs HV, confounders)
  └── Layer Metadata (Rule 3) & Method/Limits Panels (Rule 5)
```

---

## 3. Phased Execution Plan (with Confirmation Gates)
- **Phase 0:** Environment audit, NISAR data availability audit (`earthaccess` / `asf_search`) across Nile Delta, Fayoum Oasis, and Toshka Lakes / Lake Nasser / East Owainat, comparison table, `DECISIONS.md` logging, and AOI recommendation. *(Stop and wait for user confirmation)*
- **Phase 1:** Real data download (with size check and user approval if > 5 GB) + granule metadata and checksum logging. *(Stop and wait for user confirmation)*
- **Phase 2:** Processing + validated georeferenced layers (CRS, units, masks, ENL documented). *(Stop and wait for user confirmation)*
- **Phase 3:** Change detection + time series + stats + noise/threshold derivation. *(Stop and wait for user confirmation)*
- **Phase 4:** COG/tile generation + FastAPI/static serving. *(Stop and wait for user confirmation)*
- **Phase 5:** Frontend map + story mode + metadata & limits panels. *(Stop and wait for user confirmation)*
- **Phase 6:** Automated unit tests (`pytest` + `manual_tests.csv`), README, and 3-minute demo script.

