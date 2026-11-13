# Code Wiki — EARTH RHYTHM: NISAR Surface Change Storyteller

## 1. Meta Information
- **Project Name:** EARTH RHYTHM — NISAR Surface Change Storyteller
- **Challenge:** NASA Space Apps Challenge 2026 ("Dancing with the SARs")
- **Version:** 1.2.0
- **Last Updated:** 2026-11-14T00:05:00+02:00

## 2. Technical Stack
- **Data Discovery & Access:** Python 3, `earthaccess` (NASA CMR API), `asf_search` (Alaska Satellite Facility API), `h5py`
- **Geospatial Processing:** `rasterio`, `numpy`, `scipy`, GDAL/PROJ
- **Backend / Serving:** FastAPI + Uvicorn (`src/nisar_pipeline/api_server.py`) serving static COGs, `EPSG:4326` RGBA overlays, real-time HDF5 pixel inspection, live benchmark metrics (`/api/benchmark`), compiled SPA assets, and Echo AI endpoints (`/api/echo/chat`, `/api/echo/test`, `/api/echo/models`, `/api/echo/providers`)
- **Echo AI Helper Engine:** Multi-provider LLM integration (`echo_assistant.py`) supporting Google Gemini (AI Studio), Groq Cloud, OpenRouter, OpenAI, Anthropic Claude, DeepSeek, Mistral, and Local Ollama with live UI context grounding, dynamic model discovery, and automatic on-the-go fallback cascades
- **Frontend:** React 18, TypeScript, Vite, MapLibre GL JS (`frontend/`)
- **Quality Assurance:** `pytest` (10 invariants), `manual_tests.csv`

## 3. Codebase Blueprint
```text
Earth Rhythm AI/
├── .env.example                 # Template for NASA Earthdata credentials & Echo AI provider keys
├── .gitignore                   # Git ignore rules protecting .env, built dist/, and binary rasters
├── README.md                    # Complete project documentation, benchmark metrics & quickstart
├── DEMO_SCRIPT.md               # Timed 3-minute Space Apps judging presentation script
├── Project.md                   # Core challenge specification and hard rules
├── project_plan.md              # High-level project scope and phased plan
├── dev_rules.md                 # Scientific and software engineering guardrails
├── code_wiki.md                 # Architecture overview and roadmap
├── functions.md                 # Auto-generated function/class reference
├── DECISIONS.md                 # Audit log of data availability, granule IDs, and decisions
├── manual_tests.csv             # Functional QA test cases (T001-T018)
├── src/
│   └── nisar_pipeline/          # Reusable scientific SAR processing package
│       ├── __init__.py
│       ├── guards.py            # Rule 3, 7, 8 version/geometry/metadata guards
│       ├── radiometry.py        # Linear-power Lee/boxcar filtering, ENL, dB conversions
│       ├── masks.py             # Multi-temporal geophysical & NESZ/water/desert masks
│       ├── insar.py             # Exploratory GUNW LOS displacement & gamma >= 0.50 masking
│       ├── change_detection.py  # Statistical threshold derivation & 7-class dual-pol change regimes
│       ├── tiles_and_cogs.py    # Pure-SAR v3 water/island classifier, 45 COGs & 59 RGBA overlays
│       ├── api_server.py        # FastAPI backend, pixel inspector, benchmark & Echo endpoints
│       └── echo_assistant.py    # Echo AI Helper multi-provider client, model discovery & fallbacks
├── frontend/                    # React + TypeScript + Vite + MapLibre GL JS application
│   ├── index.html               # Observatory entry HTML with Echo branding & favicon
│   ├── public/                  # Static assets: echo-avatar.png, echo-icon-192.png, favicon.png, echo-full.jpg
│   ├── package.json             # Frontend dependencies and build scripts
│   ├── tsconfig.json            # Strict TypeScript configuration
│   ├── vite.config.ts           # Vite bundler + /api, /tiles, /cogs dev proxy
│   └── src/
│       ├── types.ts             # TypeScript interfaces for Rule 3/5 catalog, Story Mode & Inspector
│       ├── storySteps.ts        # 6-chapter guided narrative with camera flyTo & radar physics
│       ├── components/
│       │   ├── NisarMap.tsx     # Dual-synchronized MapLibre GL JS canvas + swipe curtain + legends
│       │   ├── TimeSeriesChart.tsx # Interactive SVG multi-temporal HH/HV/IQR/NESZ + Sentinel-2 NDVI chart
│       │   ├── BenchmarkCard.tsx   # Live /api/benchmark comparison table inside Methods & Limits
│       │   └── EchoHelper.tsx   # Echo AI Helper floating companion, grounded chat stream & provider settings
│       ├── App.tsx              # Main observatory shell, time slider, workbench & Echo integration
│       ├── styles.css           # Dark scientific glassmorphism UI stylesheet
│       └── main.tsx             # React DOM root mount
├── scripts/
│   ├── generate_functions_md.py               # AST parser that generates functions.md
│   ├── phase0_audit.py                        # Phase 0 environment & NISAR CMR/ASF archive audit
│   ├── phase1_extract_subsets.py              # Phase 1 HTTP windowed range-read extraction for GCOV & GUNW
│   ├── phase2_process_layers.py               # Phase 2 radiometric filtering, ENL verification, and masking
│   ├── phase3_change_analysis.py              # Phase 3 change detection, thresholds, time series & external context
│   ├── phase4_build_cogs_and_tiles.py         # Phase 4 COG conversion, decoupled RGB & catalog builder
│   ├── fetch_gunw_coherence_and_benchmarks.py # Option 1 (9 GUNW coherences) + Option 2 NASA benchmark download
│   └── benchmark_sar_water_accuracy.py        # Quantitative v1-v4 benchmark vs OPERA DSWx, NISAR_WM & DEM
└── tests/
    └── test_nisar_invariants.py               # Automated pytest suite verifying all 10 scientific invariants
```

