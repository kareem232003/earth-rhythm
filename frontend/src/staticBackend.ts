import { InspectResponse, LayerCatalog, StoryPayload } from './types';

interface CubeMeta {
  stride: number;
  shape_t_h_w: [number, number, number];
  native_shape_h_w: [number, number];
  dates: string[];
  granule_ids: string[];
  x0: number;
  x1: number;
  y0: number;
  y1: number;
  lon_min: number;
  lon_max: number;
  lat_min: number;
  lat_max: number;
  tau_hh_db: number;
  tau_hv_db: number;
  landcover_labels: Record<string, string>;
  regime_labels: Record<string, string>;
}

let cachedFocalInspects: Record<string, InspectResponse> | null = null;
let cachedCubeMeta: CubeMeta | null = null;
let cachedCubeBuf: ArrayBuffer | null = null;

async function fetchJsonWithFallback<T>(apiUrl: string, staticUrl: string): Promise<T> {
  try {
    const r = await fetch(apiUrl);
    const ct = r.headers.get('content-type') || '';
    if (r.ok && ct.includes('application/json')) {
      return (await r.json()) as T;
    }
  } catch {
    // Fall through to static bundle
  }
  const r2 = await fetch(staticUrl);
  if (!r2.ok) {
    throw new Error(`Failed to load ${apiUrl} (and static fallback ${staticUrl})`);
  }
  return (await r2.json()) as T;
}

export async function loadCatalog(): Promise<LayerCatalog> {
  return fetchJsonWithFallback<LayerCatalog>('/api/catalog', '/static_api/catalog.json');
}

export async function loadStory(): Promise<StoryPayload> {
  return fetchJsonWithFallback<StoryPayload>('/api/story', '/static_api/story.json');
}

export async function loadBenchmark<T = any>(): Promise<T> {
  return fetchJsonWithFallback<T>('/api/benchmark', '/static_api/benchmark.json');
}

export async function loadPrediction<T = any>(): Promise<T> {
  return fetchJsonWithFallback<T>('/api/prediction', '/static_api/prediction.json');
}

async function ensureFocalInspectsLoaded(): Promise<Record<string, InspectResponse>> {
  if (!cachedFocalInspects) {
    const fRes = await fetch('/static_api/focal_inspects.json');
    cachedFocalInspects = await fRes.json();
  }
  return cachedFocalInspects!;
}

async function ensureStaticCubeLoaded(): Promise<{
  meta: CubeMeta;
  buf: ArrayBuffer;
}> {
  if (!cachedCubeMeta || !cachedCubeBuf) {
    const [mRes, bRes] = await Promise.all([
      fetch('/static_api/cube_meta.json'),
      fetch('/static_api/cube_3x.bin'),
    ]);
    cachedCubeMeta = await mRes.json();
    cachedCubeBuf = await bRes.arrayBuffer();
  }
  return {
    meta: cachedCubeMeta!,
    buf: cachedCubeBuf!,
  };
}

function round2(n: number): number {
  return Math.round(n * 100) / 100;
}

function round6(n: number): number {
  return Math.round(n * 1e6) / 1e6;
}

function dbToLin(db: number): number {
  return Math.pow(10, db / 10);
}

function linToDb(lin: number): number {
  return 10 * Math.log10(Math.max(lin, 1e-10));
}

function percentile(sorted: number[], p: number): number {
  if (sorted.length === 0) return 0;
  if (sorted.length === 1) return sorted[0];
  const idx = (p / 100) * (sorted.length - 1);
  const lo = Math.floor(idx);
  const hi = Math.ceil(idx);
  if (lo === hi) return sorted[lo];
  return sorted[lo] + (sorted[hi] - sorted[lo]) * (idx - lo);
}

