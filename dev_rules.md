# Development Rules & Scientific Guardrails (`dev_rules.md`)

This document codifies the mandatory scientific, architectural, and engineering constraints from `Project.md` and global engineering protocols.

## 1. Scientific & Data Integrity Hard Rules
1. **No Fabricated Data:** Never fabricate, mock, or simulate satellite data or scientific metrics in the pipeline or UI. Synthetic arrays are permitted **only** inside unit tests (`tests/`) and must be explicitly labelled `"synthetic"`. If an external API or archive is unreachable or lacks coverage, report the failure/gap explicitly and stop that feature.
2. **Source Attribution:** NISAR is the primary data source. All auxiliary datasets (Sentinel-1, Sentinel-2 NDVI, DEM, land cover, rainfall) are context only and must be explicitly labelled with their true source.
3. **Mandatory Layer Metadata (Rule 3):** Every layer rendered or exported must expose:
   - `satellite`
   - `product_type` (e.g., `L2_GCOV`, `L2_GUNW`)
   - `product_version` / release maturity (e.g., `BETA` / pre-calibration vs `PROVISIONAL` / `VALIDATED`, plus CRID/version ID)
   - `acquisition_date` (UTC ISO-8601)
   - `track_frame` (`relative_orbit` / `track` and `frame`)
   - `orbit_direction` (`Ascending` / `Descending`)
   - `polarization` (`HH`, `HV`, etc.)
   - `units` (`linear power m^2/m^2`, `dB`, `meters LOS`, `unitless`)
   - `crs` (e.g., `EPSG:4326`, `EPSG:32636`)
   - `source` (archive URL / DAAC / granule ID)
4. **Radiometric vs. Interferometric Strictness:**
   - Perform all spatial averaging, multilooking, and filtering in **linear power**, converting to decibels ($10 \log_{10}(\sigma^0 \text{ or } \gamma^0)$) strictly for display and log-ratio calculation.
   - Never refer to backscatter ($\gamma^0 / \sigma^0$) changes as "ground displacement" or "subsidence". Displacement requires `GUNW` unwrapped phase with a coherence mask and an explicit reference point.
5. **Epistemic Labelling (Rule 5):** Every finding, chart, or story step must be tagged as exactly one of:
   - `OBSERVATION`
   - `CHANGE DETECTION`
   - `INTERPRETATION (hypothesis)`
   No forecasts and no arbitrary risk scores.
6. **Version & Geometry Consistency Guards (Rules 7 & 8):**
   - Never combine different product maturity versions (`BETA` vs `PROVISIONAL`, or differing software versions) into a single quantitative time series or change map.
   - Compare only acquisitions sharing identical **track, frame, orbit direction, and polarization**. Enforce this programmatically via a validation guard function that raises an error on mismatch.

## 2. Engineering & Security Rules
1. **Secrets Hygiene:** Never print, log, or commit credentials. Read `EARTHDATA_USERNAME` and `EARTHDATA_PASSWORD` exclusively via `.env` (gitignored), with `.env.example` committed as a template.
2. **Download Volume Gate:** Always report exact granule sizes and total download volume before downloading. Require explicit user confirmation if total download volume exceeds **5 GB**.
3. **Decision Logging:** Log every architectural decision, AOI selection, granule ID, source URL, and threshold derivation in `DECISIONS.md`.
4. **Automated Documentation:** Maintain `code_wiki.md` and regenerate `functions.md` via `scripts/generate_functions_md.py` whenever Python modules are added or updated.
5. **Reproducibility:** Fix and log random seeds (e.g., `SEED = 42`) for any subsampling or empirical noise estimation.

