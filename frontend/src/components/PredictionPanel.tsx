import React, { useEffect, useState } from 'react';
import { loadPrediction } from '../staticBackend';
import { roiShortName } from '../uiLabels';

interface DriverSpec {
  id: string;
  name: string;
  nasa_source: string;
  weight: number;
  weight_pct: number;
  plain_explanation: string;
}

interface SurgeScenario {
  scenario_name: string;
  epistemic_category: string;
  water_level_surge_m: number;
  hydraulic_connectivity_enforced: boolean;
  hydraulically_connected_overtop_ha: number;
  total_shoreline_and_basin_at_risk_ha: number;
  imminent_inundation_ha: number;
  agricultural_cropland_at_risk_ha: number;
  settlement_and_road_corridor_at_risk_ha: number;
}

interface CropRegimeForecast {
  regime_code: number;
  regime_label: string;
  pixel_count: number;
  area_ha: number;
  area_km2: number;
  fraction_of_cropland_pct: number;
}

interface CalibrationBin {
  bin_index: number;
  bin_range: string;
  pixel_count: number;
  mean_predicted_prob: number;
  observed_event_frequency: number;
  calibration_gap: number;
}

interface FloodEvalBlock {
  evaluated_pixels: number;
  evaluated_area_km2: number;
  roc_auc: number;
  iou: number;
  f1_score: number;
  precision: number;
  recall: number;
  overall_accuracy: number;
  brier_score: number;
  confusion_matrix: {
    true_negative_px: number;
    false_positive_px: number;
    false_negative_px: number;
    true_positive_px: number;
    sum_check_px: number;
  };
  calibration_10bin?: {
    expected_calibration_error_ece: number;
    bins: CalibrationBin[];
  };
}

interface BaselinePolMetrics {
  rmse_db_full_aoi: number;
  mae_db_full_aoi: number;
  bias_db_full_aoi: number;
  r2_full_aoi: number;
  rmse_db_cropland: number;
  mae_db_cropland: number;
  bias_db_cropland: number;
  r2_cropland: number;
}

interface BaselineEntry {
  label: string;
  hh: BaselinePolMetrics;
  hv: BaselinePolMetrics;
}

interface RollingFold {
  fold_target_pass: number;
  target_date: string;
  train_dates_range: string;
  elapsed_step_days: number;
  hh_rmse_db_aoi: number;
  hh_r2_aoi: number;
  hh_persistence_rmse_db_aoi: number;
  hv_rmse_db_aoi: number;
  hv_r2_aoi: number;
  hv_persistence_rmse_db_aoi: number;
}

interface SpatialBlockMetric {
  block_id: string;
  pixel_count: number;
  hh_rmse_db: number;
  hh_mae_db: number;
  hv_rmse_db: number;
  hv_mae_db: number;
}

interface PerClassRegimeMetric {
  regime_code: number;
  regime_label: string;
  support_px: number;
  predicted_px: number;
  precision: number;
  recall: number;
  f1_score: number;
}

interface SevenClassEvaluation {
  evaluated_pixels: number;
  overall_accuracy: number;
  macro_f1: number;
  weighted_f1: number;
  balanced_accuracy: number;
  per_class_metrics: PerClassRegimeMetric[];
  confusion_matrix_7x7: number[][];
}

interface RoiForecast {
  roi_id: string;
  title: string;
  change_type?: string;
  wgs84_lon: number;
  wgs84_lat: number;
  utm_epsg32636_x?: number;
  utm_epsg32636_y?: number;
  window_dimensions_40m_px?: string;
  historical_dates?: string[];
  historical_hh_db?: number[];
  historical_hv_db?: number[];
  backtest_20261021_predicted_hh_db?: number;
  backtest_20261021_observed_hh_db?: number;
  backtest_20261021_residual_hh_db?: number;
  backtest_20261021_predicted_hv_db?: number;
  backtest_20261021_observed_hv_db?: number;
  backtest_20261021_residual_hv_db?: number;
  observed_20261021_hh_db: number;
  observed_20261021_hv_db: number;
  predicted_20261102_hh_db: number;
  predicted_20261102_hh_1sigma_db?: number;
  predicted_20261102_hh_ci95_db: number;
  predicted_20261102_hh_ci95_bounds_db?: [number, number];
  predicted_20261102_hv_db: number;
  predicted_20261102_hv_1sigma_db?: number;
  predicted_20261102_hv_ci95_db: number;
  predicted_20261102_hv_ci95_bounds_db?: [number, number];
  forecast_confidence_score_pct?: number;
  predicted_delta_hh_db: number;
  predicted_delta_hv_db: number;
  predicted_48d_autumn_delta_hh_db?: number;
  predicted_48d_autumn_delta_hv_db?: number;
  predicted_regime_code: number;
  predicted_regime_label: string;
  mean_gunw_coherence?: number;
  dem_orthometric_msl_m?: number;
  hand_above_nearest_water_m?: number;
  distance_to_water_m?: number;
  flood_inundation_probability_pct: number;
  flood_risk_tier: string;
  driver_scores_0_to_100: {
    sar_hh_dielectric_water_index: number;
    insar_gunw_coherence_decorrelation: number;
    multi_pass_wetting_velocity: number;
    topographic_shoreline_basin_proximity: number;
  };
  sentinel2_ndvi_context?: {
    source: string;
    paired_scenes_count: number;
    ndvi_min: number;
    ndvi_max: number;
    latest_sentinel2_date: string;
    latest_ndvi: number;
    hv_vs_ndvi_summer_pearson_r?: number;
  } | null;
}

interface ExportedCogMeta {
  cog_url: string;
  size_mb: number;
  sha256: string;
  block_shape: number[];
  overview_factors: number[];
}

interface PredictionReport {
  generated_at_utc: string;
  random_seed: number;
  forecast_target_date: string;
  forecast_horizon_days: number;
  forecast_horizon_disclosure?: string;
  training_dates: string[];
  elapsed_step_days?: number[];
  irregular_interval_note?: string;
  backtest_holdout_date: string;
  vertical_datum_disclosure?: {
    dem_source: string;
    native_vertical_datum: string;
    egm2008_geoid_undulation_fayoum_m: number;
    lake_qarun_median_ellipsoidal_m: number;
    lake_qarun_median_orthometric_msl_m: number;
    upper_wadi_el_rayan_orthometric_msl_m: number;
    lower_wadi_el_rayan_orthometric_msl_m: number;
  };
  explainable_model_drivers: DriverSpec[];
  backtest_validation_pass10_20261021: {
    description: string;
    ground_truth_independence_note?: string;
    flood_inundation_classification: {
      total_evaluated_pixels: number;
      roc_auc_full_aoi: number;
      roc_auc_coastal_1500m_buffer: number;
      roc_auc_non_permanent_margin?: number;
      iou_full_aoi: number;
      iou_coastal_1500m_buffer: number;
      iou_non_permanent_margin?: number;
      f1_score: number;
      f1_score_coastal_1500m_buffer?: number;
      f1_score_non_permanent_margin?: number;
      precision: number;
      recall: number;
      brier_score: number;
      confusion_matrix: {
        true_negative_px: number;
        false_positive_px: number;
        false_negative_px: number;
        true_positive_px: number;
        sum_check_px: number;
      };
      coastal_1500m_evaluation?: FloodEvalBlock;
      non_permanent_margin_evaluation?: FloodEvalBlock;
      calibration_10bin?: {
        expected_calibration_error_ece: number;
        bins: CalibrationBin[];
      };
    };
    independent_optical_validation_opera_dswx?: {
      vs_opera_dswx_consensus_open_water_full_aoi: FloodEvalBlock;
      vs_opera_dswx_consensus_open_water_coastal_1500m: FloodEvalBlock;
      vs_opera_dswx_20260915_open_water: FloodEvalBlock;
      vs_opera_dswx_20260915_open_plus_partial_water: FloodEvalBlock;
      vs_nisar_watermask_v050_full_aoi: FloodEvalBlock;
    };
    backscatter_regression_pass10: {
      hh_rmse_db_full_aoi: number;
      hh_mae_db_full_aoi: number;
      hh_bias_db_full_aoi?: number;
      hh_r2_full_aoi: number;
      hh_rmse_db_cropland: number;
      hh_mae_db_cropland?: number;
      hh_bias_db_cropland?: number;
      hh_r2_cropland?: number;
      hh_mean_1sigma_uncertainty_db?: number;
      hh_ci95_empirical_coverage_pct?: number;
      hv_rmse_db_full_aoi: number;
      hv_mae_db_full_aoi: number;
      hv_bias_db_full_aoi?: number;
      hv_r2_full_aoi: number;
      hv_rmse_db_cropland: number;
      hv_mae_db_cropland?: number;
      hv_bias_db_cropland?: number;
      hv_r2_cropland?: number;
      hv_mean_1sigma_uncertainty_db?: number;
      hv_ci95_empirical_coverage_pct?: number;
      regime_classification_accuracy_aoi: number;
      regime_classification_accuracy_cropland: number;
      regime_macro_f1_cropland?: number;
      regime_weighted_f1_cropland?: number;
      regime_balanced_accuracy_cropland?: number;
      regime_12day_single_step_accuracy_cropland?: number;
    };
    baseline_model_comparisons_pass10?: Record<string, BaselineEntry>;
    rolling_origin_temporal_cv?: RollingFold[];
    spatial_block_validation_pass10?: SpatialBlockMetric[];
    seven_class_regime_evaluation?: {
      cropland_48day_autumn_window: SevenClassEvaluation;
      full_aoi_48day_autumn_window: SevenClassEvaluation;
      cropland_12day_single_step_window: SevenClassEvaluation;
    };
  };
  forward_forecast_20261102: {
    drainage_surge_scenarios: SurgeScenario[];
    cropland_regime_forecast_breakdown: CropRegimeForecast[];
    focal_roi_forecasts: RoiForecast[];
    map_overlays: {
      flood_risk_layer_id: string;
      crop_regime_layer_id: string;
      forecast_hh_layer_id?: string;
      forecast_hv_layer_id?: string;
    };
    exported_cogs?: Record<string, ExportedCogMeta>;
  };
}

