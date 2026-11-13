"""FastAPI Backend Server & Real-Time On-The-Fly Pixel/Area Inspector (Phase 4).

Serves precomputed Cloud-Optimized GeoTIFFs (`/cogs/...`), Web-Ready EPSG:4326 RGBA Overlays
(`/tiles/overlays/...`), the Rule 3 & Rule 5 Layer Catalog (`/api/catalog`), the Phase 2/3
Story Mode & External Context payload (`/api/story`), and an on-the-fly multi-temporal
Pixel/Patch Inspector (`/api/inspect`) backed by the calibrated 10-date linear-power cube.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from fastapi import Body, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import h5py
import numpy as np
from rasterio.warp import transform as rio_transform

from .echo_assistant import (
    PROVIDERS,
    discover_available_models,
    get_env_configured_providers,
    query_echo_llm,
)
from .radiometry import linear_to_db

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
CUBE_H5_PATH = DATA_DIR / "processed" / "fayoum_gcov_10dates_40m_filtered.h5"
CATALOG_PATH = DATA_DIR / "web_tiles" / "layer_catalog.json"
PHASE2_REPORT_PATH = DATA_DIR / "processed" / "phase2_processing_report.json"
PHASE3_REPORT_PATH = DATA_DIR / "processed" / "phase3_change_and_timeseries_report.json"
PHASE4_REPORT_PATH = DATA_DIR / "processed" / "phase4_cog_and_tile_report.json"
OVERLAYS_DIR = DATA_DIR / "web_tiles" / "overlays"
COGS_DIR = DATA_DIR / "cogs"

TAU_HH_DB = 2.73
TAU_HV_DB = 2.03

LANDCOVER_LABELS = {
    0: "Unclassified / Transitional Desert",
    1: "Permanent Open Water (Lake Qarun / Wadi El Rayan)",
    2: "Seasonal Water Margin / Dynamic Shoreline",
    3: "Irrigated Vegetated Agriculture (Fayoum Oasis)",
    4: "Urban Settlement / Built-Up Core",
    5: "Stable Consolidated Limestone Desert Reference",
    6: "Low-SNR Eolian Sand Sheet (< +3 dB above NESZ)",
}

REGIME_LABELS = {
    0: "No Statistically Significant Change (Within Noise Floor)",
    1: "Regime 1: Canopy Volume Growth (+HV >= +2.03 dB)",
    2: "Regime 2: Canopy Harvest / Clearance (-HV <= -2.03 dB)",
    3: "Regime 3: Surface Wetting / Roughness Increase (+HH >= +2.73 dB only)",
    4: "Regime 4: Surface Drying / Specular Inundation (-HH <= -2.73 dB only)",
    5: "Regime 5: Polarization Disagreement Type I (+HH Surge >= +2.73 dB & -HV Drop <= -2.03 dB)",
    6: "Regime 6: Polarization Disagreement Type II (-HH Drop <= -2.73 dB & +HV Surge >= +2.03 dB)",
}


class CalibratedCubeStore:
    """In-memory store for the 10-date 40m calibrated linear-power GCOV cube and masks."""

    def __init__(self, h5_path: Path) -> None:
        if not h5_path.exists():
            raise FileNotFoundError(f"Missing calibrated cube: {h5_path}")
        with h5py.File(h5_path, "r") as h5:
            self.dates: list[str] = [
                d.decode("utf-8") if isinstance(d, (bytes, np.bytes_)) else str(d)
                for d in h5["dates"][:]
            ]
            self.granule_ids: list[str] = [
                g.decode("utf-8") if isinstance(g, (bytes, np.bytes_)) else str(g)
                for g in h5["granule_ids"][:]
            ]
            self.x_coords: np.ndarray = h5["xCoordinates"][:].astype(np.float64)
            self.y_coords: np.ndarray = h5["yCoordinates"][:].astype(np.float64)
            self.hhhh_lin: np.ndarray = h5["HHHH_linear_filt"][:].astype(np.float32)
            self.hvhv_lin: np.ndarray = h5["HVHV_linear_filt"][:].astype(np.float32)
            self.masks: dict[str, np.ndarray] = {
                k: h5["masks"][k][:].astype(np.uint8) for k in h5["masks"].keys()
            }

        self.x_min = float(np.min(self.x_coords))
        self.x_max = float(np.max(self.x_coords))
        self.y_min = float(np.min(self.y_coords))
        self.y_max = float(np.max(self.y_coords))

    def inspect_location(
        self,
        lon: float | None = None,
        lat: float | None = None,
        utm_x: float | None = None,
        utm_y: float | None = None,
        window_px: int = 5,
    ) -> dict[str, Any]:
        """Extract 10-date time series, interval changes, regime classification, and masks at any AOI point."""
        if utm_x is None or utm_y is None:
            if lon is None or lat is None:
                raise ValueError("Provide either (lon, lat) in EPSG:4326 or (utm_x, utm_y) in EPSG:32636.")
            xs, ys = rio_transform("EPSG:4326", "EPSG:32636", [float(lon)], [float(lat)])
            utm_x, utm_y = float(xs[0]), float(ys[0])
        else:
            lons, lats = rio_transform("EPSG:32636", "EPSG:4326", [float(utm_x)], [float(utm_y)])
            lon, lat = float(lons[0]), float(lats[0])

        if not (self.x_min - 200.0 <= utm_x <= self.x_max + 200.0 and self.y_min - 200.0 <= utm_y <= self.y_max + 200.0):
            raise ValueError(
                f"Coordinates (UTM X={utm_x:.1f}, Y={utm_y:.1f}) lie outside the Fayoum Oasis AOI bounds "
                f"X=[{self.x_min}, {self.x_max}], Y=[{self.y_min}, {self.y_max}]."
            )

        col_idx = int(np.argmin(np.abs(self.x_coords - utm_x)))
        row_idx = int(np.argmin(np.abs(self.y_coords - utm_y)))

        half_win = max(0, (int(window_px) - 1) // 2)
        r0 = max(0, row_idx - half_win)
        r1 = min(len(self.y_coords), row_idx + half_win + 1)
        c0 = max(0, col_idx - half_win)
        c1 = min(len(self.x_coords), col_idx + half_win + 1)

        n_px = int((r1 - r0) * (c1 - c0))
        snapped_x = float(self.x_coords[col_idx])
        snapped_y = float(self.y_coords[row_idx])
        snapped_lons, snapped_lats = rio_transform("EPSG:32636", "EPSG:4326", [snapped_x], [snapped_y])

        series = []
        for t, dt in enumerate(self.dates):
            hh_patch = self.hhhh_lin[t, r0:r1, c0:c1].ravel()
            hv_patch = self.hvhv_lin[t, r0:r1, c0:c1].ravel()
            hh_db = linear_to_db(hh_patch)
            hv_db = linear_to_db(hv_patch)
            rat_db = hv_db - hh_db

            series.append(
                {
                    "date": dt,
                    "granule_id": self.granule_ids[t],
                    "hh_linear_mean": round(float(np.mean(hh_patch)), 6),
                    "hh_db_mean_linear": round(float(linear_to_db(np.mean(hh_patch))), 2),
                    "hh_db_median": round(float(np.median(hh_db)), 2),
                    "hh_db_p25": round(float(np.percentile(hh_db, 25)), 2),
                    "hh_db_p75": round(float(np.percentile(hh_db, 75)), 2),
                    "hv_linear_mean": round(float(np.mean(hv_patch)), 6),
                    "hv_db_mean_linear": round(float(linear_to_db(np.mean(hv_patch))), 2),
                    "hv_db_median": round(float(np.median(hv_db)), 2),
                    "hv_db_p25": round(float(np.percentile(hv_db, 25)), 2),
                    "hv_db_p75": round(float(np.percentile(hv_db, 75)), 2),
                    "hv_over_hh_db_median": round(float(np.median(rat_db)), 2),
                }
            )

        def _classify_pair(idx_start: int, idx_end: int) -> dict[str, Any]:
            d_hh = round(float(series[idx_end]["hh_db_mean_linear"] - series[idx_start]["hh_db_mean_linear"]), 2)
            d_hv = round(float(series[idx_end]["hv_db_mean_linear"] - series[idx_start]["hv_db_mean_linear"]), 2)
            d_rat = round(float(d_hv - d_hh), 2)

            hh_up = d_hh >= TAU_HH_DB
            hh_dn = d_hh <= -TAU_HH_DB
            hv_up = d_hv >= TAU_HV_DB
            hv_dn = d_hv <= -TAU_HV_DB

            if hh_up and hv_dn:
                code = 5
            elif hh_dn and hv_up:
                code = 6
            elif hv_up and not hh_dn:
                code = 1
            elif hv_dn and not hh_up:
                code = 2
            elif hh_up:
                code = 3
            elif hh_dn:
                code = 4
            else:
                code = 0

            return {
                "date_start": self.dates[idx_start],
                "date_end": self.dates[idx_end],
                "delta_hh_db": d_hh,
                "delta_hv_db": d_hv,
                "delta_hv_over_hh_db": d_rat,
                "exceeds_tau_hh": bool(abs(d_hh) >= TAU_HH_DB),
                "exceeds_tau_hv": bool(abs(d_hv) >= TAU_HV_DB),
                "regime_code": code,
                "regime_label": REGIME_LABELS[code],
            }

        intervals = {
            "early_to_peak_summer_20260623_to_20260810": _classify_pair(0, 3),
            "peak_summer_to_autumn_20260810_to_20261021": _classify_pair(3, 9),
            "full_span_20260623_to_20261021": _classify_pair(0, 9),
        }

        lc_code = int(self.masks["composite_landcover_class"][row_idx, col_idx])
        is_veg = bool(self.masks["vegetated_agriculture_mask"][row_idx, col_idx] > 0)
        is_perm_water = bool(self.masks["permanent_water_mask"][row_idx, col_idx] > 0)
        if is_veg and not is_perm_water:
            lc_code = 3
        lc_label = LANDCOVER_LABELS.get(lc_code, "Unclassified")
        low_snr = bool(self.masks["low_snr_nesz_mask"][row_idx, col_idx] > 0)

        hh_meds = [s["hh_db_median"] for s in series]
        hv_meds = [s["hv_db_median"] for s in series]

        return {
            "coordinates": {
                "wgs84_lon": round(float(snapped_lons[0]), 5),
                "wgs84_lat": round(float(snapped_lats[0]), 5),
                "utm_epsg32636_x": snapped_x,
                "utm_epsg32636_y": snapped_y,
                "grid_row": row_idx,
                "grid_col": col_idx,
            },
            "sampling": {
                "window_dimensions_40m_px": f"{r1 - r0}x{c1 - c0}",
                "spatial_sample_count_40m_pixels": n_px,
                "spatial_sample_count_native_10m_pixels": n_px * 16,
                "patch_area_ha": round((n_px * 40.0 * 40.0) / 10000.0, 2),
                "temporal_sample_count_N_dates": len(self.dates),
                "small_sample_disclosure": (
                    f"Temporal sample size N={len(self.dates)} dates (12-day repeat from 2026-06-23 to 2026-10-21); "
                    f"spatial patch size N={n_px} filtered 40m pixels ({n_px * 16} native 10m pixels)."
                ),
            },
            "geophysical_stratum": {
                "landcover_code": lc_code,
                "landcover_label": LANDCOVER_LABELS.get(lc_code, "Unclassified"),
                "low_snr_nesz_proximity_warning": low_snr,
                "is_permanent_water": bool(self.masks["permanent_water_mask"][row_idx, col_idx] > 0),
                "is_seasonal_water_margin": bool(self.masks["seasonal_water_margin_mask"][row_idx, col_idx] > 0),
                "is_vegetated_agriculture": bool(self.masks["vegetated_agriculture_mask"][row_idx, col_idx] > 0),
                "is_urban_settlement": bool(self.masks["urban_settlement_mask"][row_idx, col_idx] > 0),
                "is_stable_desert_reference": bool(self.masks["stable_desert_reference_mask"][row_idx, col_idx] > 0),
            },
            "seasonal_summary": {
                "hh_min_db": round(float(min(hh_meds)), 2),
                "hh_max_db": round(float(max(hh_meds)), 2),
                "hh_dynamic_range_db": round(float(max(hh_meds) - min(hh_meds)), 2),
                "hv_min_db": round(float(min(hv_meds)), 2),
                "hv_max_db": round(float(max(hv_meds)), 2),
                "hv_dynamic_range_db": round(float(max(hv_meds) - min(hv_meds)), 2),
                "tau_hh_db": TAU_HH_DB,
                "tau_hv_db": TAU_HV_DB,
            },
            "interval_evaluations": intervals,
            "epistemic_statements": {
                "observation": (
                    f"OBSERVATION: Over 10 Ascending passes (Track 129 / Frame 016), filtered HH gamma0 ranges from "
                    f"{min(hh_meds):.2f} dB to {max(hh_meds):.2f} dB (range {max(hh_meds)-min(hh_meds):.2f} dB) "
                    f"and HV gamma0 ranges from {min(hv_meds):.2f} dB to {max(hv_meds):.2f} dB "
                    f"(range {max(hv_meds)-min(hv_meds):.2f} dB)."
                ),
                "change_detection": (
                    f"CHANGE DETECTION: Early-to-Peak Summer (Jun 23 -> Aug 10) log-ratio change is "
                    f"dHH = {intervals['early_to_peak_summer_20260623_to_20260810']['delta_hh_db']:+.2f} dB, "
                    f"dHV = {intervals['early_to_peak_summer_20260623_to_20260810']['delta_hv_db']:+.2f} dB "
                    f"({intervals['early_to_peak_summer_20260623_to_20260810']['regime_label']}); "
                    f"Peak-to-Autumn (Aug 10 -> Oct 21) is "
                    f"dHH = {intervals['peak_summer_to_autumn_20260810_to_20261021']['delta_hh_db']:+.2f} dB, "
                    f"dHV = {intervals['peak_summer_to_autumn_20260810_to_20261021']['delta_hv_db']:+.2f} dB "
                    f"({intervals['peak_summer_to_autumn_20260810_to_20261021']['regime_label']})."
                ),
                "interpretation": (
                    f"INTERPRETATION (hypothesis): Classified within `{LANDCOVER_LABELS.get(lc_code, 'Unclassified')}`. "
                    + (
                        "Caution: pixel operates within +3 dB of the sensor NESZ thermal noise floor (-23.3 dB HH / -24.5 dB HV)."
                        if low_snr
                        else "Signal operates well above the sensor NESZ floor."
                    )
                ),
            },
            "timeseries": series,
        }


app = FastAPI(
    title="EARTH RHYTHM — NISAR Surface Change Storyteller API",
    description=(
        "NASA Space Apps 2026 ('Dancing with the SARs') scientific backend serving "
        "calibrated NISAR L2_GCOV & L2_GUNW Cloud-Optimized GeoTIFFs, EPSG:4326 web overlays, "
        "Rule 3 & Rule 5 metadata catalogs, and real-time multi-temporal pixel/area inspection."
    ),
    version="0.4.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_cube_store: CalibratedCubeStore | None = None


def get_cube_store() -> CalibratedCubeStore:
    """Lazy-load and cache the calibrated 10-date HDF5 cube in memory."""
    global _cube_store
    if _cube_store is None:
        _cube_store = CalibratedCubeStore(CUBE_H5_PATH)
    return _cube_store


@app.get("/api/health")
def api_health() -> dict[str, Any]:
    """Return server readiness, calibrated cube dimensions, and catalog counts."""
    store = get_cube_store()
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8")) if CATALOG_PATH.exists() else {}
    return {
        "status": "ok",
        "project": "EARTH RHYTHM — NISAR Surface Change Storyteller",
        "cube_shape_t_y_x": list(store.hhhh_lin.shape),
        "dates": store.dates,
        "native_crs": "EPSG:32636",
        "web_overlay_crs": "EPSG:4326",
        "cog_count": catalog.get("cog_count", 0),
        "overlay_count": catalog.get("overlay_count", 0),
        "thresholds_db": {"tau_hh_db": TAU_HH_DB, "tau_hv_db": TAU_HV_DB},
    }


@app.get("/api/catalog")
def api_catalog() -> dict[str, Any]:
    """Return the master Rule 3 & Rule 5 layer catalog (`data/web_tiles/layer_catalog.json`)."""
    if not CATALOG_PATH.exists():
        raise HTTPException(status_code=404, detail="Layer catalog not found. Run scripts/phase4_build_cogs_and_tiles.py.")
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


@app.get("/api/story")
def api_story() -> dict[str, Any]:
    """Return the complete Phase 2 + Phase 3 + Phase 4 scientific payload for Story Mode and charts."""
    if not PHASE3_REPORT_PATH.exists() or not PHASE2_REPORT_PATH.exists():
        raise HTTPException(status_code=404, detail="Phase 2 or Phase 3 report missing.")
    p2 = json.loads(PHASE2_REPORT_PATH.read_text(encoding="utf-8"))
    p3 = json.loads(PHASE3_REPORT_PATH.read_text(encoding="utf-8"))
    p4 = json.loads(PHASE4_REPORT_PATH.read_text(encoding="utf-8")) if PHASE4_REPORT_PATH.exists() else {}
    return {
        "phase2_processing_and_enl": p2,
        "phase3_change_and_timeseries": p3,
        "phase4_serving_summary": p4,
    }


@app.get("/api/inspect")
def api_inspect(
    lon: float | None = Query(default=None, description="WGS84 Longitude (e.g., 30.9806)"),
    lat: float | None = Query(default=None, description="WGS84 Latitude (e.g., 29.3201)"),
    utm_x: float | None = Query(default=None, description="EPSG:32636 Easting in meters (e.g., 303900)"),
    utm_y: float | None = Query(default=None, description="EPSG:32636 Northing in meters (e.g., 3245140)"),
    window_px: int = Query(default=5, ge=1, le=11, description="Patch size in 40m pixels (1=40m, 3=120m, 5=200m)"),
) -> dict[str, Any]:
    """Query the 10-date calibrated NISAR cube on the fly at any clicked coordinate in Fayoum Oasis."""
    store = get_cube_store()
    try:
        return store.inspect_location(lon=lon, lat=lat, utm_x=utm_x, utm_y=utm_y, window_px=window_px)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/echo/providers")
def api_echo_providers() -> dict[str, Any]:
    """Return all supported AI providers, models, and which keys are pre-configured in `.env`."""
    env_configured = get_env_configured_providers()
    return {
        "providers": PROVIDERS,
        "env_configured_providers": env_configured,
        "default_provider": next(iter(env_configured.keys()), "gemini"),
    }


@app.post("/api/echo/chat")
def api_echo_chat(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    """Answer user questions about the NISAR data and current UI state via Echo AI Helper."""
    provider = str(payload.get("provider") or "gemini")
    model = payload.get("model")
    api_key = payload.get("api_key")
    messages = payload.get("messages") or []
    ui_context = payload.get("ui_context") or {}
    if not isinstance(messages, list) or not messages:
        raise HTTPException(status_code=400, detail="`messages` must be a non-empty list.")
    return query_echo_llm(
        provider=provider,
        model=str(model) if model else None,
        api_key=str(api_key) if api_key else None,
        messages=messages,
        ui_context=ui_context if isinstance(ui_context, dict) else None,
    )


@app.post("/api/echo/test")
def api_echo_test(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    """Send a tiny 'ping' to the selected provider to verify the API key/model before chatting."""
    provider = str(payload.get("provider") or "gemini")
    model = payload.get("model")
    api_key = payload.get("api_key")
    t0 = time.perf_counter()
    result = query_echo_llm(
        provider=provider,
        model=str(model) if model else None,
        api_key=str(api_key) if api_key else None,
        messages=[{"role": "user", "content": "ping"}],
        ping=True,
    )
    result["latency_ms"] = int((time.perf_counter() - t0) * 1000)
    return result


@app.post("/api/echo/models")
def api_echo_models(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    """Dynamically query and return available models for the given provider & API key."""
    provider = str(payload.get("provider") or "gemini")
    api_key = payload.get("api_key")
    return discover_available_models(provider=provider, api_key=str(api_key) if api_key else None)


if OVERLAYS_DIR.exists():
    app.mount("/tiles/overlays", StaticFiles(directory=str(OVERLAYS_DIR)), name="overlays")

if COGS_DIR.exists():
    app.mount("/cogs", StaticFiles(directory=str(COGS_DIR)), name="cogs")

FRONTEND_DIST_DIR = PROJECT_ROOT / "frontend" / "dist"
if FRONTEND_DIST_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIST_DIR), html=True), name="frontend")
