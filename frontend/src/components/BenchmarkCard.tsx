import React, { useEffect, useState } from 'react';
import { loadBenchmark } from '../staticBackend';

interface ConfusionMetrics {
  valid_pixels: number;
  tp: number;
  fp: number;
  fn: number;
  tn: number;
  predicted_water_area_km2: number;
  truth_water_area_km2: number;
  iou: number;
  f1: number;
  precision: number;
  recall: number;
  cohens_kappa: number;
}

interface IslandCheck {
  island_total_pixels: number;
  island_area_km2: number;
  false_water_pixels: number;
  false_water_rate_pct: number;
  island_correctly_excluded_pct: number;
}

interface BenchmarkModelEntry {
  label: string;
  data_source: string;
  el_qarn_island_verification: IslandCheck;
  vs_opera_dswx_consensus_open_water: ConfusionMetrics;
  vs_nisar_watermask_v050: ConfusionMetrics;
}

interface BenchmarkReport {
  random_seed: number;
  benchmarks: {
    opera_dswx_hls_v1: {
      product: string;
      matched_dates: string[];
      consensus_open_water_pixels: number;
    };
    nisar_watermask_v050: {
      product: string;
      inland_water_pixels: number;
    };
    nisar_dem_v12_profile: {
      el_qarn_island_area_km2: number;
      el_qarn_island_dem_m: { min: number; median: number; max: number };
      lake_qarun_water_dem_m: { p10: number; median: number; p90: number };
    };
  };
  models: Record<string, BenchmarkModelEntry>;
  computed_comparison_summary: {
    best_pure_nisar_model: string;
    best_pure_nisar_iou_vs_opera: number;
    best_overall_model: string;
    best_overall_iou_vs_opera: number;
    iou_gain_v3_over_v2: number;
    el_qarn_false_water_reduction_v2_to_v3_pct_pts: number;
  };
}

export const BenchmarkCard: React.FC = () => {
  const [report, setReport] = useState<BenchmarkReport | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    loadBenchmark<BenchmarkReport>()
      .then((data: BenchmarkReport) => {
        if (active) setReport(data);
      })
      .catch((err: unknown) => {
        if (active) setError(err instanceof Error ? err.message : 'Failed to load benchmark');
      });
    return () => {
      active = false;
    };
  }, []);

  if (error) {
    return (
      <div className="data-table-card">
        <span className="section-eyebrow">RULE 2 VALIDATION • NASA BENCHMARK COMPARISON</span>
        <h3>Water &amp; Island Accuracy Benchmark</h3>
        <p className="method-note">Benchmark report unavailable ({error}).</p>
      </div>
    );
  }

  if (!report) {
    return (
      <div className="data-table-card">
        <span className="section-eyebrow">RULE 2 VALIDATION • NASA BENCHMARK COMPARISON</span>
        <h3>Water &amp; Island Accuracy Benchmark</h3>
        <p className="method-note">Loading quantitative benchmark results from /api/benchmark...</p>
      </div>
    );
  }

  const order = ['v1_baseline_lc1', 'v2_2gunw_blind_fill', 'v3_pure_nisar_9gunw', 'v4_option2_dem_fusion'];
  const demProf = report.benchmarks.nisar_dem_v12_profile;
  const summary = report.computed_comparison_summary;

  return (
    <div className="data-table-card">
      <div className="context-header" style={{ marginBottom: 6 }}>
        <span className="rule2-badge">RULE 2 VALIDATION • NASA EXTERNAL BENCHMARKS</span>
        <span className="section-eyebrow" style={{ margin: 0 }}>
          SEED = {report.random_seed}
        </span>
      </div>
      <h3>Pure-SAR Upgrade (Option 1) vs. NASA Benchmarks &amp; DEM Fusion (Option 2)</h3>
      <p className="method-note">
        The production map uses <strong>100% pure NISAR</strong> (<code>v3</code>: 10-date{' '}
        <code>L2_GCOV</code> HH/HV + all 9 <code>T129_F016</code> <code>L2_GUNW</code> coherences +
        wind-wave variability + island-preserving hole filter). Authoritative NASA datasets below are
        used strictly for independent accuracy benchmarking and Option 2 comparison: JPL{' '}
        <code>OPERA_L3_DSWX-HLS_V1</code> ({report.benchmarks.opera_dswx_hls_v1.matched_dates.join(', ')}),{' '}
        <code>NISAR_WATERMASK</code> v0.5.0, and <code>NISAR_DEM</code> v1.2. On Lake Qarun{' '}
        (median DEM {demProf.lake_qarun_water_dem_m.median} m), El-Qarn Island ({demProf.el_qarn_island_area_km2} km²)
        rises to <strong>+{demProf.el_qarn_island_dem_m.max} m</strong>.
      </p>

      <table className="sci-table">
        <thead>
          <tr>
            <th>Pipeline Stage</th>
            <th>IoU vs OPERA DSWx</th>
            <th>Precision / Recall</th>
            <th>IoU vs NISAR_WM</th>
            <th>El-Qarn False Water</th>
          </tr>
        </thead>
        <tbody>
          {order
            .filter((k) => Boolean(report.models[k]))
            .map((key) => {
              const m = report.models[key];
              const op = m.vs_opera_dswx_consensus_open_water;
              const wm = m.vs_nisar_watermask_v050;
              const iq = m.el_qarn_island_verification;
              const isProd = key === summary.best_pure_nisar_model;
              return (
                <tr key={key}>
                  <td>
                    <strong className={isProd ? 'sig-cell' : undefined}>
                      {m.label}
                      {isProd ? ' (Production)' : ''}
                    </strong>
                  </td>
                  <td>
                    <strong className={isProd ? 'sig-cell' : undefined}>{op.iou.toFixed(4)}</strong>
                  </td>
                  <td>
                    {(op.precision * 100).toFixed(2)}% / {(op.recall * 100).toFixed(2)}%
                  </td>
                  <td>{wm.iou.toFixed(4)}</td>
                  <td>
                    <strong className={iq.false_water_rate_pct < 2 ? 'sig-cell' : undefined}>
                      {iq.false_water_pixels}/{iq.island_total_pixels} ({iq.false_water_rate_pct.toFixed(2)}%)
                    </strong>
                  </td>
                </tr>
              );
            })}
        </tbody>
      </table>

      <p className="method-note" style={{ marginTop: 8, marginBottom: 0 }}>
        Verified improvement: Pure NISAR <code>v3</code> cuts El-Qarn Island false-water error by{' '}
        <strong>{summary.el_qarn_false_water_reduction_v2_to_v3_pct_pts.toFixed(1)} percentage points</strong>{' '}
        (preserving {(report.models.v3_pure_nisar_9gunw?.el_qarn_island_verification.island_correctly_excluded_pct ?? 0).toFixed(2)}%
        of the island) while lifting OPERA DSWx IoU to <strong>{summary.best_pure_nisar_iou_vs_opera.toFixed(4)}</strong>;
        exploratory Option 2 DEM fusion reaches <strong>{summary.best_overall_iou_vs_opera.toFixed(4)}</strong>.
      </p>
    </div>
  );
};

