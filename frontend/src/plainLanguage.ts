/**
 * Plain-language layer for Earth Rhythm.
 *
 * Everything here is ADDITIVE: it explains what the existing maps, charts and
 * tables already show. It never replaces or edits the scientific text in
 * `storySteps.ts` or the Methods panel.
 *
 * Rule 5 (dev_rules.md): every sentence is tagged as exactly one of
 * OBSERVATION / CHANGE DETECTION / INTERPRETATION (hypothesis).
 * No forecasts, no risk scores, and backscatter change is never called
 * "ground displacement".
 */

export type EpistemicTag = 'OBSERVATION' | 'CHANGE DETECTION' | 'INTERPRETATION (hypothesis)';

export const tagClass = (tag: string): string => {
  if (tag.startsWith('OBSERVATION')) return 'obs';
  if (tag.startsWith('CHANGE')) return 'chg';
  return 'hyp';
};

/* -------------------------------------------------------------------------- */
/* Story chapters: plain-words companion (keyed by StoryStep.stepNumber)       */
/* -------------------------------------------------------------------------- */

export interface PlainChapter {
  stepNumber: number;
  headline: string;
  /** Three tiers, one sentence each, in everyday words. */
  observation: string;
  change: string;
  hypothesis: string;
  /** What to do / look at on the map right now. */
  lookFor: string[];
  /** One sentence for someone who has never seen radar data. */
  whyItMatters: string;
}

export const PLAIN_CHAPTERS: PlainChapter[] = [
  {
    stepNumber: 1,
    headline: 'One radar picture can separate crops, towns, water and desert.',
    observation:
      'The map colours each place by how strongly it sent radar energy back to the satellite in two different "polarizations" (HV and HH).',
    change:
      'Nothing is being compared yet in this chapter. It is a single-date picture to learn the colours.',
    hypothesis:
      'Green areas most likely hold plants (stems and leaves scatter radar in many directions), red areas most likely hold buildings, and dark areas most likely hold smooth water or smooth sand.',
    lookFor: [
      'Find the bright green belt: that is the irrigated farmland of the oasis.',
      'Find the dark blue lake and the sandy-coloured desert around it.',
      'Use the date buttons above the map to see how the same place looks on another pass.',
    ],
    whyItMatters:
      'Radar works through clouds and at night, so it can watch the same fields every 12 days no matter the weather.',
  },
  {
    stepNumber: 2,
    headline: 'Cross-pol radar rises as crops grow and falls after harvest.',
    observation:
      'At the chosen field, the HV signal (the one most sensitive to plant volume) is much brighter in August than in June, then much darker again in October.',
    change:
      'The swipe map shows only pixels where the HV change is bigger than the noise threshold, so what you see is a detected change, not random speckle.',
    hypothesis:
      'The most likely explanation is a summer crop growing, peaking and being harvested. Optical NDVI from Sentinel-2 agrees with the pattern, which supports (but does not prove) this reading.',
    lookFor: [
      'Drag the swipe curtain left and right: green-teal = more plant volume, brown = less.',
      'Compare the left (June to August) and right (August to October) pictures.',
      'In the chart below, find where the HV line climbs and then drops.',
    ],
    whyItMatters:
      'Seeing growth and harvest waves across a whole region helps with crop-calendar monitoring without needing clear skies.',
  },
  {
    stepNumber: 3,
    headline: 'Different fields follow different calendars, so averages hide the action.',
    observation:
      'This parcel starts bare and gets steadily brighter in HV over many consecutive passes, while its neighbours are being harvested.',
    change:
      'Across the whole basin, growth in some places and harvest in others partly cancel out in the average, even though individual fields change a lot.',
    hypothesis:
      'A reasonable reading is staggered planting: some farmers harvest while others are just planting a new crop.',
    lookFor: [
      'Turn the "Hide noise" option on or off in the "What changed" map view.',
      'Compare the dashboard bar for growth vs harvest in the Overview tab (Dashboards).',
    ],
    whyItMatters:
      'A single number for the whole area would say "nothing changed". Pixel-level maps show that a lot did.',
  },
  {
    stepNumber: 4,
    headline: 'Smooth water looks dark to radar; wet rough mud looks bright.',
    observation:
      'At this basin, HH is very dark when the area is flooded, jumps up when it is drained and muddy, then falls again when it is re-flooded.',
    change:
      'The HH swing is large compared with the noise threshold, while HV stays low the whole time.',
    hypothesis:
      'Open standing water acts like a mirror and bounces radar away from the satellite. HV staying low suggests there is no dense plant canopy, which fits water or bare mud.',
    lookFor: [
      'Switch the map to the seasonal dynamic-range layer to see how much each pixel swings over the season.',
      'Compare the HH and HV lines in the chart: only HH moves a lot here.',
    ],
    whyItMatters:
      'Tracking when ponds and basins fill and drain supports water-management questions, again independent of clouds.',
  },
  {
    stepNumber: 5,
    headline: 'When HH and HV disagree, using only one of them can mislead you.',
    observation:
      'At this spot HH goes up while HV goes down over the same period.',
    change:
      'The 7-class regime map flags the pixels where the two signals move in opposite directions beyond their thresholds.',
    hypothesis:
      'One plausible sequence is crop clearance (HV down) followed by tillage or flooding of the bare field (HH up). This is a hypothesis; the satellite alone cannot confirm field operations.',
    lookFor: [
      'Look for the red class in the regime map (HH up and HV down).',
      'Note how few pixels are in the two disagreement classes compared with all other classes in the Overview tab (Dashboards).',
    ],
    whyItMatters:
      'A radar that only measured HH would call this "growth". Two polarizations avoid that mistake.',
  },
  {
    stepNumber: 6,
    headline: 'Honest limits: stable desert sets the noise floor, and 12-day InSAR is not subsidence.',
    observation:
      'Over bedrock desert the backscatter hardly changes from date to date, so it is a good reference for "what counts as noise".',
    change:
      'The thresholds (τ) used everywhere in the app come from how much this stable desert varies by chance.',
    hypothesis:
      'The interferometry layer shows an apparent line-of-sight phase pattern that is dominated by atmosphere over such a short period, so it is not used to claim ground sinking.',
    lookFor: [
      'Open Help & data → Methods & limits to see the noise numbers.',
      'In the Overview tab (Dashboards), open "Can we trust it?" for the threshold ladder.',
    ],
    whyItMatters:
      'Saying clearly what the data cannot show is part of the result, not a weakness.',
  },
];

