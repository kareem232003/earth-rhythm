import React, { useMemo, useState } from 'react';
import { FocalROI, LayerCatalog, StoryPayload } from '../types';
import {
  REGIME_FALLBACK_COLOR,
  REGIME_KEY_TO_CODE,
  REGIME_PLAIN,
  STRATA_PLAIN,
  tagClass,
} from '../plainLanguage';

/**
 * DASHBOARDS (additive tab)
 *
 * Every number on this page is read from the real Phase 2/3 reports served by
 * /api/story and the layer catalog served by /api/catalog. Nothing is
 * simulated, interpolated or forecast. Each card carries its Rule 5 tag.
 * External (non-NISAR) data is badged as such (Rule 2).
 */

interface Props {
  storyData: StoryPayload;
  catalog: LayerCatalog;
  focalRois: FocalROI[];
  selectedRoiId: string;
  onShowRegimeOnMap: (intervalMapKey: string) => void;
  onSelectDate: (date: string) => void;
}

type Section = 'glance' | 'breakdown' | 'landscapes' | 'context' | 'trust';
type Scope = 'aoi' | 'veg';

const SECTIONS: { id: Section; label: string; question: string }[] = [
  { id: 'glance', label: 'Season at a glance', question: 'What changed overall?' },
  { id: 'breakdown', label: 'Change breakdown', question: 'What kind of change, and how much?' },
  { id: 'landscapes', label: 'Landscape types', question: 'Which surfaces move the most?' },
  { id: 'context', label: 'Rain & optical', question: 'Does outside data agree?' },
  { id: 'trust', label: 'Can we trust it?', question: 'How big must a change be?' },
];

const f = (n: number | null | undefined, d = 2): string =>
  n === null || n === undefined || Number.isNaN(n) ? '—' : n.toFixed(d);

const signed = (n: number, d = 2): string => (n > 0 ? `+${n.toFixed(d)}` : n.toFixed(d));

const fmtInt = (n: number): string => Math.round(n).toLocaleString('en-US');

const TagChip: React.FC<{ tag: string }> = ({ tag }) => (
  <span className={`ep-tag ${tagClass(tag)}-tag`}>{tag}</span>
);

const ExternalBadge: React.FC<{ label: string }> = ({ label }) => (
  <span className="rule2-badge">NON-NISAR CONTEXT • {label}</span>
);

/* -------------------------------------------------------------------------- */
/* Small SVG building blocks                                                   */
/* -------------------------------------------------------------------------- */

const Sparkline: React.FC<{ values: number[]; color: string; width?: number; height?: number }> = ({
  values,
  color,
  width = 150,
  height = 38,
}) => {
  if (values.length < 2) return null;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const pad = 3;
  const pts = values.map((v, i) => {
    const x = pad + (i / (values.length - 1)) * (width - pad * 2);
    const y = pad + (1 - (v - min) / span) * (height - pad * 2);
    return [x, y] as const;
  });
  const d = pts.map(([x, y], i) => `${i === 0 ? 'M' : 'L'} ${x.toFixed(1)} ${y.toFixed(1)}`).join(' ');
  return (
    <svg className="dash-spark" viewBox={`0 0 ${width} ${height}`} width="100%" height={height} role="img">
      <path d={d} fill="none" stroke={color} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
      {pts.map(([x, y], i) => (
        <circle key={i} cx={x} cy={y} r={i === 0 || i === pts.length - 1 ? 2.6 : 1.6} fill={color} />
      ))}
    </svg>
  );
};

interface LineSeries {
  key: string;
  label: string;
  color: string;
  values: number[];
}

