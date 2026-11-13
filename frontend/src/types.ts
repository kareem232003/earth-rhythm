export interface Rule3Metadata {
  satellite: string;
  product_type: string;
  product_version: string;
  acquisition_date: string;
  track_frame: string;
  orbit_direction: string;
  polarization: string;
  units: string;
  crs: string;
  source: string;
  epistemic_tag: 'OBSERVATION' | 'CHANGE DETECTION' | 'INTERPRETATION (hypothesis)' | string;
  [key: string]: string | undefined;
}

export interface LegendStop {
  value: number;
  color: string;
  label: string;
}

export interface LegendClass {
  code: number;
  color: string;
  label: string;
}

export interface RGBChannelSpec {
  channel: string;
  color?: string;
  range: string;
  meaning: string;
}

export interface OverlayLegend {
  type: 'continuous' | 'diverging' | 'categorical' | 'rgb_composite';
  unit: string;
  vmin?: number;
  vmax?: number;
  threshold_db?: number;
  stops?: LegendStop[];
  classes?: LegendClass[];
  channels?: RGBChannelSpec[];
}

export interface OverlayItem {
  layer_id: string;
  group:
    | 'single_date_backscatter'
    | 'change_detection'
    | 'change_detection_thresholded'
    | 'dual_pol_regimes'
    | 'seasonal_dynamic_range'
    | 'geophysical_masks'
    | 'exploratory_insar_gunw';
  title: string;
  url: string;
  cog_url: string;
  date?: string;
  interval?: string;
  date_start?: string;
  date_end?: string;
  pair?: string;
  polarization?: string;
  threshold_db?: number;
  exploratory_disclaimer?: string;
  wgs84_bounds: [number, number, number, number];
  maplibre_coordinates: [[number, number], [number, number], [number, number], [number, number]];
  width: number;
  height: number;
  size_kb: number;
  sha256: string;
  rule3_metadata: Rule3Metadata;
  legend: OverlayLegend;
}

export interface LayerCatalog {
  generated_at_utc: string;
  project: string;
  aoi: {
    name: string;
    track: number;
    frame: number;
    orbit_direction: string;
    native_crs: string;
    web_overlay_crs: string;
    utm_bounds_m: [number, number, number, number];
    wgs84_bounds: [number, number, number, number];
    maplibre_coordinates: [[number, number], [number, number], [number, number], [number, number]];
    center_lon_lat: [number, number];
    default_zoom: number;
  };
  thresholds: {
    tau_hh_db: number;
    tau_hv_db: number;
    derivation_summary: string;
  };
  dates: string[];
  overlay_count: number;
  cog_count: number;
  overlays: OverlayItem[];
}

export interface TimeSeriesPoint {
  date: string;
  granule_id?: string;
  hh_linear_mean: number;
  hh_db_mean_linear: number;
  hh_db_median: number;
  hh_db_p25: number;
  hh_db_p75: number;
  hv_linear_mean: number;
  hv_db_mean_linear: number;
  hv_db_median: number;
  hv_db_p25: number;
  hv_db_p75: number;
  hv_over_hh_db_median: number;
}

export interface InspectResponse {
  coordinates: {
    wgs84_lon: number;
    wgs84_lat: number;
    utm_epsg32636_x: number;
    utm_epsg32636_y: number;
    grid_row: number;
    grid_col: number;
  };
  sampling: {
    window_dimensions_40m_px: string;
    spatial_sample_count_40m_pixels: number;
    spatial_sample_count_native_10m_pixels: number;
    patch_area_ha: number;
    temporal_sample_count_N_dates: number;
    small_sample_disclosure: string;
  };
  geophysical_stratum: {
    landcover_code: number;
    landcover_label: string;
    low_snr_nesz_proximity_warning: boolean;
    is_permanent_water: boolean;
    is_seasonal_water_margin: boolean;
    is_vegetated_agriculture: boolean;
    is_urban_settlement: boolean;
    is_stable_desert_reference: boolean;
  };
  seasonal_summary: {
    hh_min_db: number;
    hh_max_db: number;
    hh_dynamic_range_db: number;
    hv_min_db: number;
    hv_max_db: number;
    hv_dynamic_range_db: number;
    tau_hh_db: number;
    tau_hv_db: number;
  };
  interval_evaluations: {
    [intervalKey: string]: {
      date_start: string;
      date_end: string;
      delta_hh_db: number;
      delta_hv_db: number;
      delta_hv_over_hh_db: number;
      exceeds_tau_hh: boolean;
      exceeds_tau_hv: boolean;
      regime_code: number;
      regime_label: string;
    };
  };
  epistemic_statements: {
    observation: string;
    change_detection: string;
    interpretation: string;
  };
  timeseries: TimeSeriesPoint[];
}

export interface FocalROI {
  roi_id: string;
  title: string;
  change_type: string;
  utm_epsg32636_x: number;
  utm_epsg32636_y: number;
  wgs84_lon: number;
  wgs84_lat: number;
  window_dimensions_40m_px: string;
  spatial_sample_count_40m_pixels: number;
  spatial_sample_count_native_10m_pixels: number;
  temporal_sample_count_N_dates: number;
  small_sample_disclosure: string;
  key_interval_deltas_db: {
    [key: string]: {
      delta_hh_db?: number;
      delta_hv_db?: number;
      exceeds_hh_threshold?: boolean;
      exceeds_hv_threshold?: boolean;
      hh_dynamic_range_db?: number;
      hv_dynamic_range_db?: number;
    };
  };
  observation_statement: string;
  change_detection_statement: string;
  hypothesis_statement: string;
  confounder_note: string;
  timeseries: TimeSeriesPoint[];
}

export interface Sentinel2PairedPoint {
  sentinel2_scene_id: string;
  sentinel2_date: string;
  paired_nisar_date: string;
  cloud_cover_pct: number;
  red_b04_reflectance: number | null;
  nir_b08_reflectance: number | null;
  sentinel2_ndvi_mean: number | null;
  nisar_hv_db_median: number | null;
  nisar_hh_db_median: number | null;
}

export interface StoryPayload {
  phase2_processing_and_enl: {
    crs_validation: any;
    enl_verification: any;
    geophysical_masks_summary: any;
    gunw_exploratory_evaluation: any[];
  };
  phase3_change_and_timeseries: {
    dates: string[];
    threshold_derivation: any;
    interval_change_evaluations: any;
    basin_strata_timeseries: any;
    story_mode_focal_rois: FocalROI[];
    external_context_non_nisar: {
      rule2_compliance_notice: string;
      nasa_power_meteorology: {
        source_label: string;
        total_accumulated_precipitation_mm: number;
        days_with_precip_ge_0p5mm: number;
        mean_2m_wind_speed_m_s: number;
        max_2m_wind_speed_m_s: number;
        nisar_overpass_dates_weather: {
          nisar_date: string;
          precip_mm_day: number;
          wind_speed_2m_m_s: number;
          temp_2m_degC: number;
        }[];
        scientific_implication: string;
      };
      sentinel2_l2a_optical_ndvi: {
        source_label: string;
        paired_scenes_count: number;
        roi_optical_sar_comparison: {
          [roi_id: string]: Sentinel2PairedPoint[];
        };
        hv_vs_ndvi_correlations: {
          [roi_id: string]: {
            paired_dates_count_N: number;
            small_sample_note: string;
            full_9date_pearson_r: number;
            full_9date_p_value: number;
            full_9date_spearman_rho: number;
            summer_cycle_8date_pearson_r: number;
            summer_cycle_8date_p_value: number;
          };
        };
      };
    };
  };
  phase4_serving_summary: any;
}

