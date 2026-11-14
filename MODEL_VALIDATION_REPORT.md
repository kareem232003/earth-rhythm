# MODEL VALIDATION REPORT — EARTH RHYTHM (PHASE 3 & 4 ML AUDIT)

**Generated From:** `data/processed/phase5_prediction_report.json` (`scripts/phase5_explainable_prediction.py`, `SEED = 42`)  
**Temporal Holdout Protocol:** Train strictly on Passes 1–9 (`2026-06-23` to `2026-10-09`), predict Held-Out Pass 10 (`2026-10-21`), and score out-of-sample across all `3,070,080` pixels (`4,912.13 km²`).

---

## 1. Engine 1: Explainable Flood & Shoreline Inundation Susceptibility Validation

### 1.1 Feature Formulation & Weights ($\sum w_i = 1.00$)

$$S(x, y) = 0.38\,f_1(x,y) + 0.24\,f_2(x,y) + 0.22\,f_3(x,y) + 0.16\,f_4(x,y), \qquad P_{\text{flood}}(x,y) = \frac{1}{1 + \exp(-9.0 \cdot (S(x,y) - 0.44))}$$

- $f_1 \in [0, 1]$ (**38% — NISAR L2_GCOV HH Dielectric Water Index**): Specular smoothness from predicted $\hat{\gamma}^0_{HH}$ and $\hat{\gamma}^0_{HV}$.
- $f_2 \in [0, 1]$ (**24% — NISAR L2_GUNW Phase Instability**): $1 - \bar{\gamma}_{\text{GUNW}}$, separating open water ($\bar{\gamma} < 0.18$) from coherent dry desert sand sheets ($\bar{\gamma} > 0.35$).
- $f_3 \in [0, 1]$ (**22% — Multi-Pass Wetting Trend & Bragg Wave Activity**): Elapsed-time-normalized wetting velocity $(-d\text{HH}/dt)$ combined with temporal backscatter standard deviation $\sigma_{\text{HH}}$.
- $f_4 \in [0, 1]$ (**16% — Hydrological Basin & Shoreline Proximity**): Exponential shoreline distance decay combined with orthometric `NISAR_DEM v1.2` (`HAND <= 8.0 m`).

### 1.2 Dual Ground-Truth Validation Results

| Evaluation Track & Benchmark Reference | Evaluated Pixels ($N$) | Area ($\text{km}^2$) | ROC-AUC | IoU | F1-Score | Precision | Recall | Brier Score | ECE (10-Bin) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **Track B: Independent NASA OPERA DSWx-HLS Consensus (Full AOI)** | `3,063,660` | `4,901.86` | **0.9937** | **0.7903** | **0.8828** | `0.8174` | `0.9597` | `0.01251` | `0.01200` |
| **Track B: Independent NASA OPERA DSWx-HLS (Coastal 1.5 km Buffer)** | `349,228` | `558.76` | **0.9911** | **0.8820** | **0.9373** | `0.8956` | `0.9831` | `0.05576` | `0.05044` |
| **Track B: Independent NASA OPERA DSWx-HLS (2026-09-15 Single Scene)** | `3,063,660` | `4,901.86` | **0.9888** | **0.7773** | **0.8747** | `0.8165` | `0.9419` | `0.01325` | `0.01146` |
| **Track B: Independent NASA NISAR_WATERMASK v0.5.0 (Full AOI)** | `3,070,080` | `4,912.13` | **0.9885** | **0.7721** | **0.8714** | `0.8224` | `0.9265` | `0.01451` | `0.01106` |
| **Track A: Pass 10 SAR Holdout Self-Consistency (Full AOI)** | `3,070,080` | `4,912.13` | **0.9998** | **0.7936** | **0.8849** | `0.7939` | `0.9995` | `0.01167` | `0.01428` |
| **Track A: Pass 10 SAR Holdout (Coastal 1.5 km Buffer)** | `352,299` | `563.68` | **0.9976** | **0.8751** | **0.9334** | `0.8755` | `0.9995` | `0.05798` | `0.06808` |
| **Track A: Pass 10 SAR Holdout (Non-Permanent Dynamic Margin)** | `182,178` | `291.48` | **0.9957** | **0.6629** | **0.7973** | `0.6640` | `0.9974` | `0.05977` | `0.07257` |

#### Confusion Matrices (`Threshold = 0.50`)

- **Track B (vs. Independent NASA OPERA DSWx-HLS Consensus, `N = 3,063,660` px):**
  - `TP = 191,011` px | `FP = 42,673` px | `FN = 8,024` px | `TN = 2,821,952` px (`Sum = 3,063,660` px).
- **Track A (vs. Held-Out Pass 10 SAR Water Detection, `N = 3,070,080` px):**
  - `TP = 186,293` px | `FP = 48,359` px | `FN = 90` px | `TN = 2,835,338` px (`Sum = 3,070,080` px).

---

## 2. Engine 2: Dual-Pol Backscatter Forecasting & Baseline Comparison

### 2.1 Held-Out Pass 10 (`2026-10-21`) Benchmark vs. Baselines