interface Props {
  selectedRoiId?: string;
  onShowPredictionLayer: (layerId: string) => void;
  onFlyToRoi?: (lon: number, lat: number, roiId: string) => void;
}

const REGIME_COLORS: Record<number, string> = {
  0: '#64748b',
  1: '#22c55e',
  2: '#eab308',
  3: '#3b82f6',
  4: '#a855f7',
  5: '#ef4444',
  6: '#06b6d4',
};

const RoiForecastTrajectorySvg: React.FC<{ roi: RoiForecast }> = ({ roi }) => {
  const histDates = roi.historical_dates || [];
  const histHh = roi.historical_hh_db || [];
  const histHv = roi.historical_hv_db || [];
  if (histDates.length < 2 || histHh.length !== histDates.length || histHv.length !== histDates.length) {
    return null;
  }

  const allDates = [...histDates, '2026-11-02'];
  const hhLow = roi.predicted_20261102_hh_ci95_bounds_db
    ? roi.predicted_20261102_hh_ci95_bounds_db[0]
    : roi.predicted_20261102_hh_db - roi.predicted_20261102_hh_ci95_db;
  const hhHigh = roi.predicted_20261102_hh_ci95_bounds_db
    ? roi.predicted_20261102_hh_ci95_bounds_db[1]
    : roi.predicted_20261102_hh_db + roi.predicted_20261102_hh_ci95_db;
  const hvLow = roi.predicted_20261102_hv_ci95_bounds_db
    ? roi.predicted_20261102_hv_ci95_bounds_db[0]
    : roi.predicted_20261102_hv_db - roi.predicted_20261102_hv_ci95_db;
  const hvHigh = roi.predicted_20261102_hv_ci95_bounds_db
    ? roi.predicted_20261102_hv_ci95_bounds_db[1]
    : roi.predicted_20261102_hv_db + roi.predicted_20261102_hv_ci95_db;

  const allVals = [
    ...histHh,
    ...histHv,
    roi.predicted_20261102_hh_db,
    roi.predicted_20261102_hv_db,
    hhLow,
    hhHigh,
    hvLow,
    hvHigh,
  ];
  const yMin = Math.floor(Math.min(...allVals) - 1.5);
  const yMax = Math.ceil(Math.max(...allVals) + 1.5);

  const W = 540;
  const H = 195;
  const L = 40;
  const R = 18;
  const T = 16;
  const B = 32;
  const pw = W - L - R;
  const ph = H - T - B;

  const x = (i: number) => L + (i / (allDates.length - 1)) * pw;
  const y = (v: number) => T + ((yMax - v) / Math.max(yMax - yMin, 1)) * ph;

  const hhHistPath = histHh.map((v, i) => `${i === 0 ? 'M' : 'L'} ${x(i).toFixed(1)} ${y(v).toFixed(1)}`).join(' ');
  const hvHistPath = histHv.map((v, i) => `${i === 0 ? 'M' : 'L'} ${x(i).toFixed(1)} ${y(v).toFixed(1)}`).join(' ');

  const idx9 = histDates.length - 1;
  const idx10 = allDates.length - 1;

  const hhBandPoly = `${x(idx9).toFixed(1)},${y(histHh[idx9]).toFixed(1)} ${x(idx10).toFixed(1)},${y(hhHigh).toFixed(1)} ${x(idx10).toFixed(1)},${y(hhLow).toFixed(1)}`;
  const hvBandPoly = `${x(idx9).toFixed(1)},${y(histHv[idx9]).toFixed(1)} ${x(idx10).toFixed(1)},${y(hvHigh).toFixed(1)} ${x(idx10).toFixed(1)},${y(hvLow).toFixed(1)}`;

  const ticks = [yMin, Math.round((yMin + yMax) / 2), yMax];

  return (
    <div style={{ margin: '0.55rem 0 0.7rem', background: 'rgba(7, 11, 20, 0.75)', borderRadius: '8px', padding: '0.5rem', border: '1px solid rgba(56, 189, 248, 0.16)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.73rem', color: '#94a3b8', marginBottom: '0.25rem' }}>
        <span><strong>10 Observed Passes + Pass 10 Backtest &amp; Pass 11 Forecast Fan (±95% CI)</strong></span>
        <span>Gap Jul 17&rarr;Aug 10 = 24d (Δt-normalized)</span>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label="ROI Historical and Forecast Backscatter">
        {ticks.map((tv) => (
          <g key={tv}>
            <line x1={L} x2={W - R} y1={y(tv)} y2={y(tv)} stroke="#1e293b" strokeWidth={1} />
            <text x={L - 5} y={y(tv) + 3} fontSize={8.5} fill="#94a3b8" textAnchor="end">
              {tv} dB
            </text>
          </g>
        ))}

        {/* Vertical divider at Pass 10 -> Forecast Pass 11 */}
        <line x1={x(idx9)} x2={x(idx9)} y1={T} y2={H - B} stroke="#475569" strokeDasharray="3 3" strokeWidth={1} />

        {/* 95% CI Fan Polygons */}
        <polygon points={hhBandPoly} fill="rgba(56, 189, 248, 0.18)" />
        <polygon points={hvBandPoly} fill="rgba(34, 197, 94, 0.18)" />

        {/* Historical trajectories */}
        <path d={hhHistPath} fill="none" stroke="#38bdf8" strokeWidth={2} />
        <path d={hvHistPath} fill="none" stroke="#22c55e" strokeWidth={2} />

        {/* Forecast segments (Pass 10 -> Pass 11) */}
        <line
          x1={x(idx9)}
          y1={y(histHh[idx9])}
          x2={x(idx10)}
          y2={y(roi.predicted_20261102_hh_db)}
          stroke="#38bdf8"
          strokeWidth={2}
          strokeDasharray="4 3"
        />
        <line
          x1={x(idx9)}
          y1={y(histHv[idx9])}
          x2={x(idx10)}
          y2={y(roi.predicted_20261102_hv_db)}
          stroke="#22c55e"
          strokeWidth={2}
          strokeDasharray="4 3"
        />

        {/* Historical points */}
        {histHh.map((v, i) => (
          <circle key={`hh-${i}`} cx={x(i)} cy={y(v)} r={2.3} fill="#38bdf8" />
        ))}
        {histHv.map((v, i) => (
          <circle key={`hv-${i}`} cx={x(i)} cy={y(v)} r={2.3} fill="#22c55e" />
        ))}

        {/* Held-out Pass 10 backtest hollow diamond markers */}
        {typeof roi.backtest_20261021_predicted_hh_db === 'number' && (
          <circle
            cx={x(idx9)}
            cy={y(roi.backtest_20261021_predicted_hh_db)}
            r={4.2}
            fill="none"
            stroke="#facc15"
            strokeWidth={1.6}
          />
        )}
        {typeof roi.backtest_20261021_predicted_hv_db === 'number' && (
          <circle
            cx={x(idx9)}
            cy={y(roi.backtest_20261021_predicted_hv_db)}
            r={4.2}
            fill="none"
            stroke="#facc15"
            strokeWidth={1.6}
          />
        )}

        {/* Pass 11 Forecast points */}
        <circle cx={x(idx10)} cy={y(roi.predicted_20261102_hh_db)} r={3.6} fill="#38bdf8" stroke="#0f172a" strokeWidth={1} />
        <circle cx={x(idx10)} cy={y(roi.predicted_20261102_hv_db)} r={3.6} fill="#22c55e" stroke="#0f172a" strokeWidth={1} />

        {/* X-axis labels */}
        {allDates.map((d, i) => (
          <text
            key={d}
            x={x(i)}
            y={H - 10}
            fontSize={8}
            fill={i === idx10 ? '#38bdf8' : '#94a3b8'}
            fontWeight={i === idx10 ? 700 : 400}
            textAnchor="middle"
          >
            {d.slice(5)}
          </text>
        ))}
      </svg>
      <div style={{ display: 'flex', gap: '0.85rem', flexWrap: 'wrap', fontSize: '0.71rem', color: '#cbd5e1', marginTop: '0.15rem' }}>
        <span><strong style={{ color: '#38bdf8' }}>● HH γ⁰</strong> (Surface / Dielectric)</span>
        <span><strong style={{ color: '#22c55e' }}>● HV γ⁰</strong> (Canopy Volume)</span>
        <span><strong style={{ color: '#facc15' }}>◯ Pass 10 Holdout Pred</strong> (HH err: {roi.backtest_20261021_residual_hh_db?.toFixed(2)} dB, HV err: {roi.backtest_20261021_residual_hv_db?.toFixed(2)} dB)</span>
      </div>
    </div>
  );
};