## 4. Roadmap
### Completed
- [x] Project initialization (`project_plan.md`, `dev_rules.md`, `code_wiki.md`, `scripts/generate_functions_md.py`, `.gitignore`, `.env.example`, `manual_tests.csv`).
- [x] **Phase 0:** Environment & NISAR availability audit across Nile Delta, Fayoum Oasis, and Toshka Lakes / Lake Nasser / East Owainat.
- [x] **Phase 1:** Real NISAR data windowed HTTP range-read extraction (10 `L2_GCOV` dates + 2 exploratory `L2_GUNW` subsets over Fayoum Oasis) and metadata manifest (`data/subsets/phase1_manifest.json`).
- [x] **Phase 2:** HDF5 extraction, `EPSG:32636` alignment, mask generation, linear-power speckle filtering & multi-stage ENL verification.
- [x] **Phase 3:** Change detection (`dB` log-ratio), desert statistical thresholds (`tau_HH=2.73 dB`, `tau_HV=2.03 dB`), 7-class dual-pol regimes, 10-date ROI trajectories, and `NASA POWER` + `Sentinel-2 L2A` optical NDVI cross-checks.
- [x] **Phase 4:** `45` Cloud-Optimized GeoTIFFs (`data/cogs/`), `59` `EPSG:4326` RGBA overlays (`data/web_tiles/`), master Rule 3/5 catalog (`data/web_tiles/layer_catalog.json`), and FastAPI backend + Pixel Inspector.
- [x] **Phase 5:** React + TypeScript + Vite + MapLibre interactive application and 6-step Story Mode (`frontend/`).
- [x] **Phase 6:** Automated unit test suite (`tests/test_nisar_invariants.py`), `README.md`, and 3-minute judging script (`DEMO_SCRIPT.md`).
- [x] **Phase 7 (Echo AI Helper):** Multi-provider AI guide (`Echo`), active API connection test (`/api/echo/test`), dynamic model discovery (`/api/echo/models`), and on-the-go Gemini fallback cascades.
- [x] **Phase 8 (Decoupled RGB, Pure-SAR 9-GUNW Island Fix & NASA Benchmarks):**
  - Replaced legacy purple-tinted `HH/HV/HH-HV` RGB mapping with decoupled physical channels (Lush Green = HV canopy, Vivid Red = HH double-bounce, Deep Blue -> Cyan = specular water -> wind-wave ripples, Warm Sand = bare soil/limestone).
  - Extracted all 9 consecutive `T129_F016` `L2_GUNW` coherences (`data/processed/gunw_coherence/`) and built `compute_pure_sar_water_mask` (`v3_coh_island`) eliminating blind hole-filling error on El-Qarn Island (`100.00% -> 0.80%` false water).
  - Fetched Rule-2 separated NASA `OPERA_L3_DSWX-HLS_V1`, `NISAR_WATERMASK`, and `NISAR_DEM` benchmarks (`data/benchmarks/`) and verified `v3` IoU = `0.9243` (`99.19%` precision) via `sar_water_benchmark_report.json`, `/api/benchmark`, `BenchmarkCard.tsx`, and Invariant 10 (`10/10` tests passing).

### In-Progress
- None (`v1.2.0` complete).

### Backlog
- Multi-interferogram `L2_GUNW` SBAS velocity stacking once >= 20–30 passes accumulate over Fayoum Oasis.
