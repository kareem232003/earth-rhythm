# EARTH RHYTHM — NISAR Surface Change Storyteller

**NASA Space Apps Challenge 2026 — *"Dancing with the SARs"***

An end-to-end L-band Synthetic Aperture Radar (SAR) scientific pipeline and interactive web observatory built on **10 real NASA-ISRO SAR (`NISAR`) `L2_GCOV` dual-polarization (`HH` + `HV`) acquisitions** and **2 `L2_GUNW` interferometric pairs** (`2026-06-23` through `2026-10-21`, Relative Orbit Track `129` / Frame `016`, Ascending, `PROVISIONAL CRID P05023`) over the **Fayoum Oasis, Lake Qarun, Wadi El Rayan, and Western Desert, Egypt**.

---

## 1. Scientific Question & Core Discovery

> **How does dual-polarization L-band radar ($\lambda \approx 24\text{ cm}$, `1.239 GHz`) separate crop canopy volume dynamics (`HV`) from bare-soil moisture, flood irrigation, and wind-driven water wave roughness (`HH`) across an arid Nile-fed agricultural basin — and where would single-polarization SAR misclassify the landscape?**

### Key Quantitative Findings (`N = 10` Dates, `4,912.69 km²` Valid AOI)
| Phenomenon / Discovery | Quantitative Metric (Computed from Calibrated `EPSG:32636` Stack) | Physical Mechanism & Epistemic Tag |
| :--- | :--- | :--- |
| **Empirical Change Thresholds (`Rule 4`)** | **$\tau_{\text{HH}} = 2.73\text{ dB}$**, **$\tau_{\text{HV}} = 2.03\text{ dB}$** (`N = 218,705` stable desert pixels = `349.93 km²`; `1,968,345` 12-day pairs) | Exceeds both theoretical Stage-2 speckle ($3\sigma_{\text{speckle}} = 1.49\text{ dB HH} / 0.87\text{ dB HV}$) and empirical desert $3\sigma_{\text{MAD}}$ (`CHANGE DETECTION`) |
| **Summer Crop Canopy Growth (`Jun 23 → Aug 10`)** | **`763.88 km²`** (`39.49%` of oasis cropland) exhibits $+\Delta\text{HV} \ge +2.03\text{ dB}$ (`+4.04 dB` at `ROI_01`; paired `Sentinel-2 NDVI` $r = 0.93, p = 0.0009$) | L-band cross-pol (`HV`) depolarizes inside thickening maize, sorghum, cotton, and rice stems (`INTERPRETATION`) |
| **Late-Summer Harvest vs. Autumn Emergence (`Aug 10 → Oct 21`)** | **`594.83 km²`** (`30.75%` of cropland) harvested ($-\Delta\text{HV} \le -2.03\text{ dB}$) vs. **`174.17 km²`** (`9.00%`) newly planted autumn crops (`+10.77 dB HV` surge at `ROI_02`) | Bimodal crop calendar transition between summer harvest and autumn wheat/clover/vegetable planting (`CHANGE DETECTION`) |
| **When `HH` and `HV` Disagree (`ROI_03`)** | **`1.71 km²`** (`1,068 px`) Opposite-Sign Type I ($+\text{HH} \ge +2.73\text{ dB}$ AND $-\text{HV} \le -2.03\text{ dB}$) + **`439.03 km²`** Single-Channel Disagreement (`ROI_03`: $\Delta\text{HV} = -4.67\text{ dB}$ while $\Delta\text{HH} = +4.98\text{ dB}$) | Harvest removes canopy (`-HV`) while post-harvest flood irrigation on bare ridges spikes soil dielectric & surface scatter (`+HH`) (`INTERPRETATION`) |
| **Lake Qarun Specular Water vs. Wind Waves (`ROI_05`)** | `HV` pinned at **`-24.89 dB`** (`1.22 dB` range near `NESZ`), while `HH` swings by **`11.17 dB`** (`-23.16 dB` on Sep 27 at `3.05 m/s` wind vs. `-11.99 dB` on Oct 09 at `4.95 m/s` wind) | First-order Bragg resonant scattering from capillary waves strongly excites co-pol `HH` without depolarizing `HV` (`OBSERVATION` + `INTERPRETATION`) |
| **External Rainfall Independence (`Rule 2`)** | **`0.15 mm`** total cumulative rainfall across 133 days (`2026-06-15` to `2026-10-25`, `NASA POWER`; `0.00 mm` on all 10 NISAR overpasses) | Confirms 100% of observed soil moisture and inundation changes originate from **Bahr Youssef** Nile canal irrigation (`OBSERVATION`) |
| **Exploratory `L2_GUNW` Coherence & Limits (`Rule 6`)** | **`66.85%`** of basin passes $\gamma \ge 0.50$ (`Desert = 0.810`, `Urban = 0.728`, `Crops = 0.495`); `24.1–29.5 mm` apparent LOS std across single 12-day pairs | Single-pair L-band unwrapped phase is dominated by regional tropospheric water-vapor ramps (`2–3 cm`), requiring a multi-pair InSAR stack (`INTERPRETATION`) |

