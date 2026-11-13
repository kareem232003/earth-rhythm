import React, { useEffect, useRef, useState } from 'react';
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import { FocalROI, OverlayItem } from '../types';

export type BasemapType = 'dark' | 'satellite' | 'osm';

interface Props {
  leftOverlay?: OverlayItem;
  rightOverlay?: OverlayItem;
  isSwipeMode: boolean;
  opacity: number;
  basemap: BasemapType;
  focalRois: FocalROI[];
  selectedRoiId?: string;
  inspectedLonLat?: [number, number] | null;
  flyToTarget?: { center: [number, number]; zoom: number; seq: number } | null;
  onMapClick: (lon: number, lat: number) => void;
  onSelectRoi: (roi: FocalROI) => void;
}

function buildBasemapStyle(basemap: BasemapType): maplibregl.StyleSpecification {
  const tilesByType: Record<BasemapType, { urls: string[]; attribution: string }> = {
    dark: {
      urls: ['https://a.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}@2x.png'],
      attribution: '© OpenStreetMap contributors, © CARTO (External Basemap Context — Rule 2)',
    },
    satellite: {
      urls: ['https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'],
      attribution: '© Esri, Maxar, Earthstar Geographics (External Optical Basemap Context — Not NISAR, Rule 2)',
    },
    osm: {
      urls: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
      attribution: '© OpenStreetMap contributors (External Topographic Context — Rule 2)',
    },
  };

  const chosen = tilesByType[basemap];
  return {
    version: 8,
    sources: {
      basemap_src: {
        type: 'raster',
        tiles: chosen.urls,
        tileSize: 256,
        attribution: chosen.attribution,
      },
    },
    layers: [
      {
        id: 'basemap_layer',
        type: 'raster',
        source: 'basemap_src',
        minzoom: 0,
        maxzoom: 19,
      },
    ],
  };
}

function applyOverlayToMap(
  map: maplibregl.Map | null,
  overlay: OverlayItem | undefined,
  opacity: number
) {
  if (!map || !map.isStyleLoaded()) return;

  const srcId = 'nisar_overlay_src';
  const layerId = 'nisar_overlay_layer';

  if (!overlay) {
    if (map.getLayer(layerId)) map.removeLayer(layerId);
    if (map.getSource(srcId)) map.removeSource(srcId);
    return;
  }

  const existingSrc = map.getSource(srcId) as maplibregl.ImageSource | undefined;
  if (existingSrc) {
    existingSrc.updateImage({
      url: overlay.url,
      coordinates: overlay.maplibre_coordinates,
    });
    if (map.getLayer(layerId)) {
      map.setPaintProperty(layerId, 'raster-opacity', opacity);
    }
  } else {
    map.addSource(srcId, {
      type: 'image',
      url: overlay.url,
      coordinates: overlay.maplibre_coordinates,
    });
    map.addLayer({
      id: layerId,
      type: 'raster',
      source: srcId,
      paint: {
        'raster-opacity': opacity,
        'raster-fade-duration': 0,
        'raster-resampling': 'nearest',
      },
    });
  }
}

