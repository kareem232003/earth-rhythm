import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Activity,
  AlertTriangle,
  BookOpen,
  Compass,
  Crosshair,
  Database,
  Download,
  Eye,
  Layers,
  Pause,
  Play,
  Sliders,
  Sparkles,
  SplitSquareHorizontal,
} from 'lucide-react';
import { BasemapType, NisarMap } from './components/NisarMap';
import { TimeSeriesChart } from './components/TimeSeriesChart';
import { STORY_STEPS } from './storySteps';
import { FocalROI, InspectResponse, LayerCatalog, OverlayItem, StoryPayload } from './types';

type MapMode = 'single' | 'swipe' | 'change' | 'masks';
type WorkbenchTab = 'story' | 'inspector' | 'metadata' | 'methods';

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
  const [changeMetric, setChangeMetric] = useState<'HH' | 'HV' | 'HV_over_HH' | 'regime' | 'dyn_HH' | 'dyn_HV'>('HV');
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

  // Fetch initial catalog, story payload, and default ROI inspection
  useEffect(() => {
    async function loadInitial() {
      try {
        setLoading(true);
        const [catRes, storyRes, inspRes] = await Promise.all([
          fetch('/api/catalog'),
          fetch('/api/story'),
          fetch('/api/inspect?lon=30.9806&lat=29.3201&window_px=5'),
        ]);
        if (!catRes.ok || !storyRes.ok) {
          throw new Error('Failed to load catalog or story payload from FastAPI backend.');
        }
        const catJson: LayerCatalog = await catRes.json();
        const storyJson: StoryPayload = await storyRes.json();
        setCatalog(catJson);
        setStoryData(storyJson);
        if (inspRes.ok) {
          setInspectResult(await inspRes.json());
        }
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
        const res = await fetch(`/api/inspect?lon=${lon}&lat=${lat}&window_px=${winPx}`);
        if (res.ok) {
          const data: InspectResponse = await res.json();
          setInspectResult(data);
        }
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

  return (
    <div className="app-shell">
      {/* TOP MISSION HEADER BAR */}
      <header className="top-header">
        <div className="brand-block">
          <div className="nasa-badge">NASA SPACE APPS 2026 • DANCING WITH THE SARs</div>
          <h1 className="app-title">
            EARTH RHYTHM <span className="title-sub">NISAR L-Band Surface Change Storyteller</span>
          </h1>
          <div className="aoi-meta-pill">
            Fayoum Oasis, Egypt • Track 129 / Frame 016 Ascending • <code>NISAR_L2_GCOV_PROVISIONAL_V1</code> (CRID{' '}
            <code>P05023</code>) • 10 Passes (<code>2026-06-23</code> → <code>2026-10-21</code>)
          </div>
        </div>

        {/* MAP MODE SWITCHER */}
        <div className="mode-pill-group">
          <button
            className={`mode-btn ${mapMode === 'single' ? 'mode-btn-active' : ''}`}
            onClick={() => setMapMode('single')}
          >
            <Layers size={15} /> 10-Date Time Slider
          </button>
          <button
            className={`mode-btn ${mapMode === 'swipe' ? 'mode-btn-active' : ''}`}
            onClick={() => setMapMode('swipe')}
          >
            <SplitSquareHorizontal size={15} /> Before / After Swipe
          </button>
          <button
            className={`mode-btn ${mapMode === 'change' ? 'mode-btn-active' : ''}`}
            onClick={() => setMapMode('change')}
          >
            <Activity size={15} /> Change &amp; Disagreement
          </button>
          <button
            className={`mode-btn ${mapMode === 'masks' ? 'mode-btn-active' : ''}`}
            onClick={() => setMapMode('masks')}
          >
            <Compass size={15} /> Masks &amp; Exploratory InSAR
          </button>
        </div>

        {/* BASEMAP & OPACITY CONTROLS */}
        <div className="header-right-controls">
          <div className="control-group">
            <label>Basemap (Context):</label>
            <select value={basemap} onChange={(e) => setBasemap(e.target.value as BasemapType)}>
              <option value="satellite">ESRI Optical Satellite (Non-NISAR Context)</option>
              <option value="dark">CARTO Dark Matter Radar Canvas</option>
              <option value="osm">OpenStreetMap Topographic</option>
            </select>
          </div>
          <div className="control-group opacity-group">
            <label>SAR Opacity: {Math.round(opacity * 100)}%</label>
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
              {isPlaying ? 'Pause' : 'Animate 10 Dates'}
            </button>

            <div className="pol-toggle-group">
              <button
                className={`pol-chip ${singlePol === 'RGB' ? 'pol-chip-active' : ''}`}
                onClick={() => setSinglePol('RGB')}
              >
                Dual-Pol RGB (HH / HV / HH−HV)
              </button>
              <button
                className={`pol-chip ${singlePol === 'HH' ? 'pol-chip-active' : ''}`}
                onClick={() => setSinglePol('HH')}
              >
                HH Co-Pol (Surface / Double-Bounce)
              </button>
              <button
                className={`pol-chip ${singlePol === 'HV' ? 'pol-chip-active' : ''}`}
                onClick={() => setSinglePol('HV')}
              >
                HV Cross-Pol (Canopy Volume)
              </button>
            </div>

            <div className="date-scrubber">
              {dates.map((dt, idx) => (
                <button
                  key={dt}
                  className={`date-step-btn ${idx === activeDateIdx ? 'date-step-active' : ''}`}
                  onClick={() => {
                    setIsPlaying(false);
                    setActiveDateIdx(idx);
                  }}
                >
                  <span className="step-idx">Pass {idx + 1}</span>
                  <span className="step-date">{dt}</span>
                </button>
              ))}
            </div>
          </div>
        )}

        {mapMode === 'swipe' && (
          <div className="toolbar-row swipe-toolbar">
            <div className="swipe-select-box">
              <span className="side-tag left-tag">LEFT CURTAIN LAYER:</span>
              <select value={swipeLeftId} onChange={(e) => setSwipeLeftId(e.target.value)}>
                {catalog.overlays.map((o) => (
                  <option key={o.layer_id} value={o.layer_id}>
                    [{o.group}] {o.title}
                  </option>
                ))}
              </select>
            </div>
            <div className="swipe-presets">
              <button
                className="preset-btn"
                onClick={() => {
                  setSwipeLeftId('gcov_20260623_HV');
                  setSwipeRightId('gcov_20260810_HV');
                }}
              >
                Jun 23 vs Aug 10 (HV Growth)
              </button>
              <button
                className="preset-btn"
                onClick={() => {
                  setSwipeLeftId('gcov_20260810_HV');
                  setSwipeRightId('gcov_20261021_HV');
                }}
              >
                Aug 10 vs Oct 21 (HV Harvest)
              </button>
              <button
                className="preset-btn"
                onClick={() => {
                  setSwipeLeftId('delta_HH_20260810_to_20261021_sig');
                  setSwipeRightId('delta_HV_20260810_to_20261021_sig');
                }}
              >
                ΔHH vs ΔHV Disagreement
              </button>
            </div>
            <div className="swipe-select-box">
              <span className="side-tag right-tag">RIGHT CURTAIN LAYER:</span>
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
              <label>Seasonal Window:</label>
              <select value={changeInterval} onChange={(e) => setChangeInterval(e.target.value)}>
                <option value="20260623_to_20260810">Early → Peak Summer (2026-06-23 → 2026-08-10)</option>
                <option value="20260810_to_20261021">Peak Summer → Autumn Harvest (2026-08-10 → 2026-10-21)</option>
                <option value="20260623_to_20261021">Full 4-Month Span (2026-06-23 → 2026-10-21)</option>
              </select>
            </div>

            <div className="pol-toggle-group">
              <button
                className={`pol-chip ${changeMetric === 'HV' ? 'pol-chip-active' : ''}`}
                onClick={() => setChangeMetric('HV')}
              >
                ΔHV Canopy Change (τ = 2.03 dB)
              </button>
              <button
                className={`pol-chip ${changeMetric === 'HH' ? 'pol-chip-active' : ''}`}
                onClick={() => setChangeMetric('HH')}
              >
                ΔHH Surface/Wetting Change (τ = 2.73 dB)
              </button>
              <button
                className={`pol-chip ${changeMetric === 'regime' ? 'pol-chip-active' : ''}`}
                onClick={() => setChangeMetric('regime')}
              >
                7-Class Dual-Pol Regime &amp; Disagreement Map
              </button>
              <button
                className={`pol-chip ${changeMetric === 'HV_over_HH' ? 'pol-chip-active' : ''}`}
                onClick={() => setChangeMetric('HV_over_HH')}
              >
                Δ(HV/HH) Ratio
              </button>
              <button
                className={`pol-chip ${changeMetric === 'dyn_HV' ? 'pol-chip-active' : ''}`}
                onClick={() => setChangeMetric('dyn_HV')}
              >
                10-Date HV Dynamic Range
              </button>
              <button
                className={`pol-chip ${changeMetric === 'dyn_HH' ? 'pol-chip-active' : ''}`}
                onClick={() => setChangeMetric('dyn_HH')}
              >
                10-Date HH Dynamic Range
              </button>
            </div>

            {(changeMetric === 'HH' || changeMetric === 'HV') && (
              <label className="threshold-checkbox">
                <input
                  type="checkbox"
                  checked={thresholdMaskOnly}
                  onChange={(e) => setThresholdMaskOnly(e.target.checked)}
                />
                <span>
                  Hide Sub-Threshold Noise (|ΔdB| &lt; {changeMetric === 'HH' ? '2.73' : '2.03'} dB transparent)
                </span>
              </label>
            )}
          </div>
        )}

        {mapMode === 'masks' && (
          <div className="toolbar-row">
            <div className="control-group">
              <label>Select Geophysical Mask or Exploratory InSAR Layer:</label>
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
                setActiveTab('inspector');
              }
            }}
            onSelectRoi={(roi) => handleSelectRoi(roi, true)}
          />

          {/* Quick Focal ROI Jump Bar at Bottom of Map */}
          <div className="roi-quick-bar">
            <span className="quick-bar-label">
              <Crosshair size={13} /> Focal Story ROIs (200m × 200m):
            </span>
            {focalRois.map((roi, idx) => (
              <button
                key={roi.roi_id}
                className={`roi-quick-btn ${selectedRoiId === roi.roi_id ? 'roi-quick-active' : ''}`}
                onClick={() => handleSelectRoi(roi, true)}
              >
                <span className="pin-circle">{idx + 1}</span>
                {roi.roi_id.replace(/^ROI_0\d_/, '').replace(/_/g, ' ')}
              </button>
            ))}
          </div>
        </section>

        {/* RIGHT SCIENTIFIC WORKBENCH PANEL */}
        <aside className="workbench-panel">
          <nav className="workbench-tabs">
            <button
              className={`tab-btn ${activeTab === 'story' ? 'tab-btn-active' : ''}`}
              onClick={() => setActiveTab('story')}
            >
              <Sparkles size={14} /> Story Mode (6)
            </button>
            <button
              className={`tab-btn ${activeTab === 'inspector' ? 'tab-btn-active' : ''}`}
              onClick={() => setActiveTab('inspector')}
            >
              <Crosshair size={14} /> Pixel Inspector
            </button>
            <button
              className={`tab-btn ${activeTab === 'metadata' ? 'tab-btn-active' : ''}`}
              onClick={() => setActiveTab('metadata')}
            >
              <Database size={14} /> Rule 3 Metadata
            </button>
            <button
              className={`tab-btn ${activeTab === 'methods' ? 'tab-btn-active' : ''}`}
              onClick={() => setActiveTab('methods')}
            >
              <BookOpen size={14} /> Methods &amp; Limits
            </button>
          </nav>

          <div className="workbench-content">
            {/* TAB 1: 6-STEP GUIDED STORY MODE */}
            {activeTab === 'story' && (
              <div className="tab-pane story-pane">
                <div className="story-stepper-bar">
                  {STORY_STEPS.map((st, idx) => (
                    <button
                      key={st.id}
                      className={`step-dot-btn ${idx === storyStepIdx ? 'step-dot-active' : ''}`}
                      onClick={() => applyStoryStep(idx)}
                    >
                      {st.stepNumber}
                    </button>
                  ))}
                  <div className="step-nav-arrows">
                    <button
                      disabled={storyStepIdx === 0}
                      onClick={() => applyStoryStep(Math.max(0, storyStepIdx - 1))}
                    >
                      ← Prev
                    </button>
                    <button
                      disabled={storyStepIdx === STORY_STEPS.length - 1}
                      onClick={() => applyStoryStep(Math.min(STORY_STEPS.length - 1, storyStepIdx + 1))}
                    >
                      Next Chapter →
                    </button>
                  </div>
                </div>

                <div className="story-chapter-card">
                  <div className="chapter-badge">{activeStep.badge}</div>
                  <h2 className="chapter-title">{activeStep.title}</h2>
                  <div className="chapter-subtitle">{activeStep.subtitle}</div>

                  <p className="chapter-body">{activeStep.physicsTakeaway}</p>

                  <div className="pol-highlight-box">
                    <strong>Dual-Pol &amp; Wavelength Insight:</strong>
                    <p>{activeStep.whyPolarizationMatters}</p>
                  </div>
                </div>

                {/* Embedded Multi-Temporal Chart for Current Story Focal ROI */}
                {inspectResult && (
                  <div className="story-chart-card">
                    <div className="card-header-row">
                      <h3>
                        10-Date NISAR Trajectory •{' '}
                        <code>
                          ({inspectResult.coordinates.wgs84_lon.toFixed(4)}°E,{' '}
                          {inspectResult.coordinates.wgs84_lat.toFixed(4)}°N)
                        </code>
                      </h3>
                      <label className="s2-toggle-label">
                        <input
                          type="checkbox"
                          checked={showS2Overlay}
                          onChange={(e) => setShowS2Overlay(e.target.checked)}
                        />
                        <span>Overlay Sentinel-2 NDVI (Context)</span>
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

                    {/* Epistemic 3-Tier Statements (Rule 5) */}
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
                      <span className="section-eyebrow">LIVE CALIBRATED CUBE QUERY (/api/inspect)</span>
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
                      <label>Patch Window:</label>
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
                </div>

                <div className="story-chart-card">
                  <div className="card-header-row">
                    <h3>Multi-Temporal Backscatter (γ⁰ dB Median &amp; [P25, P75] IQR)</h3>
                    <label className="s2-toggle-label">
                      <input
                        type="checkbox"
                        checked={showS2Overlay}
                        onChange={(e) => setShowS2Overlay(e.target.checked)}
                      />
                      <span>Sentinel-2 L2A NDVI (Context)</span>
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

                {/* Seasonal Log-Ratio Interval Table */}
                <div className="data-table-card">
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
                </div>

                {/* External Meteorological Context Strip (Rule 2 — NASA POWER) */}
                <div className="external-context-card">
                  <div className="context-header">
                    <span className="rule2-badge">EXTERNAL NON-NISAR CONTEXT • RULE 2</span>
                    <strong>{nasaPower.source_label}</strong>
                  </div>
                  <p className="context-text">{nasaPower.scientific_implication}</p>
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

                {/* 4. Grounded Future NISAR Operational Applications */}
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
          </div>
        </aside>
      </main>
    </div>
  );
};