const MultiLineChart: React.FC<{
  dates: string[];
  series: LineSeries[];
  unitLabel: string;
  onSelectDate?: (d: string) => void;
}> = ({ dates, series, unitLabel, onSelectDate }) => {
  const [hidden, setHidden] = useState<Record<string, boolean>>({});
  const [hover, setHover] = useState<number | null>(null);

  const visible = series.filter((s) => !hidden[s.key]);
  const all = (visible.length ? visible : series).flatMap((s) => s.values);
  const rawMin = Math.min(...all);
  const rawMax = Math.max(...all);
  const yMin = Math.floor(rawMin - 1);
  const yMax = Math.ceil(rawMax + 1);

  const W = 560;
  const H = 250;
  const L = 44;
  const R = 14;
  const T = 14;
  const B = 36;
  const pw = W - L - R;
  const ph = H - T - B;
  const x = (i: number) => L + (dates.length > 1 ? (i / (dates.length - 1)) * pw : pw / 2);
  const y = (v: number) => T + ((yMax - v) / (yMax - yMin)) * ph;
  const ticks = 5;
  const tickVals = Array.from({ length: ticks }, (_, i) => yMin + ((yMax - yMin) * i) / (ticks - 1));

  return (
    <div className="dash-chart">
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label="Multi-series backscatter chart">
        {tickVals.map((tv) => (
          <g key={tv}>
            <line x1={L} x2={W - R} y1={y(tv)} y2={y(tv)} stroke="#1e293b" strokeWidth={1} />
            <text x={L - 6} y={y(tv) + 3} fontSize={9} fill="#94a3b8" textAnchor="end">
              {tv.toFixed(0)}
            </text>
          </g>
        ))}
        <text x={10} y={T + 4} fontSize={9} fill="#94a3b8">
          {unitLabel}
        </text>
        {dates.map((d, i) => (
          <g key={d}>
            <text
              x={x(i)}
              y={H - 12}
              fontSize={8.5}
              fill={hover === i ? '#f8fafc' : '#94a3b8'}
              textAnchor="middle"
              style={{ cursor: onSelectDate ? 'pointer' : 'default' }}
              onClick={() => onSelectDate && onSelectDate(d)}
            >
              {d.slice(5)}
            </text>
            <rect
              x={x(i) - pw / dates.length / 2}
              y={T}
              width={pw / dates.length}
              height={ph}
              fill={hover === i ? 'rgba(56,189,248,0.07)' : 'transparent'}
              onMouseEnter={() => setHover(i)}
              onMouseLeave={() => setHover(null)}
              onClick={() => onSelectDate && onSelectDate(d)}
              style={{ cursor: onSelectDate ? 'pointer' : 'default' }}
            />
          </g>
        ))}
        {visible.map((s) => (
          <g key={s.key}>
            <path
              d={s.values.map((v, i) => `${i === 0 ? 'M' : 'L'} ${x(i).toFixed(1)} ${y(v).toFixed(1)}`).join(' ')}
              fill="none"
              stroke={s.color}
              strokeWidth={2.2}
              strokeLinejoin="round"
              pointerEvents="none"
            />
            {s.values.map((v, i) => (
              <circle key={i} cx={x(i)} cy={y(v)} r={hover === i ? 3.8 : 2.4} fill={s.color} pointerEvents="none" />
            ))}
          </g>
        ))}
      </svg>

      <div className="dash-legend">
        {series.map((s) => (
          <button
            key={s.key}
            className={`dash-legend-chip ${hidden[s.key] ? 'dash-legend-off' : ''}`}
            onClick={() => setHidden((h) => ({ ...h, [s.key]: !h[s.key] }))}
            title="Click to show/hide"
          >
            <span className="dash-swatch" style={{ background: s.color }} />
            {s.label}
          </button>
        ))}
      </div>

      {hover !== null && (
        <div className="dash-hover-readout">
          <strong>{dates[hover]}</strong>
          {visible.map((s) => (
            <span key={s.key}>
              <span className="dash-swatch" style={{ background: s.color }} /> {s.label}: {f(s.values[hover])} dB
            </span>
          ))}
        </div>
      )}
    </div>
  );
};

/* -------------------------------------------------------------------------- */
/* Data helpers                                                                */
/* -------------------------------------------------------------------------- */

interface IntervalEval {
  mapKey: string;
  label: string;
  dateStart: string;
  dateEnd: string;
  aoi: any;
  veg: any;
}

interface ClassRow {
  code: number;
  key: string;
  pct: number;
  area: number;
  pixels: number;
  rule: string;
}

const classRows = (evalBlock: any): ClassRow[] => {
  const rb = evalBlock?.regime_breakdown || {};
  return Object.entries(rb)
    .map(([key, v]: [string, any]) => ({
      code: typeof v.class_code === 'number' ? v.class_code : REGIME_KEY_TO_CODE[key] ?? 0,
      key,
      pct: v.pct_of_valid_aoi as number,
      area: v.area_km2 as number,
      pixels: v.pixel_count as number,
      rule: v.rule as string,
    }))
    .sort((a, b) => a.code - b.code);
};

/* -------------------------------------------------------------------------- */
/* Main component                                                              */
/* -------------------------------------------------------------------------- */

