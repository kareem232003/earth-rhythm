export interface StoryStep {
  stepNumber: number;
  id: string;
  badge: string;
  title: string;
  subtitle: string;
  roiId: string;
  center: [number, number]; // [lon, lat]
  zoom: number;
  mapMode: 'single' | 'swipe' | 'change' | 'masks';
  primaryLayerId: string;
  swipeRightLayerId?: string;
  physicsTakeaway: string;
  whyPolarizationMatters: string;
}

export const STORY_STEPS: StoryStep[] = [
  {
    stepNumber: 1,
    id: 'step-1-oasis-heartbeat',
    badge: 'CHAPTER 1 • BASIN OVERVIEW',
    title: 'The Desert & The Oasis: 120 Days in 24 cm L-Band Radar',
    subtitle: 'Fayoum Oasis, Lake Qarun & Wadi El Rayan • Track 129 / Frame 016 Ascending',
    roiId: 'ROI_01_SUMMER_CROP_HARVEST',
    center: [30.74, 29.34],
    zoom: 9.6,
    mapMode: 'single',
    primaryLayerId: 'gcov_20260810_RGB',
    physicsTakeaway:
      'Unlike optical satellites blinded by cloud cover or limited to leaf-surface chlorophyll, NISAR’s 24 cm L-band wavelength penetrates into crop canopies to measure 3D stem volume (Green: HV), urban & trunk dihedral double-bounce (Red: HH), and specular water vs. desert roughness (Blue: HH−HV).',
    whyPolarizationMatters:
      'NASA POWER records show just 0.15 mm of total rainfall across the entire June–October 2026 season (0.00 mm on all 10 NISAR overpasses). Every hydrological and phenological pulse inside this 1,934 km² agricultural depression is driven by human-managed Nile canal water entering via the ancient Bahr Youssef canal.',
  },
  {
    stepNumber: 2,
    id: 'step-2-summer-crop-harvest',
    badge: 'CHAPTER 2 • CHANGE TYPE A1 (PHENOLOGY)',
    title: 'Summer Canopy Peak & Autumn Harvest Wave',
    subtitle: 'Sennuris / Tamia Eastern Oasis (30.9806°E, 29.3201°N) • 200m × 200m Patch (N=25 px)',
    roiId: 'ROI_01_SUMMER_CROP_HARVEST',
    center: [30.9806, 29.3201],
    zoom: 12.2,
    mapMode: 'swipe',
    primaryLayerId: 'delta_HV_20260623_to_20260810_sig',
    swipeRightLayerId: 'delta_HV_20260810_to_20261021_sig',
    physicsTakeaway:
      'Swipe between Early-to-Peak Summer (Left: +HV growth across 763.88 km² of cropland) and Peak-to-Autumn Harvest (Right: −HV loss across 594.83 km²). At ROI_01, HV rises +10.77 dB from June (−19.43 dB) to August 10 (−8.66 dB), then drops −11.23 dB by October after mechanical harvest.',
    whyPolarizationMatters:
      'Paired ESA Sentinel-2 L2A optical NDVI correlates with NISAR HV at r = 0.93 (p = 0.0009, N = 8 dates) from June to September. On October 19–21, optical NDVI rebounds to 0.661 from thin winter-crop seedling leaves, while 24 cm L-band HV stays low (−19.89 dB) because millimeter-thin seedling blades are Rayleigh-transparent to 24 cm radar waves!',
  },
  {
    stepNumber: 3,
    id: 'step-3-autumn-crop-emergence',
    badge: 'CHAPTER 3 • ASYNCHRONOUS MULTI-CROPPING',
    title: 'Fallow Soil to Dense Autumn Canopy Closure',
    subtitle: 'Northeastern Basin Parcel (31.0439°E, 29.3279°N) • Monotonic 8-Pass Growth',
    roiId: 'ROI_02_AUTUMN_CROP_EMERGENCE',
    center: [31.0439, 29.3279],
    zoom: 12.4,
    mapMode: 'change',
    primaryLayerId: 'delta_HV_20260623_to_20261021_sig',
    physicsTakeaway:
      'While neighboring summer fields are harvested in September, ROI_02 starts bare in June–July (HV = −22.97 dB, HH = −17.20 dB) and climbs monotonically across 8 consecutive 12-day passes to HV = −11.43 dB (+11.54 dB) and HH = −1.76 dB (+15.44 dB) by October 21.',
    whyPolarizationMatters:
      'Why does whole-oasis median HV vary by only 2.05 dB when individual parcels swing by 12+ dB? Because 594.83 km² of summer harvest (−HV) and 174.17 km² of late-summer/autumn planting (+HV) cancel out in basin-wide averages—proving why 40 m parcel-level SAR tracking is essential.',
  },
  {
    stepNumber: 4,
    id: 'step-4-seasonal-water-drawdown',
    badge: 'CHAPTER 4 • CHANGE TYPE A2 (HYDROLOGY)',
    title: 'Flooded Specular Basins vs. Wet Rough Mudflats',
    subtitle: 'Southern Fayoum Basin (30.8249°E, 29.2072°N) • Specular Mirror Physics',
    roiId: 'ROI_03_SEASONAL_WATER_DRAWDOWN',
    center: [30.8249, 29.2072],
    zoom: 12.3,
    mapMode: 'change',
    primaryLayerId: 'seasonal_dynamic_range_HH',
    physicsTakeaway:
      'In L-band radar, open standing water acts as a specular mirror that reflects radar pulses away from the side-looking antenna (dark HH = −16.48 dB on June 23). When the basin drains in August to expose wet, rough mudflats, HH surges +11.56 dB to −4.92 dB, then plunges back to −13.26 dB when re-flooded on September 27.',
    whyPolarizationMatters:
      'Throughout this 12.35 dB HH swing, cross-polarized HV remains below −16.2 dB because bare wet mud and open water lack 3D volumetric structure. Thus, HH tracks surface dielectric wetting versus ponded inundation while HV confirms the absence of dense vegetation.',
  },
  {
    stepNumber: 5,
    id: 'step-5-polarization-disagreement',
    badge: 'CHAPTER 5 • SCIENCE REQ 5 (HH vs HV DISAGREEMENT)',
    title: 'When Polarizations Disagree: +HH Surge with −HV Drop',
    subtitle: 'Southeastern Oasis (31.0760°E, 29.2190°N) • Regime 5 Opposite-Sign Divergence',
    roiId: 'ROI_04_POLARIZATION_DISAGREEMENT',
    center: [31.0760, 29.2190],
    zoom: 12.4,
    mapMode: 'change',
    primaryLayerId: 'dual_pol_regime_20260810_to_20261021',
    physicsTakeaway:
      'Between August 10 and October 09/21 at ROI_04, cross-pol HV drops significantly (−2.60 dB, from −14.32 to −16.92 dB) as the summer crop canopy is harvested, while co-pol HH simultaneously surges by +8.24 dB (from −7.18 dB to +1.06 dB)!',
    whyPolarizationMatters:
      'A single-polarization HH radar system would misclassify this +8.24 dB jump as vigorous growth. Dual-polarization HH+HV resolves the true physical sequence: crop canopy clearance (−HV) immediately followed by deep chisel plowing and pre-planting flood irrigation oriented perpendicular to the Ascending radar look vector (+HH dihedral/Bragg surge).',
  },
  {
    stepNumber: 6,
    id: 'step-6-calibration-and-insar-limits',
    badge: 'CHAPTER 6 • NOISE FLOOR & EXPLORATORY InSAR LIMITS',
    title: 'Desert Calibration Control & Why 12-Day InSAR Is Not Subsidence',
    subtitle: 'Jebel Qatrani Eocene Limestone Plateau (30.8969°E, 29.5847°N) • Rule 4 & 6 Guardrail',
    roiId: 'ROI_06_DESERT_CALIBRATION_CONTROL',
    center: [30.82, 29.46],
    zoom: 10.3,
    mapMode: 'masks',
    primaryLayerId: 'gunw_los_20261009_20261021',
    physicsTakeaway:
      'Over 218,705 pixels (349.93 km²) of consolidated limestone desert, 10-date backscatter is rock-solid (ROI_06 dynamic range = 0.61 dB HH, 0.77 dB HV), establishing our conservative change thresholds (τ_HH = 2.73 dB, τ_HV = 2.03 dB).',
    whyPolarizationMatters:
      'In the exploratory L2_GUNW interferogram (γ ≥ 0.50 mask applied), urban & limestone desert stay highly coherent (γ = 0.69–0.81), crops partially decorrelate (γ = 0.47), and Lake Qarun water completely decorrelates (γ = 0.08, masked transparent). Because 12-day atmospheric water-vapor phase gradients (±9–19 mm 1σ) exceed 12-day compaction (<0.5 mm), we strictly report apparent LOS phase screen—never false subsidence rates.',
  },
];

