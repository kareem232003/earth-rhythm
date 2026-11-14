/**
 * Plain-language UI labels (D-014 UI simplification).
 *
 * These are presentation labels only. Every technical name they replace is still shown
 * as a sub-label, tooltip or in an expandable "details" section — nothing is removed.
 */

/** Short, friendly names for the six focal story spots (full titles stay in tooltips & headers). */
export const ROI_SHORT_NAMES: Record<string, string> = {
  ROI_01_SUMMER_CROP_HARVEST: 'Summer crops',
  ROI_02_AUTUMN_CROP_EMERGENCE: 'Autumn crops',
  ROI_03_SEASONAL_WATER_DRAWDOWN: 'Seasonal water',
  ROI_04_POLARIZATION_DISAGREEMENT: 'HH vs HV disagree',
  ROI_05_LAKE_QARUN_OPEN_WATER: 'Lake Qarun',
  ROI_06_DESERT_CALIBRATION_CONTROL: 'Desert control',
};

export const roiShortName = (roiId: string): string =>
  ROI_SHORT_NAMES[roiId] || roiId.replace(/^ROI_0\d_/, '').replace(/_/g, ' ').toLowerCase();

/** Map-view buttons: plain label + the original technical name. */
export const MAP_MODE_LABELS: Record<'single' | 'swipe' | 'change' | 'masks', { label: string; tech: string }> = {
  single: { label: 'One date', tech: '10-Date Time Slider' },
  swipe: { label: 'Compare two', tech: 'Before / After Swipe' },
  change: { label: 'What changed', tech: 'Change & Disagreement' },
  masks: { label: 'Land types & extras', tech: 'Masks & Exploratory InSAR' },
};

/** Single-date layer chips: plain label + the original technical name. */
export const POL_LABELS: Record<'RGB' | 'HH' | 'HV', { label: string; tech: string }> = {
  RGB: { label: 'Colour mix', tech: 'Physical Scattering Map (Crops / Buildings / Water)' },
  HH: { label: 'HH · ground & buildings', tech: 'HH Co-Pol (Surface / Double-Bounce)' },
  HV: { label: 'HV · plants', tech: 'HV Cross-Pol (Canopy Volume)' },
};

/** Change-view metric chips: plain label + the original technical name. */
export const CHANGE_METRIC_LABELS: Record<
  'HV' | 'HH' | 'regime' | 'HV_over_HH' | 'dyn_HV' | 'dyn_HH',
  { label: string; tech: string; group: 'between' | 'season' }
> = {
  HV: { label: 'Plants (HV)', tech: 'ΔHV Canopy Change (τ = 2.03 dB)', group: 'between' },
  HH: { label: 'Ground & water (HH)', tech: 'ΔHH Surface/Wetting Change (τ = 2.73 dB)', group: 'between' },
  regime: { label: 'Type of change', tech: '7-Class Dual-Pol Regime & Disagreement Map', group: 'between' },
  HV_over_HH: { label: 'HV/HH balance', tech: 'Δ(HV/HH) Ratio', group: 'between' },
  dyn_HV: { label: 'Plants (HV)', tech: '10-Date HV Dynamic Range', group: 'season' },
  dyn_HH: { label: 'Ground (HH)', tech: '10-Date HH Dynamic Range', group: 'season' },
};

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

/** "2026-06-23" -> "Jun 23" (the full ISO date stays visible next to the scrubber and in tooltips). */
export const shortDate = (iso: string): string => {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
  if (!m) return iso;
  return `${MONTHS[parseInt(m[2], 10) - 1]} ${parseInt(m[3], 10)}`;
};
