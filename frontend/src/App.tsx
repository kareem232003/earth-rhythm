import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Activity,
  AlertTriangle,
  BookOpen,
  ChevronLeft,
  ChevronRight,
  Compass,
  Crosshair,
  Database,
  Download,
  Info,
  Layers,
  LayoutDashboard,
  Lightbulb,
  Pause,
  Play,
  Sliders,
  Sparkles,
  SplitSquareHorizontal,
  TrendingUp,
} from 'lucide-react';
import { BasemapType, NisarMap } from './components/NisarMap';
import { EchoHelper, EchoUiContext } from './components/EchoHelper';
import { TimeSeriesChart } from './components/TimeSeriesChart';
import { BenchmarkCard } from './components/BenchmarkCard';
import { DashboardsPanel } from './components/DashboardsPanel';
import { GuidePanel } from './components/GuidePanel';
import { PredictionPanel } from './components/PredictionPanel';
import { InspectorPlainReadout, MapReadingGuide, StoryPlainCard } from './components/PlainReadouts';
import { Disclosure } from './components/Disclosure';
import { STORY_STEPS } from './storySteps';
import { loadCatalog, loadInspect, loadStory } from './staticBackend';
import { FocalROI, InspectResponse, LayerCatalog, OverlayItem, StoryPayload } from './types';
import { CHANGE_METRIC_LABELS, MAP_MODE_LABELS, POL_LABELS, roiShortName, shortDate } from './uiLabels';

type MapMode = 'single' | 'swipe' | 'change' | 'masks';
type WorkbenchTab = 'story' | 'inspector' | 'metadata' | 'methods' | 'dashboards' | 'forecast' | 'guide';
type HelpTab = 'guide' | 'metadata' | 'methods';
type ChangeMetric = 'HH' | 'HV' | 'HV_over_HH' | 'regime' | 'dyn_HH' | 'dyn_HV';

// The 7 workbench views are grouped into 5 top-level tabs; "Help & data" holds 3 sub-views.
const HELP_TABS: HelpTab[] = ['guide', 'metadata', 'methods'];
const isHelpTab = (t: WorkbenchTab): t is HelpTab => (HELP_TABS as string[]).includes(t);
const MODE_ICONS: Record<MapMode, React.ElementType> = {
  single: Layers,
  swipe: SplitSquareHorizontal,
  change: Activity,
  masks: Compass,
};

