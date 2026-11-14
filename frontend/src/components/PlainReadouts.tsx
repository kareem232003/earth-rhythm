import React, { useState } from 'react';
import { HelpCircle, ChevronDown, ChevronUp } from 'lucide-react';
import { InspectResponse, OverlayItem } from '../types';
import {
  CHANGE_METRIC_PLAIN,
  GUNW_PLAIN,
  MAP_MODE_PLAIN,
  MASK_PLAIN,
  PLAIN_CHAPTERS,
  POL_PLAIN,
  REGIME_PLAIN,
  tagClass,
} from '../plainLanguage';

const Tag: React.FC<{ tag: string }> = ({ tag }) => <span className={`ep-tag ${tagClass(tag)}-tag`}>{tag}</span>;

const sgn = (n: number): string => (n > 0 ? `+${n.toFixed(2)}` : n.toFixed(2));

/* -------------------------------------------------------------------------- */
/* 1. Story Mode companion: "In plain words"                                   */
/* -------------------------------------------------------------------------- */

export const StoryPlainCard: React.FC<{ stepNumber: number }> = ({ stepNumber }) => {
  const ch = PLAIN_CHAPTERS.find((c) => c.stepNumber === stepNumber);
  if (!ch) return null;
  return (
    <div className="plain-card">
      <div className="plain-card-head">
        <span className="plain-eyebrow">IN PLAIN WORDS</span>
        <h3>{ch.headline}</h3>
      </div>

      <div className="epistemic-stack">
        <div className="epistemic-card obs-card">
          <span className="ep-tag obs-tag">OBSERVATION</span>
          <p>{ch.observation}</p>
        </div>
        <div className="epistemic-card chg-card">
          <span className="ep-tag chg-tag">CHANGE DETECTION</span>
          <p>{ch.change}</p>
        </div>
        <div className="epistemic-card hyp-card">
          <span className="ep-tag hyp-tag">INTERPRETATION (hypothesis)</span>
          <p>{ch.hypothesis}</p>
        </div>
      </div>

      <div className="plain-look">
        <strong>What to look at on the map</strong>
        <ul>
          {ch.lookFor.map((t) => (
            <li key={t}>{t}</li>
          ))}
        </ul>
      </div>
      <div className="plain-why">
        <strong>Why it matters:</strong> {ch.whyItMatters}
      </div>
    </div>
  );
};

/* -------------------------------------------------------------------------- */
/* 2. Pixel Inspector companion: readout generated from the REAL /api/inspect  */
/* -------------------------------------------------------------------------- */

