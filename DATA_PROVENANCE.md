# DATA PROVENANCE & SENSOR LINEAGE — EARTH RHYTHM

Every raster, time series, benchmark, and forecast layer in **EARTH RHYTHM** is traceable to real satellite granules and authoritative geophysical reference datasets. No synthetic or fabricated imagery is used anywhere in the application (`Rule 1` & `Rule 2`).

---

## 1. Primary NASA NISAR Datasets (ASF DAAC)

| Dataset / Product | Track / Frame / Orbit | CRID / Version | Acquisition Dates / Pairs | Native / Cube Grid | Role in Pipeline |
|---|---|---|---|---|---|
| **NASA-ISRO SAR `NISAR_L2_PR_GCOV`** (Geocoded Polarimetric Covariance, $\gamma^0_{HH}$ & $\gamma^0_{HV}$) | Track 129 / Frame 016 / Ascending | `PROVISIONAL P05023` (`Ver 1.0.11`, `PGE R05.02.3`) | **10 passes:** `2026-06-23`, `2026-07-05`, `2026-07-17`, `2026-08-10` *(24d gap)*, `2026-08-22`, `2026-09-03`, `2026-09-15`, `2026-09-27`, `2026-10-09`, `2026-10-21` | Native `10 m` multilooked $4\times 4$ in linear power + $3\times 3$ Lee to `40 m` `EPSG:32636` (`1560 × 1968`) | Core radiometric time series (`fayoum_gcov_10dates_40m_filtered.h5`), seasonal change regimes, and next-pass backscatter forecasting |
| **NASA-ISRO SAR `NISAR_L2_PR_GUNW`** (Geocoded Unwrapped Interferogram & Coherence) | Track 129 / Frame 016 / Ascending | `PROVISIONAL P05023` (`Ver 1.0.11`) & `BETA B04010` (`Ver 0.9.2`) | **9 consecutive pairs** (`20260623_20260705` through `20261009_20261021`) | Resampled to `40 m` `EPSG:32636` (`fayoum_gunw_9pairs_40m.h5`) | Interferometric coherence ($\bar{\gamma}_{\text{GUNW}}$) for water vs. dry sand separation, El-Qarn Island preservation, and phase instability feature $f_2$ |

---

## 2. Authoritative NASA & Copernicus Ancillary / Validation Datasets

| Dataset | Source / Archive | Native Resolution & Datum | Files in `data/benchmarks/` | Role in Pipeline |
|---|---|---|---|---|
| **NASA `NISAR_DEM v1.2`** (Modified Copernicus GLO-30 DEM) | NASA JPL / ASF DAAC | `30 m` (resampled to `40 m` `EPSG:32636`); Native **WGS84 Ellipsoidal Height** corrected by **$-14.20\text{ m}$ EGM2008 geoid undulation** to Orthometric MSL | `fayoum_nisar_dem_40m_utm36n.tif` | Topographic basin depression gating (Lake Qarun `-43.0 m MSL`, Wadi El-Rayan `-10.7 m` to `-29.7 m MSL`) and Height Above Nearest Drainage (`HAND`) surge simulator |
| **NASA JPL `OPERA_L3_DSWX-HLS_V1`** (Dynamic Surface Water Extent from Harmonized Landsat / Sentinel-2) | NASA PO.DAAC / LP DAAC (`MGRS T36RTT`) | `30 m` (`EPSG:32636`) | `OPERA_L3_DSWX-HLS_T36RTT_20260705T083601Z`, `..._20260810T082609Z`, `..._20260915T083729Z`, `fayoum_opera_dswx_consensus_water_40m.tif` | **Independent multi-sensor optical ground truth (Track B)** for evaluating pure-SAR water classification and Phase 5 flood susceptibility (`ROC-AUC = 0.9937`, `Coastal IoU = 0.8820`) |
| **NASA `NISAR_WATERMASK v0.5.0`** | NASA JPL / ASF DAAC | `40 m` (`EPSG:32636`) | `fayoum_nisar_watermask_40m_utm36n.tif` | Static water reference benchmark (`ROC-AUC = 0.9885`, `IoU = 0.7721`) |
| **ESA Copernicus `Sentinel-2 L2A`** (Optical Surface Reflectance `B04` & `B08`) | Element84 Earth Search STAC (`Tiles 36RTT & 36RUT`) | `10 m` (aggregated over $200\text{ m} \times 200\text{ m}$ focal ROIs across 9 cloud-free dates) | Stored in `data/processed/phase3_change_and_timeseries_report.json` (`external_context_non_nisar.sentinel2_l2a_optical_ndvi`) | Independent optical NDVI contextual verification ($r = 0.93$ summer HV-vs-NDVI correlation at `ROI_01_SUMMER_CROP_HARVEST`) |
| **NASA `POWER` Agroclimatology Daily API** (`MERRA-2 / GEOS-5.12.4`) | NASA Langley Research Center (`power.larc.nasa.gov`) | Daily point series at `(30.84°E, 29.31°N)`, `2026-06-15` to `2026-10-25` (`133` days) | Stored in `data/processed/phase3_change_and_timeseries_report.json` (`external_context_non_nisar.nasa_power_meteorology`) | Confirms `0.15 mm` total summer/autumn rainfall (`0` days $\ge 0.5\text{ mm}$), proving agricultural moisture changes are driven by Bahr Youssef canal irrigation rather than rainfall, while `2.1–5.0 m/s` winds drive Bragg capillary waves on Lake Qarun |