export const App: React.FC = () => {
  const [catalog, setCatalog] = useState<LayerCatalog | null>(null);
  const [storyData, setStoryData] = useState<StoryPayload | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Map & Layer Controls
  const [mapMode, setMapMode] = useState<MapMode>('single');
  const [basemap, setBasemap] = useState<BasemapType>('satellite');
  const [opacity, setOpacity] = useState<number>(0.88);

  // Single-date controls
  const [activeDateIdx, setActiveDateIdx] = useState<number>(3); // Default 2026-08-10 (Peak Summer)
  const [singlePol, setSinglePol] = useState<'HH' | 'HV' | 'RGB'>('RGB');
  const [isPlaying, setIsPlaying] = useState<boolean>(false);

  // Swipe mode layer IDs
  const [swipeLeftId, setSwipeLeftId] = useState<string>('gcov_20260623_HV');
  const [swipeRightId, setSwipeRightId] = useState<string>('gcov_20260810_HV');

  // Change mode controls
  const [changeInterval, setChangeInterval] = useState<string>('20260623_to_20260810');
  const [changeMetric, setChangeMetric] = useState<ChangeMetric>('HV');
  const [thresholdMaskOnly, setThresholdMaskOnly] = useState<boolean>(true);

  // Masks & Exploratory GUNW controls
  const [selectedMaskLayerId, setSelectedMaskLayerId] = useState<string>('mask_composite_landcover');

  // Workbench & Story Mode state
  const [activeTab, setActiveTab] = useState<WorkbenchTab>('story');
  const [storyStepIdx, setStoryStepIdx] = useState<number>(0);

  // Inspector state
  const [selectedRoiId, setSelectedRoiId] = useState<string>('ROI_01_SUMMER_CROP_HARVEST');
  const [inspectResult, setInspectResult] = useState<InspectResponse | null>(null);
  const [inspectWindowPx, setInspectWindowPx] = useState<number>(5);
  const [inspectedLonLat, setInspectedLonLat] = useState<[number, number] | null>([30.9806, 29.3201]);
  const [showS2Overlay, setShowS2Overlay] = useState<boolean>(true);
  const [flyToTarget, setFlyToTarget] = useState<{ center: [number, number]; zoom: number; seq: number } | null>(null);
  const [isEchoOpen, setIsEchoOpen] = useState<boolean>(false);

  // Simplified-header popovers (technical data details & map settings) and last-used Help sub-view
  const [showDataDetails, setShowDataDetails] = useState<boolean>(false);
  const [showMapSettings, setShowMapSettings] = useState<boolean>(false);
  const [lastHelpTab, setLastHelpTab] = useState<HelpTab>('guide');
  const dataDetailsRef = useRef<HTMLDivElement | null>(null);
  const mapSettingsRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!showDataDetails && !showMapSettings) return;
    const onDown = (e: MouseEvent) => {
      const t = e.target as Node;
      if (showDataDetails && dataDetailsRef.current && !dataDetailsRef.current.contains(t)) setShowDataDetails(false);
      if (showMapSettings && mapSettingsRef.current && !mapSettingsRef.current.contains(t)) setShowMapSettings(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setShowDataDetails(false);
        setShowMapSettings(false);
      }
    };
    document.addEventListener('mousedown', onDown);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDown);
      document.removeEventListener('keydown', onKey);
    };
  }, [showDataDetails, showMapSettings]);

  const openTab = useCallback((tab: WorkbenchTab) => {
    if (isHelpTab(tab)) setLastHelpTab(tab);
    setActiveTab(tab);
  }, []);

  // Fetch initial catalog, story payload, and default ROI inspection
  useEffect(() => {
    async function loadInitial() {
      try {
        setLoading(true);
        const [catJson, storyJson, inspJson] = await Promise.all([
          loadCatalog(),
          loadStory(),
          loadInspect(30.9806, 29.3201, 5),
        ]);
        setCatalog(catJson);
        setStoryData(storyJson);
        setInspectResult(inspJson);
      } catch (err: any) {
        setError(err.message || 'Unknown error loading data');
      } finally {
        setLoading(false);
      }
    }
    loadInitial();
  }, []);

  // Time-slider animation loop
  useEffect(() => {
    if (!isPlaying || !catalog) return;
    const timer = window.setInterval(() => {
      setActiveDateIdx((prev) => (prev + 1) % catalog.dates.length);
    }, 1100);
    return () => window.clearInterval(timer);
  }, [isPlaying, catalog]);

  const dates = catalog?.dates || [];
  const activeDate = dates[activeDateIdx] || '2026-08-10';

  // Resolve active Left and Right overlays based on current mode
  const { leftOverlay, rightOverlay } = useMemo(() => {
    if (!catalog) return { leftOverlay: undefined, rightOverlay: undefined };
    const byId = new Map<string, OverlayItem>(catalog.overlays.map((o) => [o.layer_id, o]));

    if (mapMode === 'single') {
      const dtCompact = activeDate.replace(/-/g, '');
      const lid = `gcov_${dtCompact}_${singlePol}`;
      return { leftOverlay: byId.get(lid), rightOverlay: undefined };
    }

    if (mapMode === 'swipe') {
      return {
        leftOverlay: byId.get(swipeLeftId),
        rightOverlay: byId.get(swipeRightId),
      };
    }

    if (mapMode === 'change') {
      if (changeMetric === 'dyn_HH') {
        return { leftOverlay: byId.get('seasonal_dynamic_range_HH'), rightOverlay: undefined };
      }
      if (changeMetric === 'dyn_HV') {
        return { leftOverlay: byId.get('seasonal_dynamic_range_HV'), rightOverlay: undefined };
      }
      if (changeMetric === 'regime') {
        return { leftOverlay: byId.get(`dual_pol_regime_${changeInterval}`), rightOverlay: undefined };
      }
      if (changeMetric === 'HV_over_HH') {
        return { leftOverlay: byId.get(`delta_HV_over_HH_${changeInterval}`), rightOverlay: undefined };
      }
      const suffix = thresholdMaskOnly ? '_sig' : '';
      const lid = `delta_${changeMetric}_${changeInterval}${suffix}`;
      return { leftOverlay: byId.get(lid), rightOverlay: undefined };
    }

    // mapMode === 'masks'
    return { leftOverlay: byId.get(selectedMaskLayerId), rightOverlay: undefined };
  }, [
    catalog,
    mapMode,
    activeDate,
    singlePol,
    swipeLeftId,
    swipeRightId,
    changeInterval,
    changeMetric,
    thresholdMaskOnly,
    selectedMaskLayerId,
  ]);

  // Query live /api/inspect at any (lon, lat)
  const triggerInspect = useCallback(
    async (lon: number, lat: number, winPx: number = inspectWindowPx, matchedRoiId?: string) => {
      setInspectedLonLat([lon, lat]);
      if (matchedRoiId) {
        setSelectedRoiId(matchedRoiId);
      } else {
        setSelectedRoiId('CUSTOM_PIXEL');
      }
      try {
        const data = await loadInspect(lon, lat, winPx);
        setInspectResult(data);
      } catch {
        // Ignore transient network errors
      }
    },
    [inspectWindowPx]
  );

  // Select a curated Focal ROI
  const handleSelectRoi = useCallback(
    (roi: FocalROI, fly: boolean = true) => {
      setSelectedRoiId(roi.roi_id);
      triggerInspect(roi.wgs84_lon, roi.wgs84_lat, inspectWindowPx, roi.roi_id);
      if (fly) {
        setFlyToTarget({
          center: [roi.wgs84_lon, roi.wgs84_lat],
          zoom: 12.2,
          seq: Date.now(),
        });
      }
    },
    [inspectWindowPx, triggerInspect]
  );

  // Activate a Story Mode step
  const applyStoryStep = useCallback(
    (idx: number) => {
      const step = STORY_STEPS[idx];
      if (!step || !storyData) return;
      setStoryStepIdx(idx);
      setMapMode(step.mapMode);

      if (step.mapMode === 'single') {
        if (step.primaryLayerId.endsWith('_RGB')) setSinglePol('RGB');
        else if (step.primaryLayerId.endsWith('_HV')) setSinglePol('HV');
        else setSinglePol('HH');
      } else if (step.mapMode === 'swipe') {
        setSwipeLeftId(step.primaryLayerId);
        if (step.swipeRightLayerId) setSwipeRightId(step.swipeRightLayerId);
      } else if (step.mapMode === 'change') {
        if (step.primaryLayerId === 'seasonal_dynamic_range_HH') {
          setChangeMetric('dyn_HH');
        } else if (step.primaryLayerId.startsWith('dual_pol_regime_')) {
          setChangeMetric('regime');
          setChangeInterval(step.primaryLayerId.replace('dual_pol_regime_', ''));
        } else if (step.primaryLayerId.startsWith('delta_HV_')) {
          setChangeMetric('HV');
          const iv = step.primaryLayerId.replace('delta_HV_', '').replace('_sig', '');
          setChangeInterval(iv);
          setThresholdMaskOnly(step.primaryLayerId.endsWith('_sig'));
        }
      } else if (step.mapMode === 'masks') {
        setSelectedMaskLayerId(step.primaryLayerId);
      }

      const rois = storyData.phase3_change_and_timeseries.story_mode_focal_rois;
      const targetRoi = rois.find((r) => r.roi_id === step.roiId);
      if (targetRoi) {
        triggerInspect(targetRoi.wgs84_lon, targetRoi.wgs84_lat, 5, targetRoi.roi_id);
      }
      setFlyToTarget({
        center: step.center,
        zoom: step.zoom,
        seq: Date.now(),
      });
    },
    [storyData, triggerInspect]
  );

  if (loading) {
    return (
      <div className="loading-screen">
        <div className="loading-card">
          <div className="spinner-ring" />
          <h2>EARTH RHYTHM — NISAR Surface Change Storyteller</h2>
          <p>Loading calibrated 10-date NISAR L2_GCOV &amp; L2_GUNW catalog (Fayoum Oasis, Track 129 / Frame 016)...</p>
        </div>
      </div>
    );
  }

  if (error || !catalog || !storyData) {
    return (
      <div className="loading-screen">
        <div className="loading-card error-card">
          <AlertTriangle size={36} color="#ef4444" />
          <h2>Backend Connection Error</h2>
          <p>{error || 'Unable to load catalog.'}</p>
        </div>
      </div>
    );
  }

  const focalRois = storyData.phase3_change_and_timeseries.story_mode_focal_rois;
  const activeStep = STORY_STEPS[storyStepIdx];
  const s2ComparisonByRoi =
    storyData.phase3_change_and_timeseries.external_context_non_nisar.sentinel2_l2a_optical_ndvi
      .roi_optical_sar_comparison;
  const s2Correlations =
    storyData.phase3_change_and_timeseries.external_context_non_nisar.sentinel2_l2a_optical_ndvi
      .hv_vs_ndvi_correlations;
  const nasaPower = storyData.phase3_change_and_timeseries.external_context_non_nisar.nasa_power_meteorology;

  const activeS2Points = selectedRoiId && s2ComparisonByRoi[selectedRoiId] ? s2ComparisonByRoi[selectedRoiId] : undefined;
  const activeS2Corr = selectedRoiId && s2Correlations[selectedRoiId] ? s2Correlations[selectedRoiId] : undefined;

  // Dashboards -> map shortcuts (additive helpers; they only set existing map state).
  const showRegimeOnMap = (intervalMapKey: string) => {
    setIsPlaying(false);
    setMapMode('change');
    setChangeMetric('regime');
    setChangeInterval(intervalMapKey);
  };
  const showDateOnMap = (dt: string) => {
    const i = dates.indexOf(dt);
    if (i >= 0) {
      setIsPlaying(false);
      setMapMode('single');
      setActiveDateIdx(i);
    }
  };
  const showPredictionLayerOnMap = (layerId: string) => {
    setIsPlaying(false);
    setMapMode('masks');
    setSelectedMaskLayerId(layerId);
  };

  const echoUiContext: EchoUiContext = {
    map_mode: mapMode,
    active_date: mapMode === 'single' ? activeDate : undefined,
    compare_dates: mapMode === 'swipe' ? `${swipeLeftId} vs ${swipeRightId}` : undefined,
    active_interval: mapMode === 'change' ? changeInterval : undefined,
    active_pol_or_metric: mapMode === 'single' ? singlePol : mapMode === 'change' ? changeMetric : selectedMaskLayerId,
    active_layer_title: leftOverlay?.title,
    active_layer_id: leftOverlay?.layer_id,
    active_layer_units: leftOverlay?.rule3_metadata?.units,
    active_layer_epistemic_tag: leftOverlay?.rule3_metadata?.epistemic_tag,
    significance_filter_on: mapMode === 'change' ? thresholdMaskOnly : undefined,
    active_workbench_tab: activeTab,
    story_step: `${activeStep.stepNumber}: ${activeStep.title}`,
    selected_roi_or_stratum: selectedRoiId,
    inspected_patch: inspectResult
      ? `${inspectResult.geophysical_stratum.landcover_label} at (${inspectResult.coordinates.wgs84_lon.toFixed(4)}°E, ${inspectResult.coordinates.wgs84_lat.toFixed(4)}°N) | HH range [${inspectResult.seasonal_summary.hh_min_db}, ${inspectResult.seasonal_summary.hh_max_db}] dB, HV range [${inspectResult.seasonal_summary.hv_min_db}, ${inspectResult.seasonal_summary.hv_max_db}] dB`
      : undefined,
  };

  return (
    <div className="app-shell">
      {/* TOP MISSION HEADER BAR */}
      <header className="top-header">
        <div className="brand-block">
          <div className="brand-title-row">
            <img
              src="/echo-avatar.png"
              alt="Earth Rhythm & Echo Logo"
              className="brand-logo-icon"
              onClick={() => setIsEchoOpen((v) => !v)}
              title="Click to ask Echo — Your Earth Rhythm AI Guide!"
            />
            <div>
              <div className="nasa-badge">NASA SPACE APPS 2026 • DANCING WITH THE SARs</div>
              <h1 className="app-title">
                EARTH RHYTHM <span className="title-sub">NISAR L-Band Surface Change Storyteller</span>
              </h1>
              <div className="brand-plain-line" ref={dataDetailsRef}>
                <span>
                  <strong>Fayoum Oasis, Egypt</strong> · one season of farms, water &amp; desert ·{' '}
                  {dates.length} radar passes, {shortDate(dates[0] || '2026-06-23')} →{' '}
                  {shortDate(dates[dates.length - 1] || '2026-10-21')} 2026
                </span>
                <button
                  type="button"
                  className={`data-details-btn ${showDataDetails ? 'active' : ''}`}
                  onClick={() => setShowDataDetails((v) => !v)}
                  aria-expanded={showDataDetails}
                  title="Show the satellite product, orbit and date range behind every layer"
                >
                  <Info size={12} /> Data details
                </button>
                {showDataDetails && (
                  <div className="header-popover data-details-popover" role="dialog" aria-label="Data details">
                    <div className="popover-title">Where the data comes from</div>
                    <dl className="popover-kv">
                      <dt>Place</dt>
                      <dd>Fayoum Oasis, Egypt</dd>
                      <dt>Orbit</dt>
                      <dd>Track 129 / Frame 016 Ascending</dd>
                      <dt>Product</dt>
                      <dd>
                        <code>NISAR_L2_GCOV_PROVISIONAL_V1</code> (CRID <code>P05023</code>)
                      </dd>
                      <dt>Passes</dt>
                      <dd>
                        10 Passes (<code>2026-06-23</code> → <code>2026-10-21</code>)
                      </dd>
                    </dl>
                    <div className="aoi-meta-pill">
                      Fayoum Oasis, Egypt • Track 129 / Frame 016 Ascending • <code>NISAR_L2_GCOV_PROVISIONAL_V1</code> (CRID{' '}
                      <code>P05023</code>) • 10 Passes (<code>2026-06-23</code> → <code>2026-10-21</code>)
                    </div>
                    <button
                      type="button"
                      className="dash-link-btn"
                      onClick={() => {
                        openTab('metadata');
                        setShowDataDetails(false);
                      }}
                    >
                      Full sheet for the layer on the map (Rule 3) →
                    </button>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* MAP MODE SWITCHER — plain label on top, original technical name underneath */}
        <div className="mode-pill-group" role="group" aria-label="Map view">
          <span className="mode-group-label">Map view</span>
          {(Object.keys(MAP_MODE_LABELS) as MapMode[]).map((m) => {
            const Icon = MODE_ICONS[m];
            return (
              <button
                key={m}
                className={`mode-btn mode-btn-2line ${mapMode === m ? 'mode-btn-active' : ''}`}
                onClick={() => setMapMode(m)}
                title={MAP_MODE_LABELS[m].tech}
              >
                <Icon size={15} />
                <span className="mode-btn-text">
                  <span className="mode-btn-label">{MAP_MODE_LABELS[m].label}</span>
                  <span className="mode-btn-tech">{MAP_MODE_LABELS[m].tech}</span>
                </span>
              </button>
            );
          })}
        </div>

        {/* BASEMAP & OPACITY CONTROLS (folded into a "Map settings" popover) */}
        <div className="header-right-controls">
          <div className="popover-anchor" ref={mapSettingsRef}>
            <button
              type="button"
              className={`settings-btn ${showMapSettings ? 'active' : ''}`}
              onClick={() => setShowMapSettings((v) => !v)}
              aria-expanded={showMapSettings}
              title="Background map and radar layer opacity"
            >
              <Sliders size={14} />
              <span className="settings-btn-text">
                <span>Map settings</span>
                <small>
                  {basemap === 'satellite' ? 'Satellite photo' : basemap === 'dark' ? 'Dark' : 'Street map'} •{' '}
                  {Math.round(opacity * 100)}%
                </small>
              </span>
            </button>
            {showMapSettings && (
              <div className="header-popover settings-popover" role="dialog" aria-label="Map settings">
                <div className="control-group control-stack">
                  <label>Background map — Basemap (Context, not NISAR data):</label>
                  <select value={basemap} onChange={(e) => setBasemap(e.target.value as BasemapType)}>
                    <option value="satellite">ESRI Optical Satellite (Non-NISAR Context)</option>
                    <option value="dark">CARTO Dark Matter Radar Canvas</option>
                    <option value="osm">OpenStreetMap Topographic</option>
                  </select>
                </div>
                <div className="control-group control-stack opacity-group">
                  <label>Radar layer see-through — SAR Opacity: {Math.round(opacity * 100)}%</label>
                  <input
                    type="range"
                    min="0"
                    max="1"
                    step="0.02"
                    value={opacity}
                    onChange={(e) => setOpacity(parseFloat(e.target.value))}
                  />
                </div>
              </div>
            )}
          </div>
          <button
            className={`echo-header-trigger ${isEchoOpen ? 'active' : ''}`}
            onClick={() => setIsEchoOpen((v) => !v)}
            title="Open Echo — Your Earth Rhythm AI Guide"
          >
            <img src="/echo-avatar.png" alt="Echo" className="echo-trigger-img" />
            <span>Ask Echo 🍃</span>
          </button>
        </div>
      </header>

      {/* SECONDARY LAYER / TIMELINE CONTROL STRIP */}
      <div className="sub-toolbar">
        {mapMode === 'single' && (
          <div className="toolbar-row">
            <button
              className={`play-btn ${isPlaying ? 'playing' : ''}`}
              onClick={() => setIsPlaying((p) => !p)}
              title="Play/Pause 10-Date NISAR Time Series"
            >
              {isPlaying ? <Pause size={14} /> : <Play size={14} />}
              {isPlaying ? 'Pause' : 'Play season'}
            </button>

            <div className="toolbar-field">
              <span className="toolbar-label">Show</span>
              <div className="pol-toggle-group">
                {(['RGB', 'HH', 'HV'] as const).map((p) => (
                  <button
                    key={p}
                    className={`pol-chip ${singlePol === p ? 'pol-chip-active' : ''}`}
                    onClick={() => setSinglePol(p)}
                    title={POL_LABELS[p].tech}
                  >
                    {POL_LABELS[p].label}
                  </button>
                ))}
              </div>
            </div>

            <div className="date-stepper">
              <button
                className="date-arrow"
                disabled={activeDateIdx === 0}
                onClick={() => {
                  setIsPlaying(false);
                  setActiveDateIdx((i) => Math.max(0, i - 1));
                }}
                aria-label="Previous pass"
                title="Previous pass"
              >
                <ChevronLeft size={14} />
              </button>
              <div className="date-scrubber">
                {dates.map((dt, idx) => (
                  <button
                    key={dt}
                    className={`date-step-btn ${idx === activeDateIdx ? 'date-step-active' : ''}`}
                    onClick={() => {
                      setIsPlaying(false);
                      setActiveDateIdx(idx);
                    }}
                    title={`Pass ${idx + 1} of ${dates.length} • ${dt}`}
                  >
                    <span className="step-idx">Pass {idx + 1}</span>
                    <span className="step-date">{shortDate(dt)}</span>
                  </button>
                ))}
              </div>
              <button
                className="date-arrow"
                disabled={activeDateIdx >= dates.length - 1}
                onClick={() => {
                  setIsPlaying(false);
                  setActiveDateIdx((i) => Math.min(dates.length - 1, i + 1));
                }}
                aria-label="Next pass"
                title="Next pass"
              >
                <ChevronRight size={14} />
              </button>
              <span className="date-current">
                Pass {activeDateIdx + 1}/{dates.length} • <code>{activeDate}</code>
              </span>
            </div>
          </div>
        )}

        {mapMode === 'swipe' && (
          <div className="toolbar-row swipe-toolbar">
            <div className="swipe-select-box">
              <span className="side-tag left-tag" title="LEFT CURTAIN LAYER">LEFT SIDE</span>
              <select value={swipeLeftId} onChange={(e) => setSwipeLeftId(e.target.value)}>
                {catalog.overlays.map((o) => (
                  <option key={o.layer_id} value={o.layer_id}>
                    [{o.group}] {o.title}
                  </option>
                ))}
              </select>
            </div>
            <div className="swipe-presets">
              <span className="toolbar-label">Quick picks</span>
              <button
                className="preset-btn"
                title="Jun 23 vs Aug 10 (HV Growth)"
                onClick={() => {
                  setSwipeLeftId('gcov_20260623_HV');
                  setSwipeRightId('gcov_20260810_HV');
                }}
              >
                Crop growth · Jun 23 vs Aug 10 (HV)
              </button>
              <button
                className="preset-btn"
                title="Aug 10 vs Oct 21 (HV Harvest)"
                onClick={() => {
                  setSwipeLeftId('gcov_20260810_HV');
                  setSwipeRightId('gcov_20261021_HV');
                }}
              >
                Harvest · Aug 10 vs Oct 21 (HV)
              </button>
              <button
                className="preset-btn"
                title="ΔHH vs ΔHV Disagreement (Aug 10 → Oct 21, thresholded)"
                onClick={() => {
                  setSwipeLeftId('delta_HH_20260810_to_20261021_sig');
                  setSwipeRightId('delta_HV_20260810_to_20261021_sig');
                }}
              >
                HH vs HV disagreement (ΔHH | ΔHV)
              </button>
            </div>
            <div className="swipe-select-box">
              <span className="side-tag right-tag" title="RIGHT CURTAIN LAYER">RIGHT SIDE</span>
              <select value={swipeRightId} onChange={(e) => setSwipeRightId(e.target.value)}>
                {catalog.overlays.map((o) => (
                  <option key={o.layer_id} value={o.layer_id}>
                    [{o.group}] {o.title}
                  </option>
                ))}
              </select>
            </div>
          </div>
        )}

        {mapMode === 'change' && (
          <div className="toolbar-row">
            <div className="control-group">
              <label title="Seasonal Window">Time window:</label>
              <select value={changeInterval} onChange={(e) => setChangeInterval(e.target.value)}>
                <option value="20260623_to_20260810">Early → Peak Summer (2026-06-23 → 2026-08-10)</option>
                <option value="20260810_to_20261021">Peak Summer → Autumn Harvest (2026-08-10 → 2026-10-21)</option>
                <option value="20260623_to_20261021">Full 4-Month Span (2026-06-23 → 2026-10-21)</option>
              </select>
            </div>

            <div className="toolbar-field">
              <span className="toolbar-label" title="Change between the 2 dates of the time window">
                Between 2 dates
              </span>
              <div className="pol-toggle-group">
                {(['HV', 'HH', 'regime', 'HV_over_HH'] as ChangeMetric[]).map((m) => (
                  <button
                    key={m}
                    className={`pol-chip ${changeMetric === m ? 'pol-chip-active' : ''}`}
                    onClick={() => setChangeMetric(m)}
                    title={CHANGE_METRIC_LABELS[m].tech}
                  >
                    {CHANGE_METRIC_LABELS[m].label}
                  </button>
                ))}
              </div>
            </div>

            <div className="toolbar-field">
              <span className="toolbar-label" title="How far each pixel swung over all 10 dates">
                Over all 10 dates
              </span>
              <div className="pol-toggle-group">
                {(['dyn_HV', 'dyn_HH'] as ChangeMetric[]).map((m) => (
                  <button
                    key={m}
                    className={`pol-chip ${changeMetric === m ? 'pol-chip-active' : ''}`}
                    onClick={() => setChangeMetric(m)}
                    title={CHANGE_METRIC_LABELS[m].tech}
                  >
                    {CHANGE_METRIC_LABELS[m].label}
                  </button>
                ))}
              </div>
            </div>

            {(changeMetric === 'HH' || changeMetric === 'HV') && (
              <label
                className="threshold-checkbox"
                title={`Hide Sub-Threshold Noise (|ΔdB| < ${changeMetric === 'HH' ? '2.73' : '2.03'} dB transparent)`}
              >
                <input
                  type="checkbox"
                  checked={thresholdMaskOnly}
                  onChange={(e) => setThresholdMaskOnly(e.target.checked)}
                />
                <span>
                  Hide noise: changes smaller than τ = {changeMetric === 'HH' ? '2.73' : '2.03'} dB
                </span>
              </label>
            )}
          </div>
        )}

        {mapMode === 'masks' && (
          <div className="toolbar-row">
            <div className="control-group">
              <label title="Select Geophysical Mask or Exploratory InSAR Layer">
                Supporting layer (land types, quality masks, forecasts, exploratory InSAR):
              </label>
              <select value={selectedMaskLayerId} onChange={(e) => setSelectedMaskLayerId(e.target.value)}>
                <optgroup label="Phase 2 Geophysical & Radiometric Calibration Masks (40m)">
                  {catalog.overlays
                    .filter((o) => o.group === 'geophysical_masks')
                    .map((o) => (
                      <option key={o.layer_id} value={o.layer_id}>
                        {o.title}
                      </option>
                    ))}
                </optgroup>
                <optgroup label="Exploratory Change Type B — L2_GUNW Coherence-Masked (γ ≥ 0.50) Phase Screen (80m)">
                  {catalog.overlays
                    .filter((o) => o.group === 'exploratory_insar_gunw')
                    .map((o) => (
                      <option key={o.layer_id} value={o.layer_id}>
                        {o.title}
                      </option>
                    ))}
                </optgroup>
              </select>
            </div>
          </div>
        )}
      </div>

      {/* PLAIN-LANGUAGE READING GUIDE FOR THE CURRENT MAP VIEW (additive) */}
      <MapReadingGuide
        mapMode={mapMode}
        singlePol={singlePol}
        changeMetric={changeMetric}
        thresholdMaskOnly={thresholdMaskOnly}
        leftOverlay={leftOverlay}
        rightOverlay={rightOverlay}
        selectedMaskLayerId={selectedMaskLayerId}
      />

      {/* MAIN SPLIT WORKSPACE: INTERACTIVE MAP (LEFT) + SCIENTIFIC WORKBENCH (RIGHT) */}
      <main className="main-workspace">
        <section className="map-column">
          <NisarMap
            leftOverlay={leftOverlay}
            rightOverlay={rightOverlay}
            isSwipeMode={mapMode === 'swipe'}
            opacity={opacity}
            basemap={basemap}
            focalRois={focalRois}
            selectedRoiId={selectedRoiId}
            inspectedLonLat={inspectedLonLat}
            flyToTarget={flyToTarget}
            onMapClick={(lon, lat) => {
              triggerInspect(lon, lat, inspectWindowPx);
              if (activeTab !== 'inspector' && activeTab !== 'story') {
                openTab('inspector');
              }
            }}
            onSelectRoi={(roi) => handleSelectRoi(roi, true)}
          />

          {/* Quick Focal ROI Jump Bar at Bottom of Map (short names; full titles in tooltips) */}
          <div className="roi-quick-bar">
            <span className="quick-bar-label" title="Focal Story ROIs (200m × 200m)">
              <Crosshair size={13} />
              <span className="quick-bar-label-text">
                Story spots <small>200 m × 200 m each</small>
              </span>
            </span>
            {focalRois.map((roi, idx) => (
              <button
                key={roi.roi_id}
                className={`roi-quick-btn ${selectedRoiId === roi.roi_id ? 'roi-quick-active' : ''}`}
                onClick={() => handleSelectRoi(roi, true)}
                title={`${roi.title} — ${roi.roi_id}`}
              >
                <span className="pin-circle">{idx + 1}</span>
                {roiShortName(roi.roi_id)}
              </button>
            ))}
          </div>
        </section>

        {/* RIGHT SCIENTIFIC WORKBENCH PANEL */}
        <aside className="workbench-panel">
          <nav className="workbench-tabs workbench-tabs-5">
            <button
              className={`tab-btn ${activeTab === 'story' ? 'tab-btn-active' : ''}`}
              onClick={() => openTab('story')}
              title="Story Mode — 6 guided chapters"
            >
              <Sparkles size={14} /> Story
            </button>
            <button
              className={`tab-btn ${activeTab === 'inspector' ? 'tab-btn-active' : ''}`}
              onClick={() => openTab('inspector')}
              title="Pixel Inspector — what happened at the selected spot"
            >
              <Crosshair size={14} /> This spot
            </button>
            <button
              className={`tab-btn ${activeTab === 'dashboards' ? 'tab-btn-active' : ''}`}
              onClick={() => openTab('dashboards')}
              title="Dashboards — the whole area at a glance"
            >
              <LayoutDashboard size={14} /> Overview
            </button>
            <button
              className={`tab-btn ${activeTab === 'forecast' ? 'tab-btn-active' : ''}`}
              onClick={() => {
                openTab('forecast');
                showPredictionLayerOnMap('pred_flood_risk_20261102');
              }}
              title="Forecast — flood & crop outlook for the next pass"
            >
              <TrendingUp size={14} /> Forecast
            </button>
            <button
              className={`tab-btn ${isHelpTab(activeTab) ? 'tab-btn-active' : ''}`}
              onClick={() => openTab(isHelpTab(activeTab) ? activeTab : lastHelpTab)}
              title="Guide & glossary, Rule 3 layer metadata, Methods & Limits"
            >
              <BookOpen size={14} /> Help &amp; data
            </button>
          </nav>

          <div className="workbench-content">
            {/* "Help & data" sub-views */}
            {isHelpTab(activeTab) && (
              <div className="subtab-bar" role="tablist" aria-label="Help and data">
                <button
                  className={`subtab-btn ${activeTab === 'guide' ? 'subtab-active' : ''}`}
                  onClick={() => openTab('guide')}
                  title="Guide"
                >
                  <Lightbulb size={13} /> How to read the app
                </button>
                <button
                  className={`subtab-btn ${activeTab === 'metadata' ? 'subtab-active' : ''}`}
                  onClick={() => openTab('metadata')}
                  title="Rule 3 Metadata"
                >
                  <Database size={13} /> Layer data sheet <span className="subtab-tech">Rule 3</span>
                </button>
                <button
                  className={`subtab-btn ${activeTab === 'methods' ? 'subtab-active' : ''}`}
                  onClick={() => openTab('methods')}
                  title="Methods & Limits"
                >
                  <BookOpen size={13} /> Methods &amp; limits
                </button>
              </div>
            )}

            {/* TAB 1: 6-STEP GUIDED STORY MODE */}
            {activeTab === 'story' && (
              <div className="tab-pane story-pane">
                <div className="story-stepper-bar">
                  <span className="story-progress">
                    Chapter <strong>{storyStepIdx + 1}</strong> of {STORY_STEPS.length}
                  </span>
                  {STORY_STEPS.map((st, idx) => (
                    <button
                      key={st.id}
                      className={`step-dot-btn ${idx === storyStepIdx ? 'step-dot-active' : ''}`}
                      onClick={() => applyStoryStep(idx)}
                      title={`Chapter ${st.stepNumber}: ${st.title}`}
                    >
                      {st.stepNumber}
                    </button>
                  ))}
                  <div className="step-nav-arrows">
                    <button
                      disabled={storyStepIdx === 0}
                      onClick={() => applyStoryStep(Math.max(0, storyStepIdx - 1))}
                    >
                      ← Back
                    </button>
                    <button
                      className="step-next-btn"
                      disabled={storyStepIdx === STORY_STEPS.length - 1}
                      onClick={() => applyStoryStep(Math.min(STORY_STEPS.length - 1, storyStepIdx + 1))}
                    >
                      Next chapter →
                    </button>
                  </div>
                </div>

                {/* Plain words first; the technical chapter text is one click away */}
                <StoryPlainCard
                  stepNumber={activeStep.stepNumber}
                  badge={activeStep.badge}
                  title={activeStep.title}
                  subtitle={activeStep.subtitle}
                >
                  <Disclosure
                    title="Science details for this chapter"
                    hint="radar physics & dual-pol / wavelength insight"
                    className="story-chapter-card"
                  >
                    <p className="chapter-body">{activeStep.physicsTakeaway}</p>
                    <div className="pol-highlight-box">
                      <strong>Dual-Pol &amp; Wavelength Insight:</strong>
                      <p>{activeStep.whyPolarizationMatters}</p>
                    </div>
                  </Disclosure>
                </StoryPlainCard>

                {/* Embedded Multi-Temporal Chart for Current Story Focal ROI */}
                {inspectResult && (
                  <div className="story-chart-card">
                    <div className="card-header-row">
                      <div>
                        <h3>How this spot changed over the 10 passes</h3>
                        <div className="card-sub">
                          10-Date NISAR Trajectory •{' '}
                          {selectedRoiId !== 'CUSTOM_PIXEL' ? `${roiShortName(selectedRoiId)} • ` : 'Clicked spot • '}
                          <code>
                            ({inspectResult.coordinates.wgs84_lon.toFixed(4)}°E,{' '}
                            {inspectResult.coordinates.wgs84_lat.toFixed(4)}°N)
                          </code>{' '}
                          • click a date to show it on the map
                        </div>
                      </div>
                      <label className="s2-toggle-label">
                        <input
                          type="checkbox"
                          checked={showS2Overlay}
                          onChange={(e) => setShowS2Overlay(e.target.checked)}
                        />
                        <span>Overlay Sentinel-2 NDVI (optical context, not NISAR)</span>
                      </label>
                    </div>

                    <TimeSeriesChart
                      timeseries={inspectResult.timeseries}
                      activeDate={activeDate}
                      onSelectDate={(dt) => {
                        const i = dates.indexOf(dt);
                        if (i >= 0) {
                          setMapMode('single');
                          setActiveDateIdx(i);
                        }
                      }}
                      sentinel2Points={activeS2Points}
                      showSentinel2Overlay={showS2Overlay}
                    />

                    {/* Epistemic 3-Tier Statements (Rule 5) — technical wording, folded */}
                    <Disclosure
                      title="Technical findings for this spot"
                      hint="OBSERVATION • CHANGE DETECTION • INTERPRETATION (hypothesis)"
                    >
                      <div className="epistemic-stack">
                        <div className="epistemic-card obs-card">
                          <span className="ep-tag obs-tag">OBSERVATION</span>
                          <p>{inspectResult.epistemic_statements.observation}</p>
                        </div>
                        <div className="epistemic-card chg-card">
                          <span className="ep-tag chg-tag">CHANGE DETECTION</span>
                          <p>{inspectResult.epistemic_statements.change_detection}</p>
                        </div>
                        <div className="epistemic-card hyp-card">
                          <span className="ep-tag hyp-tag">INTERPRETATION (hypothesis)</span>
                          <p>
                            {focalRois.find((r) => r.roi_id === selectedRoiId)?.hypothesis_statement ||
                              inspectResult.epistemic_statements.interpretation}
                          </p>
                        </div>
                      </div>
                    </Disclosure>
                  </div>
                )}
              </div>
            )}

            {/* TAB 2: LIVE PIXEL / PATCH TIME-SERIES INSPECTOR */}
            {activeTab === 'inspector' && inspectResult && (
              <div className="tab-pane inspector-pane">
                <div className="inspector-header-card">
                  <div className="inspector-coords-row">
                    <div>
                      <span className="section-eyebrow">
                        THIS SPOT{selectedRoiId !== 'CUSTOM_PIXEL' ? ` • ${roiShortName(selectedRoiId).toUpperCase()}` : ' • CLICKED ON MAP'}
                        <span className="eyebrow-tech"> • LIVE CALIBRATED CUBE QUERY (/api/inspect)</span>
                      </span>
                      <h3>
                        {selectedRoiId !== 'CUSTOM_PIXEL'
                          ? focalRois.find((r) => r.roi_id === selectedRoiId)?.title || selectedRoiId
                          : `Custom Map Patch (${inspectResult.coordinates.wgs84_lon}°E, ${inspectResult.coordinates.wgs84_lat}°N)`}
                      </h3>
                      <div className="coord-mono-line">
                        WGS84: <code>{inspectResult.coordinates.wgs84_lon}°E, {inspectResult.coordinates.wgs84_lat}°N</code>{' '}
                        • UTM 36N: <code>X={inspectResult.coordinates.utm_epsg32636_x}m, Y={inspectResult.coordinates.utm_epsg32636_y}m</code>
                      </div>
                    </div>

                    <div className="patch-size-selector">
                      <label title="Patch Window">Area averaged (patch window):</label>
                      <select
                        value={inspectWindowPx}
                        onChange={(e) => {
                          const w = parseInt(e.target.value, 10);
                          setInspectWindowPx(w);
                          triggerInspect(
                            inspectResult.coordinates.wgs84_lon,
                            inspectResult.coordinates.wgs84_lat,
                            w,
                            selectedRoiId !== 'CUSTOM_PIXEL' ? selectedRoiId : undefined
                          );
                        }}
                      >
                        <option value={1}>1×1 px (40m × 40m = 16 native 10m px)</option>
                        <option value={3}>3×3 px (120m × 120m = 144 native 10m px)</option>
                        <option value={5}>5×5 px (200m × 200m = 400 native 10m px)</option>
                        <option value={7}>7×7 px (280m × 280m = 784 native 10m px)</option>
                      </select>
                    </div>
                  </div>

                  <div className="stratum-badges-row">
                    <span className="stratum-pill">{inspectResult.geophysical_stratum.landcover_label}</span>
                    <span className="sample-honesty-pill">
                      N = {inspectResult.sampling.temporal_sample_count_N_dates} dates • N ={' '}
                      {inspectResult.sampling.spatial_sample_count_40m_pixels} 40m px ({inspectResult.sampling.patch_area_ha}{' '}
                      ha)
                    </span>
                    {inspectResult.geophysical_stratum.low_snr_nesz_proximity_warning && (
                      <span className="nesz-warning-pill">
                        <AlertTriangle size={12} /> Near NESZ Floor (&lt; +3 dB above sensor noise)
                      </span>
                    )}
                  </div>
                  <div className="inspector-tip">Click anywhere on the map, or a numbered story spot, to inspect another place.</div>
                </div>

                {/* Plain-language readout generated from the live /api/inspect result (additive) */}
                <InspectorPlainReadout data={inspectResult} />

                <div className="story-chart-card">
                  <div className="card-header-row">
                    <div>
                      <h3>Radar signal over the season</h3>
                      <div className="card-sub">
                        Multi-Temporal Backscatter (γ⁰ dB Median &amp; [P25, P75] IQR) • click a date to show it on the map
                      </div>
                    </div>
                    <label className="s2-toggle-label">
                      <input
                        type="checkbox"
                        checked={showS2Overlay}
                        onChange={(e) => setShowS2Overlay(e.target.checked)}
                      />
                      <span>Sentinel-2 L2A NDVI (optical context, not NISAR)</span>
                    </label>
                  </div>

                  <TimeSeriesChart
                    timeseries={inspectResult.timeseries}
                    activeDate={activeDate}
                    onSelectDate={(dt) => {
                      const i = dates.indexOf(dt);
                      if (i >= 0) {
                        setMapMode('single');
                        setActiveDateIdx(i);
                      }
                    }}
                    sentinel2Points={activeS2Points}
                    showSentinel2Overlay={showS2Overlay}
                  />

                  {activeS2Corr && (
                    <div className="context-correlation-banner">
                      <strong>External Optical Cross-Check (Rule 2 — ESA Sentinel-2 L2A STAC):</strong> Summer cycle (N=8
                      paired dates) HV-vs-NDVI Pearson <code>r = {activeS2Corr.summer_cycle_8date_pearson_r}</code> (
                      <code>p = {activeS2Corr.summer_cycle_8date_p_value}</code>); Full 9-date Spearman{' '}
                      <code>ρ = {activeS2Corr.full_9date_spearman_rho}</code>.
                    </div>
                  )}
                </div>

                {/* Seasonal Log-Ratio Interval Table (folded: the plain readout above shows the same ΔHH/ΔHV values) */}
                <Disclosure
                  title="Exact numbers per time window"
                  hint="ΔHH, ΔHV, Δ(HV/HH) and change class in one table"
                  className="data-table-card"
                >
                  <h3>Seasonal Log-Ratio Change &amp; Threshold Evaluation (τ_HH = 2.73 dB, τ_HV = 2.03 dB)</h3>
                  <table className="sci-table">
                    <thead>
                      <tr>
                        <th>Seasonal Window</th>
                        <th>ΔHH (dB)</th>
                        <th>ΔHV (dB)</th>
                        <th>Δ(HV/HH)</th>
                        <th>Dual-Pol Regime Classification</th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.entries(inspectResult.interval_evaluations).map(([k, ev]) => (
                        <tr key={k}>
                          <td>
                            <code>{ev.date_start}</code> → <code>{ev.date_end}</code>
                          </td>
                          <td className={ev.exceeds_tau_hh ? 'sig-cell' : ''}>
                            {ev.delta_hh_db > 0 ? `+${ev.delta_hh_db.toFixed(2)}` : ev.delta_hh_db.toFixed(2)} dB{' '}
                            {ev.exceeds_tau_hh ? '★' : ''}
                          </td>
                          <td className={ev.exceeds_tau_hv ? 'sig-cell' : ''}>
                            {ev.delta_hv_db > 0 ? `+${ev.delta_hv_db.toFixed(2)}` : ev.delta_hv_db.toFixed(2)} dB{' '}
                            {ev.exceeds_tau_hv ? '★' : ''}
                          </td>
                          <td>
                            {ev.delta_hv_over_hh_db > 0
                              ? `+${ev.delta_hv_over_hh_db.toFixed(2)}`
                              : ev.delta_hv_over_hh_db.toFixed(2)}{' '}
                            dB
                          </td>
                          <td>
                            <span className={`regime-badge regime-code-${ev.regime_code}`}>{ev.regime_label}</span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  <p className="table-foot">★ = the change is bigger than the noise threshold τ for that channel.</p>
                </Disclosure>

                {/* External Meteorological Context Strip (Rule 2 — NASA POWER) */}
                <div className="external-context-card">
                  <div className="context-header">
                    <span className="rule2-badge">EXTERNAL NON-NISAR CONTEXT • RULE 2</span>
                    <strong>{nasaPower.source_label}</strong>
                  </div>
                  <p className="context-text">{nasaPower.scientific_implication}</p>
                  <div className="weather-caption">Weather on each radar pass date: rain (mm/day) and wind at 2 m (m/s)</div>
                  <div className="weather-mini-grid">
                    {nasaPower.nisar_overpass_dates_weather.map((w) => (
                      <div key={w.nisar_date} className="weather-chip">
                        <span className="w-date">{w.nisar_date.slice(5)}</span>
                        <span className="w-rain">{w.precip_mm_day.toFixed(1)} mm</span>
                        <span className="w-wind">{w.wind_speed_2m_m_s.toFixed(1)} m/s</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {/* TAB 3: MANDATORY RULE 3 LAYER METADATA PANEL */}
            {activeTab === 'metadata' && (
              <div className="plain-intro">
                <strong>The “receipt” for the layer on the map.</strong> Which satellite and product it comes from, its
                date(s), polarization, units, map projection, source file and certainty label. Change the map view and this
                sheet follows it.
              </div>
            )}
            {activeTab === 'metadata' && !leftOverlay && (
              <div className="empty-chart">No layer is currently shown on the map.</div>
            )}
            {activeTab === 'metadata' && leftOverlay && (
              <div className="tab-pane metadata-pane">
                <div className="metadata-card">
                  <div className="card-header-row">
                    <div>
                      <span className="section-eyebrow">MANDATORY RULE 3 &amp; RULE 5 LAYER METADATA</span>
                      <h3>{leftOverlay.title}</h3>
                    </div>
                    <a
                      href={leftOverlay.cog_url}
                      download
                      className="cog-download-btn"
                      title="Download Cloud-Optimized GeoTIFF (EPSG:32636 with Rule 3 Tags)"
                    >
                      <Download size={14} /> Download Native COG (.tif)
                    </a>
                  </div>

                  <table className="sci-table meta-kv-table">
                    <tbody>
                      <tr>
                        <th>1. Satellite / Sensor</th>
                        <td>{leftOverlay.rule3_metadata.satellite}</td>
                      </tr>
                      <tr>
                        <th>2. Product Type</th>
                        <td>
                          <code>{leftOverlay.rule3_metadata.product_type}</code>
                        </td>
                      </tr>
                      <tr>
                        <th>3. Product Version / CRID</th>
                        <td>
                          <code>{leftOverlay.rule3_metadata.product_version}</code>
                        </td>
                      </tr>
                      <tr>
                        <th>4. Acquisition Date(s)</th>
                        <td>
                          <code>{leftOverlay.rule3_metadata.acquisition_date}</code>
                        </td>
                      </tr>
                      <tr>
                        <th>5. Track / Frame</th>
                        <td>
                          <code>{leftOverlay.rule3_metadata.track_frame}</code>
                        </td>
                      </tr>
                      <tr>
                        <th>6. Orbit Direction</th>
                        <td>{leftOverlay.rule3_metadata.orbit_direction}</td>
                      </tr>
                      <tr>
                        <th>7. Polarization</th>
                        <td>
                          <code>{leftOverlay.rule3_metadata.polarization}</code>
                        </td>
                      </tr>
                      <tr>
                        <th>8. Physical Units</th>
                        <td>
                          <code>{leftOverlay.rule3_metadata.units}</code>
                        </td>
                      </tr>
                      <tr>
                        <th>9. Coordinate Reference System (CRS)</th>
                        <td>
                          Native COG: <code>EPSG:32636 (WGS 84 / UTM Zone 36N)</code> • Web Overlay:{' '}
                          <code>EPSG:4326 (WGS84)</code>
                        </td>
                      </tr>
                      <tr>
                        <th>10. Official Data Source &amp; Granule ID</th>
                        <td className="mono-wrap">{leftOverlay.rule3_metadata.source}</td>
                      </tr>
                      <tr>
                        <th>11. Rule 5 Epistemic Tag</th>
                        <td>
                          <span
                            className={`epistemic-chip epistemic-${leftOverlay.rule3_metadata.epistemic_tag
                              .split(' ')[0]
                              .toLowerCase()}`}
                          >
                            {leftOverlay.rule3_metadata.epistemic_tag}
                          </span>
                        </td>
                      </tr>
                      <tr>
                        <th>Overlay SHA256 Checksum</th>
                        <td className="mono-wrap">
                          <code>{leftOverlay.sha256}</code>
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>

                {mapMode === 'swipe' && rightOverlay && (
                  <div className="metadata-card">
                    <div className="card-header-row">
                      <div>
                        <span className="section-eyebrow">RIGHT SWIPE LAYER METADATA (RULE 3)</span>
                        <h3>{rightOverlay.title}</h3>
                      </div>
                      <a href={rightOverlay.cog_url} download className="cog-download-btn">
                        <Download size={14} /> Download Right COG (.tif)
                      </a>
                    </div>
                    <table className="sci-table meta-kv-table">
                      <tbody>
                        <tr>
                          <th>Acquisition Date(s)</th>
                          <td>
                            <code>{rightOverlay.rule3_metadata.acquisition_date}</code>
                          </td>
                        </tr>
                        <tr>
                          <th>Polarization &amp; Units</th>
                          <td>
                            <code>{rightOverlay.rule3_metadata.polarization}</code> •{' '}
                            <code>{rightOverlay.rule3_metadata.units}</code>
                          </td>
                        </tr>
                        <tr>
                          <th>Source &amp; Granule ID</th>
                          <td className="mono-wrap">{rightOverlay.rule3_metadata.source}</td>
                        </tr>
                        <tr>
                          <th>Rule 5 Epistemic Tag</th>
                          <td>
                            <span
                              className={`epistemic-chip epistemic-${rightOverlay.rule3_metadata.epistemic_tag
                                .split(' ')[0]
                                .toLowerCase()}`}
                            >
                              {rightOverlay.rule3_metadata.epistemic_tag}
                            </span>
                          </td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )}

            {/* TAB 4: METHOD & LIMITS PANEL + FUTURE NISAR APPLICATIONS */}
            {activeTab === 'methods' && (
              <div className="tab-pane methods-pane">
                {/* Plain summary of the cards below (no new numbers — every value is restated from them) */}
                <div className="plain-card">
                  <div className="plain-card-head">
                    <span className="plain-eyebrow">IN SHORT • HOW WE KEEP THE SCIENCE HONEST</span>
                    <h3>Four things to know before trusting a change</h3>
                  </div>
                  <ol className="plain-steps">
                    <li>
                      <strong>Speckle is smoothed without bias.</strong> Pixels are averaged in linear power before
                      converting to dB, so the mean brightness is kept within 0.02%.
                    </li>
                    <li>
                      <strong>A change only counts if it beats the noise.</strong> Stable desert sets the bar: τ = 2.73 dB
                      for HH and τ = 2.03 dB for HV.
                    </li>
                    <li>
                      <strong>Some things can fool the radar.</strong> Wind ripples on Lake Qarun and very smooth sand near
                      the sensor noise floor.
                    </li>
                    <li>
                      <strong>12-day InSAR is not ground sinking.</strong> The atmosphere alone adds 8.80–18.78 mm of
                      apparent motion, far more than plausible compaction, so we never claim subsidence.
                    </li>
                  </ol>
                </div>

                {/* 1. Multi-Stage Speckle Filtering & ENL Verification */}
                <div className="data-table-card">
                  <span className="section-eyebrow">SCIENCE REQ 2 • LINEAR-POWER SPECKLE FILTERING &amp; ENL</span>
                  <h3>Multi-Stage Equivalent Number of Looks (ENL = μ² / σ² in Linear γ⁰)</h3>
                  <p className="method-note">
                    All spatial averaging (4×4 block multilooking from 10 m → 40 m) and 3×3 Adaptive Lee filtering are
                    performed <strong>strictly in linear power (γ⁰, m²/m²)</strong> prior to decibel conversion (10
                    log₁₀ γ⁰), preserving mean radiometric power within &lt; 0.02%.
                  </p>
                  <table className="sci-table">
                    <thead>
                      <tr>
                        <th>Calibration Patch (EPSG:32636)</th>
                        <th>Stage 0: 10m Native</th>
                        <th>Stage 1: 40m Block Avg</th>
                        <th>Stage 2: 40m + 3×3 Lee</th>
                        <th>Two-Date σ_ΔdB</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr>
                        <td>Lake Qarun Open Water (HH)</td>
                        <td>ENL = 4.88</td>
                        <td>ENL = 41.04</td>
                        <td>
                          <strong>ENL = 152.74</strong>
                        </td>
                        <td>0.497 dB</td>
                      </tr>
                      <tr>
                        <td>Lake Qarun Open Water (HV)</td>
                        <td>ENL = 5.49</td>
                        <td>ENL = 57.28</td>
                        <td>
                          <strong>ENL = 444.01</strong>
                        </td>
                        <td>0.291 dB</td>
                      </tr>
                      <tr>
                        <td>Limestone Desert Plateau (HH)</td>
                        <td>ENL = 4.91</td>
                        <td>ENL = 45.64</td>
                        <td>
                          <strong>ENL = 237.00</strong>
                        </td>
                        <td>0.399 dB</td>
                      </tr>
                      <tr>
                        <td>Limestone Desert Plateau (HV)</td>
                        <td>ENL = 5.33</td>
                        <td>ENL = 56.41</td>
                        <td>
                          <strong>ENL = 481.06</strong>
                        </td>
                        <td>0.280 dB</td>
                      </tr>
                    </tbody>
                  </table>
                </div>

                {/* 2. Statistical Threshold Justification */}
                <div className="data-table-card">
                  <span className="section-eyebrow">SCIENCE REQ 3 • EMPIRICAL &amp; THEORETICAL THRESHOLDS</span>
                  <h3>Noise Floor &amp; Change Threshold Derivation (N = 218,705 Stable Desert Pixels = 349.93 km²)</h3>
                  <table className="sci-table">
                    <thead>
                      <tr>
                        <th>Channel</th>
                        <th>3σ Theoretical Speckle</th>
                        <th>12-Day 3σ_MAD (Desert)</th>
                        <th>12-Day P99 (Desert)</th>
                        <th>Adopted Threshold (τ)</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr>
                        <td>
                          <strong>HH (Co-Pol)</strong>
                        </td>
                        <td>1.49 dB</td>
                        <td>1.66 dB</td>
                        <td>2.73 dB</td>
                        <td>
                          <strong className="sig-cell">τ_HH = 2.73 dB</strong>
                        </td>
                      </tr>
                      <tr>
                        <td>
                          <strong>HV (Cross-Pol)</strong>
                        </td>
                        <td>0.87 dB</td>
                        <td>2.03 dB</td>
                        <td>1.99 dB</td>
                        <td>
                          <strong className="sig-cell">τ_HV = 2.03 dB</strong>
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>

                {/* 3. Confounders & Exploratory GUNW Limits */}
                <div className="data-table-card">
                  <span className="section-eyebrow">SCIENCE REQ 4, 6 &amp; RULE 5 • CONFOUNDERS &amp; InSAR LIMITS</span>
                  <h3>Physical Confounders &amp; Why 12-Day L2_GUNW Phase Is Not Ground Subsidence</h3>
                  <ul className="limits-list">
                    <li>
                      <strong>Wind-Driven Bragg Waves on Open Water:</strong> Calm open water reflects L-band pulses
                      away from the sensor (−18 to −23 dB HH), but 2–5 m/s winds generate surface capillary/short-gravity
                      waves that cause 1.6–3.7 dB HH fluctuations over Lake Qarun.
                    </li>
                    <li>
                      <strong>Rayleigh-Smooth Eolian Sand Sheets &amp; NESZ Floor:</strong> Dry fine-grained sand sheets
                      in the Western Desert satisfy the L-band Rayleigh smoothness criterion and drop near the sensor
                      NESZ floor (−23.26 dB HH, −24.52 dB HV). We explicitly isolate 1,402.90 km² (28.56%) in{' '}
                      <code>low_snr_nesz_mask</code> and combine multi-temporal backscatter with InSAR decorrelation (γ̄
                      &lt; 0.15) to separate true open water (310.18 km²) from dry sand sheets.
                    </li>
                    <li>
                      <strong>12-Day L2_GUNW Tropospheric Phase vs. Subsidence (Rules 4 &amp; 6):</strong> While urban
                      (98.4% γ ≥ 0.50) and consolidated limestone desert (94.5% γ ≥ 0.50) are highly coherent in 24 cm
                      L-band, apparent 12-day LOS range standard deviation over tectonically stable desert bedrock is{' '}
                      <strong>8.80–18.78 mm</strong> due to atmospheric water-vapor gradients between the humid oasis and
                      hyper-arid desert. Because this exceeds plausible 12-day compaction (&lt; 0.5 mm) by &gt;20×, we
                      never claim ground subsidence rates from 2 interferometric pairs.
                    </li>
                  </ul>
                </div>

                {/* 4. Quantitative Benchmark Comparison vs Authoritative NASA Datasets */}
                <BenchmarkCard />

                {/* 5. Grounded Future NISAR Operational Applications */}
                <div className="data-table-card future-apps-card">
                  <span className="section-eyebrow">REQUIRED SECTION • OPERATIONAL ROADMAP</span>
                  <h3>Future NISAR Operational Applications in the Nile Basin &amp; Arid Agro-Ecosystems</h3>
                  <div className="future-grid">
                    <div className="future-item">
                      <h4>1. Canal-Scale Irrigation Auditing (Bahr Youssef)</h4>
                      <p>
                        Operational 12-day tracking of Regime 3 (+HH bare-soil wetting) and Regime 4 (−HH ponded flood
                        sheets) across irrigation command blocks to detect tail-end canal delivery deficits for the
                        Egyptian Ministry of Water Resources &amp; Irrigation.
                      </p>
                    </div>
                    <div className="future-item">
                      <h4>2. All-Weather Structural Crop Biomass Census</h4>
                      <p>
                        Combining NISAR L-band HV (woody/stem structural volume) with Sentinel-2 NDVI (surface leaf
                        chlorophyll) to separate newly emerged winter seedlings from mature high-biomass summer crops.
                      </p>
                    </div>
                    <div className="future-item">
                      <h4>3. Lake Qarun &amp; Wadi El Rayan Water-Balance Monitoring</h4>
                      <p>
                        Automated tracking of the 165.85 km² seasonal water margin and aquaculture pond inundation
                        without cloud-cover gaps.
                      </p>
                    </div>
                    <div className="future-item">
                      <h4>4. Multi-Year SBAS / PS InSAR Deformation Time Series</h4>
                      <p>
                        Once &gt;30 Ascending &amp; Descending NISAR L2_GUNW acquisitions accumulate over 1–3 years,
                        time-series velocity stacking will average out random tropospheric delay (∝ 1/√N) to resolve
                        millimeter-per-year clay compaction and canal embankment stability.
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* TAB 5: DASHBOARDS (additive) */}
            {activeTab === 'dashboards' && (
              <DashboardsPanel
                storyData={storyData}
                catalog={catalog}
                focalRois={focalRois}
                selectedRoiId={selectedRoiId}
                onShowRegimeOnMap={showRegimeOnMap}
                onSelectDate={showDateOnMap}
              />
            )}

            {/* TAB 6: EXPLAINABLE FLOOD & CROP FORECAST (additive) */}
            {activeTab === 'forecast' && (
              <PredictionPanel
                selectedRoiId={selectedRoiId}
                onShowPredictionLayer={showPredictionLayerOnMap}
                onFlyToRoi={(lon, lat, roiId) => {
                  triggerInspect(lon, lat, inspectWindowPx, roiId);
                  setFlyToTarget({ center: [lon, lat], zoom: 12.2, seq: Date.now() });
                }}
              />
            )}

            {/* TAB 7: PLAIN-LANGUAGE GUIDE & GLOSSARY (additive) */}
            {activeTab === 'guide' && (
              <GuidePanel
                catalog={catalog}
                onNavigate={(tab) => openTab(tab)}
                onOpenEcho={() => setIsEchoOpen(true)}
              />
            )}
          </div>
        </aside>
      </main>

      {/* ECHO AI HELPER (Floating Launcher & Context-Aware Chat Guide) */}
      <EchoHelper
        uiContext={echoUiContext}
        isOpen={isEchoOpen}
        onToggleOpen={() => setIsEchoOpen((v) => !v)}
      />
    </div>
  );
};