export const NisarMap: React.FC<Props> = ({
  leftOverlay,
  rightOverlay,
  isSwipeMode,
  opacity,
  basemap,
  focalRois,
  selectedRoiId,
  inspectedLonLat,
  flyToTarget,
  onMapClick,
  onSelectRoi,
}) => {
  const leftContainerRef = useRef<HTMLDivElement | null>(null);
  const rightContainerRef = useRef<HTMLDivElement | null>(null);
  const leftMapRef = useRef<maplibregl.Map | null>(null);
  const rightMapRef = useRef<maplibregl.Map | null>(null);
  const markersRef = useRef<maplibregl.Marker[]>([]);
  const inspectMarkerRef = useRef<maplibregl.Marker | null>(null);

  const [swipePct, setSwipePct] = useState<number>(50);
  const [isDraggingSwipe, setIsDraggingSwipe] = useState<boolean>(false);

  // Initialize left & right maps
  useEffect(() => {
    if (!leftContainerRef.current || !rightContainerRef.current) return;

    const initialCenter: [number, number] = [30.74, 29.34];
    const initialZoom = 9.6;

    const mapL = new maplibregl.Map({
      container: leftContainerRef.current,
      style: buildBasemapStyle(basemap),
      center: initialCenter,
      zoom: initialZoom,
      attributionControl: false,
    });

    const mapR = new maplibregl.Map({
      container: rightContainerRef.current,
      style: buildBasemapStyle(basemap),
      center: initialCenter,
      zoom: initialZoom,
      attributionControl: false,
    });

    mapL.addControl(new maplibregl.NavigationControl({ showCompass: true }), 'top-left');
    mapL.addControl(new maplibregl.ScaleControl({ maxWidth: 120, unit: 'metric' }), 'bottom-left');

    // Synchronize camera movement between mapL and mapR
    let syncing = false;
    const syncLtoR = () => {
      if (syncing) return;
      syncing = true;
      mapR.jumpTo({
        center: mapL.getCenter(),
        zoom: mapL.getZoom(),
        bearing: mapL.getBearing(),
        pitch: mapL.getPitch(),
      });
      syncing = false;
    };
    const syncRtoL = () => {
      if (syncing) return;
      syncing = true;
      mapL.jumpTo({
        center: mapR.getCenter(),
        zoom: mapR.getZoom(),
        bearing: mapR.getBearing(),
        pitch: mapR.getPitch(),
      });
      syncing = false;
    };

    mapL.on('move', syncLtoR);
    mapR.on('move', syncRtoL);

    const handleClick = (e: maplibregl.MapMouseEvent) => {
      onMapClick(e.lngLat.lng, e.lngLat.lat);
    };
    mapL.on('click', handleClick);
    mapR.on('click', handleClick);

    mapL.on('load', () => {
      applyOverlayToMap(mapL, leftOverlay, opacity);
    });
    mapR.on('load', () => {
      applyOverlayToMap(mapR, rightOverlay, opacity);
    });

    leftMapRef.current = mapL;
    rightMapRef.current = mapR;

    return () => {
      mapL.remove();
      mapR.remove();
      leftMapRef.current = null;
      rightMapRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Update basemap when changed
  useEffect(() => {
    const mapL = leftMapRef.current;
    const mapR = rightMapRef.current;
    if (!mapL || !mapR) return;

    const newStyle = buildBasemapStyle(basemap);
    mapL.setStyle(newStyle);
    mapR.setStyle(newStyle);

    mapL.once('styledata', () => {
      applyOverlayToMap(mapL, leftOverlay, opacity);
    });
    mapR.once('styledata', () => {
      applyOverlayToMap(mapR, rightOverlay, opacity);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [basemap]);

  // Update overlays & opacity
  useEffect(() => {
    const mapL = leftMapRef.current;
    if (mapL) {
      if (mapL.isStyleLoaded()) {
        applyOverlayToMap(mapL, leftOverlay, opacity);
      } else {
        mapL.once('load', () => applyOverlayToMap(mapL, leftOverlay, opacity));
      }
    }
  }, [leftOverlay, opacity]);

  useEffect(() => {
    const mapR = rightMapRef.current;
    if (mapR) {
      if (mapR.isStyleLoaded()) {
        applyOverlayToMap(mapR, rightOverlay, opacity);
      } else {
        mapR.once('load', () => applyOverlayToMap(mapR, rightOverlay, opacity));
      }
    }
  }, [rightOverlay, opacity]);

  // Render Focal ROI pins on Left Map (or top overlay)
  useEffect(() => {
    const mapL = leftMapRef.current;
    if (!mapL) return;

    markersRef.current.forEach((m) => m.remove());
    markersRef.current = [];

    focalRois.forEach((roi, idx) => {
      const el = document.createElement('button');
      const isSelected = roi.roi_id === selectedRoiId;
      el.className = `roi-map-pin ${isSelected ? 'roi-map-pin-active' : ''}`;
      el.innerHTML = `<span class="roi-pin-num">${idx + 1}</span>`;
      el.title = `${roi.roi_id}: ${roi.title}`;
      el.onclick = (ev) => {
        ev.stopPropagation();
        onSelectRoi(roi);
      };

      const marker = new maplibregl.Marker({ element: el, anchor: 'center' })
        .setLngLat([roi.wgs84_lon, roi.wgs84_lat])
        .addTo(mapL);

      markersRef.current.push(marker);
    });
  }, [focalRois, selectedRoiId, onSelectRoi]);

  // Render clicked inspection crosshair marker
  useEffect(() => {
    const mapL = leftMapRef.current;
    if (!mapL) return;

    if (inspectMarkerRef.current) {
      inspectMarkerRef.current.remove();
      inspectMarkerRef.current = null;
    }

    if (inspectedLonLat) {
      const el = document.createElement('div');
      el.className = 'inspect-crosshair-marker';
      inspectMarkerRef.current = new maplibregl.Marker({ element: el, anchor: 'center' })
        .setLngLat(inspectedLonLat)
        .addTo(mapL);
    }
  }, [inspectedLonLat]);

  // FlyTo camera when Story Mode step or ROI changes
  useEffect(() => {
    const mapL = leftMapRef.current;
    if (!mapL || !flyToTarget) return;
    mapL.flyTo({
      center: flyToTarget.center,
      zoom: flyToTarget.zoom,
      duration: 1400,
      essential: true,
    });
  }, [flyToTarget]);

  // Handle dragging swipe curtain
  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!isDraggingSwipe || !leftContainerRef.current) return;
    const rect = leftContainerRef.current.getBoundingClientRect();
    const pct = ((e.clientX - rect.left) / rect.width) * 100;
    setSwipePct(Math.max(5, Math.min(95, pct)));
  };

  return (
    <div
      className="map-stage"
      onMouseMove={handleMouseMove}
      onMouseUp={() => setIsDraggingSwipe(false)}
      onMouseLeave={() => setIsDraggingSwipe(false)}
    >
      {/* Base Left Map */}
      <div ref={leftContainerRef} className="map-canvas map-canvas-left" />

      {/* Clipped Right Map for Swipe Mode */}
      <div
        ref={rightContainerRef}
        className="map-canvas map-canvas-right"
        style={{
          clipPath: isSwipeMode ? `inset(0 0 0 ${swipePct}%)` : 'inset(0 0 0 100%)',
          pointerEvents: isSwipeMode ? 'auto' : 'none',
        }}
      />

      {/* Swipe Divider Handle & Labels */}
      {isSwipeMode && (
        <>
          <div
            className="swipe-divider-line"
            style={{ left: `${swipePct}%` }}
            onMouseDown={(e) => {
              e.preventDefault();
              setIsDraggingSwipe(true);
            }}
          >
            <div className="swipe-handle-pill">⇔ SWIPE</div>
          </div>
          {leftOverlay && (
            <div className="swipe-corner-badge swipe-badge-left">
              <span className="badge-side">LEFT</span> {leftOverlay.title}
            </div>
          )}
          {rightOverlay && (
            <div className="swipe-corner-badge swipe-badge-right">
              <span className="badge-side">RIGHT</span> {rightOverlay.title}
            </div>
          )}
        </>
      )}

      {/* Floating Legend Box on Map Bottom-Right */}
      {leftOverlay && (
        <div className="map-floating-legend">
          <div className="legend-header">
            <span className={`epistemic-chip epistemic-${leftOverlay.rule3_metadata.epistemic_tag.split(' ')[0].toLowerCase()}`}>
              {leftOverlay.rule3_metadata.epistemic_tag}
            </span>
            <span className="legend-title-text">{leftOverlay.title}</span>
          </div>
          <div className="legend-unit-sub">
            Units: <code>{leftOverlay.legend.unit}</code> • CRS: <code>{leftOverlay.rule3_metadata.crs}</code>
          </div>

          {leftOverlay.legend.stops && (
            <div className="legend-gradient-block">
              <div
                className="legend-color-bar"
                style={{
                  background: `linear-gradient(to right, ${leftOverlay.legend.stops.map((s) => s.color).join(', ')})`,
                }}
              />
              <div className="legend-stops-labels">
                {leftOverlay.legend.stops.map((s) => (
                  <div key={s.value} className="legend-stop-item">
                    <strong>{s.value > 0 ? `+${s.value}` : s.value}</strong>
                    <span>{s.label.replace(/^[-+0-9.]+ dB\s*/, '')}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {leftOverlay.legend.classes && (
            <div className="legend-categorical-grid">
              {leftOverlay.legend.classes.map((c) => (
                <div key={c.code} className="legend-cat-row">
                  <span className="legend-cat-swatch" style={{ backgroundColor: c.color }} />
                  <span className="legend-cat-label">{c.label}</span>
                </div>
              ))}
            </div>
          )}

          {leftOverlay.legend.channels && (
            <div className="legend-categorical-grid">
              {leftOverlay.legend.channels.map((ch) => {
                const lc = ch.channel.toLowerCase();
                const fallbackColor = lc.includes('green')
                  ? '#22c55e'
                  : lc.includes('red')
                  ? '#ef4444'
                  : lc.includes('blue') || lc.includes('cyan')
                  ? '#0ea5e9'
                  : '#b48a52';
                return (
                  <div key={ch.channel} className="legend-cat-row">
                    <span
                      className="legend-cat-swatch"
                      style={{ backgroundColor: ch.color || fallbackColor }}
                    />
                    <span className="legend-cat-label">
                      <strong>{ch.channel}</strong> ({ch.range}): {ch.meaning}
                    </span>
                  </div>
                );
              })}
            </div>
          )}

          {leftOverlay.exploratory_disclaimer && (
            <div className="gunw-disclaimer-box">{leftOverlay.exploratory_disclaimer}</div>
          )}
        </div>
      )}
    </div>
  );
};