export const InspectorPlainReadout: React.FC<{ data: InspectResponse }> = ({ data }) => {
  const ss = data.seasonal_summary;
  const entries = Object.entries(data.interval_evaluations);
  const tauHH = ss.tau_hh_db;
  const tauHV = ss.tau_hv_db;
  const maxAbs =
    Math.max(tauHH, tauHV, ...entries.flatMap(([, e]) => [Math.abs(e.delta_hh_db), Math.abs(e.delta_hv_db)])) * 1.1;

  const pos = (v: number) => 50 + (v / maxAbs) * 50; // % along the track

  const Bar: React.FC<{ label: string; value: number; tau: number; exceeds: boolean }> = ({ label, value, tau, exceeds }) => {
    const left = value >= 0 ? 50 : pos(value);
    const width = Math.abs(pos(value) - 50);
    return (
      <div className="dv-row">
        <span className="dv-label">{label}</span>
        <div className="dv-track">
          <div className="dv-center" />
          <div className="dv-tau" style={{ left: `${pos(-tau)}%` }} title={`−τ = −${tau} dB`} />
          <div className="dv-tau" style={{ left: `${pos(tau)}%` }} title={`+τ = +${tau} dB`} />
          <div
            className={`dv-fill ${exceeds ? 'dv-on' : 'dv-off'} ${value >= 0 ? 'dv-pos' : 'dv-neg'}`}
            style={{ left: `${left}%`, width: `${width}%` }}
          />
        </div>
        <span className={`dv-num ${exceeds ? 'sig-cell' : ''}`}>
          {sgn(value)} dB {exceeds ? '★' : ''}
        </span>
      </div>
    );
  };

  const hhSwingBig = ss.hh_dynamic_range_db >= tauHH;
  const hvSwingBig = ss.hv_dynamic_range_db >= tauHV;

  return (
    <div className="plain-card">
      <div className="plain-card-head">
        <span className="plain-eyebrow">IN PLAIN WORDS • THIS SPOT</span>
        <h3>What happened here, in one minute</h3>
      </div>

      <div className="epistemic-card obs-card">
        <span className="ep-tag obs-tag">OBSERVATION</span>
        <p>
          You are looking at <strong>{data.geophysical_stratum.landcover_label}</strong> (
          {data.sampling.patch_area_ha} ha, {data.sampling.temporal_sample_count_N_dates} satellite passes). Over the season
          the HH signal ranged by <strong>{ss.hh_dynamic_range_db.toFixed(2)} dB</strong> and the HV signal by{' '}
          <strong>{ss.hv_dynamic_range_db.toFixed(2)} dB</strong>.
        </p>
      </div>

      <div className="plain-sub">How big was each change compared with the noise threshold?</div>
      <p className="dash-help">
        Bars show the change between two dates. The two thin vertical lines are ±τ. A bar that passes a line is a real
        detected change (★); a bar inside the lines is within noise.
      </p>

      {entries.map(([k, ev]) => (
        <div key={k} className="dv-block">
          <div className="dv-title">
            <code>{ev.date_start}</code> → <code>{ev.date_end}</code>
          </div>
          <Bar label="HH" value={ev.delta_hh_db} tau={tauHH} exceeds={ev.exceeds_tau_hh} />
          <Bar label="HV" value={ev.delta_hv_db} tau={tauHV} exceeds={ev.exceeds_tau_hv} />

          {ev.regime_code === 0 ? (
            <div className="epistemic-card chg-card">
              <span className="ep-tag chg-tag">CHANGE DETECTION</span>
              <p>
                No change above the threshold. This means “not detectable above noise”, not “nothing happened”.
              </p>
            </div>
          ) : (
            <>
              <div className="epistemic-card chg-card">
                <span className="ep-tag chg-tag">CHANGE DETECTION</span>
                <p>
                  Detected class: <strong>{REGIME_PLAIN[ev.regime_code]?.short || ev.regime_label}</strong>.{' '}
                  {REGIME_PLAIN[ev.regime_code]?.meaning}
                </p>
              </div>
              <div className="epistemic-card hyp-card">
                <span className="ep-tag hyp-tag">INTERPRETATION (hypothesis)</span>
                <p>{REGIME_PLAIN[ev.regime_code]?.hypothesis}</p>
              </div>
            </>
          )}
        </div>
      ))}

      <div className="epistemic-card chg-card">
        <span className="ep-tag chg-tag">CHANGE DETECTION</span>
        <p>
          Across all ten passes, HH {hhSwingBig ? 'swung more than' : 'stayed within'} its threshold ({tauHH} dB) and HV{' '}
          {hvSwingBig ? 'swung more than' : 'stayed within'} its threshold ({tauHV} dB).
        </p>
      </div>

      {data.geophysical_stratum.low_snr_nesz_proximity_warning && (
        <div className="plain-warn">
          Careful: this spot is close to the sensor noise floor, so very small differences here are less reliable.
        </div>
      )}
      {data.sampling.small_sample_disclosure && (
        <div className="plain-note">
          <strong>Sample size:</strong> {data.sampling.small_sample_disclosure}
        </div>
      )}
    </div>
  );
};

/* -------------------------------------------------------------------------- */
/* 3. Map companion: collapsible "What am I looking at?"                       */
/* -------------------------------------------------------------------------- */

interface MapGuideProps {
  mapMode: 'single' | 'swipe' | 'change' | 'masks';
  singlePol: 'HH' | 'HV' | 'RGB';
  changeMetric: string;
  thresholdMaskOnly: boolean;
  leftOverlay?: OverlayItem;
  rightOverlay?: OverlayItem;
  selectedMaskLayerId: string;
}

