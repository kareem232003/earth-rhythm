# Code Wiki — EARTH RHYTHM: NISAR Surface Change Storyteller

## 1. Meta Information
- **Project Name:** EARTH RHYTHM — NISAR Surface Change Storyteller
- **Challenge:** NASA Space Apps 2026 ("Dancing with the SARs")
- **Version:** 1.0.0
- **Last Updated:** 2026-11-13T17:44:30+02:00

## 2. Technical Stack
- **Data Discovery & Access:** Python 3, `earthaccess` (NASA CMR API), `asf_search` (Alaska Satellite Facility API), `h5py`
- **Geospatial Processing:** `rasterio`, `numpy`, `scipy`, GDAL/PROJ
- **Backend / Serving:** FastAPI + Uvicorn (`src/nisar_pipeline/api_server.py`) serving static COGs, `EPSG:4326` RGBA overlays, real-time HDF5 pixel inspection, and compiled SPA assets
- **Frontend:** React 18, TypeScript, Vite, MapLibre GL JS (`frontend/`)
- **Quality Assurance:** `pytest`, `manual_tests.csv`

## 3. Codebase Blueprint
```
Earth Rhythm AI/
├── .env.example                 # Template for NASA Earthdata credentials
├── .gitignore                   # Git ignore rules protecting .env and raw data
├── README.md                    # Complete project documentation, findings & quickstart
├── DEMO_SCRIPT.md               # Timed 3-minute Space Apps judging presentation script
├── Project.md                   # Core challenge specification and hard rules
├── project_plan.md              # High-level project scope and phased plan
├── dev_rules.md                 # Scientific and software engineering guardrails
├── code_wiki.md                 # Architecture overview and roadmap
├── functions.md                 # Auto-generated function/class reference
├── DECISIONS.md                 # Audit log of data availability, granule IDs, and decisions
├── manual_tests.csv             # Functional QA test cases
├── src/
│   └── nisar_pipeline/          # Reusable scientific SAR processing package
│       ├── __init__.py
│       ├── guards.py            # Rule 3, 7, 8 version/geometry/metadata guards
│       ├── radiometry.py        # Linear-power Lee/boxcar filtering, ENL, dB conversions
│       ├── masks.py             # Multi-temporal geophysical & NESZ/water/desert masks
│       ├── insar.py             # Exploratory GUNW LOS displacement & gamma >= 0.50 masking
│       ├── change_detection.py  # Statistical threshold derivation & 7-class dual-pol change regimes
│       ├── tiles_and_cogs.py    # Cloud-Optimized GeoTIFF (COG) & EPSG:4326 RGBA overlay renderer
│       └── api_server.py        # FastAPI backend & real-time on-the-fly pixel/patch inspector
├── frontend/                    # React + TypeScript + Vite + MapLibre GL JS application
│   ├── index.html               # Observatory entry HTML
│   ├── package.json             # Frontend dependencies and build scripts
│   ├── tsconfig.json            # Strict TypeScript configuration
│   ├── vite.config.ts           # Vite bundler + /api, /tiles, /cogs dev proxy
│   └── src/
│       ├── types.ts             # TypeScript interfaces for Rule 3/5 catalog, Story Mode & Inspector
│       ├── storySteps.ts        # 6-chapter guided narrative with camera flyTo & radar physics
│       ├── components/
│       │   ├── NisarMap.tsx     # Dual-synchronized MapLibre GL JS canvas + swipe curtain + legends
│       │   └── TimeSeriesChart.tsx # Interactive SVG multi-temporal HH/HV/IQR/NESZ + Sentinel-2 NDVI chart
│       ├── App.tsx              # Main observatory shell, time slider, and 4-tab scientific workbench
│       ├── styles.css           # Dark scientific glassmorphism UI stylesheet
│       └── main.tsx             # React DOM root mount
└── scripts/
    ├── generate_functions_md.py # AST parser that generates functions.md
    ├── phase0_audit.py          # Phase 0 environment & NISAR CMR/ASF archive audit
    ├── phase1_extract_subsets.py # Phase 1 HTTP windowed range-read extraction for GCOV & GUNW
    ├── phase2_process_layers.py # Phase 2 radiometric filtering, ENL verification, and masking
    ├── phase3_change_analysis.py # Phase 3 change detection, thresholds, time series & external context
    └── phase4_build_cogs_and_tiles.py # Phase 4 COG conversion, EPSG:4326 PNG overlays & layer catalog
└── tests/
    └── test_nisar_invariants.py # Phase 6 automated pytest suite verifying all 8 scientific invariants
```

## 4. Roadmap
### Completed
- [x] Project initialization (`project_plan.md`, `dev_rules.md`, `code_wiki.md`, `scripts/generate_functions_md.py`, `.gitignore`, `.env.example`, `manual_tests.csv`).
- [x] **Phase 0:** Environment & NISAR availability audit across Nile Delta, Fayoum Oasis, and Toshka Lakes / Lake Nasser / East Owainat (`scripts/phase0_audit.py`, `data/phase0_audit_results.json`, `DECISIONS.md`).
- [x] **Phase 1:** Real NISAR data windowed HTTP range-read extraction (10 `L2_GCOV` dates + 2 `L2_GUNW` pairs over Fayoum Oasis, `455.11 MB` total < 500 MB gate) and metadata manifest (`scripts/phase1_extract_subsets.py`, `data/subsets/phase1_manifest.json`, `DECISIONS.md`).
- [x] **Phase 2:** HDF5 extraction, radiometric/geometric alignment (`EPSG:32636`), mask generation (`data/processed/masks/*.tif`), linear-power speckle filtering & multi-stage ENL verification (`data/processed/phase2_processing_report.json`, `DECISIONS.md`).
- [x] **Phase 3:** Change detection (`dB` log-ratio), statistical noise threshold justification (`tau_HH=2.73 dB`, `tau_HV=2.03 dB`), 7-class dual-pol regime & disagreement mapping (`data/processed/change_maps/*.tif`), 10-date time-series extraction (5 strata + 6 focal ROIs), and external non-NISAR context (`NASA POWER` meteorology + `Sentinel-2 L2A` optical NDVI) (`data/processed/phase3_change_and_timeseries_report.json`, `DECISIONS.md`).
- [x] **Phase 4:** Cloud-Optimized GeoTIFF (`COG`) generation (`45` COGs in `data/cogs/`), web-ready `EPSG:4326` RGBA PNG overlays (`59` overlays in `data/web_tiles/overlays/`), master layer catalog (`data/web_tiles/layer_catalog.json`), and FastAPI backend + real-time Pixel/Patch Inspector (`src/nisar_pipeline/api_server.py`, `data/processed/phase4_cog_and_tile_report.json`, `DECISIONS.md`).
- [x] **Phase 5:** React + TypeScript + Vite + MapLibre interactive application and 6-step Story Mode (`frontend/`, `DECISIONS.md`).
- [x] **Phase 6:** Automated unit test suite (`tests/test_nisar_invariants.py` — 8/8 passing) + `README.md` + 3-minute judging demo script (`DEMO_SCRIPT.md`).

### In-Progress
- None — All 6 phases complete (`v1.0.0`).

### Backlog
- Optional future extensions: multi-interferogram `L2_GUNW` SBAS time-series inversion once $\ge 20$ consecutive 12-day passes accumulate over Fayoum Oasis.