---

## 2. Quick Start (Run in Under 60 Seconds)

### Prerequisites
- Python `3.11+` with virtual environment `.venv` (`fastapi`, `uvicorn`, `h5py`, `rasterio`, `numpy`, `scipy`, `requests`, `pytest`)
- Node.js `20+` and `npm` (only required if rebuilding `frontend/dist`; production assets are already compiled in `frontend/dist/`)

### 1. Launch the Full-Stack Observatory (`http://127.0.0.1:8000`)
```powershell
.\.venv\Scripts\python.exe -m uvicorn nisar_pipeline.api_server:app --app-dir src --host 127.0.0.1 --port 8000
```
Open **[http://127.0.0.1:8000](http://127.0.0.1:8000)** in your browser. The FastAPI server serves:
- **`GET /`** — Compiled React + TypeScript + MapLibre GL JS Observatory (`frontend/dist/`)
- **`GET /api/health`** — Server readiness, loaded `10 × 1560 × 1968` calibrated linear-power cube, and catalog counts (`45` COGs, `59` overlays)
- **`GET /api/catalog`** — Master **Rule 3 & Rule 5** layer catalog (`data/web_tiles/layer_catalog.json`)
- **`GET /api/story`** — Complete Phase 2 + Phase 3 + Phase 4 scientific report payload
- **`GET /api/inspect?lon=30.9806&lat=29.3201&window_px=5`** — Real-time on-the-fly 10-date pixel/patch inspector (`~26 ms`)
- **`GET /tiles/overlays/...`** — `59` reprojected `EPSG:4326` RGBA PNG map overlays
- **`GET /cogs/...`** — `45` downloadable Cloud-Optimized GeoTIFFs (`EPSG:32636`, `256×256` tiled, `[2, 4, 8]` overviews)

### 2. Run the Automated Scientific Invariant Test Suite (`pytest`)
```powershell
.\.venv\Scripts\python.exe -m pytest -v tests/test_nisar_invariants.py
```

---

## 3. Real NISAR Datasets Used (`10 L2_GCOV` + `2 L2_GUNW` Granules)

All granules were accessed via authenticated NASA Earthdata / ASF DAAC HTTPS windowed range-reading (`scripts/phase1_extract_subsets.py`), keeping local subset storage to **`455.11 MB`** (vs. `657.6 GB` full granules). Every granule shares identical **Track `129`**, **Frame `016`**, **Ascending** pass direction, **`PROVISIONAL CRID P05023` (`PGE R05.02.3`, Version `1.0.11`)**, and **`EPSG:32636` (`WGS 84 / UTM Zone 36N`)** projection:

| # | Acquisition Date (UTC) | Product Type | Official NASA / ASF Granule ID | Pol / Mode | Local Subset (`40m` Grid) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | `2026-06-23T03:15:46Z` | `L2_GCOV` | `NISAR_L2_PR_GCOV_013_129_A_016_4005_DHDH_A_20260623T031546_20260623T031621_P05023_N_F_J_001` | `HH + HV` (`4005`) | `1560 × 1968` (`24.83 MB`) |
| 2 | `2026-07-05T03:15:46Z` | `L2_GCOV` | `NISAR_L2_PR_GCOV_014_129_A_016_4005_DHDH_A_20260705T031546_20260705T031621_P05023_N_F_J_001` | `HH + HV` (`4005`) | `1560 × 1968` (`24.84 MB`) |
| 3 | `2026-07-17T03:15:47Z` | `L2_GCOV` | `NISAR_L2_PR_GCOV_015_129_A_016_4005_DHDH_A_20260717T031547_20260717T031621_P05023_N_F_J_001` | `HH + HV` (`4005`) | `1560 × 1968` (`24.85 MB`) |
| 4 | `2026-08-10T03:15:47Z` | `L2_GCOV` | `NISAR_L2_PR_GCOV_017_129_A_016_4005_DHDH_A_20260810T031547_20260810T031622_P05023_N_F_J_001` | `HH + HV` (`4005`) | `1560 × 1968` (`24.85 MB`) |
| 5 | `2026-08-22T03:15:47Z` | `L2_GCOV` | `NISAR_L2_PR_GCOV_018_129_A_016_4005_DHDH_A_20260822T031547_20260822T031622_P05023_N_F_J_001` | `HH + HV` (`4005`) | `1560 × 1968` (`24.85 MB`) |
| 6 | `2026-09-03T03:15:48Z` | `L2_GCOV` | `NISAR_L2_PR_GCOV_019_129_A_016_4005_DHDH_A_20260903T031548_20260903T031623_P05023_N_F_J_001` | `HH + HV` (`4005`) | `1560 × 1968` (`24.85 MB`) |
| 7 | `2026-09-15T03:15:48Z` | `L2_GCOV` | `NISAR_L2_PR_GCOV_020_129_A_016_4005_DHDH_A_20260915T031548_20260915T031623_P05023_N_F_J_001` | `HH + HV` (`4005`) | `1560 × 1968` (`24.85 MB`) |
| 8 | `2026-09-27T03:15:48Z` | `L2_GCOV` | `NISAR_L2_PR_GCOV_021_129_A_016_4005_DHDH_A_20260927T031548_20260927T031623_P05023_N_F_J_001` | `HH + HV` (`4005`) | `1560 × 1968` (`24.84 MB`) |
| 9 | `2026-10-09T03:15:48Z` | `L2_GCOV` | `NISAR_L2_PR_GCOV_022_129_A_016_4005_DHDH_A_20261009T031548_20261009T031623_P05023_N_F_J_001` | `HH + HV` (`4005`) | `1560 × 1968` (`24.84 MB`) |
| 10 | `2026-10-21T03:15:48Z` | `L2_GCOV` | `NISAR_L2_PR_GCOV_023_129_A_016_4005_DHDH_A_20261021T031548_20261021T031623_P05023_N_F_J_001` | `HH + HV` (`4005`) | `1560 × 1968` (`24.83 MB`) |
| 11 | `2026-07-05 → 2026-07-17` | `L2_GUNW` | `NISAR_L2_PR_GUNW_014_129_A_016_4005_DHDH_A_20260705T031546_20260705T031621_20260717T031547_20260717T031621_P05023_N_F_J_001` | `HH` (`80m` Grid) | `780 × 984` (`6.02 MB`) |
| 12 | `2026-10-09 → 2026-10-21` | `L2_GUNW` | `NISAR_L2_PR_GUNW_022_129_A_016_4005_DHDH_A_20261009T031548_20261009T031623_20261021T031548_20261021T031623_P05023_N_F_J_001` | `HH` (`80m` Grid) | `780 × 984` (`6.26 MB`) |

>Full SHA256 checksums, HDF5 dataset paths, and CRS bounds are logged in [`data/subsets/phase1_manifest.json`](file:///f:/Projects/Python/GitHub/Earth%20Rhythm%20AI/data/subsets/phase1_manifest.json) and [`DECISIONS.md`](file:///f:/Projects/Python/GitHub/Earth%20Rhythm%20AI/DECISIONS.md).

---

## 4. Reproducible Pipeline Architecture (`Phases 0–6`)

```text
Earth Rhythm AI/
├── src/nisar_pipeline/
│   ├── guards.py            # Rules 3, 5, 7, 8 version/geometry/CRS/metadata guards
│   ├── radiometry.py        # Linear-power Lee & boxcar filtering, ENL, dB & log-ratio math
│   ├── masks.py             # Multi-temporal water, desert, cropland, urban & NESZ masks
│   ├── insar.py             # L2_GUNW unwrapped phase -> LOS displacement & gamma >= 0.50 mask
│   ├── change_detection.py  # Threshold derivation (tau_HH=2.73, tau_HV=2.03 dB) & 7-class regimes
│   ├── tiles_and_cogs.py    # Cloud-Optimized GeoTIFF (COG) & EPSG:4326 RGBA PNG renderer
│   └── api_server.py        # FastAPI server + real-time HDF5 pixel/patch inspector
├── scripts/
│   ├── phase0_audit.py              # Phase 0: Environment & NASA CMR / ASF archive audit
│   ├── phase1_extract_subsets.py    # Phase 1: Authenticated HTTP range-read HDF5 subsetting
│   ├── phase2_process_layers.py     # Phase 2: Linear-power Lee filtering, ENL & masks
│   ├── phase3_change_analysis.py    # Phase 3: Log-ratio change maps, ROIs & external context
│   └── phase4_build_cogs_and_tiles.py # Phase 4: 45 COGs + 59 WGS84 overlays + layer_catalog.json
├── frontend/                # Phase 5: React 18 + TypeScript + Vite + MapLibre GL JS SPA
└── tests/
    └── test_nisar_invariants.py     # Phase 6: 8 automated scientific invariant unit tests
```

---

## 5. Honest Final Report: What Works, Limitations & What We Cannot Conclude (`Rule 5 & Rule 6`)

### What Works & Is Tested
- **100% Real Calibrated NISAR Data:** All 10 `L2_GCOV` dates and 2 `L2_GUNW` pairs are real `PROVISIONAL CRID P05023` acquisitions over Fayoum Oasis.
- **Strict Linear-Power Radiometry (`Rule 4`):** All multilooking (`10 m` → `40 m`) and `3×3` Adaptive Lee filtering occur strictly in linear $\gamma^0$ (`m²/m²`), increasing `ENL` from `4.90` (`10 m`) → `41.15–45.14` (`40 m`) → `152.74–481.20` (`40 m` Lee) with `< 0.08%` mean power drift.
- **Full Rule 3 & Rule 5 Provenance:** Every one of the `59` web overlays and `45` downloadable COGs embeds all 11 mandatory metadata and epistemic tags (`OBSERVATION`, `CHANGE DETECTION`, `INTERPRETATION (hypothesis)`), verified by `pytest`.

### Explicit Limitations & What We Cannot Conclude (`Rule 6`)
1. **Backscatter Is Not Ground Subsidence (`Rule 4`):** $\gamma^0$ (`L2_GCOV`) changes measure dielectric and structural scattering changes; they must never be interpreted as vertical land motion.
2. **Single-Pair L-Band `L2_GUNW` Tropospheric Ramp:** Although `66.85%` of the Fayoum basin maintains 12-day L-band coherence $\gamma \ge 0.50$, a single interferogram contains `24.1–29.5 mm` of regional tropospheric water-vapor phase delay between the low-lying Lake Qarun depression (`-43 m` ASL) and the surrounding desert plateau (`+120 m` ASL). **We cannot conclude sub-centimeter ground subsidence from 1–2 `L2_GUNW` pairs**; doing so requires stacking $\ge 15\text{–}20$ consecutive interferograms (SBAS/PS-InSAR).
3. **Crop Species & Volumetric Soil Moisture (`m³/m³`):** Without contemporaneous in-situ field boundaries and gravimetric soil cores, dual-pol SAR separates **canopy volume growth (`+HV`)** from **bare-surface wetting/tillage (`+HH`)**, but cannot uniquely assign individual fields to maize vs. sorghum or convert $\Delta\text{HH}$ into absolute volumetric soil moisture (`m³/m³`).
4. **Low-SNR Sand-Sheet Zones (`11.21%` of AOI):** Smooth quartz sand sheets where backscatter falls within `+3 dB` of the sensor `NESZ` floor (`-23.3 dB HH`, `-24.5 dB HV`) are explicitly flagged and excluded from quantitative change claims.