const LegendKey: React.FC<{ overlay: OverlayItem }> = ({ overlay }) => {
  const lg = overlay.legend;
  if (lg.type === 'categorical' && lg.classes) {
    return (
      <div className="mg-legend">
        {lg.classes.map((c) => (
          <span key={c.code} className="mg-key">
            <i style={{ background: c.color }} />
            {c.label}
          </span>
        ))}
      </div>
    );
  }
  if (lg.type === 'rgb_composite' && lg.channels) {
    return (
      <div className="mg-legend">
        {lg.channels.map((c) => (
          <span key={c.channel} className="mg-key">
            <i style={{ background: c.color || '#64748b' }} />
            <b>{c.channel}:</b> {c.meaning}
          </span>
        ))}
      </div>
    );
  }
  if (lg.stops) {
    return (
      <div className="mg-legend">
        {lg.stops.map((s) => (
          <span key={`${s.value}-${s.label}`} className="mg-key">
            <i style={{ background: s.color }} />
            {s.label}
          </span>
        ))}
      </div>
    );
  }
  return null;
};

export const MapReadingGuide: React.FC<MapGuideProps> = ({
  mapMode,
  singlePol,
  changeMetric,
  thresholdMaskOnly,
  leftOverlay,
  rightOverlay,
  selectedMaskLayerId,
}) => {
  const [open, setOpen] = useState<boolean>(false);

  let what = MAP_MODE_PLAIN[mapMode];
  let how = '';
  if (mapMode === 'single') how = POL_PLAIN[singlePol];
  if (mapMode === 'change') {
    how = CHANGE_METRIC_PLAIN[changeMetric] || '';
    if (changeMetric === 'HH' || changeMetric === 'HV') {
      how += thresholdMaskOnly
        ? ' The noise filter is ON: places with changes below the threshold are transparent.'
        : ' The noise filter is OFF: tiny differences (mostly speckle) are also coloured.';
    }
  }
  if (mapMode === 'masks') {
    how = selectedMaskLayerId.startsWith('gunw') ? GUNW_PLAIN : MASK_PLAIN;
  }
  if (mapMode === 'swipe') {
    how =
      'Both layers use the same grid and geometry. Pick any two layers in the dropdowns; presets show the main stories.';
  }

  const tag = leftOverlay?.rule3_metadata?.epistemic_tag;

  return (
    <div className="map-guide">
      <button className="map-guide-bar" onClick={() => setOpen((v) => !v)} aria-expanded={open}>
        <HelpCircle size={14} />
        <span className="map-guide-title">What am I looking at?</span>
        <span className="map-guide-summary">{leftOverlay ? leftOverlay.title : what}</span>
        {open ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
      </button>

      {open && (
        <div className="map-guide-body">
          <p>
            <strong>This view:</strong> {what}
          </p>
          {how && (
            <p>
              <strong>How to read it:</strong> {how}
            </p>
          )}
          {leftOverlay && (
            <p className="mg-meta">
              {tag && <Tag tag={tag} />}
              <span>
                Units: <code>{leftOverlay.rule3_metadata.units}</code> • Polarization:{' '}
                <code>{leftOverlay.rule3_metadata.polarization}</code> • Date(s):{' '}
                <code>{leftOverlay.rule3_metadata.acquisition_date}</code>
              </span>
            </p>
          )}
          {leftOverlay && (
            <>
              <div className="mg-sub">Colour key{rightOverlay ? ' (left layer)' : ''}</div>
              <LegendKey overlay={leftOverlay} />
            </>
          )}
          {rightOverlay && (
            <>
              <div className="mg-sub">Colour key (right layer: {rightOverlay.title})</div>
              <LegendKey overlay={rightOverlay} />
            </>
          )}
          <p className="mg-foot">
            Tip: click anywhere on the map to see what that spot did over the season in the Pixel Inspector.
          </p>
        </div>
      )}
    </div>
  );
};