/* -------------------------------------------------------------------------- */
/* 7 dual-pol change classes (class code -> plain words)                       */
/* -------------------------------------------------------------------------- */

export interface RegimePlain {
  code: number;
  short: string;
  meaning: string;
  hypothesis: string;
}

export const REGIME_PLAIN: Record<number, RegimePlain> = {
  0: {
    code: 0,
    short: 'No detectable change',
    meaning: 'Both signals moved less than the noise threshold.',
    hypothesis:
      'Surface probably stable, or changed in a way too small for this threshold to detect. "Not detected" is not the same as "did not change".',
  },
  1: {
    code: 1,
    short: 'Plant volume up',
    meaning: 'HV (cross-pol) increased by more than its threshold.',
    hypothesis: 'Consistent with crop or vegetation growth (more stems and leaves scattering the radar).',
  },
  2: {
    code: 2,
    short: 'Plant volume down',
    meaning: 'HV (cross-pol) decreased by more than its threshold.',
    hypothesis: 'Consistent with harvest, clearance or senescence of vegetation.',
  },
  3: {
    code: 3,
    short: 'Surface brighter (HH only)',
    meaning: 'HH increased by more than its threshold while HV stayed within noise.',
    hypothesis: 'Consistent with wetter or rougher bare ground, e.g. tillage or irrigation of bare soil.',
  },
  4: {
    code: 4,
    short: 'Surface darker (HH only)',
    meaning: 'HH decreased by more than its threshold while HV stayed within noise.',
    hypothesis: 'Consistent with drying or with smooth standing water (inundation).',
  },
  5: {
    code: 5,
    short: 'Disagreement: HH up, HV down',
    meaning: 'The two polarizations moved in opposite directions beyond their thresholds.',
    hypothesis: 'Consistent with canopy removal followed by wet or tilled ground.',
  },
  6: {
    code: 6,
    short: 'Disagreement: HH down, HV up',
    meaning: 'The two polarizations moved in opposite directions beyond their thresholds.',
    hypothesis: 'Could reflect new plant growth over smoother or wetter ground; needs outside evidence.',
  },
};

