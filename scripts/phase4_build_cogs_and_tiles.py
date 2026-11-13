"""Phase 4: Build Cloud-Optimized GeoTIFFs (COGs), Web-Ready EPSG:4326 RGBA Overlays, and Master Layer Catalog.

Executes Phase 4 of Earth Rhythm AI:
  1. Converts all 45 Rule-3 tagged EPSG:32636 GeoTIFFs (20 GCOV filtered dB rasters,
     14 Phase 3 change maps, 9 Phase 2 masks, and 2 exploratory L2_GUNW LOS rasters)
     into internally tiled (256x256), DEFLATE-compressed Cloud-Optimized GeoTIFFs
     with [2, 4, 8] overview pyramids in `data/cogs/`.
  2. Renders 59 web-ready EPSG:4326 RGBA PNG overlays in `data/web_tiles/overlays/`
     with exact WGS84 corner coordinates and calibrated scientific colorbars for
     instant MapLibre GL JS rendering.
  3. Writes `data/web_tiles/layer_catalog.json` and `data/processed/phase4_cog_and_tile_report.json`.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from nisar_pipeline.guards import build_rule3_metadata
from nisar_pipeline.tiles_and_cogs import (
    DUAL_POL_REGIME_PALETTE,
    LANDCOVER_CLASS_PALETTE,
    convert_geotiff_to_cog,
    render_categorical_wgs84_png,
    render_continuous_wgs84_png,
    render_dual_pol_rgb_composite_wgs84_png,
)

PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
COGS_DIR = PROJECT_ROOT / "data" / "cogs"
OVERLAYS_DIR = PROJECT_ROOT / "data" / "web_tiles" / "overlays"
CATALOG_PATH = PROJECT_ROOT / "data" / "web_tiles" / "layer_catalog.json"
REPORT_PATH = PROCESSED_DIR / "phase4_cog_and_tile_report.json"
MANIFEST_PATH = PROJECT_ROOT / "data" / "subsets" / "phase1_manifest.json"

TAU_HH_DB = 2.73
TAU_HV_DB = 2.03


def main() -> None:
    t0 = time.time()
    print("=" * 80)
    print("PHASE 4: CLOUD-OPTIMIZED GEOTIFFS (COGs) & WEB-READY EPSG:4326 OVERLAY GENERATION")
    print("=" * 80)

    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    gcov_records = manifest["gcov_subsets"]

    # 1. Convert all 45 processed GeoTIFFs into verified COGs
    print("\n[Step 1] Converting all 45 processed EPSG:32636 GeoTIFFs to Cloud-Optimized GeoTIFFs (COGs)...")
    cog_records: list[dict[str, Any]] = []
    subdirs = ["gcov_filtered_db", "change_maps", "masks", "gunw_los"]

    for sub in subdirs:
        src_dir = PROCESSED_DIR / sub
        dst_dir = COGS_DIR / sub
        tif_files = sorted(src_dir.glob("*.tif"))
        for src_tif in tif_files:
            dst_cog = dst_dir / src_tif.name
            info = convert_geotiff_to_cog(src_tif, dst_cog, overview_factors=(2, 4, 8))
            info["category"] = sub
            info["relative_cog_url"] = f"/cogs/{sub}/{src_tif.name}"
            cog_records.append(info)

    total_cog_mb = round(sum(r["size_bytes"] for r in cog_records) / (1024 * 1024), 2)
    print(f"  -> Converted and verified {len(cog_records)} COGs ({total_cog_mb} MB total; all 256x256 tiled with [2, 4, 8] overviews).")

    # 2. Render Web-Ready EPSG:4326 RGBA Overlays for MapLibre GL JS
    print("\n[Step 2] Rendering 59 Web-Ready EPSG:4326 RGBA PNG Overlays...")
    overlays: list[dict[str, Any]] = []

    # 2A. 10-Date Single-Date Backscatter Overlays (HH, HV, and Dual-Pol RGB Composite = 30 overlays)
    for rec in gcov_records:
        dt = rec["date"]
        dt_compact = dt.replace("-", "")
        gid = rec["granule_id"]

        hh_tif = PROCESSED_DIR / "gcov_filtered_db" / f"NISAR_L2_GCOV_T129_F016_{dt_compact}_HH_gamma0_dB_40m.tif"
        hv_tif = PROCESSED_DIR / "gcov_filtered_db" / f"NISAR_L2_GCOV_T129_F016_{dt_compact}_HV_gamma0_dB_40m.tif"

        # HH dB [-24, 0] dB
        hh_png = OVERLAYS_DIR / "gcov_dates" / f"gcov_{dt_compact}_HH_dB.png"
        hh_info = render_continuous_wgs84_png(hh_tif, hh_png, vmin=-24.0, vmax=0.0, cmap_name="viridis")
        hh_info.update(
            {
                "layer_id": f"gcov_{dt_compact}_HH",
                "group": "single_date_backscatter",
                "date": dt,
                "polarization": "HH",
                "title": f"NISAR L2_GCOV HH Backscatter ({dt})",
                "url": f"/tiles/overlays/gcov_dates/{hh_png.name}",
                "cog_url": f"/cogs/gcov_filtered_db/{hh_tif.name}",
                "legend": {
                    "type": "continuous",
                    "unit": "dB (10*log10 gamma0)",
                    "vmin": -24.0,
                    "vmax": 0.0,
                    "stops": [
                        {"value": -24.0, "color": "#440154", "label": "-24 dB (Specular Water / Sand)"},
                        {"value": -18.0, "color": "#3b528b", "label": "-18 dB (Dry Bare Soil)"},
                        {"value": -12.0, "color": "#21918c", "label": "-12 dB (Moderate Roughness / Crop)"},
                        {"value": -6.0, "color": "#5ec962", "label": "-6 dB (Dense Canopy / Wet Soil)"},
                        {"value": 0.0, "color": "#fde725", "label": "0 dB (Urban Double-Bounce)"},
                    ],
                },
            }
        )
        overlays.append(hh_info)

        # HV dB [-26, -6] dB
        hv_png = OVERLAYS_DIR / "gcov_dates" / f"gcov_{dt_compact}_HV_dB.png"
        hv_info = render_continuous_wgs84_png(hv_tif, hv_png, vmin=-26.0, vmax=-6.0, cmap_name="viridis")
        hv_info.update(
            {
                "layer_id": f"gcov_{dt_compact}_HV",
                "group": "single_date_backscatter",
                "date": dt,
                "polarization": "HV",
                "title": f"NISAR L2_GCOV HV Cross-Pol Backscatter ({dt})",
                "url": f"/tiles/overlays/gcov_dates/{hv_png.name}",
                "cog_url": f"/cogs/gcov_filtered_db/{hv_tif.name}",
                "legend": {
                    "type": "continuous",
                    "unit": "dB (10*log10 gamma0)",
                    "vmin": -26.0,
                    "vmax": -6.0,
                    "stops": [
                        {"value": -26.0, "color": "#440154", "label": "-26 dB (NESZ Floor / Water)"},
                        {"value": -21.0, "color": "#3b528b", "label": "-21 dB (Bare Desert / Fallow)"},
                        {"value": -16.0, "color": "#21918c", "label": "-16 dB (Emergent / Moderate Crop)"},
                        {"value": -11.0, "color": "#5ec962", "label": "-11 dB (Dense Crop Biomass)"},
                        {"value": -6.0, "color": "#fde725", "label": "-6 dB (Peak Volume Depolarization)"},
                    ],
                },
            }
        )
        overlays.append(hv_info)

        # Dual-Pol Decoupled Physical RGB Composite
        rgb_png = OVERLAYS_DIR / "gcov_dates" / f"gcov_{dt_compact}_RGB_composite.png"
        rgb_meta = build_rule3_metadata(
            product_type="NISAR_L2_GCOV_PROVISIONAL_V1",
            product_version="1.0.11 (CRID P05023 / PGE R05.02.3)",
            acquisition_date=dt,
            track=129,
            frame=16,
            orbit_direction="Ascending",
            polarization="HH+HV Decoupled Physical RGB Composite",
            units="dB (10*log10 gamma0)",
            crs="EPSG:4326 (reprojected from EPSG:32636)",
            source=f"NASA ASF DAAC | {gid}",
            epistemic_tag="OBSERVATION",
            extra={
                "rgb_channels": (
                    "Green=Vegetation Canopy (HV -19.5..-11 dB), "
                    "Red=Urban Double-Bounce (HH -7..+2 dB), "
                    "Blue/Cyan=Calm to Wind-Roughened Water, "
                    "Warm Sand=Bare Soil & Desert"
                )
            },
        )
        rgb_info = render_dual_pol_rgb_composite_wgs84_png(hh_tif, hv_tif, rgb_png, rgb_meta)
        rgb_info.update(
            {
                "layer_id": f"gcov_{dt_compact}_RGB",
                "group": "single_date_backscatter",
                "date": dt,
                "polarization": "RGB (Green=Crops / Red=Buildings / Blue-Cyan=Water / Sand=Desert)",
                "title": f"NISAR Physical Scattering Composite ({dt})",
                "url": f"/tiles/overlays/gcov_dates/{rgb_png.name}",
                "cog_url": f"/cogs/gcov_filtered_db/{hh_tif.name}",
                "legend": {
                    "type": "rgb_composite",
                    "unit": "dB (10*log10 gamma0)",
                    "channels": [
                        {
                            "channel": "Lush Green (HV Volume)",
                            "color": "#22c55e",
                            "range": "HV: -19.5 to -11 dB",
                            "meaning": "Vegetation & Crops (3D plant stems & canopy volume scattering)",
                        },
                        {
                            "channel": "Vivid Red (HH Double-Bounce)",
                            "color": "#ef4444",
                            "range": "HH: -7 to +2 dB",
                            "meaning": "Buildings & Towns (90° wall-ground corner reflection)",
                        },
                        {
                            "channel": "Deep Blue → Cyan (Water & Waves)",
                            "color": "#0ea5e9",
                            "range": "HH: -22 to -13 dB (low HV)",
                            "meaning": "Calm Water (Deep Blue) → Wind-Wave Ripples & Wet Shore (Cyan)",
                        },
                        {
                            "channel": "Warm Sand (Surface Roughness)",
                            "color": "#b48a52",
                            "range": "HH: -18 to -9 dB (low HV)",
                            "meaning": "Bare Soil, Harvested Fields & Consolidated Desert Limestone",
                        },
                    ],
                },
            }
        )
        overlays.append(rgb_info)

    # 2B. Phase 3 Change Maps across 3 Key Intervals (3 intervals x 6 overlays = 18 overlays)
    intervals = [
        ("20260623_to_20260810", "2026-06-23", "2026-08-10", "Early Summer to Peak Summer Canopy"),
        ("20260810_to_20261021", "2026-08-10", "2026-10-21", "Peak Summer Canopy to Autumn Harvest"),
        ("20260623_to_20261021", "2026-06-23", "2026-10-21", "Full 4-Month Seasonal Span"),
    ]

    for iv_code, dt1, dt2, iv_label in intervals:
        hh_chg_tif = PROCESSED_DIR / "change_maps" / f"delta_HH_dB_{iv_code}_40m.tif"
        hv_chg_tif = PROCESSED_DIR / "change_maps" / f"delta_HV_dB_{iv_code}_40m.tif"
        rat_chg_tif = PROCESSED_DIR / "change_maps" / f"delta_HV_over_HH_dB_{iv_code}_40m.tif"
        cls_chg_tif = PROCESSED_DIR / "change_maps" / f"dual_pol_regime_{iv_code}_40m.tif"

        # 1) Full Delta HH [-8, +8] dB
        p_hh = OVERLAYS_DIR / "change_maps" / f"delta_HH_dB_{iv_code}.png"
        inf_hh = render_continuous_wgs84_png(hh_chg_tif, p_hh, vmin=-8.0, vmax=8.0, cmap_name="diverging_change")
        inf_hh.update(
            {
                "layer_id": f"delta_HH_{iv_code}",
                "group": "change_detection",
                "interval": iv_code,
                "date_start": dt1,
                "date_end": dt2,
                "polarization": "HH",
                "title": f"Delta HH Log-Ratio ({iv_label})",
                "url": f"/tiles/overlays/change_maps/{p_hh.name}",
                "cog_url": f"/cogs/change_maps/{hh_chg_tif.name}",
                "threshold_db": TAU_HH_DB,
                "legend": {
                    "type": "diverging",
                    "unit": "dB difference (10*log10(P2/P1))",
                    "vmin": -8.0,
                    "vmax": 8.0,
                    "threshold_db": TAU_HH_DB,
                    "stops": [
                        {"value": -8.0, "color": "#053061", "label": "-8 dB (Strong Drying / Specular Flooding)"},
                        {"value": -2.73, "color": "#4393c3", "label": "-2.73 dB (-tau_HH Significance Cutoff)"},
                        {"value": 0.0, "color": "#f0f0f0", "label": "0 dB (Within Noise Floor)"},
                        {"value": 2.73, "color": "#f4a582", "label": "+2.73 dB (+tau_HH Significance Cutoff)"},
                        {"value": 8.0, "color": "#b2182b", "label": "+8 dB (Strong Wetting / Tillage / Double-Bounce)"},
                    ],
                },
            }
        )
        overlays.append(inf_hh)

        # 2) Threshold-Masked Significant Delta HH (|dHH| >= 2.73 dB only)
        p_hh_sig = OVERLAYS_DIR / "change_maps" / f"delta_HH_dB_{iv_code}_sig_only.png"
        inf_hh_sig = render_continuous_wgs84_png(
            hh_chg_tif, p_hh_sig, vmin=-8.0, vmax=8.0, cmap_name="diverging_change", transparent_within_abs=TAU_HH_DB
        )
        inf_hh_sig.update(
            {
                "layer_id": f"delta_HH_{iv_code}_sig",
                "group": "change_detection_thresholded",
                "interval": iv_code,
                "date_start": dt1,
                "date_end": dt2,
                "polarization": "HH (|dHH| >= 2.73 dB)",
                "title": f"Significant Delta HH Only >= {TAU_HH_DB} dB ({iv_label})",
                "url": f"/tiles/overlays/change_maps/{p_hh_sig.name}",
                "cog_url": f"/cogs/change_maps/{hh_chg_tif.name}",
                "threshold_db": TAU_HH_DB,
                "legend": inf_hh["legend"],
            }
        )
        overlays.append(inf_hh_sig)

        # 3) Full Delta HV [-8, +8] dB
        p_hv = OVERLAYS_DIR / "change_maps" / f"delta_HV_dB_{iv_code}.png"
        inf_hv = render_continuous_wgs84_png(hv_chg_tif, p_hv, vmin=-8.0, vmax=8.0, cmap_name="diverging_canopy")
        inf_hv.update(
            {
                "layer_id": f"delta_HV_{iv_code}",
                "group": "change_detection",
                "interval": iv_code,
                "date_start": dt1,
                "date_end": dt2,
                "polarization": "HV",
                "title": f"Delta HV Canopy Change ({iv_label})",
                "url": f"/tiles/overlays/change_maps/{p_hv.name}",
                "cog_url": f"/cogs/change_maps/{hv_chg_tif.name}",
                "threshold_db": TAU_HV_DB,
                "legend": {
                    "type": "diverging",
                    "unit": "dB difference (10*log10(P2/P1))",
                    "vmin": -8.0,
                    "vmax": 8.0,
                    "threshold_db": TAU_HV_DB,
                    "stops": [
                        {"value": -8.0, "color": "#8c510a", "label": "-8 dB (Complete Crop Harvest / Clearance)"},
                        {"value": -2.03, "color": "#d8b365", "label": "-2.03 dB (-tau_HV Significance Cutoff)"},
                        {"value": 0.0, "color": "#f5f5f5", "label": "0 dB (Within Noise Floor)"},
                        {"value": 2.03, "color": "#5ab4ac", "label": "+2.03 dB (+tau_HV Significance Cutoff)"},
                        {"value": 8.0, "color": "#01665e", "label": "+8 dB (Vigorous Canopy Volume Growth)"},
                    ],
                },
            }
        )
        overlays.append(inf_hv)

        # 4) Threshold-Masked Significant Delta HV (|dHV| >= 2.03 dB only)
        p_hv_sig = OVERLAYS_DIR / "change_maps" / f"delta_HV_dB_{iv_code}_sig_only.png"
        inf_hv_sig = render_continuous_wgs84_png(
            hv_chg_tif, p_hv_sig, vmin=-8.0, vmax=8.0, cmap_name="diverging_canopy", transparent_within_abs=TAU_HV_DB
        )
        inf_hv_sig.update(
            {
                "layer_id": f"delta_HV_{iv_code}_sig",
                "group": "change_detection_thresholded",
                "interval": iv_code,
                "date_start": dt1,
                "date_end": dt2,
                "polarization": "HV (|dHV| >= 2.03 dB)",
                "title": f"Significant Delta HV Only >= {TAU_HV_DB} dB ({iv_label})",
                "url": f"/tiles/overlays/change_maps/{p_hv_sig.name}",
                "cog_url": f"/cogs/change_maps/{hv_chg_tif.name}",
                "threshold_db": TAU_HV_DB,
                "legend": inf_hv["legend"],
            }
        )
        overlays.append(inf_hv_sig)

        # 5) Delta (HV/HH) Depolarization Ratio [-6, +6] dB
        p_rat = OVERLAYS_DIR / "change_maps" / f"delta_HV_over_HH_dB_{iv_code}.png"
        inf_rat = render_continuous_wgs84_png(rat_chg_tif, p_rat, vmin=-6.0, vmax=6.0, cmap_name="diverging_canopy")
        inf_rat.update(
            {
                "layer_id": f"delta_HV_over_HH_{iv_code}",
                "group": "change_detection",
                "interval": iv_code,
                "date_start": dt1,
                "date_end": dt2,
                "polarization": "HV/HH",
                "title": f"Delta (HV/HH) Depolarization Ratio ({iv_label})",
                "url": f"/tiles/overlays/change_maps/{p_rat.name}",
                "cog_url": f"/cogs/change_maps/{rat_chg_tif.name}",
                "legend": {
                    "type": "diverging",
                    "unit": "dB difference (dHV - dHH)",
                    "vmin": -6.0,
                    "vmax": 6.0,
                    "stops": [
                        {"value": -6.0, "color": "#8c510a", "label": "-6 dB (Shift to Co-Pol Surface/Dihedral)"},
                        {"value": 0.0, "color": "#f5f5f5", "label": "0 dB (Unchanged Depolarization Ratio)"},
                        {"value": 6.0, "color": "#01665e", "label": "+6 dB (Shift to Cross-Pol Canopy Volume)"},
                    ],
                },
            }
        )
        overlays.append(inf_rat)

        # 6) 7-Class Dual-Pol Change Regime & Disagreement Map
        p_cls = OVERLAYS_DIR / "change_maps" / f"dual_pol_regime_{iv_code}.png"
        inf_cls = render_categorical_wgs84_png(cls_chg_tif, p_cls, palette=DUAL_POL_REGIME_PALETTE)
        inf_cls.update(
            {
                "layer_id": f"dual_pol_regime_{iv_code}",
                "group": "dual_pol_regimes",
                "interval": iv_code,
                "date_start": dt1,
                "date_end": dt2,
                "polarization": "HH+HV Dual-Pol",
                "title": f"7-Class Dual-Pol Change & Disagreement Map ({iv_label})",
                "url": f"/tiles/overlays/change_maps/{p_cls.name}",
                "cog_url": f"/cogs/change_maps/{cls_chg_tif.name}",
                "legend": {
                    "type": "categorical",
                    "unit": "categorical mask (uint8)",
                    "classes": [
                        {"code": 1, "color": "#10b981", "label": "1: Canopy Volume Growth (+HV >= +2.03 dB)"},
                        {"code": 2, "color": "#f59e0b", "label": "2: Canopy Harvest / Clearance (-HV <= -2.03 dB)"},
                        {"code": 3, "color": "#3b82f6", "label": "3: Surface Wetting / Tillage (+HH >= +2.73 dB only)"},
                        {"code": 4, "color": "#a855f7", "label": "4: Surface Drying / Inundation (-HH <= -2.73 dB only)"},
                        {"code": 5, "color": "#ef4444", "label": "5: Disagreement I (+HH Surge & -HV Canopy Loss)"},
                        {"code": 6, "color": "#06b6d4", "label": "6: Disagreement II (-HH Drop & +HV Canopy Surge)"},
                        {"code": 0, "color": "#28303c", "label": "0: Within Noise Floor (|dHH|<2.73 & |dHV|<2.03 dB)"},
                    ],
                },
            }
        )
        overlays.append(inf_cls)

    # 2C. 10-Date Seasonal Dynamic Range (max_t - min_t in dB) for HH and HV (2 overlays)
    for pol in ["HH", "HV"]:
        dyn_tif = PROCESSED_DIR / "change_maps" / f"seasonal_dynamic_range_{pol}_dB_10dates_40m.tif"
        dyn_png = OVERLAYS_DIR / "change_maps" / f"seasonal_dynamic_range_{pol}_dB_10dates.png"
        inf_dyn = render_continuous_wgs84_png(dyn_tif, dyn_png, vmin=0.0, vmax=14.0, cmap_name="plasma")
        inf_dyn.update(
            {
                "layer_id": f"seasonal_dynamic_range_{pol}",
                "group": "seasonal_dynamic_range",
                "polarization": pol,
                "title": f"10-Date Seasonal Dynamic Range (max - min {pol} dB)",
                "url": f"/tiles/overlays/change_maps/{dyn_png.name}",
                "cog_url": f"/cogs/change_maps/{dyn_tif.name}",
                "legend": {
                    "type": "continuous",
                    "unit": "dB difference (10*log10(P2/P1))",
                    "vmin": 0.0,
                    "vmax": 14.0,
                    "stops": [
                        {"value": 0.0, "color": "#0d0887", "label": "0–1 dB (Stable Desert / Urban Control)"},
                        {"value": 3.5, "color": "#7e03a8", "label": "3.5 dB (Moderate Seasonal Variation)"},
                        {"value": 7.0, "color": "#cc4778", "label": "7.0 dB (Active Cropland / Shorelines)"},
                        {"value": 10.5, "color": "#f89540", "label": "10.5 dB (High Phenological Turnover)"},
                        {"value": 14.0, "color": "#f0f921", "label": "14+ dB (Peak Crop / Flood-Drawdown Cycle)"},
                    ],
                },
            }
        )
        overlays.append(inf_dyn)

    # 2D. Phase 2 Geophysical & Quality Masks (7 overlays)
    comp_tif = PROCESSED_DIR / "masks" / "fayoum_composite_landcover_class_40m.tif"
    comp_png = OVERLAYS_DIR / "masks" / "fayoum_composite_landcover_class.png"
    inf_comp = render_categorical_wgs84_png(comp_tif, comp_png, palette=LANDCOVER_CLASS_PALETTE)
    inf_comp.update(
        {
            "layer_id": "mask_composite_landcover",
            "group": "geophysical_masks",
            "title": "Fayoum Oasis Geophysical Land-Cover & Calibration Strata",
            "url": f"/tiles/overlays/masks/{comp_png.name}",
            "cog_url": f"/cogs/masks/{comp_tif.name}",
            "legend": {
                "type": "categorical",
                "unit": "categorical mask (uint8)",
                "classes": [
                    {"code": 1, "color": "#0e7490", "label": "1: Permanent Open Water (310.18 km^2 / 6.31%)"},
                    {"code": 2, "color": "#38bdf8", "label": "2: Seasonal Water Margin (165.85 km^2 / 3.38%)"},
                    {"code": 3, "color": "#22c55e", "label": "3: Vegetated Agriculture (1,934.36 km^2 / 39.38%)"},
                    {"code": 4, "color": "#ef4444", "label": "4: Urban Settlement (145.51 km^2 / 2.96%)"},
                    {"code": 5, "color": "#d97706", "label": "5: Stable Limestone Desert Reference (349.93 km^2 / 7.12%)"},
                    {"code": 6, "color": "#94a3b8", "label": "6: Low-SNR Eolian Sand Sheet (1,402.90 km^2 / 28.56%)"},
                ],
            },
        }
    )
    overlays.append(inf_comp)

    binary_mask_specs = [
        ("fayoum_permanent_water_mask_40m.tif", "mask_permanent_water", "Permanent Open Water Mask (Lake Qarun & Wadi El Rayan)", (14, 116, 144, 230)),
        ("fayoum_seasonal_water_margin_mask_40m.tif", "mask_seasonal_water", "Seasonal Water & Dynamic Shoreline Mask", (56, 189, 248, 230)),
        ("fayoum_vegetated_agriculture_mask_40m.tif", "mask_vegetated_ag", "Irrigated Vegetated Agriculture Mask", (34, 197, 94, 210)),
        ("fayoum_urban_settlement_mask_40m.tif", "mask_urban", "Urban Settlement Dihedral Mask", (239, 68, 68, 240)),
        ("fayoum_stable_desert_reference_mask_40m.tif", "mask_stable_desert", "Stable Consolidated Desert Reference Mask (Noise Calibration)", (217, 119, 6, 220)),
        ("fayoum_low_snr_nesz_mask_40m.tif", "mask_low_snr_nesz", "Low-SNR / NESZ Proximity Mask (< +3 dB above NESZ)", (148, 163, 184, 180)),
    ]
    for tif_name, lid, title, rgba_color in binary_mask_specs:
        m_tif = PROCESSED_DIR / "masks" / tif_name
        m_png = OVERLAYS_DIR / "masks" / tif_name.replace("_40m.tif", ".png")
        m_inf = render_categorical_wgs84_png(m_tif, m_png, palette={}, binary_color=rgba_color)
        hex_col = "#{:02x}{:02x}{:02x}".format(rgba_color[0], rgba_color[1], rgba_color[2])
        m_inf.update(
            {
                "layer_id": lid,
                "group": "geophysical_masks",
                "title": title,
                "url": f"/tiles/overlays/masks/{m_png.name}",
                "cog_url": f"/cogs/masks/{tif_name}",
                "legend": {
                    "type": "categorical",
                    "unit": "categorical mask (uint8)",
                    "classes": [{"code": 1, "color": hex_col, "label": title}],
                },
            }
        )
        overlays.append(m_inf)

    # 2E. Exploratory L2_GUNW Coherence-Masked LOS Displacement Overlays (2 overlays)
    gunw_specs = [
        (
            "NISAR_L2_GUNW_T129_F016_20260705_to_20260717_LOS_displacement_m_coh050_80m.tif",
            "gunw_los_20260705_20260717",
            "2026-07-05 to 2026-07-17",
            "Exploratory L2_GUNW Apparent LOS Phase Screen (2026-07-05 -> 2026-07-17, gamma >= 0.50)",
        ),
        (
            "NISAR_L2_GUNW_T129_F016_20261009_to_20261021_LOS_displacement_m_coh050_80m.tif",
            "gunw_los_20261009_20261021",
            "2026-10-09 to 2026-10-21",
            "Exploratory L2_GUNW Apparent LOS Phase Screen (2026-10-09 -> 2026-10-21, gamma >= 0.50)",
        ),
    ]
    for g_tif_name, g_lid, g_pair, g_title in gunw_specs:
        g_tif = PROCESSED_DIR / "gunw_los" / g_tif_name
        g_png = OVERLAYS_DIR / "gunw_los" / f"{g_lid}.png"
        g_inf = render_continuous_wgs84_png(g_tif, g_png, vmin=-0.06, vmax=0.06, cmap_name="coolwarm")
        g_inf.update(
            {
                "layer_id": g_lid,
                "group": "exploratory_insar_gunw",
                "pair": g_pair,
                "polarization": "HH (SH 40 MHz)",
                "title": g_title,
                "url": f"/tiles/overlays/gunw_los/{g_png.name}",
                "cog_url": f"/cogs/gunw_los/{g_tif_name}",
                "exploratory_disclaimer": (
                    "Rule 4 & Rule 6 Guardrail: Pixels with coherence gamma < 0.50 are masked as UNRELIABLE (transparent). "
                    "Anchored to Fayoum Urban Core (Easting 292680m, Northing 3244840m). 12-day L-band phase variations "
                    "(±9-19 mm 1-sigma over stable bedrock) are dominated by tropospheric water-vapor gradients and soil "
                    "moisture dielectric phase, NOT long-term ground subsidence."
                ),
                "legend": {
                    "type": "diverging",
                    "unit": "meters LOS",
                    "vmin": -0.06,
                    "vmax": 0.06,
                    "stops": [
                        {"value": -0.06, "color": "#3b4cc0", "label": "-60 mm Apparent LOS Range Change"},
                        {"value": 0.0, "color": "#f7f7f7", "label": "0 mm (Anchored at Fayoum Urban Benchmark)"},
                        {"value": 0.06, "color": "#b40426", "label": "+60 mm Apparent LOS Range Change"},
                    ],
                },
            }
        )
        overlays.append(g_inf)

    total_png_mb = round(sum(o["size_bytes"] for o in overlays) / (1024 * 1024), 2)
    print(f"  -> Rendered and verified {len(overlays)} EPSG:4326 RGBA PNG overlays ({total_png_mb} MB total).")

    # 3. Write Master Layer Catalog (`data/web_tiles/layer_catalog.json`) and Phase 4 Report
    catalog = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "project": "EARTH RHYTHM — NISAR Surface Change Storyteller",
        "aoi": {
            "name": "Fayoum Oasis, Egypt (Lake Qarun, Wadi El Rayan & Nile-Fed Agricultural Basin)",
            "track": 129,
            "frame": 16,
            "orbit_direction": "Ascending",
            "native_crs": "EPSG:32636",
            "web_overlay_crs": "EPSG:4326",
            "utm_bounds_m": [237280.0, 3215040.0, 316000.0, 3277440.0],
            "wgs84_bounds": overlays[0]["wgs84_bounds"],
            "maplibre_coordinates": overlays[0]["maplibre_coordinates"],
            "center_lon_lat": [30.72, 29.35],
            "default_zoom": 9.6,
        },
        "thresholds": {
            "tau_hh_db": TAU_HH_DB,
            "tau_hv_db": TAU_HV_DB,
            "derivation_summary": (
                "Derived from Stage-2 empirical ENL (HH=152.74, HV=444.01) and N=218,705 Stable Consolidated "
                "Desert Reference pixels (349.93 km^2; 1,968,345 consecutive 12-day pairs)."
            ),
        },
        "dates": [r["date"] for r in gcov_records],
        "overlay_count": len(overlays),
        "cog_count": len(cog_records),
        "overlays": overlays,
        "cogs": cog_records,
    }

    CATALOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CATALOG_PATH.write_text(json.dumps(catalog, indent=2), encoding="utf-8")

    # Compute total workspace data size to confirm < 1 GB budget
    data_dir = PROJECT_ROOT / "data"
    total_workspace_bytes = sum(f.stat().st_size for f in data_dir.rglob("*") if f.is_file())
    total_workspace_mb = round(total_workspace_bytes / (1024 * 1024), 2)

    report = {
        "phase": "Phase 4 — Cloud-Optimized GeoTIFF (COG) & Web-Ready Overlay Tile Generation",
        "generated_at_utc": catalog["generated_at_utc"],
        "elapsed_seconds": round(time.time() - t0, 2),
        "cog_summary": {
            "total_cogs_generated": len(cog_records),
            "total_cog_size_mb": total_cog_mb,
            "tile_block_size": [256, 256],
            "overview_pyramids": [2, 4, 8],
            "compression": "DEFLATE (predictor 2/3)",
            "all_rule3_tags_verified": True,
        },
        "web_overlay_summary": {
            "total_png_overlays_generated": len(overlays),
            "total_png_size_mb": total_png_mb,
            "reprojected_crs": "EPSG:4326 (WGS84)",
            "wgs84_bounds": overlays[0]["wgs84_bounds"],
            "maplibre_corner_coordinates": overlays[0]["maplibre_coordinates"],
            "groups_breakdown": {
                grp: sum(1 for o in overlays if o["group"] == grp)
                for grp in sorted({o["group"] for o in overlays})
            },
        },
        "storage_budget_verification": {
            "total_data_directory_mb": total_workspace_mb,
            "within_budget": total_workspace_mb < 1024.0,
        },
        "catalog_path": str(CATALOG_PATH.relative_to(PROJECT_ROOT).as_posix()),
    }

    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\n[COMPLETE] Wrote {CATALOG_PATH} and {REPORT_PATH} in {report['elapsed_seconds']}s.")
    print(f"           Total data directory footprint: {total_workspace_mb} MB.")


if __name__ == "__main__":
    main()

