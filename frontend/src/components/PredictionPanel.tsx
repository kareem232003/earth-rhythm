import React, { useEffect, useState } from 'react';
import { loadPrediction } from '../staticBackend';

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
  water_level_surge_m: number;
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

interface RoiForecast {
  roi_id: string;
  title: string;
  wgs84_lon: number;
  wgs84_lat: number;
  observed_20261021_hh_db: number;
  observed_20261021_hv_db: number;
  predicted_20261102_hh_db: number;
  predicted_20261102_hh_ci95_db: number;
  predicted_20261102_hv_db: number;
  predicted_20261102_hv_ci95_db: number;
  predicted_delta_hh_db: number;
  predicted_delta_hv_db: number;
  predicted_regime_code: number;
  predicted_regime_label: string;
  flood_inundation_probability_pct: number;
  flood_risk_tier: string;
  driver_scores_0_to_100: {
    sar_hh_dielectric_water_index: number;
    insar_gunw_coherence_decorrelation: number;
    multi_pass_wetting_velocity: number;
    topographic_shoreline_basin_proximity: number;
  };
}

interface PredictionReport {
  generated_at_utc: string;
  random_seed: number;
  forecast_target_date: string;
  forecast_horizon_days: number;
  training_dates: string[];
  backtest_holdout_date: string;
  explainable_model_drivers: DriverSpec[];
  backtest_validation_pass10_20261021: {
    description: string;
    flood_inundation_classification: {
      total_evaluated_pixels: number;
      roc_auc_full_aoi: number;
      roc_auc_coastal_1500m_buffer: number;
      iou_full_aoi: number;
      iou_coastal_1500m_buffer: number;
      f1_score: number;
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
    };
    backscatter_regression_pass10: {
      hh_rmse_db_full_aoi: number;
      hh_mae_db_full_aoi: number;
      hh_r2_full_aoi: number;
      hv_rmse_db_full_aoi: number;
      hv_mae_db_full_aoi: number;
      hv_r2_full_aoi: number;
      hh_rmse_db_cropland: number;
      hv_rmse_db_cropland: number;
      regime_classification_accuracy_aoi: number;
      regime_classification_accuracy_cropland: number;
    };
  };
  forward_forecast_20261102: {
    drainage_surge_scenarios: SurgeScenario[];
    cropland_regime_forecast_breakdown: CropRegimeForecast[];
    focal_roi_forecasts: RoiForecast[];
    map_overlays: {
      flood_risk_layer_id: string;
      crop_regime_layer_id: string;
    };
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
  5: '#06b6d4',
  6: '#ef4444',
};

export const PredictionPanel: React.FC<Props> = ({
  selectedRoiId,
  onShowPredictionLayer,
  onFlyToRoi,
}) => {
  const [report, setReport] = useState<PredictionReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selectedSurgeIdx, setSelectedSurgeIdx] = useState<number>(1);
  const [activeLayerId, setActiveLayerId] = useState<string>('pred_flood_risk_20261102');

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

  const btFlood = report.backtest_validation_pass10_20261021.flood_inundation_classification;
  const btReg = report.backtest_validation_pass10_20261021.backscatter_regression_pass10;
  const scenarios = report.forward_forecast_20261102.drainage_surge_scenarios;
  const activeScenario = scenarios[selectedSurgeIdx] || scenarios[0];
  const cropBreakdown = report.forward_forecast_20261102.cropland_regime_forecast_breakdown;
  const roiList = report.forward_forecast_20261102.focal_roi_forecasts;
  const activeRoi = roiList.find((r) => r.roi_id === selectedRoiId) || roiList[0];

  const handleActivateLayer = (lid: string) => {
    setActiveLayerId(lid);
    onShowPredictionLayer(lid);
  };