export const DashboardsPanel: React.FC<Props> = ({
  storyData,
  catalog,
  focalRois,
  selectedRoiId,
  onShowRegimeOnMap,
  onSelectDate,
}) => {
  const [section, setSection] = useState<Section>('glance');
  const [scope, setScope] = useState<Scope>('aoi');
  const [intervalIdx, setIntervalIdx] = useState<number>(1);
  const [strataMetric, setStrataMetric] = useState<'hv' | 'hh'>('hv');

  const p3: any = storyData.phase3_change_and_timeseries;

  const intervals: IntervalEval[] = useMemo(() => {
    const raw = Object.values(p3.interval_change_evaluations || {}) as any[];
    return raw
      .map((iv) => ({
        mapKey: `${String(iv.date_start).replace(/-/g, '')}_to_${String(iv.date_end).replace(/-/g, '')}`,
        label: iv.label as string,
        dateStart: iv.date_start as string,
        dateEnd: iv.date_end as string,
        aoi: iv.aoi_valid_evaluation,
        veg: iv.vegetated_agriculture_only_evaluation,
      }))
      // Shortest window first: early→peak, peak→autumn, then the full span.
      .sort((a, b) => {
        const span = (v: IntervalEval) => new Date(v.dateEnd).getTime() - new Date(v.dateStart).getTime();
        return span(a) - span(b) || a.dateStart.localeCompare(b.dateStart);
      });
  }, [p3]);

  const safeIdx = Math.min(intervalIdx, Math.max(0, intervals.length - 1));
  const iv = intervals[safeIdx];
  const evalBlock = iv ? (scope === 'aoi' ? iv.aoi : iv.veg) : undefined;
  const rows = useMemo(() => classRows(evalBlock), [evalBlock]);

  // Colours come from the live legend of the regime layer, so the dashboard
  // always matches the map.
  const regimeColors: Record<number, string> = useMemo(() => {
    const out: Record<number, string> = { ...REGIME_FALLBACK_COLOR };
    if (!iv) return out;
    const layer = catalog.overlays.find((o) => o.layer_id === `dual_pol_regime_${iv.mapKey}`);
    layer?.legend.classes?.forEach((c) => {
      out[c.code] = c.color;
    });
    return out;
  }, [catalog, iv]);

  const byCode = (code: number): ClassRow | undefined => rows.find((r) => r.code === code);
  const valid = evalBlock?.valid_evaluated_area_km2 as number | undefined;

  const IntervalPicker = (
    <div className="dash-controls">
      <div className="dash-control">
        <label>Time window</label>
        <select value={safeIdx} onChange={(e) => setIntervalIdx(parseInt(e.target.value, 10))}>
          {intervals.map((v, i) => (
            <option key={v.mapKey} value={i}>
              {v.dateStart} → {v.dateEnd}
            </option>
          ))}
        </select>
      </div>
      <div className="dash-control">
        <label>Area counted</label>
        <div className="dash-seg">
          <button className={scope === 'aoi' ? 'on' : ''} onClick={() => setScope('aoi')}>
            Whole valid area
          </button>
          <button className={scope === 'veg' ? 'on' : ''} onClick={() => setScope('veg')}>
            Farmland only
          </button>
        </div>
      </div>
    </div>
  );

  /* ----------------------------- SECTION: GLANCE ----------------------------- */
  const renderGlance = () => {
    if (!iv || !evalBlock) return <div className="empty-chart">No interval evaluations found in the Phase 3 report.</div>;
    const none = byCode(0);
    const growth = byCode(1);
    const harvest = byCode(2);
    const surfUp = byCode(3);
    const surfDn = byCode(4);
    const dis5 = byCode(5);
    const dis6 = byCode(6);
    const surfacePct = (surfUp?.pct ?? 0) + (surfDn?.pct ?? 0);
    const surfaceArea = (surfUp?.area ?? 0) + (surfDn?.area ?? 0);
    const disPct = (dis5?.pct ?? 0) + (dis6?.pct ?? 0);
    const disArea = (dis5?.area ?? 0) + (dis6?.area ?? 0);

    const changed = rows.filter((r) => r.code !== 0).sort((a, b) => b.area - a.area);
    const top = changed[0];

    const kpis: { label: string; value: string; sub: string; plain: string; color: string }[] = [
      {
        label: 'No detectable change',
        value: `${f(none?.pct, 1)}%`,
        sub: `${f(none?.area, 0)} km²`,
        plain: 'Both radar signals stayed inside the noise threshold.',
        color: regimeColors[0],
      },
      {
        label: 'Plant volume up',
        value: `${f(growth?.pct, 1)}%`,
        sub: `${f(growth?.area, 0)} km²`,
        plain: 'HV rose more than its threshold: consistent with growth.',
        color: regimeColors[1],
      },
      {
        label: 'Plant volume down',
        value: `${f(harvest?.pct, 1)}%`,
        sub: `${f(harvest?.area, 0)} km²`,
        plain: 'HV fell more than its threshold: consistent with harvest.',
        color: regimeColors[2],
      },
      {
        label: 'Surface-only change',
        value: `${f(surfacePct, 1)}%`,
        sub: `${f(surfaceArea, 0)} km²`,
        plain: 'Only HH moved: soil wetness, tillage, drying or flooding.',
        color: regimeColors[3],
      },
      {
        label: 'HH & HV disagree',
        value: `${f(disPct, 2)}%`,
        sub: `${f(disArea, 1)} km²`,
        plain: 'The two signals moved in opposite directions.',
        color: regimeColors[5],
      },
    ];

    // Season arc: growth vs harvest area in every window, for the chosen scope.
    const arc = intervals.map((v) => {
      const r = classRows(scope === 'aoi' ? v.aoi : v.veg);
      return {
        label: `${v.dateStart.slice(5)} → ${v.dateEnd.slice(5)}`,
        growth: r.find((x) => x.code === 1)?.area ?? 0,
        harvest: r.find((x) => x.code === 2)?.area ?? 0,
      };
    });
    const arcMax = Math.max(1, ...arc.flatMap((a) => [a.growth, a.harvest]));

    return (
      <>
        {IntervalPicker}

        <div className="dash-card dash-callout">
          <TagChip tag="CHANGE DETECTION" />
          <p>
            Between <strong>{iv.dateStart}</strong> and <strong>{iv.dateEnd}</strong>, <strong>{f(none?.pct, 1)}%</strong>{' '}
            of the {f(valid, 0)} km² evaluated showed no change above the noise threshold.
            {top && (
              <>
                {' '}
                The largest detected change class was “<strong>{REGIME_PLAIN[top.code]?.short}</strong>” with{' '}
                <strong>{f(top.area, 1)} km²</strong> ({f(top.pct, 2)}%).
              </>
            )}
          </p>
          {top && (
            <div className="dash-subnote">
              <TagChip tag="INTERPRETATION (hypothesis)" />
              <span>{REGIME_PLAIN[top.code]?.hypothesis}</span>
            </div>
          )}
        </div>

        <div className="dash-kpi-caption">
          <TagChip tag="CHANGE DETECTION" />
          <span>Share of the evaluated area in each class, {iv.dateStart} → {iv.dateEnd}</span>
        </div>
        <div className="kpi-grid">
          {kpis.map((k) => (
            <div key={k.label} className="kpi-card" style={{ borderTopColor: k.color }}>
              <div className="kpi-label">{k.label}</div>
              <div className="kpi-value">{k.value}</div>
              <div className="kpi-sub">{k.sub}</div>
              <div className="kpi-plain">{k.plain}</div>
            </div>
          ))}
        </div>

        <div className="dash-card">
          <div className="dash-card-head">
            <h4>Season arc: growth vs harvest area</h4>
            <TagChip tag="CHANGE DETECTION" />
          </div>
          <p className="dash-help">
            Each row is one time window. The amber bar is area where plant volume dropped, the green bar is area where it rose.
            Notice how the balance flips from early summer to autumn.
          </p>
          <div className="arc-rows">
            {arc.map((a) => (
              <div key={a.label} className="arc-row">
                <div className="arc-label">{a.label}</div>
                <div className="arc-bars">
                  <div className="arc-bar-line">
                    <div
                      className="arc-bar"
                      style={{ width: `${(a.growth / arcMax) * 100}%`, background: regimeColors[1] }}
                    />
                    <span>{f(a.growth, 0)} km² ↑</span>
                  </div>
                  <div className="arc-bar-line">
                    <div
                      className="arc-bar"
                      style={{ width: `${(a.harvest / arcMax) * 100}%`, background: regimeColors[2] }}
                    />
                    <span>{f(a.harvest, 0)} km² ↓</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </>
    );
  };

  /* ---------------------------- SECTION: BREAKDOWN ---------------------------- */
  const renderBreakdown = () => {
    if (!iv || !evalBlock) return <div className="empty-chart">No interval evaluations found in the Phase 3 report.</div>;
    const total = rows.reduce((s, r) => s + r.pct, 0) || 1;
    const dis: any = evalBlock.polarization_disagreement_summary;

    return (
      <>
        {IntervalPicker}

        <div className="dash-card">
          <div className="dash-card-head">
            <h4>Where does the evaluated area fall?</h4>
            <TagChip tag="CHANGE DETECTION" />
          </div>
          <p className="dash-help">
            One bar = 100% of the valid area for this window. Hover a colour to see its share. Colours are exactly the
            map legend colours.
          </p>
          <div className="stack-bar" role="img" aria-label="Share of area per change class">
            {rows.map((r) => (
              <div
                key={r.code}
                className="stack-seg"
                style={{ width: `${(r.pct / total) * 100}%`, background: regimeColors[r.code] }}
                title={`${REGIME_PLAIN[r.code]?.short}: ${f(r.pct, 2)}% • ${f(r.area, 1)} km²`}
              />
            ))}
          </div>
          <div className="stack-axis">
            <span>0%</span>
            <span>100% of {f(valid, 0)} km²</span>
          </div>
        </div>

        <div className="dash-card">
          <div className="dash-card-head">
            <h4>The seven change classes in plain words</h4>
            <button className="dash-link-btn" onClick={() => iv && onShowRegimeOnMap(iv.mapKey)}>
              Show this window on the map →
            </button>
          </div>
          <div className="class-list">
            {rows.map((r) => (
              <div key={r.code} className="class-row">
                <span className="class-dot" style={{ background: regimeColors[r.code] }} />
                <div className="class-main">
                  <div className="class-title">
                    {REGIME_PLAIN[r.code]?.short}
                    <span className="class-num">
                      {f(r.pct, 2)}% • {f(r.area, 1)} km²
                    </span>
                  </div>
                  <div className="class-bar-track">
                    <div
                      className="class-bar-fill"
                      style={{ width: `${Math.max(0.5, r.pct)}%`, background: regimeColors[r.code] }}
                    />
                  </div>
                  <div className="class-meaning">{REGIME_PLAIN[r.code]?.meaning}</div>
                  <div className="class-rule">
                    <code>{r.rule}</code>
                  </div>
                  {r.code !== 0 && (
                    <div className="dash-subnote">
                      <TagChip tag="INTERPRETATION (hypothesis)" />
                      <span>{REGIME_PLAIN[r.code]?.hypothesis}</span>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>

        {dis && (
          <div className="dash-card">
            <div className="dash-card-head">
              <h4>Why two polarizations are better than one</h4>
              <TagChip tag="CHANGE DETECTION" />
            </div>
            <div className="mini-kpis">
              <div>
                <strong>{f(dis.hv_only_change_hh_stable_area_km2, 1)} km²</strong>
                <span>changed in HV only (plant volume), HH unchanged</span>
              </div>
              <div>
                <strong>{f(dis.hh_only_change_hv_stable_area_km2, 1)} km²</strong>
                <span>changed in HH only (surface), HV unchanged</span>
              </div>
              <div>
                <strong>{f(dis.opposite_sign_disagreement_area_km2, 2)} km²</strong>
                <span>moved in opposite directions</span>
              </div>
            </div>
            <p className="dash-help">
              A radar with a single polarization would blend these three very different situations together.
            </p>
          </div>
        )}
      </>
    );
  };

  /* --------------------------- SECTION: LANDSCAPES --------------------------- */
  const strata: any = p3.basin_strata_timeseries || {};
  const strataOrder = STRATA_PLAIN.filter((s) => strata[s.key]);

  const renderLandscapes = () => {
    if (strataOrder.length === 0) {
      return <div className="empty-chart">No per-landscape time series found in the Phase 3 report.</div>;
    }
    const dateList: string[] = (strata[strataOrder[0].key].timeseries as any[]).map((t) => t.date as string);
    const field = strataMetric === 'hv' ? 'hv_db_median' : 'hh_db_median';
    const rangeField = strataMetric === 'hv' ? 'hv_seasonal_median_range_db' : 'hh_seasonal_median_range_db';
    const series: LineSeries[] = strataOrder.map((s) => ({
      key: s.key,
      label: s.label,
      color: s.color,
      values: (strata[s.key].timeseries as any[]).map((t) => t[field] as number),
    }));
    const ranked = strataOrder
      .map((s) => ({ s, range: strata[s.key][rangeField] as number }))
      .sort((a, b) => b.range - a.range);
    const maxRange = Math.max(0.1, ...ranked.map((r) => r.range));

    return (
      <>
        <div className="dash-controls">
          <div className="dash-control">
            <label>Polarization</label>
            <div className="dash-seg">
              <button className={strataMetric === 'hv' ? 'on' : ''} onClick={() => setStrataMetric('hv')}>
                HV (plant volume)
              </button>
              <button className={strataMetric === 'hh' ? 'on' : ''} onClick={() => setStrataMetric('hh')}>
                HH (surface)
              </button>
            </div>
          </div>
        </div>

        <div className="dash-card">
          <div className="dash-card-head">
            <h4>Typical brightness per landscape type, over {dateList.length} passes</h4>
            <TagChip tag="OBSERVATION" />
          </div>
          <p className="dash-help">
            Each line is the median backscatter (dB) of all pixels of one landscape type on each date. Click a date label to
            show that pass on the map. Click a legend chip to hide a line.
          </p>
          <MultiLineChart
            dates={dateList}
            series={series}
            unitLabel={`γ⁰ ${strataMetric.toUpperCase()} median (dB)`}
            onSelectDate={onSelectDate}
          />
        </div>

        <div className="dash-card">
          <div className="dash-card-head">
            <h4>Which landscape swings the most?</h4>
            <TagChip tag="OBSERVATION" />
          </div>
          <p className="dash-help">
            Season range = highest minus lowest date-median ({strataMetric.toUpperCase()}). Because these are medians over
            thousands of pixels, they understate how much individual fields change.
          </p>
          <div className="rank-list">
            {ranked.map(({ s, range }) => (
              <div key={s.key} className="rank-row">
                <div className="rank-label">{s.label}</div>
                <div className="rank-track">
                  <div className="rank-fill" style={{ width: `${(range / maxRange) * 100}%`, background: s.color }} />
                </div>
                <div className="rank-val">{f(range, 2)} dB</div>
              </div>
            ))}
          </div>
        </div>

        <div className="strata-grid">
          {strataOrder.map((s) => {
            const st = strata[s.key];
            const vals = (st.timeseries as any[]).map((t) => t[field] as number);
            return (
              <div key={s.key} className="dash-card strata-card" style={{ borderTopColor: s.color }}>
                <div className="strata-title">{s.label}</div>
                <div className="strata-meta">
                  {f(st.area_km2, 1)} km² • N = {st.temporal_sample_count_N_dates} dates
                </div>
                <Sparkline values={vals} color={s.color} />
                <div className="strata-range">
                  {strataMetric.toUpperCase()} range: <strong>{f(st[rangeField], 2)} dB</strong>
                </div>
                <div className="strata-what">{s.whatItIs}</div>
                <div className="dash-subnote">
                  <TagChip tag="INTERPRETATION (hypothesis)" />
                  <span>{s.hypothesis}</span>
                </div>
              </div>
            );
          })}
        </div>
      </>
    );
  };

  /* ----------------------------- SECTION: CONTEXT ----------------------------- */
  const renderContext = () => {
    const ext = p3.external_context_non_nisar;
    const power = ext?.nasa_power_meteorology;
    const s2 = ext?.sentinel2_l2a_optical_ndvi;
    const corr = s2?.hv_vs_ndvi_correlations || {};
    const vegSeries: any[] | undefined = strata.vegetated_agriculture?.timeseries;

    // Rain bars + HV line share the NISAR overpass dates (dates must match).
    const weather: any[] = power?.nisar_overpass_dates_weather || [];
    const paired = weather
      .map((w) => {
        const hv = vegSeries?.find((t) => t.date === w.nisar_date);
        return hv ? { date: w.nisar_date as string, rain: w.precip_mm_day as number, wind: w.wind_speed_2m_m_s as number, hv: hv.hv_db_median as number } : null;
      })
      .filter((x): x is { date: string; rain: number; wind: number; hv: number } => x !== null);

    const rainMax = Math.max(1, ...paired.map((p) => p.rain));
    const hvMin = paired.length ? Math.min(...paired.map((p) => p.hv)) - 1 : -20;
    const hvMax = paired.length ? Math.max(...paired.map((p) => p.hv)) + 1 : -10;
    const W = 560;
    const H = 230;
    const L = 44;
    const R = 44;
    const T = 14;
    const B = 34;
    const pw = W - L - R;
    const ph = H - T - B;
    const x = (i: number) => L + (paired.length > 1 ? (i / (paired.length - 1)) * pw : pw / 2);
    const yHv = (v: number) => T + ((hvMax - v) / (hvMax - hvMin)) * ph;
    const yRain = (v: number) => T + (1 - v / rainMax) * ph;
    const barW = Math.min(22, pw / Math.max(1, paired.length) - 6);

    const total = power?.total_accumulated_precipitation_mm as number | undefined;
    const rainHypothesis =
      total !== undefined && total < 5
        ? 'Very little rain fell over the whole period, so rainfall alone is an unlikely driver of the radar changes. Irrigation or canal water is a more plausible source of any wetting, but this app cannot confirm that.'
        : 'Some rain fell during the period. Rain wets soil and can brighten backscatter, so compare the rain bars with the radar line before attributing changes to crops.';

    const rois = focalRois.filter((r) => corr[r.roi_id]);

    return (
      <>
        <div className="dash-card">
          <div className="dash-card-head">
            <h4>Rain at each satellite pass vs. farmland radar</h4>
            <ExternalBadge label="RULE 2" />
          </div>
          <p className="dash-help">
            Blue bars: daily rain on each overpass date ({power?.source_label || 'NASA POWER'}). Green line: NISAR HV median
            over farmland. Rain is outside context, not NISAR data.
          </p>

          {paired.length > 0 ? (
            <div className="dash-chart">
              <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label="Rain vs HV chart">
                {[0, 0.25, 0.5, 0.75, 1].map((t) => (
                  <line key={t} x1={L} x2={W - R} y1={T + t * ph} y2={T + t * ph} stroke="#1e293b" />
                ))}
                {[0, 0.5, 1].map((t) => (
                  <text key={t} x={L - 6} y={T + (1 - t) * ph + 3} fontSize={9} fill="#38bdf8" textAnchor="end">
                    {(rainMax * t).toFixed(1)}
                  </text>
                ))}
                {[0, 0.5, 1].map((t) => (
                  <text key={t} x={W - R + 6} y={T + (1 - t) * ph + 3} fontSize={9} fill="#22c55e">
                    {(hvMin + (hvMax - hvMin) * t).toFixed(0)}
                  </text>
                ))}
                <text x={4} y={9} fontSize={8.5} fill="#38bdf8">
                  rain mm/day
                </text>
                <text x={W - R - 14} y={9} fontSize={8.5} fill="#22c55e">
                  HV dB
                </text>
                {paired.map((p, i) => (
                  <g key={p.date}>
                    <rect
                      x={x(i) - barW / 2}
                      y={yRain(p.rain)}
                      width={barW}
                      height={Math.max(1, T + ph - yRain(p.rain))}
                      fill="#38bdf8"
                      opacity={0.75}
                    />
                    <text x={x(i)} y={H - 12} fontSize={8.5} fill="#94a3b8" textAnchor="middle">
                      {p.date.slice(5)}
                    </text>
                  </g>
                ))}
                <path
                  d={paired.map((p, i) => `${i === 0 ? 'M' : 'L'} ${x(i).toFixed(1)} ${yHv(p.hv).toFixed(1)}`).join(' ')}
                  fill="none"
                  stroke="#22c55e"
                  strokeWidth={2.2}
                />
                {paired.map((p, i) => (
                  <circle key={p.date} cx={x(i)} cy={yHv(p.hv)} r={2.6} fill="#22c55e" />
                ))}
              </svg>
            </div>
          ) : (
            <div className="empty-chart">Weather records could not be matched to NISAR dates.</div>
          )}

          {power && (
            <div className="mini-kpis">
              <div>
                <strong>{f(power.total_accumulated_precipitation_mm, 2)} mm</strong>
                <span>total rain in the window</span>
              </div>
              <div>
                <strong>{power.days_with_precip_ge_0p5mm} days</strong>
                <span>with ≥ 0.5 mm rain</span>
              </div>
              <div>
                <strong>{f(power.max_2m_wind_speed_m_s, 1)} m/s</strong>
                <span>strongest daily wind (matters for water roughness)</span>
              </div>
            </div>
          )}
          <div className="dash-subnote">
            <TagChip tag="INTERPRETATION (hypothesis)" />
            <span>{rainHypothesis}</span>
          </div>
        </div>

        <div className="dash-card">
          <div className="dash-card-head">
            <h4>Do radar and optical greenness move together?</h4>
            <ExternalBadge label="SENTINEL-2 NDVI" />
          </div>
          <p className="dash-help">
            Each bar is Pearson r between NISAR HV and Sentinel-2 NDVI at one focal area over the summer cycle. Right of the
            centre line = they rise and fall together. This is supporting evidence, not proof, and it rests on few dates.
          </p>
          <div className="corr-list">
            {rois.map((r) => {
              const c = corr[r.roi_id];
              const val = c.summer_cycle_8date_pearson_r as number;
              const isSel = r.roi_id === selectedRoiId;
              return (
                <div key={r.roi_id} className={`corr-row ${isSel ? 'corr-selected' : ''}`}>
                  <div className="corr-label">{r.title}</div>
                  <div className="corr-track">
                    <div className="corr-zero" />
                    <div
                      className="corr-fill"
                      style={{
                        left: val >= 0 ? '50%' : `${50 + (val / 1) * 50}%`,
                        width: `${Math.abs(val) * 50}%`,
                        background: val >= 0 ? '#10b981' : '#ef4444',
                      }}
                    />
                  </div>
                  <div className="corr-val">
                    r = {f(val, 2)}
                    <small>
                      p = {f(c.summer_cycle_8date_p_value, 4)} • all-dates Spearman ρ = {f(c.full_9date_spearman_rho, 2)}
                    </small>
                  </div>
                </div>
              );
            })}
          </div>
          <p className="dash-help">
            Caution: with only about eight paired dates a high r can still be chance, and water or desert areas are not
            expected to follow a vegetation relationship, so read those rows with care.
          </p>
          <div className="dash-subnote">
            <TagChip tag="OBSERVATION" />
            <span>{s2?.source_label}</span>
          </div>
        </div>
      </>
    );
  };

  /* ------------------------------ SECTION: TRUST ------------------------------ */
  const renderTrust = () => {
    const td: any = p3.threshold_derivation || {};
    const pols: { key: 'HH' | 'HV'; label: string; color: string }[] = [
      { key: 'HH', label: 'HH (co-pol, surface)', color: '#38bdf8' },
      { key: 'HV', label: 'HV (cross-pol, plant volume)', color: '#22c55e' },
    ];
    const first = catalog.overlays[0]?.rule3_metadata;

    return (
      <>
        <div className="dash-card dash-callout">
          <TagChip tag="CHANGE DETECTION" />
          <p>
            A change is drawn on the map only if it is bigger than a threshold <strong>τ</strong>. τ is measured from how much{' '}
            <strong>stable desert</strong> varies by chance ({fmtInt(td?.HH?.stable_desert_pixel_count || 0)} desert pixels, fixed random
            seed {td?.random_seed ?? '—'}), so noise is not mistaken for change.
          </p>
        </div>

        {pols.map((p) => {
          const d = td?.[p.key];
          if (!d) return null;
          const marks: { name: string; value: number; kind: 'ref' | 'adopted' }[] = [
            { name: '3σ theoretical speckle', value: d.theoretical_3sigma_speckle_threshold_db, kind: 'ref' },
            { name: '12-day 3σ (desert, robust)', value: d.empirical_12day_3sigma_mad_db, kind: 'ref' },
            { name: '12-day 99th percentile (desert)', value: d.empirical_12day_p99_abs_db, kind: 'ref' },
            { name: 'Adopted τ', value: d.recommended_threshold_db, kind: 'adopted' },
          ];
          const maxV = Math.max(...marks.map((m) => m.value)) * 1.2;
          return (
            <div key={p.key} className="dash-card">
              <div className="dash-card-head">
                <h4>{p.label}: how big is “big enough”?</h4>
                <TagChip tag="OBSERVATION" />
              </div>
              <div className="ladder">
                {marks.map((m) => (
                  <div key={m.name} className={`ladder-row ${m.kind === 'adopted' ? 'ladder-adopted' : ''}`}>
                    <div className="ladder-name">{m.name}</div>
                    <div className="ladder-track">
                      <div
                        className="ladder-fill"
                        style={{ width: `${(m.value / maxV) * 100}%`, background: m.kind === 'adopted' ? p.color : '#475569' }}
                      />
                    </div>
                    <div className="ladder-val">{f(m.value, 2)} dB</div>
                  </div>
                ))}
              </div>
              <p className="dash-help">
                So an {p.key} change smaller than <strong>{f(d.recommended_threshold_db, 2)} dB</strong> is treated as noise.
                {d.recommended_threshold_db >= d.empirical_12day_p99_abs_db &&
                  ' The adopted level is at or above the 99th percentile of ordinary 12-day desert fluctuation.'}
              </p>
            </div>
          );
        })}

        <div className="dash-card">
          <div className="dash-card-head">
            <h4>Data consistency checklist</h4>
            <TagChip tag="OBSERVATION" />
          </div>
          <ul className="check-list">
            <li>
              <b>Same geometry only:</b> Track {catalog.aoi.track} / Frame {catalog.aoi.frame}, {catalog.aoi.orbit_direction} for every
              date, so geometry differences cannot masquerade as change.
            </li>
            <li>
              <b>One product version:</b> <code>{first?.product_version}</code> everywhere; versions are never mixed in one series or map.
            </li>
            <li>
              <b>{catalog.dates.length} passes:</b> {catalog.dates[0]} → {catalog.dates[catalog.dates.length - 1]}; no gaps are filled or interpolated.
            </li>
            <li>
              <b>Units:</b> averaging in linear power, shown in dB only for display and ratios.
            </li>
          </ul>
        </div>

        <div className="dash-card dash-limits">
          <div className="dash-card-head">
            <h4>What this app does not claim</h4>
          </div>
          <ul className="check-list">
            <li>Backscatter change is <b>not</b> ground displacement or subsidence.</li>
            <li>The interferometry (GUNW) layer is exploratory; over 12 days atmosphere dominates.</li>
            <li>No forecasts and no risk scores; every explanation is a hypothesis unless outside evidence supports it.</li>
            <li>Sentinel-2 and NASA POWER are context only and are never presented as NISAR.</li>
          </ul>
        </div>
      </>
    );
  };

  return (
    <div className="tab-pane dashboards-pane">
      <div className="dash-intro">
        <span className="section-eyebrow">DASHBOARDS • PLAIN-LANGUAGE VIEW OF THE SAME REAL DATA</span>
        <p>
          Pick a question. Every card shows real NISAR numbers from this project (or labelled outside context) with its
          confidence label.
        </p>
      </div>

      <div className="dash-nav" role="tablist">
        {SECTIONS.map((s) => (
          <button
            key={s.id}
            role="tab"
            aria-selected={section === s.id}
            className={`dash-nav-btn ${section === s.id ? 'dash-nav-active' : ''}`}
            onClick={() => setSection(s.id)}
          >
            <span className="dash-nav-title">{s.label}</span>
            <span className="dash-nav-q">{s.question}</span>
          </button>
        ))}
      </div>

      {section === 'glance' && renderGlance()}
      {section === 'breakdown' && renderBreakdown()}
      {section === 'landscapes' && renderLandscapes()}
      {section === 'context' && renderContext()}
      {section === 'trust' && renderTrust()}
    </div>
  );
};
