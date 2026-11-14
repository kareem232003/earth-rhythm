# SCIENTIFIC & MODEL LIMITATIONS — EARTH RHYTHM

In strict compliance with `Rule 4`, `Rule 5`, `Rule 6`, and the NASA Space Apps Scientific Audit guidelines, this document states the physical, statistical, and operational boundaries of the **EARTH RHYTHM** analysis and forecasting engines.

---

## 1. Temporal Sample Size ($N = 10$ Passes) & Irregular 24-Day Gap

1. **Sample Size Constraint ($N = 10$):** The archived NISAR `L2_GCOV` stack spans 10 orbital passes from `2026-06-23` to `2026-10-21`. With $N = 10$ time steps per pixel, large deep-learning architectures (e.g., 3D-CNNs, ConvLSTMs, or spatio-temporal Transformers) would severely overfit spatial autocorrelation and memorize seasonal trends without generalizing across years. Therefore, we intentionally use a physically constrained, low-degree-of-freedom **Speckle-Aware Spatio-Temporal State-Space Forecaster** (`4` linear state-space gains fitted strictly on historical transitions inside the training window).
2. **Irregular Acquisition Step (`2026-07-17` $\to$ `2026-08-10` = 24 Days):** Pass 3 and Pass 4 are separated by 24 days (one missed 12-day orbital cycle), whereas all other consecutive passes are separated by 12 days. All velocity calculations explicitly normalize by actual elapsed days $\Delta t_k$.
3. **Forecast Target Date (`2026-11-02`):** Because no post-`2026-10-21` NISAR granules exist in the local archive, `2026-11-02` represents the immediate $+12\text{-day}$ next-pass forecast horizon (`Pass 11`) following the last observed pass (`Pass 10: 2026-10-21`). No post-cutoff satellite observations are fabricated.

---

## 2. Distinction Between Water Detection, Flood Susceptibility & Surge Scenarios

1. **Water Detection vs. Flood Susceptibility:**
   - **Water Detection** identifies surfaces currently covered by open water on an observed SAR pass.
   - **Flood & Shoreline Inundation Susceptibility (`Engine 1`)** estimates the probability $P_{\text{flood}} \in [0, 1]$ that a pixel will be inundated or saturated on the next pass (`2026-11-02`) based on forecasted dielectric smoothness ($f_1$), 9-pair InSAR phase instability ($f_2$), multi-pass wetting trend ($f_3$), and orthometric DEM basin/shoreline proximity ($f_4$).
2. **Dynamic Shoreline Margin vs. Full-AOI Performance:**
   - Full-AOI flood metrics (`ROC-AUC = 0.9937` vs. OPERA DSWx-HLS; `0.9998` vs. Pass 10 SAR) and Coastal 1.5 km Buffer metrics (`IoU = 0.8820` vs. OPERA; `0.8751` vs. Pass 10 SAR) include the permanent open-water basins of Lake Qarun and Wadi El-Rayan.
   - When permanent water is excluded and evaluation is restricted strictly to the **Non-Permanent Dynamic Shoreline Margin** (`N = 182,178` px = `291.48 km²`), Held-Out Pass 10 performance is **`ROC-AUC = 0.9957`, `IoU = 0.6629`, `F1 = 0.7973` (`Precision = 66.40%`, `Recall = 99.74%`)**.
3. **Hypothetical HAND Drainage Surge Scenarios (`+0.5 m`, `+1.0 m`):**
   - While our surge simulator enforces **8-connected hydraulic connectivity** over orthometric `NISAR_DEM v1.2` (`HAND <= surge_m`), it is a hydrostatic topographic-routing model rather than a full 2D hydrodynamic shallow-water solver (e.g., HEC-RAS 2D or LISFLOOD-FP) with canal gate discharge hydrographs and Manning roughness. Accordingly, `+0.5 m` and `+1.0 m` scenarios are explicitly badged as **`HYPOTHETICAL SCENARIO`**.

---

## 3. Seven-Class Dual-Pol Regime Classification Boundaries

1. **No Crop Species Identification from L-Band SAR Alone:** L-band dual-polarization (`HH`, `HV`) backscatter measures dielectric moisture and structural canopy volume ($\text{cm}$-scale stems, branches, and soil roughness). It cannot distinguish specific crop species (e.g., maize vs. sorghum vs. cotton) without optical/field labels. Our 7 classes represent **physical scattering regimes** (`Canopy Growth`, `Harvest/Clearance`, `Soil Wetting`, `Surface Drying`, etc.), with `Sentinel-2 L2A` NDVI used strictly as supporting contextual evidence.
2. **Class Imbalance in Rare Regimes (`Classes 3, 5, 6`):**
   - Over the 48-day autumn window (`2026-09-03` $\to$ `2026-10-21`), dominant classes such as `Class 0: Stable` (`F1 = 0.8618`), `Class 2: Harvest` (`F1 = 0.7828`), and `Class 1: Canopy Growth` (`F1 = 0.6264`) achieve high accuracy (`Cropland OA = 80.38%`, `Full AOI OA = 90.89%`).
   - However, transient single-pass events—such as `Class 3: Irrigation / Soil Wetting` (`F1 = 0.2531`), `Class 5: Flooded Vegetation (+HH, -HV)` (`939` px support, `F1 = 0.1651`), and `Class 6: Specular Inundation (-HH, +HV)` (`1,421` px support, `F1 = 0.1784`)—occur over small area fractions (`< 1.5%` of cropland) and depend on the exact timing of farmer canal turnouts relative to the 12-day satellite overpass, lowering unweighted `Macro F1` to `0.4786` (`Balanced Accuracy = 43.54%`).

---

## 4. Physical Radar Confounders & 12-Day InSAR Tropospheric Limits

1. **Wind-Induced Bragg Scattering on Lake Qarun:** Moderate surface winds (`2.1–5.0 m/s` confirmed by NASA POWER MERRA-2) roughen open water at centimeter-to-decimeter scales, generating up to `1.6–3.7 dB` HH backscatter fluctuations across passes.
2. **Hyper-Arid Rayleigh-Smooth Sand Sheets (`NESZ Floor`):** Dry fine-grained eolian sand in the Western Desert drops near the NISAR L-band Noise-Equivalent Sigma Zero (`NESZ ~ -24 dB`), mimicking specular water in single-pass backscatter. Multi-pass `L2_GUNW` coherence ($\bar{\gamma} > 0.35$ on sand vs. $< 0.18$ on water) and `composite_landcover_class == 6` are required to prevent false water classification.
3. **12-Day L2_GUNW Phase Is Dominated by Tropospheric Water Vapor (`Rule 6`):** Apparent 12-day Line-of-Sight (`LOS`) phase variations over stable desert bedrock exhibit a standard deviation of **`8.80–18.78 mm`**, which is $>20\times$ larger than plausible 12-day clay compaction (`< 0.5 mm`). Therefore, 12-day unwrapped phase is never interpreted as ground subsidence; multi-year SBAS/PS-InSAR stacking ($>30$ passes) is required to isolate millimeter-per-year vertical deformation.