export async function loadInspect(lon: number, lat: number, windowPx: number): Promise<InspectResponse> {
  try {
    const res = await fetch(`/api/inspect?lon=${lon}&lat=${lat}&window_px=${windowPx}`);
    const ct = res.headers.get('content-type') || '';
    if (res.ok && ct.includes('application/json')) {
      return (await res.json()) as InspectResponse;
    }
  } catch {
    // Fall through to static cube evaluation
  }

  const focal = await ensureFocalInspectsLoaded();
  const exactKey = `${lon.toFixed(4)}_${lat.toFixed(4)}_${windowPx}`;
  if (focal[exactKey]) {
    return focal[exactKey];
  }

  const { meta, buf } = await ensureStaticCubeLoaded();

  const [T, H3, W3] = meta.shape_t_h_w;
  const [H, W] = meta.native_shape_h_w;
  const u = Math.max(0, Math.min(1, (lon - meta.lon_min) / (meta.lon_max - meta.lon_min)));
  const v = Math.max(0, Math.min(1, (meta.lat_max - lat) / (meta.lat_max - meta.lat_min)));

  const row3 = Math.max(0, Math.min(H3 - 1, Math.round(v * (H3 - 1))));
  const col3 = Math.max(0, Math.min(W3 - 1, Math.round(u * (W3 - 1))));
  const rowNative = Math.min(H - 1, row3 * meta.stride + 1);
  const colNative = Math.min(W - 1, col3 * meta.stride + 1);

  const half3 = windowPx >= 9 ? 1 : 0;
  const r0 = Math.max(0, row3 - half3);
  const r1 = Math.min(H3, row3 + half3 + 1);
  const c0 = Math.max(0, col3 - half3);
  const c1 = Math.min(W3, col3 + half3 + 1);

  const planePixels = H3 * W3;
  const hhI16 = new Int16Array(buf, 0, T * planePixels);
  const hvI16 = new Int16Array(buf, T * planePixels * 2, T * planePixels);
  const lcU8 = new Uint8Array(buf, T * planePixels * 4, planePixels);
  const flagsU8 = new Uint8Array(buf, T * planePixels * 4 + planePixels, planePixels);

  const series = meta.dates.map((dt, t) => {
    const hhDbVals: number[] = [];
    const hvDbVals: number[] = [];
    const ratVals: number[] = [];
    let hhLinSum = 0;
    let hvLinSum = 0;

    for (let r = r0; r < r1; r++) {
      for (let c = c0; c < c1; c++) {
        const idx = t * planePixels + r * W3 + c;
        const hhDb = hhI16[idx] / 100.0;
        const hvDb = hvI16[idx] / 100.0;
        hhDbVals.push(hhDb);
        hvDbVals.push(hvDb);
        ratVals.push(hvDb - hhDb);
        hhLinSum += dbToLin(hhDb);
        hvLinSum += dbToLin(hvDb);
      }
    }

    const count = Math.max(1, hhDbVals.length);
    const hhSorted = [...hhDbVals].sort((a, b) => a - b);
    const hvSorted = [...hvDbVals].sort((a, b) => a - b);
    const ratSorted = [...ratVals].sort((a, b) => a - b);
    const hhLinMean = hhLinSum / count;
    const hvLinMean = hvLinSum / count;

    return {
      date: dt,
      granule_id: meta.granule_ids[t],
      hh_linear_mean: round6(hhLinMean),
      hh_db_mean_linear: round2(linToDb(hhLinMean)),
      hh_db_median: round2(percentile(hhSorted, 50)),
      hh_db_p25: round2(percentile(hhSorted, 25)),
      hh_db_p75: round2(percentile(hhSorted, 75)),
      hv_linear_mean: round6(hvLinMean),
      hv_db_mean_linear: round2(linToDb(hvLinMean)),
      hv_db_median: round2(percentile(hvSorted, 50)),
      hv_db_p25: round2(percentile(hvSorted, 25)),
      hv_db_p75: round2(percentile(hvSorted, 75)),
      hv_over_hh_db_median: round2(percentile(ratSorted, 50)),
    };
  });

  const classifyPair = (idxStart: number, idxEnd: number) => {
    const dHh = round2(series[idxEnd].hh_db_mean_linear - series[idxStart].hh_db_mean_linear);
    const dHv = round2(series[idxEnd].hv_db_mean_linear - series[idxStart].hv_db_mean_linear);
    const dRat = round2(dHv - dHh);
    const hhUp = dHh >= meta.tau_hh_db;
    const hhDn = dHh <= -meta.tau_hh_db;
    const hvUp = dHv >= meta.tau_hv_db;
    const hvDn = dHv <= -meta.tau_hv_db;

    let code = 0;
    if (hhUp && hvDn) code = 5;
    else if (hhDn && hvUp) code = 6;
    else if (hvUp && !hhDn) code = 1;
    else if (hvDn && !hhUp) code = 2;
    else if (hhUp) code = 3;
    else if (hhDn) code = 4;

    return {
      date_start: meta.dates[idxStart],
      date_end: meta.dates[idxEnd],
      delta_hh_db: dHh,
      delta_hv_db: dHv,
      delta_hv_over_hh_db: dRat,
      exceeds_tau_hh: Math.abs(dHh) >= meta.tau_hh_db,
      exceeds_tau_hv: Math.abs(dHv) >= meta.tau_hv_db,
      regime_code: code,
      regime_label: meta.regime_labels[String(code)] || 'Unchanged (< tau)',
    };
  };

  const intervals = {
    early_to_peak_summer_20260623_to_20260810: classifyPair(0, 3),
    peak_summer_to_autumn_20260810_to_20261021: classifyPair(3, 9),
    full_span_20260623_to_20261021: classifyPair(0, 9),
  };

  const centerIdx = row3 * W3 + col3;
  const flag = flagsU8[centerIdx];
  const lowSnr = Boolean(flag & (1 << 0));
  const isPermWater = Boolean(flag & (1 << 1));
  const isSeasonalWater = Boolean(flag & (1 << 2));
  const isVeg = Boolean(flag & (1 << 3));
  const isUrban = Boolean(flag & (1 << 4));
  const isDesert = Boolean(flag & (1 << 5));

  let lcCode = lcU8[centerIdx];
  if (isVeg && !isPermWater) lcCode = 3;
  const lcLabel = meta.landcover_labels[String(lcCode)] || 'Unclassified';

  const hhMeds = series.map((s) => s.hh_db_median);
  const hvMeds = series.map((s) => s.hv_db_median);
  const hhMin = round2(Math.min(...hhMeds));
  const hhMax = round2(Math.max(...hhMeds));
  const hvMin = round2(Math.min(...hvMeds));
  const hvMax = round2(Math.max(...hvMeds));

  const nPx = windowPx * windowPx;
  const utmX = round2(meta.x0 + u * (meta.x1 - meta.x0));
  const utmY = round2(meta.y0 + v * (meta.y1 - meta.y0));

  return {
    coordinates: {
      wgs84_lon: Number(lon.toFixed(5)),
      wgs84_lat: Number(lat.toFixed(5)),
      utm_epsg32636_x: utmX,
      utm_epsg32636_y: utmY,
      grid_row: rowNative,
      grid_col: colNative,
    },
    sampling: {
      window_dimensions_40m_px: `${windowPx}x${windowPx}`,
      spatial_sample_count_40m_pixels: nPx,
      spatial_sample_count_native_10m_pixels: nPx * 16,
      patch_area_ha: round2((nPx * 40 * 40) / 10000),
      temporal_sample_count_N_dates: meta.dates.length,
      small_sample_disclosure: `Temporal sample size N=${meta.dates.length} dates (12-day repeat from 2026-06-23 to 2026-10-21); spatial patch size N=${nPx} filtered 40m pixels (${nPx * 16} native 10m pixels).`,
    },
    geophysical_stratum: {
      landcover_code: lcCode,
      landcover_label: lcLabel,
      low_snr_nesz_proximity_warning: lowSnr,
      is_permanent_water: isPermWater,
      is_seasonal_water_margin: isSeasonalWater,
      is_vegetated_agriculture: isVeg,
      is_urban_settlement: isUrban,
      is_stable_desert_reference: isDesert,
    },
    seasonal_summary: {
      hh_min_db: hhMin,
      hh_max_db: hhMax,
      hh_dynamic_range_db: round2(hhMax - hhMin),
      hv_min_db: hvMin,
      hv_max_db: hvMax,
      hv_dynamic_range_db: round2(hvMax - hvMin),
      tau_hh_db: meta.tau_hh_db,
      tau_hv_db: meta.tau_hv_db,
    },
    interval_evaluations: intervals,
    epistemic_statements: {
      observation: `OBSERVATION: Over 10 Ascending passes (Track 129 / Frame 016), filtered HH gamma0 ranges from ${hhMin.toFixed(2)} dB to ${hhMax.toFixed(2)} dB (range ${(hhMax - hhMin).toFixed(2)} dB) and HV gamma0 ranges from ${hvMin.toFixed(2)} dB to ${hvMax.toFixed(2)} dB (range ${(hvMax - hvMin).toFixed(2)} dB).`,
      change_detection: `CHANGE DETECTION: Early-to-Peak Summer (Jun 23 -> Aug 10) log-ratio change is dHH = ${intervals.early_to_peak_summer_20260623_to_20260810.delta_hh_db >= 0 ? '+' : ''}${intervals.early_to_peak_summer_20260623_to_20260810.delta_hh_db.toFixed(2)} dB, dHV = ${intervals.early_to_peak_summer_20260623_to_20260810.delta_hv_db >= 0 ? '+' : ''}${intervals.early_to_peak_summer_20260623_to_20260810.delta_hv_db.toFixed(2)} dB (${intervals.early_to_peak_summer_20260623_to_20260810.regime_label}); Peak-to-Autumn (Aug 10 -> Oct 21) is dHH = ${intervals.peak_summer_to_autumn_20260810_to_20261021.delta_hh_db >= 0 ? '+' : ''}${intervals.peak_summer_to_autumn_20260810_to_20261021.delta_hh_db.toFixed(2)} dB, dHV = ${intervals.peak_summer_to_autumn_20260810_to_20261021.delta_hv_db >= 0 ? '+' : ''}${intervals.peak_summer_to_autumn_20260810_to_20261021.delta_hv_db.toFixed(2)} dB (${intervals.peak_summer_to_autumn_20260810_to_20261021.regime_label}).`,
      interpretation:
        `INTERPRETATION (hypothesis): Classified within \`${lcLabel}\`. ` +
        (lowSnr
          ? 'Caution: pixel operates within +3 dB of the sensor NESZ thermal noise floor (-23.3 dB HH / -24.5 dB HV).'
          : 'Signal operates well above the sensor NESZ floor.'),
    },
    timeseries: series,
  };
}