export const PredictionPanel: React.FC<Props> = ({
  selectedRoiId,
  onShowPredictionLayer,
  onFlyToRoi,
}) => {
  const [report, setReport] = useState<PredictionReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selectedSurgeIdx, setSelectedSurgeIdx] = useState<number>(0);
  const [activeLayerId, setActiveLayerId] = useState<string>('pred_flood_risk_20261102');
  const [floodValTrack, setFloodValTrack] = useState<'opera_independent' | 'sar_holdout'>('opera_independent');
  const [regimeScopeTab, setRegimeScopeTab] = useState<'cropland' | 'aoi'>('cropland');

  useEffect(() => {
    let active = true;
    loadPrediction<PredictionReport>()
      .then((data) => {
        if (active) setReport(data);
      })
      .catch((err: unknown) => {
        if (active) setError(err instanceof Error ? err.message : 'Failed to load prediction report');
      });
    return () => {
      active = false;
    };
  }, []);

  if (error) {
    return (
      <div className="workbench-section">
        <div className="data-table-card">
          <h3>Forecast &amp; Flood Risk Module Unavailable</h3>
          <p className="method-note">{error}</p>
        </div>
      </div>
    );
  }

  if (!report) {
    return (
      <div className="workbench-section">
        <div className="data-table-card">
          <p className="method-note">Loading Phase 5 Explainable Flood &amp; Crop Forecast...</p>
        </div>
      </div>
    );
  }

  const bt = report.backtest_validation_pass10_20261021;
  const btFlood = bt.flood_inundation_classification;
  const btOpera = bt.independent_optical_validation_opera_dswx;
  const btReg = bt.backscatter_regression_pass10;
  const baselines = bt.baseline_model_comparisons_pass10;
  const rollingFolds = bt.rolling_origin_temporal_cv || [];
  const spatialBlocks = bt.spatial_block_validation_pass10 || [];
  const sevenClass = bt.seven_class_regime_evaluation;

  const scenarios = report.forward_forecast_20261102.drainage_surge_scenarios;
  const activeScenario = scenarios[selectedSurgeIdx] || scenarios[0];
  const cropBreakdown = report.forward_forecast_20261102.cropland_regime_forecast_breakdown;
  const roiList = report.forward_forecast_20261102.focal_roi_forecasts;
  const activeRoi = roiList.find((r) => r.roi_id === selectedRoiId) || roiList[0];
  const exportedCogs = report.forward_forecast_20261102.exported_cogs || {};

  const handleActivateLayer = (lid: string) => {
    setActiveLayerId(lid);
    onShowPredictionLayer(lid);
  };

  const operaFull = btOpera?.vs_opera_dswx_consensus_open_water_full_aoi;
  const operaCoastal = btOpera?.vs_opera_dswx_consensus_open_water_coastal_1500m;
  const activeCalBins =
    floodValTrack === 'opera_independent' && operaFull?.calibration_10bin
      ? operaFull.calibration_10bin
      : btFlood.calibration_10bin;

  const activeRegimeEval =
    regimeScopeTab === 'cropland'
      ? sevenClass?.cropland_48day_autumn_window
      : sevenClass?.full_aoi_48day_autumn_window;

  return (
    <div className="workbench-section">
      {/* 1. PLAIN-LANGUAGE HEADER, EPISTEMIC BADGES & 4-LAYER MAP SWITCHER */}
      <div className="plain-card">
        <div className="plain-card-head">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.4rem' }}>
            <span className="plain-eyebrow">
              EXPLAINABLE NASA SAR FORECAST • NEXT PASS: {report.forecast_target_date} (+12 DAYS)
            </span>
            <span
              style={{
                fontSize: '0.68rem',
                fontWeight: 700,
                padding: '0.15rem 0.5rem',
                borderRadius: '4px',
                background: 'rgba(245, 158, 11, 0.16)',
                color: '#fbbf24',
                border: '1px solid rgba(245, 158, 11, 0.35)',
              }}
            >
              RULE 5: MODEL FORECAST (INTERPRETATION)
            </span>
          </div>
          <h3>Flood Susceptibility &amp; Dual-Pol Crop Forecaster</h3>
        </div>
        <p style={{ fontSize: '0.82rem', lineHeight: 1.5, color: '#cbd5e1', margin: '0.35rem 0 0.65rem' }}>
          Calibrated on 10 <strong>NISAR L2_GCOV</strong> passes (<code>2026-06-23</code> &rarr; <code>2026-10-21</code>,
          accounting for the 24-day gap between Jul 17 and Aug 10), 9 <strong>NISAR L2_GUNW</strong> coherence pairs,
          orthometric <strong>NISAR_DEM v1.2</strong> (EGM2008 geoid-corrected), and validated against independent{' '}
          <strong>NASA OPERA DSWx-HLS v1.0</strong> optical water masks.
        </p>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '0.45rem' }}>
          <button
            type="button"
            className={`mode-btn ${activeLayerId === 'pred_flood_risk_20261102' ? 'mode-btn-active' : ''}`}
            onClick={() => handleActivateLayer('pred_flood_risk_20261102')}
            style={{ justifyContent: 'center', fontWeight: 600, fontSize: '0.76rem', padding: '0.45rem 0.5rem' }}
          >
            🌊 Flood Susceptibility Map (Nov 02)
          </button>
          <button
            type="button"
            className={`mode-btn ${activeLayerId === 'pred_crop_regime_20261102' ? 'mode-btn-active' : ''}`}
            onClick={() => handleActivateLayer('pred_crop_regime_20261102')}
            style={{ justifyContent: 'center', fontWeight: 600, fontSize: '0.76rem', padding: '0.45rem 0.5rem' }}
          >
            🌾 7-Class Crop &amp; Moisture Map (Nov 02)
          </button>
          <button
            type="button"
            className={`mode-btn ${activeLayerId === 'pred_hh_db_20261102' ? 'mode-btn-active' : ''}`}
            onClick={() => handleActivateLayer('pred_hh_db_20261102')}
            style={{ justifyContent: 'center', fontWeight: 600, fontSize: '0.76rem', padding: '0.45rem 0.5rem' }}
          >
            📡 Forecast HH Backscatter γ⁰ (dB)
          </button>
          <button
            type="button"
            className={`mode-btn ${activeLayerId === 'pred_hv_db_20261102' ? 'mode-btn-active' : ''}`}
            onClick={() => handleActivateLayer('pred_hv_db_20261102')}
            style={{ justifyContent: 'center', fontWeight: 600, fontSize: '0.76rem', padding: '0.45rem 0.5rem' }}
          >
            🌿 Forecast HV Backscatter γ⁰ (dB)
          </button>
        </div>
      </div>

      {/* 2. HYDRAULICALLY CONNECTED DRAINAGE SURGE SIMULATOR */}
      <div className="data-table-card">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.4rem' }}>
          <span className="section-eyebrow">ENGINE 1 • HYDRAULICALLY CONNECTED HAND SURGE SIMULATOR</span>
          <span
            style={{
              fontSize: '0.68rem',
              fontWeight: 700,
              padding: '0.12rem 0.45rem',
              borderRadius: '4px',
              background:
                activeScenario.epistemic_category === 'MODEL FORECAST'
                  ? 'rgba(56, 189, 248, 0.15)'
                  : 'rgba(249, 115, 22, 0.18)',
              color: activeScenario.epistemic_category === 'MODEL FORECAST' ? '#38bdf8' : '#fb923c',
              border: '1px solid rgba(148, 163, 184, 0.25)',
            }}
          >
            {activeScenario.epistemic_category || (activeScenario.water_level_surge_m === 0 ? 'MODEL FORECAST' : 'HYPOTHETICAL SCENARIO')}
          </span>
        </div>
        <h3>Lake Qarun (-43.0 m MSL) &amp; Wadi El-Rayan Drainage Surge Scenarios</h3>
        <p className="method-note" style={{ marginBottom: '0.6rem' }}>
          Height Above Nearest Drainage (<code>HAND</code>) is computed from orthometric <code>NISAR_DEM v1.2</code>{' '}
          (<code>WGS84 ellipsoidal - 14.20 m EGM2008 geoid</code>). Surge scenarios enforce{' '}
          <strong>8-connected hydraulic path continuity</strong> from permanent water bodies so isolated upland depressions
          are never falsely flooded:
        </p>

        <div style={{ display: 'flex', gap: '0.45rem', marginBottom: '0.7rem', flexWrap: 'wrap' }}>
          {scenarios.map((sc, idx) => (
            <button
              key={sc.scenario_name}
              type="button"
              className={`mode-btn ${selectedSurgeIdx === idx ? 'mode-btn-active' : ''}`}
              onClick={() => {
                setSelectedSurgeIdx(idx);
                handleActivateLayer('pred_flood_risk_20261102');
              }}
              style={{ flex: 1, fontSize: '0.74rem', padding: '0.4rem 0.55rem' }}
            >
              {sc.water_level_surge_m === 0
                ? 'Baseline (+0.0 m Forecast)'
                : sc.water_level_surge_m === 0.5
                ? 'Hypothetical Surge (+0.5 m)'
                : 'Hypothetical Flash Surge (+1.0 m)'}
            </button>
          ))}
        </div>

        <div className="inspector-metrics-grid" style={{ gridTemplateColumns: 'repeat(2, 1fr)', gap: '0.5rem', marginBottom: '0.6rem' }}>
          <div className="metric-box">
            <span className="metric-label">Shoreline &amp; Basin at Risk</span>
            <strong className="metric-value" style={{ color: '#facc15' }}>
              {activeScenario.total_shoreline_and_basin_at_risk_ha.toLocaleString()} ha
            </strong>
            <span className="metric-sub">Non-permanent margin (&ge;35% prob or connected overtop)</span>
          </div>
          <div className="metric-box">
            <span className="metric-label">Imminent Inundation Zone</span>
            <strong className="metric-value" style={{ color: '#ef4444' }}>
              {activeScenario.imminent_inundation_ha.toLocaleString()} ha
            </strong>
            <span className="metric-sub">High susceptibility (&ge;65% prob) | Overtop: {(activeScenario.hydraulically_connected_overtop_ha ?? 0).toLocaleString()} ha</span>
          </div>
          <div className="metric-box">
            <span className="metric-label">Cropland at Flood Risk</span>
            <strong className="metric-value" style={{ color: '#f97316' }}>
              {activeScenario.agricultural_cropland_at_risk_ha.toLocaleString()} ha
            </strong>
            <span className="metric-sub">Low-lying vegetated farmland connected to lakeshore</span>
          </div>
          <div className="metric-box">
            <span className="metric-label">Road &amp; Settlement Corridors</span>
            <strong className="metric-value" style={{ color: '#38bdf8' }}>
              {activeScenario.settlement_and_road_corridor_at_risk_ha.toLocaleString()} ha
            </strong>
            <span className="metric-sub">Built-up embankments within connected surge level</span>
          </div>
        </div>

        <table className="scientific-table" style={{ fontSize: '0.74rem' }}>
          <thead>
            <tr>
              <th>Scenario</th>
              <th>Epistemic Tier</th>
              <th>Connected Overtop</th>
              <th>Total Risk</th>
              <th>Cropland</th>
              <th>Settlements</th>
            </tr>
          </thead>
          <tbody>
            {scenarios.map((sc, i) => (
              <tr
                key={sc.scenario_name}
                style={{ background: i === selectedSurgeIdx ? 'rgba(56, 189, 248, 0.08)' : undefined, cursor: 'pointer' }}
                onClick={() => setSelectedSurgeIdx(i)}
              >
                <td><strong>+{sc.water_level_surge_m.toFixed(1)} m</strong></td>
                <td><code>{sc.epistemic_category}</code></td>
                <td>{(sc.hydraulically_connected_overtop_ha ?? 0).toLocaleString()} ha</td>
                <td><strong>{sc.total_shoreline_and_basin_at_risk_ha.toLocaleString()} ha</strong></td>
                <td>{sc.agricultural_cropland_at_risk_ha.toLocaleString()} ha</td>
                <td>{sc.settlement_and_road_corridor_at_risk_ha.toLocaleString()} ha</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* 3. EXPLAINABLE AI: 4 PHYSICAL DRIVERS */}
      <div className="data-table-card">
        <span className="section-eyebrow">EXPLAINABLE AI • 4 NORMALIZED [0, 1] PHYSICAL SIGNALS (WEIGHTS = 100%)</span>
        <h3>Transparent Physical Feature Attribution</h3>
        <p className="method-note" style={{ marginBottom: '0.6rem' }}>
          Every 40 m pixel’s flood susceptibility probability is computed via a calibrated logistic link{' '}
          <code>P = σ(9.0 · (S − 0.44))</code> with dry eolian sand sheets (<code>composite_landcover == 6</code>) and
          upland plateaus gated out:
        </p>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.55rem' }}>
          {report.explainable_model_drivers.map((drv) => (
            <div
              key={drv.id}
              style={{
                background: 'rgba(15, 23, 42, 0.65)',
                border: '1px solid rgba(148, 163, 184, 0.18)',
                borderRadius: '8px',
                padding: '0.5rem 0.65rem',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.2rem' }}>
                <strong style={{ fontSize: '0.8rem', color: '#f8fafc' }}>{drv.name}</strong>
                <span
                  style={{
                    fontSize: '0.73rem',
                    fontWeight: 700,
                    color: '#38bdf8',
                    background: 'rgba(56, 189, 248, 0.12)',
                    padding: '0.08rem 0.42rem',
                    borderRadius: '4px',
                  }}
                >
                  Weight: {drv.weight_pct.toFixed(0)}%
                </span>
              </div>
              <div
                style={{
                  height: '5px',
                  background: 'rgba(51, 65, 85, 0.7)',
                  borderRadius: '3px',
                  overflow: 'hidden',
                  marginBottom: '0.3rem',
                }}
              >
                <div
                  style={{
                    width: `${drv.weight_pct}%`,
                    height: '100%',
                    background: 'linear-gradient(90deg, #0ea5e9, #22c55e)',
                  }}
                />
              </div>
              <div style={{ fontSize: '0.74rem', color: '#94a3b8' }}>
                <strong style={{ color: '#cbd5e1' }}>Source:</strong> {drv.nasa_source} — {drv.plain_explanation}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* 4. FOCAL ROI SPOTLIGHT FORECAST, TRAJECTORY FAN & SENTINEL-2 CONTEXT */}
      {activeRoi && (
        <div className="data-table-card">
          <span className="section-eyebrow">SITE-SPECIFIC EXPLAINABLE FORECAST • ALL 6 STORY FOCAL ROIS</span>
          <h3>Focal Site Spotlight: {activeRoi.title}</h3>

          <div style={{ display: 'flex', gap: '0.35rem', flexWrap: 'wrap', marginBottom: '0.6rem' }}>
            {roiList.map((r) => (
              <button
                key={r.roi_id}
                type="button"
                className={`mode-btn ${r.roi_id === activeRoi.roi_id ? 'mode-btn-active' : ''}`}
                onClick={() => onFlyToRoi && onFlyToRoi(r.wgs84_lon, r.wgs84_lat, r.roi_id)}
                style={{ fontSize: '0.72rem', padding: '0.28rem 0.5rem' }}
                title={r.title}
              >
                {roiShortName(r.roi_id)}
              </button>
            ))}
          </div>

          <div className="inspector-metrics-grid" style={{ gridTemplateColumns: 'repeat(4, 1fr)', gap: '0.45rem', marginBottom: '0.5rem' }}>
            <div className="metric-box">
              <span className="metric-label">Forecast HH (Nov 02)</span>
              <strong className="metric-value" style={{ color: '#38bdf8' }}>
                {activeRoi.predicted_20261102_hh_db.toFixed(2)} dB
              </strong>
              <span className="metric-sub">
                &plusmn;{activeRoi.predicted_20261102_hh_ci95_db.toFixed(2)} dB (95% CI)
              </span>
            </div>
            <div className="metric-box">
              <span className="metric-label">Forecast HV (Nov 02)</span>
              <strong className="metric-value" style={{ color: '#22c55e' }}>
                {activeRoi.predicted_20261102_hv_db.toFixed(2)} dB
              </strong>
              <span className="metric-sub">
                &plusmn;{activeRoi.predicted_20261102_hv_ci95_db.toFixed(2)} dB (95% CI)
              </span>
            </div>
            <div className="metric-box">
              <span className="metric-label">Flood Susceptibility</span>
              <strong
                className="metric-value"
                style={{
                  color:
                    activeRoi.flood_inundation_probability_pct >= 50
                      ? '#ef4444'
                      : activeRoi.flood_inundation_probability_pct >= 20
                      ? '#facc15'
                      : '#22c55e',
                }}
              >
                {activeRoi.flood_inundation_probability_pct.toFixed(1)}%
              </strong>
              <span className="metric-sub">{activeRoi.flood_risk_tier}</span>
            </div>
            <div className="metric-box">
              <span className="metric-label">Model Confidence</span>
              <strong className="metric-value" style={{ color: '#a855f7' }}>
                {(activeRoi.forecast_confidence_score_pct ?? 75.0).toFixed(1)}%
              </strong>
              <span className="metric-sub">1/(1 + σ_err/τ) stability</span>
            </div>
          </div>

          <RoiForecastTrajectorySvg roi={activeRoi} />

          <div style={{ fontSize: '0.76rem', color: '#cbd5e1', marginBottom: '0.45rem', display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.4rem' }}>
            <span><strong>Predicted Regime:</strong> <code>{activeRoi.predicted_regime_label}</code></span>
            {typeof activeRoi.dem_orthometric_msl_m === 'number' && (
              <span>
                <strong>DEM (MSL):</strong> <code>{activeRoi.dem_orthometric_msl_m.toFixed(1)} m</code> •{' '}
                <strong>HAND:</strong> <code>{(activeRoi.hand_above_nearest_water_m ?? 0).toFixed(1)} m</code> •{' '}
                <strong>γ̄_GUNW:</strong> <code>{(activeRoi.mean_gunw_coherence ?? 0).toFixed(3)}</code>
              </span>
            )}
          </div>

          <div className="driver-score-grid" title="Normalized driver scores (0–100) for this 5x5 patch">
            <div>
              <span>Dielectric Water (38%)</span>
              <code>{activeRoi.driver_scores_0_to_100.sar_hh_dielectric_water_index}%</code>
            </div>
            <div>
              <span>InSAR Decorrelation (24%)</span>
              <code>{activeRoi.driver_scores_0_to_100.insar_gunw_coherence_decorrelation}%</code>
            </div>
            <div>
              <span>Wetting Trend (22%)</span>
              <code>{activeRoi.driver_scores_0_to_100.multi_pass_wetting_velocity}%</code>
            </div>
            <div>
              <span>Basin Proximity (16%)</span>
              <code>{activeRoi.driver_scores_0_to_100.topographic_shoreline_basin_proximity}%</code>
            </div>
          </div>

          {activeRoi.sentinel2_ndvi_context && (
            <div
              style={{
                marginTop: '0.55rem',
                padding: '0.45rem 0.6rem',
                borderRadius: '6px',
                background: 'rgba(16, 185, 129, 0.09)',
                border: '1px solid rgba(16, 185, 129, 0.28)',
                fontSize: '0.74rem',
                color: '#d1fae5',
              }}
            >
              <strong>Independent Sentinel-2 L2A Optical Context (Rule 2):</strong> {activeRoi.sentinel2_ndvi_context.paired_scenes_count}{' '}
              cloud-free scenes | NDVI range <code>[{activeRoi.sentinel2_ndvi_context.ndvi_min.toFixed(2)}, {activeRoi.sentinel2_ndvi_context.ndvi_max.toFixed(2)}]</code>{' '}
              | Latest ({activeRoi.sentinel2_ndvi_context.latest_sentinel2_date}): <code>NDVI = {activeRoi.sentinel2_ndvi_context.latest_ndvi.toFixed(2)}</code>
              {typeof activeRoi.sentinel2_ndvi_context.hv_vs_ndvi_summer_pearson_r === 'number' && (
                <> | Summer HV-vs-NDVI <code>r = {activeRoi.sentinel2_ndvi_context.hv_vs_ndvi_summer_pearson_r.toFixed(2)}</code></>
              )}
            </div>
          )}
        </div>
      )}

      {/* 5. ENGINE 2: NEXT-PASS CROP & MOISTURE REGIME FORECAST BREAKDOWN */}
      <div className="data-table-card">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '0.5rem' }}>
          <div>
            <span className="section-eyebrow">ENGINE 2 • DUAL-POL AGRICULTURAL &amp; SURFACE REGIME FORECAST</span>
            <h3>Predicted Cropland State on Next Pass ({report.forecast_target_date})</h3>
          </div>
          <button
            type="button"
            className="mode-btn"
            onClick={() => handleActivateLayer('pred_crop_regime_20261102')}
            style={{ fontSize: '0.74rem' }}
          >
            View on Map
          </button>
        </div>
        <p className="method-note" style={{ marginBottom: '0.55rem' }}>
          Forecasts <code>HH</code> and <code>HV</code> 12 days ahead across all <code>1,208,974</code> vegetated
          agricultural pixels (<code>193,435.8 ha</code> = <code>1,934.36 km²</code>) using desert-calibrated noise
          thresholds (<code>τ_HH = 2.73 dB</code>, <code>τ_HV = 2.03 dB</code>):
        </p>

        <table className="scientific-table">
          <thead>
            <tr>
              <th>Predicted Regime (Nov 02)</th>
              <th>Cropland Area (ha)</th>
              <th>Area (km²)</th>
              <th>Share (%)</th>
            </tr>
          </thead>
          <tbody>
            {cropBreakdown.map((row) => (
              <tr key={row.regime_code}>
                <td>
                  <span
                    style={{
                      display: 'inline-block',
                      width: '10px',
                      height: '10px',
                      borderRadius: '2px',
                      backgroundColor: REGIME_COLORS[row.regime_code] || '#64748b',
                      marginRight: '6px',
                    }}
                  />
                  {row.regime_label}
                </td>
                <td>{row.area_ha.toLocaleString()} ha</td>
                <td>{row.area_km2.toFixed(2)} km²</td>
                <td>
                  <strong>{row.fraction_of_cropland_pct.toFixed(2)}%</strong>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* 6. DUAL GROUND-TRUTH FLOOD VALIDATION (INDEPENDENT OPERA DSWx-HLS vs PASS 10 SAR HOLDOUT) */}
      <div className="data-table-card">
        <span className="section-eyebrow">PHASE 2 &amp; 3 SCIENTIFIC AUDIT • GROUND-TRUTH INDEPENDENCE</span>
        <h3>Flood Susceptibility Validation &amp; Probability Calibration</h3>
        <p className="method-note" style={{ marginBottom: '0.6rem' }}>
          To prevent circular accuracy claims, we report both <strong>Track B (Independent Multi-Sensor Optical
          Validation vs. NASA JPL OPERA DSWx-HLS v1.0 &amp; NISAR_WATERMASK v0.5.0)</strong> and <strong>Track A
          (Temporal Holdout Self-Consistency on Held-Out Pass 10: 2026-10-21)</strong>:
        </p>

        <div style={{ display: 'flex', gap: '0.45rem', marginBottom: '0.7rem', flexWrap: 'wrap' }}>
          <button
            type="button"
            className={`mode-btn ${floodValTrack === 'opera_independent' ? 'mode-btn-active' : ''}`}
            onClick={() => setFloodValTrack('opera_independent')}
            style={{ flex: 1, fontSize: '0.74rem' }}
          >
            🛰️ Track B: Independent Optical (NASA OPERA DSWx-HLS)
          </button>
          <button
            type="button"
            className={`mode-btn ${floodValTrack === 'sar_holdout' ? 'mode-btn-active' : ''}`}
            onClick={() => setFloodValTrack('sar_holdout')}
            style={{ flex: 1, fontSize: '0.74rem' }}
          >
            📡 Track A: Pass 10 SAR Holdout (Self-Consistency)
          </button>
        </div>

        {floodValTrack === 'opera_independent' && operaFull && operaCoastal ? (
          <>
            <div className="inspector-metrics-grid" style={{ gridTemplateColumns: 'repeat(4, 1fr)', gap: '0.45rem', marginBottom: '0.6rem' }}>
              <div className="metric-box">
                <span className="metric-label">OPERA ROC-AUC</span>
                <strong className="metric-value" style={{ color: '#22c55e' }}>
                  {(operaFull.roc_auc * 100).toFixed(2)}%
                </strong>
                <span className="metric-sub">Coastal 1.5km: {(operaCoastal.roc_auc * 100).toFixed(2)}%</span>
              </div>
              <div className="metric-box">
                <span className="metric-label">Coastal 1.5km IoU</span>
                <strong className="metric-value" style={{ color: '#38bdf8' }}>
                  {(operaCoastal.iou * 100).toFixed(2)}%
                </strong>
                <span className="metric-sub">Full AOI IoU: {(operaFull.iou * 100).toFixed(2)}%</span>
              </div>
              <div className="metric-box">
                <span className="metric-label">Precision / Recall</span>
                <strong className="metric-value" style={{ color: '#facc15' }}>
                  {(operaFull.precision * 100).toFixed(1)}% / {(operaFull.recall * 100).toFixed(1)}%
                </strong>
                <span className="metric-sub">F1 = {operaFull.f1_score.toFixed(4)}</span>
              </div>
              <div className="metric-box">
                <span className="metric-label">Brier / ECE</span>
                <strong className="metric-value" style={{ color: '#a855f7' }}>
                  {operaFull.brier_score.toFixed(4)}
                </strong>
                <span className="metric-sub">ECE = {operaFull.calibration_10bin?.expected_calibration_error_ece.toFixed(4)}</span>
              </div>
            </div>

            <table className="scientific-table" style={{ fontSize: '0.73rem', marginBottom: '0.6rem' }}>
              <thead>
                <tr>
                  <th>Independent Benchmark Reference</th>
                  <th>Pixels (N)</th>
                  <th>ROC-AUC</th>
                  <th>IoU</th>
                  <th>F1</th>
                  <th>Precision</th>
                  <th>Recall</th>
                  <th>Brier</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td><strong>OPERA DSWx-HLS Consensus (Full AOI)</strong></td>
                  <td>{operaFull.evaluated_pixels.toLocaleString()}</td>
                  <td>{operaFull.roc_auc.toFixed(4)}</td>
                  <td><strong>{(operaFull.iou * 100).toFixed(2)}%</strong></td>
                  <td>{operaFull.f1_score.toFixed(4)}</td>
                  <td>{(operaFull.precision * 100).toFixed(2)}%</td>
                  <td>{(operaFull.recall * 100).toFixed(2)}%</td>
                  <td>{operaFull.brier_score.toFixed(4)}</td>
                </tr>
                <tr>
                  <td><strong>OPERA DSWx-HLS (Coastal 1.5 km Buffer)</strong></td>
                  <td>{operaCoastal.evaluated_pixels.toLocaleString()}</td>
                  <td>{operaCoastal.roc_auc.toFixed(4)}</td>
                  <td><strong>{(operaCoastal.iou * 100).toFixed(2)}%</strong></td>
                  <td>{operaCoastal.f1_score.toFixed(4)}</td>
                  <td>{(operaCoastal.precision * 100).toFixed(2)}%</td>
                  <td>{(operaCoastal.recall * 100).toFixed(2)}%</td>
                  <td>{operaCoastal.brier_score.toFixed(4)}</td>
                </tr>
                {btOpera?.vs_opera_dswx_20260915_open_water && (
                  <tr>
                    <td>OPERA DSWx-HLS (2026-09-15 Single Scene)</td>
                    <td>{btOpera.vs_opera_dswx_20260915_open_water.evaluated_pixels.toLocaleString()}</td>
                    <td>{btOpera.vs_opera_dswx_20260915_open_water.roc_auc.toFixed(4)}</td>
                    <td>{(btOpera.vs_opera_dswx_20260915_open_water.iou * 100).toFixed(2)}%</td>
                    <td>{btOpera.vs_opera_dswx_20260915_open_water.f1_score.toFixed(4)}</td>
                    <td>{(btOpera.vs_opera_dswx_20260915_open_water.precision * 100).toFixed(2)}%</td>
                    <td>{(btOpera.vs_opera_dswx_20260915_open_water.recall * 100).toFixed(2)}%</td>
                    <td>{btOpera.vs_opera_dswx_20260915_open_water.brier_score.toFixed(4)}</td>
                  </tr>
                )}
                {btOpera?.vs_nisar_watermask_v050_full_aoi && (
                  <tr>
                    <td>NASA NISAR_WATERMASK v0.5.0 (Static Ref)</td>
                    <td>{btOpera.vs_nisar_watermask_v050_full_aoi.evaluated_pixels.toLocaleString()}</td>
                    <td>{btOpera.vs_nisar_watermask_v050_full_aoi.roc_auc.toFixed(4)}</td>
                    <td>{(btOpera.vs_nisar_watermask_v050_full_aoi.iou * 100).toFixed(2)}%</td>
                    <td>{btOpera.vs_nisar_watermask_v050_full_aoi.f1_score.toFixed(4)}</td>
                    <td>{(btOpera.vs_nisar_watermask_v050_full_aoi.precision * 100).toFixed(2)}%</td>
                    <td>{(btOpera.vs_nisar_watermask_v050_full_aoi.recall * 100).toFixed(2)}%</td>
                    <td>{btOpera.vs_nisar_watermask_v050_full_aoi.brier_score.toFixed(4)}</td>
                  </tr>
                )}
              </tbody>
            </table>
          </>
        ) : (
          <>
            <div className="inspector-metrics-grid" style={{ gridTemplateColumns: 'repeat(4, 1fr)', gap: '0.45rem', marginBottom: '0.6rem' }}>
              <div className="metric-box">
                <span className="metric-label">Coastal ROC-AUC</span>
                <strong className="metric-value" style={{ color: '#22c55e' }}>
                  {(btFlood.roc_auc_coastal_1500m_buffer * 100).toFixed(2)}%
                </strong>
                <span className="metric-sub">Full AOI: {(btFlood.roc_auc_full_aoi * 100).toFixed(2)}%</span>
              </div>
              <div className="metric-box">
                <span className="metric-label">Coastal 1.5km IoU</span>
                <strong className="metric-value" style={{ color: '#38bdf8' }}>
                  {(btFlood.iou_coastal_1500m_buffer * 100).toFixed(2)}%
                </strong>
                <span className="metric-sub">Full AOI IoU: {(btFlood.iou_full_aoi * 100).toFixed(2)}%</span>
              </div>
              <div className="metric-box">
                <span className="metric-label">Dynamic Margin IoU</span>
                <strong className="metric-value" style={{ color: '#facc15' }}>
                  {((btFlood.iou_non_permanent_margin ?? 0.6629) * 100).toFixed(2)}%
                </strong>
                <span className="metric-sub">Non-permanent shoreline F1 = {(btFlood.f1_score_non_permanent_margin ?? 0.7973).toFixed(3)}</span>
              </div>
              <div className="metric-box">
                <span className="metric-label">Brier Score</span>
                <strong className="metric-value" style={{ color: '#a855f7' }}>
                  {btFlood.brier_score.toFixed(4)}
                </strong>
                <span className="metric-sub">TP={btFlood.confusion_matrix.true_positive_px.toLocaleString()} | FP={btFlood.confusion_matrix.false_positive_px.toLocaleString()}</span>
              </div>
            </div>
          </>
        )}

        {activeCalBins && (
          <div style={{ marginTop: '0.4rem' }}>
            <div style={{ fontSize: '0.74rem', color: '#cbd5e1', marginBottom: '0.35rem' }}>
              <strong>10-Bin Probability Calibration Curve</strong> (Expected Calibration Error{' '}
              <code>ECE = {activeCalBins.expected_calibration_error_ece.toFixed(4)}</code>):
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(10, 1fr)', gap: '4px', alignItems: 'end', height: '64px', padding: '4px 6px', background: 'rgba(7, 11, 20, 0.7)', borderRadius: '6px' }}>
              {activeCalBins.bins.map((b) => (
                <div key={b.bin_index} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', height: '100%', justifyContent: 'flex-end' }} title={`Bin ${b.bin_range}: Pred ${(b.mean_predicted_prob * 100).toFixed(1)}% vs Obs ${(b.observed_event_frequency * 100).toFixed(1)}% (N=${b.pixel_count.toLocaleString()} px)`}>
                  <div style={{ width: '100%', display: 'flex', gap: '1px', alignItems: 'flex-end', height: '46px' }}>
                    <div style={{ flex: 1, height: `${Math.max(4, b.mean_predicted_prob * 100)}%`, background: '#38bdf8', borderRadius: '2px 2px 0 0' }} />
                    <div style={{ flex: 1, height: `${Math.max(4, b.observed_event_frequency * 100)}%`, background: '#22c55e', borderRadius: '2px 2px 0 0' }} />
                  </div>
                  <span style={{ fontSize: '0.62rem', color: '#94a3b8', marginTop: '2px' }}>{b.bin_range.split('-')[1]}</span>
                </div>
              ))}
            </div>
            <div style={{ display: 'flex', gap: '1rem', fontSize: '0.69rem', color: '#94a3b8', marginTop: '0.25rem' }}>
              <span><strong style={{ color: '#38bdf8' }}>■</strong> Mean Predicted Probability</span>
              <span><strong style={{ color: '#22c55e' }}>■</strong> Observed Water Frequency</span>
            </div>
          </div>
        )}
      </div>

      {/* 7. BACKSCATTER FORECAST BENCHMARK VS BASELINES + ROLLING-ORIGIN CV */}
      <div className="data-table-card">
        <span className="section-eyebrow">PHASE 3 &amp; 4 ML VALIDATION • LEAKAGE-FREE BENCHMARK VS BASELINES</span>
        <h3>Backscatter Forecaster vs. Persistence, Moving-Average &amp; OLS Baselines</h3>
        <p className="method-note" style={{ marginBottom: '0.55rem' }}>
          Evaluated strictly out-of-sample on Held-Out Pass 10 (<code>2026-10-21</code>, <code>N = 3,070,080</code> AOI
          px; <code>N = 1,208,974</code> cropland px). Our <strong>Speckle-Aware Spatio-Temporal State-Space
          Forecaster</strong> outperforms all three baselines on both HH and HV:
        </p>

        {baselines && (
          <table className="scientific-table" style={{ fontSize: '0.73rem', marginBottom: '0.65rem' }}>
            <thead>
              <tr>
                <th>Forecasting Model (Pass 10 Holdout)</th>
                <th>HH RMSE (AOI)</th>
                <th>HH RMSE (Crop)</th>
                <th>HH R²</th>
                <th>HV RMSE (AOI)</th>
                <th>HV RMSE (Crop)</th>
                <th>HV R²</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(baselines).map(([key, b]) => {
                const isOurs = key === 'adaptive_state_space_model';
                return (
                  <tr key={key} style={{ background: isOurs ? 'rgba(34, 197, 94, 0.1)' : undefined }}>
                    <td>
                      <strong>{b.label}</strong>
                    </td>
                    <td><strong>{b.hh.rmse_db_full_aoi.toFixed(3)} dB</strong></td>
                    <td>{b.hh.rmse_db_cropland.toFixed(3)} dB</td>
                    <td>{b.hh.r2_full_aoi.toFixed(4)}</td>
                    <td><strong>{b.hv.rmse_db_full_aoi.toFixed(3)} dB</strong></td>
                    <td>{b.hv.rmse_db_cropland.toFixed(3)} dB</td>
                    <td>{b.hv.r2_full_aoi.toFixed(4)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '0.45rem', marginBottom: '0.6rem' }}>
          <div className="metric-box">
            <span className="metric-label">HH MAE / Bias (AOI)</span>
            <strong className="metric-value" style={{ fontSize: '0.88rem' }}>
              {btReg.hh_mae_db_full_aoi.toFixed(3)} dB
            </strong>
            <span className="metric-sub">Bias: {(btReg.hh_bias_db_full_aoi ?? 0).toFixed(3)} dB</span>
          </div>
          <div className="metric-box">
            <span className="metric-label">HV MAE / Bias (AOI)</span>
            <strong className="metric-value" style={{ fontSize: '0.88rem' }}>
              {btReg.hv_mae_db_full_aoi.toFixed(3)} dB
            </strong>
            <span className="metric-sub">Bias: +{(btReg.hv_bias_db_full_aoi ?? 0).toFixed(3)} dB</span>
          </div>
          <div className="metric-box">
            <span className="metric-label">HH 95% CI Coverage</span>
            <strong className="metric-value" style={{ fontSize: '0.88rem', color: '#38bdf8' }}>
              {(btReg.hh_ci95_empirical_coverage_pct ?? 86.41).toFixed(1)}%
            </strong>
            <span className="metric-sub">Mean 1σ = {(btReg.hh_mean_1sigma_uncertainty_db ?? 0.702).toFixed(2)} dB</span>
          </div>
          <div className="metric-box">
            <span className="metric-label">HV 95% CI Coverage</span>
            <strong className="metric-value" style={{ fontSize: '0.88rem', color: '#22c55e' }}>
              {(btReg.hv_ci95_empirical_coverage_pct ?? 90.87).toFixed(1)}%
            </strong>
            <span className="metric-sub">Mean 1σ = {(btReg.hv_mean_1sigma_uncertainty_db ?? 0.706).toFixed(2)} dB</span>
          </div>
        </div>

        {rollingFolds.length > 0 && (
          <>
            <div style={{ fontSize: '0.75rem', fontWeight: 600, color: '#e2e8f0', marginBottom: '0.3rem' }}>
              4-Fold Rolling-Origin Temporal Cross-Validation (Expanding Window, Passes 7&rarr;10):
            </div>
            <table className="scientific-table" style={{ fontSize: '0.72rem', marginBottom: '0.55rem' }}>
              <thead>
                <tr>
                  <th>Target Pass</th>
                  <th>Training Window</th>
                  <th>HH RMSE (Ours vs Persist)</th>
                  <th>HV RMSE (Ours vs Persist)</th>
                  <th>HH R² / HV R²</th>
                </tr>
              </thead>
              <tbody>
                {rollingFolds.map((f) => (
                  <tr key={f.fold_target_pass}>
                    <td><strong>Pass {f.fold_target_pass} ({f.target_date})</strong></td>
                    <td><code>{f.train_dates_range}</code></td>
                    <td>
                      <strong style={{ color: '#38bdf8' }}>{f.hh_rmse_db_aoi.toFixed(3)} dB</strong> vs {f.hh_persistence_rmse_db_aoi.toFixed(3)} dB
                    </td>
                    <td>
                      <strong style={{ color: '#22c55e' }}>{f.hv_rmse_db_aoi.toFixed(3)} dB</strong> vs {f.hv_persistence_rmse_db_aoi.toFixed(3)} dB
                    </td>
                    <td>{f.hh_r2_aoi.toFixed(3)} / {f.hv_r2_aoi.toFixed(3)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}

        {spatialBlocks.length > 0 && (
          <>
            <div style={{ fontSize: '0.75rem', fontWeight: 600, color: '#e2e8f0', marginBottom: '0.3rem' }}>
              4-Quadrant Spatial Block Validation on Held-Out Pass 10 (N = 767,520 px per quadrant):
            </div>
            <table className="scientific-table" style={{ fontSize: '0.72rem' }}>
              <thead>
                <tr>
                  <th>Spatial Quadrant</th>
                  <th>Pixels</th>
                  <th>HH RMSE</th>
                  <th>HH MAE</th>
                  <th>HV RMSE</th>
                  <th>HV MAE</th>
                </tr>
              </thead>
              <tbody>
                {spatialBlocks.map((sb) => (
                  <tr key={sb.block_id}>
                    <td><code>{sb.block_id}</code></td>
                    <td>{sb.pixel_count.toLocaleString()}</td>
                    <td>{sb.hh_rmse_db.toFixed(3)} dB</td>
                    <td>{sb.hh_mae_db.toFixed(3)} dB</td>
                    <td>{sb.hv_rmse_db.toFixed(3)} dB</td>
                    <td>{sb.hv_mae_db.toFixed(3)} dB</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}
      </div>

      {/* 8. SEVEN-CLASS DUAL-POL REGIME CLASSIFICATION SCORECARD & CONFUSION MATRIX */}
      {activeRegimeEval && (
        <div className="data-table-card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.4rem', marginBottom: '0.4rem' }}>
            <div>
              <span className="section-eyebrow">SEVEN-CLASS REGIME VALIDATION • PASS 10 HOLDOUT</span>
              <h3>7-Class Per-Regime Precision, Recall, F1 &amp; Confusion Matrix</h3>
            </div>
            <div style={{ display: 'flex', gap: '0.35rem' }}>
              <button
                type="button"
                className={`mode-btn ${regimeScopeTab === 'cropland' ? 'mode-btn-active' : ''}`}
                onClick={() => setRegimeScopeTab('cropland')}
                style={{ fontSize: '0.72rem', padding: '0.25rem 0.5rem' }}
              >
                Cropland (80.38% OA)
              </button>
              <button
                type="button"
                className={`mode-btn ${regimeScopeTab === 'aoi' ? 'mode-btn-active' : ''}`}
                onClick={() => setRegimeScopeTab('aoi')}
                style={{ fontSize: '0.72rem', padding: '0.25rem 0.5rem' }}
              >
                Full AOI (90.89% OA)
              </button>
            </div>
          </div>

          <div className="inspector-metrics-grid" style={{ gridTemplateColumns: 'repeat(4, 1fr)', gap: '0.45rem', marginBottom: '0.55rem' }}>
            <div className="metric-box">
              <span className="metric-label">Overall Accuracy</span>
              <strong className="metric-value" style={{ color: '#22c55e' }}>
                {(activeRegimeEval.overall_accuracy * 100).toFixed(2)}%
              </strong>
              <span className="metric-sub">N = {activeRegimeEval.evaluated_pixels.toLocaleString()} px</span>
            </div>
            <div className="metric-box">
              <span className="metric-label">Weighted F1</span>
              <strong className="metric-value" style={{ color: '#38bdf8' }}>
                {activeRegimeEval.weighted_f1.toFixed(4)}
              </strong>
              <span className="metric-sub">Support-weighted across 7 classes</span>
            </div>
            <div className="metric-box">
              <span className="metric-label">Macro F1</span>
              <strong className="metric-value" style={{ color: '#facc15' }}>
                {activeRegimeEval.macro_f1.toFixed(4)}
              </strong>
              <span className="metric-sub">Unweighted mean (incl. rare classes 5–6)</span>
            </div>
            <div className="metric-box">
              <span className="metric-label">Balanced Accuracy</span>
              <strong className="metric-value" style={{ color: '#a855f7' }}>
                {(activeRegimeEval.balanced_accuracy * 100).toFixed(2)}%
              </strong>
              <span className="metric-sub">12-day single-step OA: {((btReg.regime_12day_single_step_accuracy_cropland ?? 0.8653) * 100).toFixed(2)}%</span>
            </div>
          </div>

          <table className="scientific-table" style={{ fontSize: '0.72rem', marginBottom: '0.55rem' }}>
            <thead>
              <tr>
                <th>Class</th>
                <th>Support (px)</th>
                <th>Predicted (px)</th>
                <th>Precision</th>
                <th>Recall</th>
                <th>F1-Score</th>
              </tr>
            </thead>
            <tbody>
              {activeRegimeEval.per_class_metrics.map((c) => (
                <tr key={c.regime_code}>
                  <td>
                    <span
                      style={{
                        display: 'inline-block',
                        width: '8px',
                        height: '8px',
                        borderRadius: '2px',
                        backgroundColor: REGIME_COLORS[c.regime_code] || '#64748b',
                        marginRight: '5px',
                      }}
                    />
                    <strong>C{c.regime_code}:</strong> {c.regime_label}
                  </td>
                  <td>{c.support_px.toLocaleString()}</td>
                  <td>{c.predicted_px.toLocaleString()}</td>
                  <td>{(c.precision * 100).toFixed(1)}%</td>
                  <td>{(c.recall * 100).toFixed(1)}%</td>
                  <td><strong>{c.f1_score.toFixed(3)}</strong></td>
                </tr>
              ))}
            </tbody>
          </table>

          <details style={{ fontSize: '0.73rem', color: '#cbd5e1' }}>
            <summary style={{ cursor: 'pointer', fontWeight: 600, color: '#38bdf8', marginBottom: '0.35rem' }}>
              Show Full 7×7 Confusion Matrix (Rows = Observed Pass 10, Columns = Predicted Pass 10)
            </summary>
            <div style={{ overflowX: 'auto' }}>
              <table className="scientific-table" style={{ fontSize: '0.69rem' }}>
                <thead>
                  <tr>
                    <th>Obs \ Pred</th>
                    {[0, 1, 2, 3, 4, 5, 6].map((c) => (
                      <th key={c}>C{c}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {activeRegimeEval.confusion_matrix_7x7.map((row, rIdx) => (
                    <tr key={rIdx}>
                      <td><strong>C{rIdx}</strong></td>
                      {row.map((val, cIdx) => (
                        <td
                          key={cIdx}
                          style={{
                            fontWeight: rIdx === cIdx ? 700 : 400,
                            color: rIdx === cIdx ? '#22c55e' : val > 0 ? '#cbd5e1' : '#64748b',
                          }}
                        >
                          {val.toLocaleString()}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </details>
        </div>
      )}

      {/* 9. DIRECT NATIVE COG DOWNLOADS FOR ALL 4 PREDICTION PRODUCTS */}
      {Object.keys(exportedCogs).length > 0 && (
        <div className="data-table-card">
          <span className="section-eyebrow">CLOUD-OPTIMIZED GEOTIFF EXPORTS • NATIVE EPSG:32636 (256×256 TILED)</span>
          <h3>Download Forecast GeoTIFFs (.tif) for GIS (QGIS / ArcGIS / Python)</h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '0.45rem', marginTop: '0.45rem' }}>
            {Object.entries(exportedCogs).map(([fname, meta]) => (
              <a
                key={fname}
                href={meta.cog_url}
                download
                className="cog-download-btn"
                style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-start', padding: '0.45rem 0.6rem', textDecoration: 'none' }}
              >
                <span style={{ fontWeight: 700, fontSize: '0.73rem', color: '#f8fafc', wordBreak: 'break-all' }}>{fname}</span>
                <span style={{ fontSize: '0.68rem', color: '#bae6fd' }}>
                  {meta.size_mb.toFixed(2)} MB • EPSG:32636 • Overviews [2,4,8]
                </span>
              </a>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