/** Map the API's long class names (phase3 report keys) to class codes. */
export const REGIME_KEY_TO_CODE: Record<string, number> = {
  No_Significant_Change: 0,
  Canopy_Volume_Growth_HV_Up: 1,
  Canopy_Harvest_Senescence_HV_Down: 2,
  Surface_Wetting_or_Tillage_HH_Up_Only: 3,
  Surface_Drying_or_Inundation_HH_Down_Only: 4,
  Polarization_Disagreement_HH_Up_HV_Down: 5,
  Polarization_Disagreement_HH_Down_HV_Up: 6,
};

/** Fallback colours (identical to the catalog legend); the live legend wins when present. */
export const REGIME_FALLBACK_COLOR: Record<number, string> = {
  0: '#28303c',
  1: '#10b981',
  2: '#f59e0b',
  3: '#3b82f6',
  4: '#a855f7',
  5: '#ef4444',
  6: '#06b6d4',
};

/* -------------------------------------------------------------------------- */
/* Landscape types (strata)                                                    */
/* -------------------------------------------------------------------------- */

export interface StratumPlain {
  key: string;
  label: string;
  color: string;
  whatItIs: string;
  hypothesis: string;
}

export const STRATA_PLAIN: StratumPlain[] = [
  {
    key: 'vegetated_agriculture',
    label: 'Farmland',
    color: '#22c55e',
    whatItIs: 'Irrigated crops and orchards inside the oasis.',
    hypothesis:
      'Its average moves modestly because some fields grow while others are harvested at the same time.',
  },
  {
    key: 'permanent_open_water',
    label: 'Open water',
    color: '#38bdf8',
    whatItIs: 'Lake and permanent water bodies.',
    hypothesis:
      'Calm water is dark to radar; wind-roughened water can look brighter, which can make the signal wander.',
  },
  {
    key: 'seasonal_water_margins',
    label: 'Seasonal water edges',
    color: '#a855f7',
    whatItIs: 'Shorelines and basins that fill and drain.',
    hypothesis:
      'Flooding makes it dark and wet mud makes it bright, so it changes more than most other types.',
  },
  {
    key: 'urban_settlements',
    label: 'Towns & villages',
    color: '#ef4444',
    whatItIs: 'Built-up areas.',
    hypothesis:
      'Walls and the ground form corner reflectors that return strong, steady signal, so towns barely change.',
  },
  {
    key: 'stable_consolidated_desert',
    label: 'Stable desert (reference)',
    color: '#f59e0b',
    whatItIs: 'Hard bedrock desert used as the "nothing changes here" control.',
    hypothesis:
      'It is used to measure noise, because real surface change there is expected to be small.',
  },
];

/* -------------------------------------------------------------------------- */
/* Glossary                                                                    */
/* -------------------------------------------------------------------------- */

export interface GlossaryEntry {
  term: string;
  plain: string;
  detail?: string;
}

export const GLOSSARY: GlossaryEntry[] = [
  {
    term: 'NISAR',
    plain: 'A NASA–ISRO radar satellite that images the land through clouds, day and night.',
  },
  {
    term: 'L-band (24 cm)',
    plain:
      'The radar wavelength used. It is long enough to go through leaves and sense stems, branches and soil more than thin leaf surfaces.',
  },
  {
    term: 'Backscatter',
    plain: 'How much of the radar signal bounces back to the satellite. Brighter = more returned.',
    detail:
      'Backscatter is not the same as ground movement. This app never calls backscatter change "displacement" or "subsidence".',
  },
  {
    term: 'dB (decibel)',
    plain:
      'A log scale for brightness. +3 dB is about double the power, −3 dB about half. Averages are computed in linear power first and only shown in dB.',
  },
  {
    term: 'HH',
    plain: 'Radar sent horizontally and received horizontally. Sensitive to smooth surfaces, water, soil wetness and corner reflections from buildings.',
  },
  {
    term: 'HV',
    plain: 'Sent horizontally, received vertically. It mostly comes from many-direction scattering inside plant canopy, so it tracks vegetation volume.',
  },
  {
    term: 'Speckle',
    plain: 'Grain-like noise that is natural in radar images. It is reduced by averaging neighbouring pixels (multilooking) and filtering.',
  },
  {
    term: 'ENL',
    plain: 'Equivalent Number of Looks. Higher ENL = smoother, less speckle noise. It is used to compute how big a change must be to be believable.',
  },
  {
    term: 'τ (threshold)',
    plain: 'The smallest dB change that counts as real change. It comes from how much the stable desert varies by chance, so it is not arbitrary.',
  },
  {
    term: 'Log-ratio / ΔdB',
    plain: 'The change between two dates measured as a difference in dB (later minus earlier).',
  },
  {
    term: 'Regime (change class)',
    plain: 'One of seven categories combining the HH change and the HV change, such as "plant volume up" or "HH up and HV down".',
  },
  {
    term: 'Coherence (γ)',
    plain: 'How similar two radar images are in phase. High coherence means a trustworthy interferogram; water and some crops lose it.',
  },
  {
    term: 'GUNW / InSAR',
    plain: 'Interferometry: it compares radar phase between two dates. Here it is exploratory only, and 12-day atmosphere effects are larger than any expected ground motion.',
  },
  {
    term: 'NESZ floor',
    plain: 'The sensor noise floor. Signals close to it (very smooth sand or calm water) are unreliable for comparison.',
  },
  {
    term: 'NDVI',
    plain: 'A greenness index from Sentinel-2 optical imagery (not NISAR). It is shown only as outside context for plausibility.',
  },
  {
    term: 'Pearson r',
    plain: 'A number from −1 to +1 for how closely two series rise and fall together. It describes association, not cause, and few dates (N) make it fragile.',
  },
  {
    term: 'Provisional product',
    plain: 'Data that has not completed final calibration/validation. All layers use one product version, never mixed.',
  },
];