| Forecasting Model | HH RMSE (AOI) | HH MAE (AOI) | HH Bias | HH $R^2$ (AOI) | HH RMSE (Crop) | HV RMSE (AOI) | HV MAE (AOI) | HV Bias | HV $R^2$ (AOI) | HV RMSE (Crop) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **Speckle-Aware Spatio-Temporal State-Space (Ours)** | **0.903 dB** | **0.606 dB** | `-0.126 dB` | **0.9646** | **1.222 dB** | **0.857 dB** | **0.539 dB** | `+0.044 dB` | **0.9181** | **1.269 dB** |
| **Persistence Baseline ($y_t$)** | `0.964 dB` | `0.631 dB` | `-0.160 dB` | `0.9597` | `1.289 dB` | `0.902 dB` | `0.548 dB` | `+0.036 dB` | `0.9094` | `1.326 dB` |
| **3-Pass Moving Average Baseline** | `1.009 dB` | `0.676 dB` | `-0.108 dB` | `0.9558` | `1.378 dB` | `1.088 dB` | `0.764 dB` | `-0.243 dB` | `0.8680` | `1.547 dB` |
| **Elapsed-Time Linear OLS Trend (4-Pass)** | `1.188 dB` | `0.806 dB` | `-0.270 dB` | `0.9387` | `1.610 dB` | `1.223 dB` | `0.833 dB` | `-0.328 dB` | `0.8334` | `1.768 dB` |

- **Uncertainty Calibration:** Mean per-pixel $1\sigma$ predictive uncertainty is `0.702 dB` (HH) and `0.706 dB` (HV), achieving empirical `±95% CI` (`±1.96σ`) coverage of **`86.41%` (HH)** and **`90.87%` (HV)** on Held-Out Pass 10.

### 2.2 4-Fold Rolling-Origin Temporal Cross-Validation (`Passes 7, 8, 9, 10`)

| Target Pass & Date | Training Window | Elapsed Step | HH RMSE (Ours) | HH RMSE (Persistence) | HH $R^2$ | HV RMSE (Ours) | HV RMSE (Persistence) | HV $R^2$ |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| **Pass 7 (`2026-09-15`)** | `2026-06-23..2026-09-03` | `12 d` | **1.014 dB** | `1.089 dB` | `0.9573` | **1.029 dB** | `1.090 dB` | `0.8928` |
| **Pass 8 (`2026-09-27`)** | `2026-06-23..2026-09-15` | `12 d` | **1.108 dB** | `1.207 dB` | `0.9517` | **1.024 dB** | `1.072 dB` | `0.9041` |
| **Pass 9 (`2026-10-09`)** | `2026-06-23..2026-09-27` | `12 d` | **1.093 dB** | `1.219 dB` | `0.9479` | **1.177 dB** | `1.204 dB` | `0.8445` |
| **Pass 10 (`2026-10-21`)** | `2026-06-23..2026-10-09` | `12 d` | **0.903 dB** | `0.964 dB` | `0.9646` | **0.857 dB** | `0.902 dB` | `0.9181` |

### 2.3 4-Quadrant Spatial Block Validation (`Pass 10 Holdout`, `767,520` px per block)

| Spatial Quadrant | Pixel Count | HH RMSE | HH MAE | HV RMSE | HV MAE |
|---|---:|---:|---:|---:|---:|
| `NW_Lake_Qarun_West_Basin` | `767,520` | `0.641 dB` | `0.446 dB` | `0.545 dB` | `0.338 dB` |
| `NE_Tamia_Sennuris_Oasis` | `767,520` | `1.019 dB` | `0.698 dB` | `0.958 dB` | `0.636 dB` |
| `SW_Wadi_El_Rayan_Depression` | `767,520` | `0.747 dB` | `0.495 dB` | `0.615 dB` | `0.368 dB` |
| `SE_Etsa_Bahr_Youssef_Inlet` | `767,520` | `1.120 dB` | `0.784 dB` | `1.161 dB` | `0.814 dB` |

---

## 3. Seven-Class Dual-Pol Change Regime Validation (`Pass 10 Holdout`)

- **Cropland 48-Day Autumn Window (`2026-09-03 -> 2026-10-21`, `N = 1,208,974` px):**
  - **Overall Accuracy:** `80.38%` (`0.8038`)
  - **Weighted F1:** `0.7945`
  - **Macro F1:** `0.4786`
  - **Balanced Accuracy:** `43.54%` (`0.4354`)
- **Full AOI 48-Day Autumn Window (`N = 3,070,080` px):**
  - **Overall Accuracy:** `90.89%` (`0.9089`) | **Weighted F1:** `0.9007` | **Macro F1:** `0.4833`
- **Cropland 12-Day Single-Step Window (`2026-10-09 -> 2026-10-21`, `N = 1,208,974` px):**
  - **Overall Accuracy:** `86.53%` (`0.8653`) | **Weighted F1:** `0.8048`

### Per-Class Cropland Regime Metrics (`48-Day Autumn Window`, `N = 1,208,974` px)

| Code | Regime Label | Support (px) | Predicted (px) | Precision | Recall | F1-Score |
|---:|---|---:|---:|---:|---:|---:|
| `0` | Stable / Unchanged ($<\tau$) | `734,327` | `842,315` | `80.66%` | `92.52%` | **0.8618** |
| `1` | Canopy Growth / Winter Crop Emergence ($+\text{HV}$) | `129,111` | `94,610` | `74.07%` | `54.27%` | **0.6264** |
| `2` | Harvest / Canopy Clearance ($-\text{HV}$) | `281,757` | `228,522` | `87.39%` | `70.88%` | **0.7828** |
| `3` | Irrigation / Soil Wetting ($+\text{HH}$) | `16,553` | `6,873` | `43.14%` | `17.91%` | **0.2531** |
| `4` | Surface Drying / Tilled Soil ($-\text{HH}$) | `44,866` | `35,318` | `54.75%` | `43.10%` | **0.4823** |
| `5` | Flooded Vegetation / Standing Water ($+\text{HH}, -\text{HV}$) | `939` | `212` | `44.81%` | `10.12%` | **0.1651** |
| `6` | Specular Inundation / Smooth Wet Margin ($-\text{HH}, +\text{HV}$) | `1,421` | `1,124` | `20.20%` | `15.97%` | **0.1784** |
