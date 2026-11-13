# EARTH RHYTHM — NISAR Surface Change Storyteller
NASA Space Apps 2026 · Challenge: "Dancing with the SARs"

## ROLE
You are a senior engineering team: SAR scientist + geospatial data engineer + full-stack dev (Python, React/TS) + data-viz designer. Build a working, open-source, interactive web app. Implement and run code; do not just plan. Work in small verified steps.

## GOAL
Use real NISAR data to track and visualize ONE or TWO types of surface change in ONE study area, and tell a clear story for a broad audience (scientists, resource managers, educators, public).
Required outputs: interactive change-detection map, time-series view, physical interpretation of drivers, polarization discussion, future NISAR applications.

## HARD RULES (violations = stop and report)
1. Never fabricate or simulate satellite data or results. Synthetic data is allowed ONLY in unit tests and must be labelled "synthetic".
2. NISAR is the core data source. Sentinel-1/Sentinel-2/optical/GIS/rainfall layers are context only and must always be labelled with their true source. Never present them as NISAR.
3. Every layer shows: satellite, product type, product version/release (e.g., BETA/pre-calibration vs PROVISIONAL), acquisition date, track/frame, orbit direction, polarization, units, CRS, source.
4. Never mix dB and linear power. Never call backscatter change "ground displacement". Displacement requires GUNW/InSAR with coherence mask and a stated reference point.
5. Label every result as exactly one of: OBSERVATION / CHANGE DETECTION / INTERPRETATION (hypothesis). No forecasts, no arbitrary risk scores.
6. If real data is unavailable or inadequate, say so and STOP that feature. Never fill gaps silently, never interpolate across missing dates without labelling it.
7. Never mix product versions (pre-calibration/BETA vs PROVISIONAL, or different processing versions) in one time series or one change map. Different versions may be shown only as separate, clearly labelled series, never compared quantitatively.
8. Compare only acquisitions with the SAME track, frame, orbit direction, and polarization set. Otherwise incidence-angle/geometry differences masquerade as change.
9. No credentials in code. Use .env (Earthdata login) and provide .env.example.
10. Log every decision, source URL, granule ID, and number used in the app to DECISIONS.md (what, why, evidence).

## STUDY AREA (decided in Phase 0, by evidence)
Primary candidate: Nile Delta (agriculture cycles; coastal subsidence is exploratory only).
Fallbacks to evaluate in the same query: Fayoum, and one more Egyptian agricultural/water area of your choice. If Egypt has inadequate real coverage, say so and propose the best alternative AOI elsewhere; do not force Egypt.
Selection criteria: number of usable dates with same track/frame/direction/product version, polarization availability (HH and HV both present), full AOI footprint coverage, and a time span that covers a meaningful physical change (e.g., crop/flood/irrigation cycle).

## SCOPE (keep small)
- Change type A: GCOV backscatter time series (agriculture/water/flooded fields), HH vs HV comparison.
- Change type B: line-of-sight displacement from GUNW with coherence mask. EXPLORATORY ONLY, and only if GUNW exists with enough pairs. Short series over the Delta are likely dominated by atmosphere/ionosphere/decorrelation relative to mm/yr subsidence. If the signal can't be separated from noise, say so and drop B. Do not claim subsidence rates.
- Context layers (external, labelled): optical basemap, Sentinel-2 NDVI, land cover, DEM, rainfall/crop-calendar info.
- NOT in scope: ML forecasting, SHAP, atmospheric deep learning, multi-hazard scores.

## SCIENCE REQUIREMENTS
- Speckle: apply and document multilooking/filtering and state the effective number of looks (ENL) before any change map.
- Units: convert linear power to dB only for display/ratios; document every conversion.
- Change metric: log-ratio (dB difference) between dates, with a statistically justified threshold (based on speckle/ENL or an empirical noise estimate over stable pixels). No arbitrary thresholds. Report the threshold and its derivation.
- Masks: NoData, layover/shadow, low-quality pixels, and water/permanent-water handling; document each mask and its pixel share.
- Confounders: soil moisture/rain/irrigation can drive backscatter as much as vegetation. Overlay external rainfall (labelled) and discuss, do not ignore.
- Polarization: explain HH vs HV (surface/double-bounce vs volume scattering sensitivity) and show where they disagree. Interpretations are hypotheses unless supported by external evidence.
- Validation: no ground truth is assumed. Use Sentinel-2 NDVI or other external data as context to check plausibility, clearly labelled as such and described as supporting evidence, not proof.

## DATA REALITY CHECKS (do in Phase 0)
- Report how much of the NISAR archive is actually public for the AOI today (release dates, acquisition date ranges, product versions). Do not assume the full history is available; check.
- Check whether server-side spatial subsetting exists for GCOV. If not, plan for full-granule download or ranged reads (h5py/earthaccess streaming). State actual granule sizes and total download volume BEFORE downloading; get my confirmation if above 5 GB.
- Check the environment: Python version, network access to Earthdata/ASF, GDAL/rasterio, node. If network is blocked, STOP and report; do not continue with mock data.
- Check that Earthdata credentials are present via .env; if not, tell me what to set up.

## PIPELINE
earthaccess/asf_search query → download (minimal subset, sizes stated) → HDF5 inspection (h5py) → extract layers → unit check → align/reproject (rasterio) → masks → speckle handling → change maps + stats → precompute COGs/tiles + JSON time series → thin FastAPI (or static files if enough) → React.

## APP (React + TS + Vite + MapLibre only; FastAPI backend optional)
Prefer precomputed COGs/tiles and JSON over live processing. All scientific processing stays in the Python backend/pipeline; the frontend only renders.
1. Map page: before/after swipe, date slider with animation, layer toggle (HH / HV / change), opacity, legends with units.
2. Pixel/area inspector: time-series chart for a clicked point or drawn polygon (state if the series is in dB, and N dates).
3. Story mode: 4-6 steps (what changed, hypothesized drivers: roughness, dielectric/moisture, vegetation structure; why polarization matters).
4. Layer metadata panel: every layer shows rule 3 fields.
5. Method & Limits panel: sources, processing, uncertainty, thresholds, what we cannot conclude.
6. Future NISAR applications section.

## PHASES (each ends with a runnable, checkable result; wait for my confirmation between phases)
0. Environment audit + NISAR availability audit + AOI comparison table (candidates × usable dates, track/frame, direction, polarization, product version, granule sizes, footprint coverage) + recommendation with reasons + stated risks.
1. Real data download + metadata log (granule IDs, versions, sizes, checksums if available).
2. Processing + validated georeferenced layers (CRS, units, masks documented).
3. Change detection + time series + stats + noise/threshold justification.
4. COG/tiles + API (or static serving).
5. Frontend map + story mode.
6. Tests (CRS mismatch, NoData, dB/linear conversion, change calc, geometry/version-mixing guard, API errors) + README + 3-minute demo script.

## DEFINITION OF DONE
A person opens the app, sees real NISAR change over the chosen area, understands the story in under 3 minutes, and can verify every layer's satellite, product, version, date, polarization, units, CRS, and source.

## FINAL REPORT (honest)
What works, what's tested, which real datasets were used (IDs, versions), what is incomplete, limitations, what we cannot conclude, how to run.

## START NOW
Do Phase 0 only. Report findings in the comparison table format above, state anything that blocks Phase 1, propose the AOI, and wait for my confirmation.