/* -------------------------------------------------------------------------- */
/* The three "epistemic" labels                                                */
/* -------------------------------------------------------------------------- */

export const EPISTEMIC_EXPLAINED: { tag: EpistemicTag; plain: string }[] = [
  {
    tag: 'OBSERVATION',
    plain: 'What the satellite measured, with no judgement added (for example "HV was −19 dB on this date").',
  },
  {
    tag: 'CHANGE DETECTION',
    plain: 'A comparison between dates that passed a statistical threshold (for example "HV rose by more than τ").',
  },
  {
    tag: 'INTERPRETATION (hypothesis)',
    plain: 'A possible physical explanation. It is a hypothesis unless outside evidence supports it.',
  },
];

/* -------------------------------------------------------------------------- */
/* Map: what-am-I-looking-at text                                              */
/* -------------------------------------------------------------------------- */

export const MAP_MODE_PLAIN: Record<string, string> = {
  single:
    'A single satellite pass. Use the date buttons or Animate to watch the landscape through the season.',
  swipe:
    'Two layers on one map. Drag the vertical curtain: the left layer shows on one side, the right layer on the other.',
  change:
    'A comparison between two dates. Only changes bigger than the noise threshold are drawn when the noise filter is on.',
  masks:
    'Supporting layers: land-cover classes, quality masks and the exploratory interferometry phase screen.',
};

export const POL_PLAIN: Record<string, string> = {
  RGB: 'Combined colour picture: green ≈ vegetation volume (HV), red ≈ buildings and corner reflections (HH), blue/cyan ≈ water and smooth surfaces.',
  HH: 'HH co-pol: bright = rough or wet surfaces and building corners; dark = smooth water or smooth sand.',
  HV: 'HV cross-pol: bright = dense plant volume; dark = bare ground, water or sparse vegetation.',
};

export const CHANGE_METRIC_PLAIN: Record<string, string> = {
  HV: 'ΔHV: how much plant volume changed. Teal = increase (growth), brown = decrease (harvest).',
  HH: 'ΔHH: how much surface brightness changed. It reflects soil wetness, roughness and standing water more than plants.',
  regime:
    '7-class map that combines the HH and HV changes into one category per pixel (see the colour key).',
  HV_over_HH:
    'Δ(HV/HH): whether scattering shifted toward plant volume (positive) or toward surface/corner reflection (negative).',
  dyn_HV: 'Season range of HV: how far each pixel’s HV swung between its lowest and highest date. Bigger = more active.',
  dyn_HH: 'Season range of HH: how far each pixel’s HH swung between its lowest and highest date. Bigger = more active.',
};

export const MASK_PLAIN =
  'Masks tell you where a layer can be trusted: water, built-up areas, stable desert, and places near the sensor noise floor. The interferometry layer is exploratory and is not a ground-motion measurement.';

export const GUNW_PLAIN =
  'Exploratory apparent line-of-sight phase screen, with low-coherence pixels hidden. Over 12 days it is dominated by atmospheric effects, so it must not be read as subsidence.';