  return (
    <div className="workbench-section">
      {/* 1. PLAIN-LANGUAGE HEADER & MAP LAYER SWITCHER */}
      <div className="plain-card">
        <div className="plain-card-head">
          <span className="plain-eyebrow">EXPLAINABLE NASA SAR FORECAST • NEXT PASS: {report.forecast_target_date} (+12 DAYS)</span>
          <h3>Flood Inundation &amp; Crop Phenology Predictor</h3>
        </div>
        <p style={{ fontSize: '0.84rem', lineHeight: 1.5, color: '#cbd5e1', margin: '0.4rem 0 0.8rem' }}>
          Using 10 calibrated <strong>NISAR L2_GCOV</strong> radar passes, 9 <strong>NISAR L2_GUNW</strong> interferometric
          coherence pairs, <strong>NASA OPERA DSWx-HLS</strong> water masks, and the <strong>NASA NISAR_DEM</strong> elevation
          model, this module forecasts the next 12-day satellite pass (<strong>{report.forecast_target_date}</strong>) and maps
          which shorelines and farms face flood risk.
        </p>

        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
          <button
            type="button"
            className={`mode-btn ${activeLayerId === 'pred_flood_risk_20261102' ? 'mode-btn-active' : ''}`}
            onClick={() => handleActivateLayer('pred_flood_risk_20261102')}
            style={{ flex: 1, minWidth: '210px', justifyContent: 'center', fontWeight: 600 }}
          >
            🌊 Show Flood Risk Map (Nov 02)
          </button>
          <button
            type="button"
            className={`mode-btn ${activeLayerId === 'pred_crop_regime_20261102' ? 'mode-btn-active' : ''}`}
            onClick={() => handleActivateLayer('pred_crop_regime_20261102')}
            style={{ flex: 1, minWidth: '210px', justifyContent: 'center', fontWeight: 600 }}
          >
            🌾 Show Crop &amp; Moisture Forecast (Nov 02)
          </button>
        </div>
      </div>

      {/* 2. INTERACTIVE DRAINAGE SURGE SIMULATOR (OPTION 1: FLOOD PREDICTION) */}
      <div className="data-table-card">
        <span className="section-eyebrow">OPTION 1 • HYDROLOGICAL FLOOD &amp; SHORELINE INUNDATION SIMULATOR</span>
        <h3>Lake Qarun &amp; Wadi El-Rayan Drainage Surge Scenarios ({report.forecast_target_date})</h3>
        <p className="method-note" style={{ marginBottom: '0.65rem' }}>
          Fayoum is a closed basin (<code>-43 m</code> below sea level): all agricultural drainage flows into Lake Qarun and
          Wadi El-Rayan. Select an inflow water-level scenario below to see how many hectares of low-lying shoreline and
          farmland (<code>HAND &le; surge</code> in NASA <code>NISAR_DEM</code>) are predicted to flood:
        </p>

        <div style={{ display: 'flex', gap: '0.45rem', marginBottom: '0.75rem', flexWrap: 'wrap' }}>
          {scenarios.map((sc, idx) => (
            <button
              key={sc.scenario_name}
              type="button"
              className={`mode-btn ${selectedSurgeIdx === idx ? 'mode-btn-active' : ''}`}
              onClick={() => {
                setSelectedSurgeIdx(idx);
                handleActivateLayer('pred_flood_risk_20261102');
              }}
              style={{ flex: 1, fontSize: '0.76rem', padding: '0.4rem 0.6rem' }}
            >
              {sc.water_level_surge_m === 0
                ? 'Baseline (+0.0 m Normal)'
                : sc.water_level_surge_m === 0.5
                ? 'Moderate Surge (+0.5 m)'
                : 'Severe Flash Surge (+1.0 m)'}
            </button>
          ))}
        </div>

        <div className="inspector-metrics-grid" style={{ gridTemplateColumns: 'repeat(2, 1fr)', gap: '0.55rem' }}>
          <div className="metric-box">
            <span className="metric-label">Shoreline &amp; Basin at Risk</span>
            <strong className="metric-value" style={{ color: '#facc15' }}>
              {activeScenario.total_shoreline_and_basin_at_risk_ha.toLocaleString()} ha
            </strong>
            <span className="metric-sub">Mudflats, fish farms &amp; wetland margins (&ge;35% prob)</span>
          </div>
          <div className="metric-box">
            <span className="metric-label">Imminent Inundation Zone</span>
            <strong className="metric-value" style={{ color: '#ef4444' }}>
              {activeScenario.imminent_inundation_ha.toLocaleString()} ha
            </strong>
            <span className="metric-sub">High-confidence shoreline overtopping (&ge;65% prob)</span>
          </div>
          <div className="metric-box">
            <span className="metric-label">Cropland at Flood Risk</span>
            <strong className="metric-value" style={{ color: '#f97316' }}>
              {activeScenario.agricultural_cropland_at_risk_ha.toLocaleString()} ha
            </strong>
            <span className="metric-sub">Low-lying vegetated farmland along lakeshore</span>
          </div>
          <div className="metric-box">
            <span className="metric-label">Road &amp; Settlement Corridors</span>
            <strong className="metric-value" style={{ color: '#38bdf8' }}>
              {activeScenario.settlement_and_road_corridor_at_risk_ha.toLocaleString()} ha
            </strong>
            <span className="metric-sub">Built-up embankments within surge elevation</span>
          </div>
        </div>
      </div>

      {/* 3. EXPLAINABLE AI: WHY DOES THE MODEL PREDICT THIS? (4 PHYSICAL DRIVERS) */}
      <div className="data-table-card">
        <span className="section-eyebrow">EXPLAINABLE AI • 4 PHYSICAL NASA SIGNALS (WEIGHTS SUM TO 100%)</span>
        <h3>How the Flood &amp; Moisture Predictor Works (In Plain Words)</h3>
        <p className="method-note" style={{ marginBottom: '0.65rem' }}>
          No black-box guessing: every pixel’s flood risk score is a transparent weighted combination of 4 physical
          measurements from NASA satellites:
        </p>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
          {report.explainable_model_drivers.map((drv) => (
            <div
              key={drv.id}
              style={{
                background: 'rgba(15, 23, 42, 0.65)',
                border: '1px solid rgba(148, 163, 184, 0.18)',
                borderRadius: '8px',
                padding: '0.55rem 0.7rem',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.25rem' }}>
                <strong style={{ fontSize: '0.82rem', color: '#f8fafc' }}>{drv.name}</strong>
                <span
                  style={{
                    fontSize: '0.75rem',
                    fontWeight: 700,
                    color: '#38bdf8',
                    background: 'rgba(56, 189, 248, 0.12)',
                    padding: '0.1rem 0.45rem',
                    borderRadius: '4px',
                  }}
                >
                  Weight: {drv.weight_pct.toFixed(0)}%
                </span>
              </div>
              <div
                style={{
                  height: '6px',
                  background: 'rgba(51, 65, 85, 0.7)',
                  borderRadius: '3px',
                  overflow: 'hidden',
                  marginBottom: '0.35rem',
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
              <div style={{ fontSize: '0.76rem', color: '#94a3b8' }}>
                <strong style={{ color: '#cbd5e1' }}>Source:</strong> {drv.nasa_source} — {drv.plain_explanation}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* 4. OPTION 2: NEXT-PASS CROP & MOISTURE REGIME FORECAST (2026-11-02) */}
      <div className="data-table-card">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '0.5rem' }}>
          <div>
            <span className="section-eyebrow">OPTION 2 • AGRICULTURAL PHENOLOGY &amp; MOISTURE FORECAST</span>
            <h3>Predicted Cropland State on Next Pass ({report.forecast_target_date})</h3>
          </div>
          <button
            type="button"
            className="mode-btn"
            onClick={() => handleActivateLayer('pred_crop_regime_20261102')}
            style={{ fontSize: '0.75rem' }}
          >
            View on Map
          </button>
        </div>
        <p className="method-note" style={{ marginBottom: '0.6rem' }}>
          Forecasts `HH` (soil/water moisture) and `HV` (crop canopy volume) 12 days ahead across all{' '}
          <code>193,435 ha</code> (<code>1,934.35 km²</code>) of Fayoum vegetated farmland:
        </p>

        <table className="scientific-table">
          <thead>
            <tr>
              <th>Predicted Regime (Nov 02)</th>
              <th>Cropland Area (ha)</th>
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
                <td>
                  <strong>{row.fraction_of_cropland_pct.toFixed(2)}%</strong>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* 5. FOCAL ROI SPOTLIGHT FORECAST & DRIVER BREAKDOWN */}
      {activeRoi && (
        <div className="data-table-card">
          <span className="section-eyebrow">SITE-SPECIFIC FORECAST • CLICK ANY ROI TO INSPECT</span>
          <h3>Focal Site Forecast: {activeRoi.title}</h3>
          <div style={{ display: 'flex', gap: '0.35rem', flexWrap: 'wrap', marginBottom: '0.65rem' }}>
            {roiList.map((r) => (
              <button
                key={r.roi_id}
                type="button"
                className={`mode-btn ${r.roi_id === activeRoi.roi_id ? 'mode-btn-active' : ''}`}
                onClick={() => onFlyToRoi && onFlyToRoi(r.wgs84_lon, r.wgs84_lat, r.roi_id)}
                style={{ fontSize: '0.72rem', padding: '0.28rem 0.5rem' }}
              >
                {r.title.split('(')[0].trim()}
              </button>
            ))}
          </div>

          <div className="inspector-metrics-grid" style={{ gridTemplateColumns: 'repeat(3, 1fr)', gap: '0.45rem', marginBottom: '0.6rem' }}>
            <div className="metric-box">
              <span className="metric-label">Predicted HH (Nov 02)</span>
              <strong className="metric-value">
                {activeRoi.predicted_20261102_hh_db.toFixed(2)} dB
              </strong>
              <span className="metric-sub">
                &plusmn;{activeRoi.predicted_20261102_hh_ci95_db.toFixed(2)} dB (Oct 21: {activeRoi.observed_20261021_hh_db.toFixed(2)} dB)
              </span>
            </div>
            <div className="metric-box">
              <span className="metric-label">Predicted HV (Nov 02)</span>
              <strong className="metric-value">
                {activeRoi.predicted_20261102_hv_db.toFixed(2)} dB
              </strong>
              <span className="metric-sub">
                &plusmn;{activeRoi.predicted_20261102_hv_ci95_db.toFixed(2)} dB (Oct 21: {activeRoi.observed_20261021_hv_db.toFixed(2)} dB)
              </span>
            </div>
            <div className="metric-box">
              <span className="metric-label">Flood Inundation Risk</span>
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
          </div>

          <div style={{ fontSize: '0.78rem', color: '#cbd5e1' }}>
            <strong>Predicted Regime:</strong> <code>{activeRoi.predicted_regime_label}</code> —{' '}
            <span>
              Dielectric Water Score: <code>{activeRoi.driver_scores_0_to_100.sar_hh_dielectric_water_index}%</code>, InSAR
              Decorrelation: <code>{activeRoi.driver_scores_0_to_100.insar_gunw_coherence_decorrelation}%</code>, Wetting
              Velocity: <code>{activeRoi.driver_scores_0_to_100.multi_pass_wetting_velocity}%</code>, Basin Proximity:{' '}
              <code>{activeRoi.driver_scores_0_to_100.topographic_shoreline_basin_proximity}%</code>.
            </span>
          </div>
        </div>
      )}

      {/* 6. SCIENTIFIC PROOF: HELD-OUT PASS 10 BACKTEST SCORECARD */}
      <div className="data-table-card">
        <span className="section-eyebrow">VERIFIED ACCURACY • TEMPORAL HOLDOUT BACKTEST ON PASS 10 (2026-10-21)</span>
        <h3>Why You Can Trust This Forecast (Real Backtest Scorecard)</h3>
        <p className="method-note" style={{ marginBottom: '0.6rem' }}>
          To prove accuracy without guessing, we hid the real <strong>2026-10-21 (Pass 10)</strong> satellite acquisition,
          trained the model strictly on <strong>Passes 1..9 (Jun 23 &rarr; Oct 09)</strong>, predicted Pass 10, and scored the
          prediction against the actual observed NASA Pass 10 data across all <code>{btFlood.total_evaluated_pixels.toLocaleString()}</code> pixels:
        </p>

        <div className="inspector-metrics-grid" style={{ gridTemplateColumns: 'repeat(3, 1fr)', gap: '0.5rem', marginBottom: '0.65rem' }}>
          <div className="metric-box">
            <span className="metric-label">Flood ROC-AUC (Shoreline)</span>
            <strong className="metric-value" style={{ color: '#22c55e' }}>
              {(btFlood.roc_auc_coastal_1500m_buffer * 100).toFixed(2)}%
            </strong>
            <span className="metric-sub">Full AOI ROC-AUC: {btFlood.roc_auc_full_aoi.toFixed(4)}</span>
          </div>
          <div className="metric-box">
            <span className="metric-label">Shoreline Flood IoU / F1</span>
            <strong className="metric-value" style={{ color: '#38bdf8' }}>
              {(btFlood.iou_coastal_1500m_buffer * 100).toFixed(2)}%
            </strong>
            <span className="metric-sub">F1 = {btFlood.f1_score.toFixed(4)} | Recall = {(btFlood.recall * 100).toFixed(2)}%</span>
          </div>
          <div className="metric-box">
            <span className="metric-label">Next-Pass Radar RMSE</span>
            <strong className="metric-value" style={{ color: '#a855f7' }}>
              {btReg.hv_rmse_db_full_aoi.toFixed(2)} dB (HV)
            </strong>
            <span className="metric-sub">
              HH RMSE = {btReg.hh_rmse_db_full_aoi.toFixed(2)} dB (R&sup2; = {btReg.hh_r2_full_aoi.toFixed(3)})
            </span>
          </div>
        </div>

        <table className="scientific-table">
          <thead>
            <tr>
              <th>Held-Out Pass 10 Confusion Matrix (N = {btFlood.total_evaluated_pixels.toLocaleString()} px)</th>
              <th>Observed Water (Pass 10)</th>
              <th>Observed Dry Land (Pass 10)</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td><strong>Predicted Inundated (&ge;50% prob)</strong></td>
              <td>TP = <code>{btFlood.confusion_matrix.true_positive_px.toLocaleString()}</code> px</td>
              <td>FP = <code>{btFlood.confusion_matrix.false_positive_px.toLocaleString()}</code> px</td>
            </tr>
            <tr>
              <td><strong>Predicted Dry (&lt;50% prob)</strong></td>
              <td>FN = <code>{btFlood.confusion_matrix.false_negative_px.toLocaleString()}</code> px</td>
              <td>TN = <code>{btFlood.confusion_matrix.true_negative_px.toLocaleString()}</code> px</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  );
};

