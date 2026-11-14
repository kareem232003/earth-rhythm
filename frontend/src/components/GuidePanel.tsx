import React, { useMemo, useState } from 'react';
import { LayerCatalog } from '../types';
import { EPISTEMIC_EXPLAINED, GLOSSARY, tagClass } from '../plainLanguage';

export type GuideTarget = 'story' | 'inspector' | 'metadata' | 'methods' | 'dashboards';

interface Props {
  catalog: LayerCatalog;
  onNavigate: (tab: GuideTarget) => void;
  onOpenEcho: () => void;
}

const PATH: { n: number; title: string; text: string; go?: GuideTarget; goLabel?: string }[] = [
  {
    n: 1,
    title: 'Follow the story',
    text: 'Open Story Mode and press “Next Chapter”. Each chapter moves the map for you and explains it in plain words.',
    go: 'story',
    goLabel: 'Open Story Mode',
  },
  {
    n: 2,
    title: 'Explore the four map views',
    text: 'Use the buttons on top of the map: a 10-date slider, a before/after swipe, change maps, and supporting masks. The bar under them (“What am I looking at?”) explains the current view and its colours.',
  },
  {
    n: 3,
    title: 'Click any spot',
    text: 'Click the map to see that place’s 10-date radar trajectory and a plain-language readout of what changed and whether it beats the noise threshold.',
    go: 'inspector',
    goLabel: 'Open Pixel Inspector',
  },
  {
    n: 4,
    title: 'See the whole picture',
    text: 'Dashboards summarise the entire area: how much changed, what kind of change, which landscapes move most, whether rain and optical data agree, and how big a change has to be to count.',
    go: 'dashboards',
    goLabel: 'Open Dashboards',
  },
  {
    n: 5,
    title: 'Check the receipts',
    text: 'Rule 3 Metadata shows satellite, product, version, date, polarization, units, CRS and source for every layer. Methods & Limits states what we cannot conclude.',
    go: 'metadata',
    goLabel: 'Open Metadata',
  },
];

export const GuidePanel: React.FC<Props> = ({ catalog, onNavigate, onOpenEcho }) => {
  const [query, setQuery] = useState<string>('');

  const rgb = useMemo(
    () => catalog.overlays.find((o) => o.legend.type === 'rgb_composite')?.legend.channels || [],
    [catalog]
  );

  const q = query.trim().toLowerCase();
  const glossary = GLOSSARY.filter(
    (g) => !q || g.term.toLowerCase().includes(q) || g.plain.toLowerCase().includes(q) || (g.detail || '').toLowerCase().includes(q)
  );

  return (
    <div className="tab-pane guide-pane">
      <div className="dash-intro">
        <span className="section-eyebrow">GUIDE • NEW TO RADAR? START HERE</span>
        <p>
          Earth Rhythm uses a NASA–ISRO radar satellite (NISAR) to watch how farmland, water and desert in the Fayoum Oasis
          change through the season. This tab explains how to read everything you see. Nothing here changes the science.
        </p>
      </div>

      <div className="dash-card">
        <div className="dash-card-head">
          <h4>Read the app in about 3 minutes</h4>
        </div>
        <ol className="guide-steps">
          {PATH.map((s) => (
            <li key={s.n}>
              <span className="guide-num">{s.n}</span>
              <div>
                <strong>{s.title}</strong>
                <p>{s.text}</p>
                {s.go && (
                  <button className="dash-link-btn" onClick={() => onNavigate(s.go as GuideTarget)}>
                    {s.goLabel} →
                  </button>
                )}
              </div>
            </li>
          ))}
          <li>
            <span className="guide-num">6</span>
            <div>
              <strong>Ask Echo</strong>
              <p>Stuck on a word or a colour? Echo, the built-in guide, knows which view you are on.</p>
              <button className="dash-link-btn" onClick={onOpenEcho}>
                Open Echo →
              </button>
            </div>
          </li>
        </ol>
      </div>

      <div className="dash-card">
        <div className="dash-card-head">
          <h4>Three labels, three levels of certainty</h4>
        </div>
        <p className="dash-help">Every finding in the app carries exactly one of these labels.</p>
        <div className="epistemic-stack">
          {EPISTEMIC_EXPLAINED.map((e) => (
            <div key={e.tag} className={`epistemic-card ${tagClass(e.tag)}-card`}>
              <span className={`ep-tag ${tagClass(e.tag)}-tag`}>{e.tag}</span>
              <p>{e.plain}</p>
            </div>
          ))}
        </div>
      </div>

      {rgb.length > 0 && (
        <div className="dash-card">
          <div className="dash-card-head">
            <h4>Colour cheat sheet for the main radar picture</h4>
          </div>
          <div className="class-list">
            {rgb.map((c) => (
              <div key={c.channel} className="class-row">
                <span className="class-dot" style={{ background: c.color || '#64748b' }} />
                <div className="class-main">
                  <div className="class-title">{c.channel}</div>
                  <div className="class-meaning">{c.meaning}</div>
                </div>
              </div>
            ))}
          </div>
          <p className="dash-help">These meanings are physical hypotheses about what scatters the radar, not ground-truth labels.</p>
        </div>
      )}

      <div className="dash-card">
        <div className="dash-card-head">
          <h4>Glossary</h4>
        </div>
        <input
          className="glossary-search"
          type="search"
          placeholder="Search a term (e.g. dB, HV, threshold)…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <dl className="glossary-list">
          {glossary.map((g) => (
            <div key={g.term} className="glossary-item">
              <dt>{g.term}</dt>
              <dd>
                {g.plain}
                {g.detail && <span className="glossary-detail"> {g.detail}</span>}
              </dd>
            </div>
          ))}
          {glossary.length === 0 && <div className="empty-chart">No matching term.</div>}
        </dl>
      </div>
    </div>
  );
};
