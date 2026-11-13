import React, { useState } from 'react';
import { Sentinel2PairedPoint, TimeSeriesPoint } from '../types';

interface Props {
  timeseries: TimeSeriesPoint[];
  activeDate?: string;
  onSelectDate?: (date: string) => void;
  sentinel2Points?: Sentinel2PairedPoint[];
  showSentinel2Overlay?: boolean;
  showIqrBands?: boolean;
}

export const TimeSeriesChart: React.FC<Props> = ({
  timeseries,
  activeDate,
  onSelectDate,
  sentinel2Points,
  showSentinel2Overlay = true,
  showIqrBands = true,
}) => {
  const [hoverIdx, setHoverIdx] = useState<number | null>(null);

  if (!timeseries || timeseries.length === 0) {
    return <div className="empty-chart">Click any location on the map to inspect its 10-date NISAR trajectory.</div>;
  }

  const width = 560;
  const height = 235;
  const padLeft = 46;
  const padRight = showSentinel2Overlay && sentinel2Points?.length ? 46 : 18;
  const padTop = 18;
  const padBottom = 34;
  const plotW = width - padLeft - padRight;
  const plotH = height - padTop - padBottom;

  const yMin = -26.0;
  const yMax = 2.0;

  const xForIdx = (i: number) =>
    padLeft + (timeseries.length > 1 ? (i / (timeseries.length - 1)) * plotW : plotW / 2);
  const yForDb = (db: number) => {
    const clamped = Math.max(yMin, Math.min(yMax, db));
    return padTop + ((yMax - clamped) / (yMax - yMin)) * plotH;
  };
  const yForNdvi = (ndvi: number) => {
    const clamped = Math.max(-0.3, Math.min(1.0, ndvi));
    return padTop + ((1.0 - clamped) / 1.3) * plotH;
  };

  const buildLinePath = (vals: number[], yFn: (v: number) => number) =>
    vals.map((v, i) => `${i === 0 ? 'M' : 'L'} ${xForIdx(i).toFixed(1)} ${yFn(v).toFixed(1)}`).join(' ');

  const buildBandPath = (p25: number[], p75: number[]) => {
    const top = p75.map((v, i) => `${i === 0 ? 'M' : 'L'} ${xForIdx(i).toFixed(1)} ${yForDb(v).toFixed(1)}`).join(' ');
    const bot = [...p25]
      .reverse()
      .map((v, revIdx) => {
        const i = p25.length - 1 - revIdx;
        return `L ${xForIdx(i).toFixed(1)} ${yForDb(v).toFixed(1)}`;
      })
      .join(' ');
    return `${top} ${bot} Z`;
  };

  const hhMed = timeseries.map((p) => p.hh_db_median);
  const hvMed = timeseries.map((p) => p.hv_db_median);
  const hhP25 = timeseries.map((p) => p.hh_db_p25);
  const hhP75 = timeseries.map((p) => p.hh_db_p75);
  const hvP25 = timeseries.map((p) => p.hv_db_p25);
  const hvP75 = timeseries.map((p) => p.hv_db_p75);

  // Map Sentinel-2 NDVI points to their paired NISAR date index
  const s2Coords: { idx: number; x: number; y: number; pt: Sentinel2PairedPoint }[] = [];
  if (showSentinel2Overlay && sentinel2Points) {
    sentinel2Points.forEach((sp) => {
      if (sp.sentinel2_ndvi_mean !== null) {
        const idx = timeseries.findIndex((t) => t.date === sp.paired_nisar_date);
        if (idx >= 0) {
          s2Coords.push({
            idx,
            x: xForIdx(idx),
            y: yForNdvi(sp.sentinel2_ndvi_mean),
            pt: sp,
          });
        }
      }
    });
  }

  const s2Path = s2Coords
    .map((c, i) => `${i === 0 ? 'M' : 'L'} ${c.x.toFixed(1)} ${c.y.toFixed(1)}`)
    .join(' ');

  const dbTicks = [-25, -20, -15, -10, -5, 0];
  const ndviTicks = [0.0, 0.4, 0.8];

  const activeIdx = hoverIdx !== null ? hoverIdx : timeseries.findIndex((t) => t.date === activeDate);
  const focusPt = activeIdx >= 0 ? timeseries[activeIdx] : timeseries[timeseries.length - 1];
  const focusS2 =
    activeIdx >= 0 && sentinel2Points
      ? sentinel2Points.find((s) => s.paired_nisar_date === timeseries[activeIdx].date)
      : undefined;

  return (
    <div className="ts-chart-wrapper">
      <div className="ts-chart-legend-bar">
        <span className="legend-pill hh-pill">
          <span className="dot hh-dot" /> HH Co-Pol (dB)
        </span>
        <span className="legend-pill hv-pill">
          <span className="dot hv-dot" /> HV Cross-Pol (dB)
        </span>
        {s2Coords.length > 0 && (
          <span className="legend-pill s2-pill" title="External Non-NISAR Context (Rule 2)">
            <span className="dot s2-dot" /> Sentinel-2 NDVI (Context)
          </span>
        )}
        <span className="sample-badge">N = {timeseries.length} dates</span>
      </div>

      <svg viewBox={`0 0 ${width} ${height}`} className="ts-svg">
        {/* Horizontal dB grid lines */}
        {dbTicks.map((tick) => {
          const y = yForDb(tick);
          return (
            <g key={tick}>
              <line x1={padLeft} y1={y} x2={width - padRight} y2={y} stroke="#1e293b" strokeWidth="1" />
              <text x={padLeft - 6} y={y + 3.5} textAnchor="end" fill="#94a3b8" fontSize="10" fontFamily="JetBrains Mono">
                {tick}
              </text>
            </g>
          );
        })}

        {/* Left Y-axis label */}
        <text
          x={12}
          y={padTop + plotH / 2}
          transform={`rotate(-90, 12, ${padTop + plotH / 2})`}
          textAnchor="middle"
          fill="#94a3b8"
          fontSize="10"
          fontWeight="600"
        >
          NISAR γ⁰ (dB)
        </text>

        {/* Right Y-axis for Sentinel-2 NDVI if active */}
        {s2Coords.length > 0 && (
          <>
            {ndviTicks.map((nt) => {
              const y = yForNdvi(nt);
              return (
                <text
                  key={nt}
                  x={width - padRight + 6}
                  y={y + 3.5}
                  textAnchor="start"
                  fill="#f59e0b"
                  fontSize="10"
                  fontFamily="JetBrains Mono"
                >
                  {nt.toFixed(1)}
                </text>
              );
            })}
            <text
              x={width - 8}
              y={padTop + plotH / 2}
              transform={`rotate(90, ${width - 8}, ${padTop + plotH / 2})`}
              textAnchor="middle"
              fill="#f59e0b"
              fontSize="9.5"
              fontWeight="600"
            >
              S2 NDVI (Context)
            </text>
          </>
        )}

        {/* NESZ Thermal Noise Floor Line (-23.26 dB HH / -24.52 dB HV) */}
        <line
          x1={padLeft}
          y1={yForDb(-23.26)}
          x2={width - padRight}
          y2={yForDb(-23.26)}
          stroke="#64748b"
          strokeDasharray="3 3"
          strokeWidth="1"
        />
        <text x={padLeft + 4} y={yForDb(-23.26) - 4} fill="#64748b" fontSize="8.5" fontFamily="JetBrains Mono">
          NESZ Floor (−23.3 dB HH / −24.5 dB HV)
        </text>

        {/* IQR [P25, P75] shaded bands */}
        {showIqrBands && (
          <>
            <path d={buildBandPath(hhP25, hhP75)} fill="rgba(56, 189, 248, 0.16)" />
            <path d={buildBandPath(hvP25, hvP75)} fill="rgba(16, 185, 129, 0.18)" />
          </>
        )}

        {/* HH and HV median trajectories */}
        <path d={buildLinePath(hhMed, yForDb)} fill="none" stroke="#38bdf8" strokeWidth="2.4" />
        <path d={buildLinePath(hvMed, yForDb)} fill="none" stroke="#10b981" strokeWidth="2.4" />

        {/* Sentinel-2 NDVI dashed context line */}
        {s2Coords.length > 1 && (
          <path d={s2Path} fill="none" stroke="#f59e0b" strokeWidth="1.8" strokeDasharray="4 3" />
        )}

        {/* Active date vertical cursor */}
        {activeIdx >= 0 && (
          <line
            x1={xForIdx(activeIdx)}
            y1={padTop}
            x2={xForIdx(activeIdx)}
            y2={padTop + plotH}
            stroke="#e2e8f0"
            strokeWidth="1.2"
            strokeDasharray="2 2"
          />
        )}

        {/* Data points & interactive hover columns */}
        {timeseries.map((pt, i) => {
          const cx = xForIdx(i);
          const isSelected = pt.date === activeDate || i === hoverIdx;
          return (
            <g
              key={pt.date}
              style={{ cursor: 'pointer' }}
              onMouseEnter={() => setHoverIdx(i)}
              onMouseLeave={() => setHoverIdx(null)}
              onClick={() => onSelectDate && onSelectDate(pt.date)}
            >
              <rect x={cx - plotW / 20} y={padTop} width={plotW / 10} height={plotH} fill="transparent" />
              <circle
                cx={cx}
                cy={yForDb(pt.hh_db_median)}
                r={isSelected ? 4.8 : 3.2}
                fill="#38bdf8"
                stroke="#0f172a"
                strokeWidth="1.2"
              />
              <circle
                cx={cx}
                cy={yForDb(pt.hv_db_median)}
                r={isSelected ? 4.8 : 3.2}
                fill="#10b981"
                stroke="#0f172a"
                strokeWidth="1.2"
              />
              {/* X-axis date tick */}
              <text
                x={cx}
                y={height - 10}
                textAnchor="middle"
                fill={isSelected ? '#f8fafc' : '#94a3b8'}
                fontSize="9.5"
                fontWeight={isSelected ? '700' : '400'}
                fontFamily="JetBrains Mono"
              >
                {pt.date.slice(5)}
              </text>
            </g>
          );
        })}

        {/* Sentinel-2 NDVI points */}
        {s2Coords.map((c) => (
          <circle
            key={c.pt.sentinel2_scene_id}
            cx={c.x}
            cy={c.y}
            r={3.2}
            fill="#f59e0b"
            stroke="#0f172a"
            strokeWidth="1"
          />
        ))}
      </svg>

      {/* Readout strip for hovered or active date */}
      {focusPt && (
        <div className="ts-readout-strip">
          <span className="readout-date">{focusPt.date}</span>
          <span className="readout-val hh-text">
            HH: <strong>{focusPt.hh_db_median.toFixed(2)} dB</strong>{' '}
            <small>[{focusPt.hh_db_p25.toFixed(1)}, {focusPt.hh_db_p75.toFixed(1)}]</small>
          </span>
          <span className="readout-val hv-text">
            HV: <strong>{focusPt.hv_db_median.toFixed(2)} dB</strong>{' '}
            <small>[{focusPt.hv_db_p25.toFixed(1)}, {focusPt.hv_db_p75.toFixed(1)}]</small>
          </span>
          <span className="readout-val ratio-text">
            HV/HH: <strong>{focusPt.hv_over_hh_db_median.toFixed(2)} dB</strong>
          </span>
          {focusS2 && focusS2.sentinel2_ndvi_mean !== null && (
            <span className="readout-val s2-text" title={`Scene: ${focusS2.sentinel2_scene_id} (${focusS2.sentinel2_date})`}>
              S2 NDVI: <strong>{focusS2.sentinel2_ndvi_mean.toFixed(3)}</strong>
            </span>
          )}
        </div>
      )}
    </div>
  );
};

