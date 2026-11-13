"""Phase 0 Environment and NISAR Data Availability Audit Script.

Executes non-destructive environment diagnostics and queries NASA CMR (`earthaccess`)
and ASF (`asf_search`) for real NISAR L2 GCOV and L2 GUNW coverage over:
  1. Nile Delta
  2. Fayoum Oasis
  3a. Lake Nasser / Toshka Lakes
  3b. East Owainat
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

AOIS: Dict[str, Tuple[float, float, float, float]] = {
    "1. Nile Delta": (29.8, 30.0, 32.3, 31.6),
    "2. Fayoum Oasis": (30.3, 29.1, 31.1, 29.6),
    "3a. Lake Nasser / Toshka Lakes": (31.2, 22.3, 33.2, 23.8),
    "3b. East Owainat": (28.0, 22.0, 29.2, 23.0),
}


def inspect_env_file(env_path: Path) -> Dict[str, Any]:
    """Safely inspect .env keys without ever reading or printing secret values to stdout."""
    info: Dict[str, Any] = {
        "exists": env_path.exists(),
        "keys_present": [],
        "has_earthdata_username": False,
        "has_earthdata_password": False,
        "has_earthdata_token": False,
    }
    if not env_path.exists():
        return info

    raw_lines = env_path.read_text(encoding="utf-8", errors="replace").splitlines()
    keys: List[str] = []
    for line in raw_lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        k, v = stripped.split("=", 1)
        k = k.strip()
        v = v.strip().strip("'").strip('"')
        keys.append(k)
        if k in ("EARTHDATA_USERNAME", "NASA_EARTHDATA_USERNAME", "URS_USERNAME") and len(v) > 0:
            info["has_earthdata_username"] = True
        if k in ("EARTHDATA_PASSWORD", "NASA_EARTHDATA_PASSWORD", "URS_PASSWORD") and len(v) > 0:
            info["has_earthdata_password"] = True
        if k in ("EARTHDATA_TOKEN", "CMR_TOKEN", "ASF_TOKEN") and len(v) > 0:
            info["has_earthdata_token"] = True
    info["keys_present"] = keys
    return info


def check_environment(project_root: Path) -> Dict[str, Any]:
    """Check Python version, geospatial/SAR packages, Node.js, npm, and .env key presence."""
    packages = [
        "earthaccess",
        "asf_search",
        "h5py",
        "rasterio",
        "numpy",
        "scipy",
        "fastapi",
        "pytest",
        "dotenv",
        "requests",
    ]
    pkg_status: Dict[str, str] = {}
    for pkg in packages:
        try:
            mod = __import__(pkg)
            ver = getattr(mod, "__version__", "installed")
            pkg_status[pkg] = str(ver)
        except Exception as exc:
            pkg_status[pkg] = f"MISSING ({type(exc).__name__})"

    node_ver = "MISSING"
    npm_ver = "MISSING"
    node_bin = shutil.which("node")
    npm_bin = shutil.which("npm.cmd") or shutil.which("npm")
    if node_bin:
        try:
            node_ver = subprocess.check_output([node_bin, "-v"], text=True, timeout=5).strip()
        except Exception as exc:
            node_ver = f"ERROR ({exc})"
    if npm_bin:
        try:
            npm_ver = subprocess.check_output([npm_bin, "-v"], text=True, timeout=5).strip()
        except Exception as exc:
            npm_ver = f"ERROR ({exc})"

    env_info = inspect_env_file(project_root / ".env")

    # Test earthaccess authentication if available
    earthaccess_auth = "not_tested"
    if "MISSING" not in pkg_status.get("earthaccess", "MISSING") and "MISSING" not in pkg_status.get("dotenv", "MISSING"):
        try:
            from dotenv import load_dotenv
            import earthaccess
            load_dotenv(project_root / ".env")
            auth = earthaccess.login(strategy="environment")
            earthaccess_auth = "authenticated" if getattr(auth, "authenticated", False) else "failed_or_unverified"
        except Exception as exc:
            earthaccess_auth = f"error ({type(exc).__name__})"

    return {
        "python_version": sys.version.split()[0],
        "python_executable": sys.executable,
        "packages": pkg_status,
        "node_version": node_ver,
        "npm_version": npm_ver,
        "env_file": env_info,
        "earthaccess_login_status": earthaccess_auth,
    }


def http_get_json(url: str, timeout: int = 30) -> Any:
    """Perform an HTTP GET request and parse JSON response."""
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "EarthRhythm-NISAR-Audit/0.1 (NASA-Space-Apps-2026)"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def query_cmr_nisar_collections() -> List[Dict[str, Any]]:
    """Query NASA CMR for all public NISAR collections and check subsetting/service capabilities."""
    url = (
        "https://cmr.earthdata.nasa.gov/search/collections.umm_json"
        "?keyword=NISAR&page_size=200"
    )
    data = http_get_json(url)
    items = data.get("items", [])
    collections: List[Dict[str, Any]] = []
    for item in items:
        meta = item.get("meta", {})
        umm = item.get("umm", {})
        short_name = umm.get("ShortName", "")
        title = umm.get("EntryTitle", "")
        provider = meta.get("provider-id", "")
        concept_id = meta.get("concept-id", "")
        version = umm.get("Version", "")
        collection_progress = umm.get("CollectionProgress", "")
        associations = meta.get("associations", {})
        platforms = [p.get("ShortName", "") for p in umm.get("Platforms", [])]
        if (
            "NISAR" in short_name.upper()
            or "NISAR" in title.upper()
            or any("NISAR" in p.upper() for p in platforms)
        ):
            collections.append(
                {
                    "concept_id": concept_id,
                    "provider": provider,
                    "short_name": short_name,
                    "version": version,
                    "collection_progress": collection_progress,
                    "platforms": platforms,
                    "title": title,
                    "associations": associations,
                }
            )
    return collections


def format_maturity(crid: str) -> str:
    """Format a NISAR CRID code into human-readable maturity + CRID."""
    if crid.startswith(("B", "T", "X")):
        return f"BETA/Pre-Cal ({crid})"
    if crid.startswith("P"):
        return f"PROVISIONAL ({crid})"
    if crid.startswith("V"):
        return f"VALIDATED ({crid})"
    return crid


def parse_nisar_granule_id(granule_ur: str) -> Dict[str, str]:
    """Parse standard NISAR L2 GCOV and L2 GUNW filename conventions."""
    info: Dict[str, str] = {}
    parts = granule_ur.split("_")
    if len(parts) < 14 or parts[0] != "NISAR":
        return info

    info["level"] = parts[1]
    info["processing_type"] = parts[2]
    prod = parts[3]
    info["product_type"] = prod
    info["cycle"] = parts[4]
    info["relative_orbit_track"] = parts[5]
    info["direction"] = (
        "Ascending" if parts[6] == "A" else ("Descending" if parts[6] == "D" else parts[6])
    )
    info["frame"] = parts[7]

    if prod == "GUNW" and len(parts) >= 18:
        info["secondary_cycle"] = parts[8]
        info["mode_bandwidth"] = parts[9]
        info["polarization_code"] = parts[10]
        info["start_datetime"] = parts[11]
        info["end_datetime"] = parts[12]
        info["secondary_start_datetime"] = parts[13]
        info["secondary_end_datetime"] = parts[14]
        info["crid_version"] = parts[15]
        info["maturity"] = format_maturity(parts[15])
        info["frame_coverage_flag"] = "Full" if parts[17] == "F" else ("Partial" if parts[17] == "P" else parts[17])
        ref_d = f"{parts[11][:4]}-{parts[11][4:6]}-{parts[11][6:8]}"
        sec_d = f"{parts[13][:4]}-{parts[13][4:6]}-{parts[13][6:8]}"
        info["pair_label"] = f"{ref_d}->{sec_d}"
    else:
        info["mode_bandwidth"] = parts[8]
        info["polarization_code"] = parts[9]
        info["obs_mode"] = parts[10]
        info["start_datetime"] = parts[11]
        info["end_datetime"] = parts[12]
        info["crid_version"] = parts[13]
        info["maturity"] = format_maturity(parts[13])
        if len(parts) >= 16:
            info["frame_coverage_flag"] = "Full" if parts[15] == "F" else ("Partial" if parts[15] == "P" else parts[15])
    return info


def bbox_intersection_fraction(
    aoi_bbox: Tuple[float, float, float, float],
    granule_polys: List[List[Tuple[float, float]]],
) -> float:
    """Approximate fraction of AOI bounding box covered by granule polygon envelope."""
    if not granule_polys:
        return 0.0
    w, s, e, n = aoi_bbox
    aoi_area = max((e - w) * (n - s), 1e-9)
    best_frac = 0.0
    for poly in granule_polys:
        lons = [pt[0] for pt in poly]
        lats = [pt[1] for pt in poly]
        gw, gs, ge, gn = min(lons), min(lats), max(lons), max(lats)
        iw = max(w, gw)
        is_ = max(s, gs)
        ie = min(e, ge)
        in_ = min(n, gn)
        if ie > iw and in_ > is_:
            inter_area = (ie - iw) * (in_ - is_)
            best_frac = max(best_frac, min(1.0, inter_area / aoi_area))
    return best_frac


def extract_polygons_from_umm(umm: Dict[str, Any]) -> List[List[Tuple[float, float]]]:
    """Extract (lon, lat) polygon rings from UMM-G SpatialExtent."""
    polys: List[List[Tuple[float, float]]] = []
    try:
        gpolys = (
            umm.get("SpatialExtent", {})
            .get("HorizontalSpatialDomain", {})
            .get("Geometry", {})
            .get("GPolygons", [])
        )
        for gp in gpolys:
            pts = gp.get("Boundary", {}).get("Points", [])
            ring = [(float(p["Longitude"]), float(p["Latitude"])) for p in pts]
            if ring:
                polys.append(ring)
    except Exception:
        pass
    return polys


def query_cmr_granule_sizes(
    concept_id: str,
    bbox: Tuple[float, float, float, float],
    page_size: int = 200,
) -> Dict[str, float]:
    """Query CMR granules.json to map producer_granule_id/title to granule_size in MB."""
    params = {
        "collection_concept_id": concept_id,
        "bounding_box": f"{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]}",
        "page_size": page_size,
        "sort_key": "-start_date",
    }
    url = "https://cmr.earthdata.nasa.gov/search/granules.json?" + urllib.parse.urlencode(params)
    data = http_get_json(url)
    entries = data.get("feed", {}).get("entry", [])
    sizes: Dict[str, float] = {}
    for e in entries:
        gid = e.get("title") or e.get("producer_granule_id")
        sz = e.get("granule_size")
        if gid and sz is not None:
            try:
                sizes[gid] = float(sz)
            except ValueError:
                pass
    return sizes


def query_cmr_granules_for_collection(
    concept_id: str,
    bbox: Optional[Tuple[float, float, float, float]] = None,
    page_size: int = 200,
) -> Tuple[int, List[Dict[str, Any]], Dict[str, float]]:
    """Query CMR UMM-G granules and sizes for a given collection concept_id and optional bbox."""
    params: Dict[str, Any] = {
        "collection_concept_id": concept_id,
        "page_size": page_size,
        "sort_key": "-start_date",
    }
    if bbox is not None:
        params["bounding_box"] = f"{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]}"
    url = "https://cmr.earthdata.nasa.gov/search/granules.umm_json?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "EarthRhythm-NISAR-Audit/0.1 (NASA-Space-Apps-2026)"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        hits = int(resp.headers.get("CMR-Hits", "0"))
        data = json.loads(resp.read().decode("utf-8"))
    items = data.get("items", [])
    sizes: Dict[str, float] = {}
    if bbox is not None and hits > 0:
        sizes = query_cmr_granule_sizes(concept_id, bbox, page_size=page_size)
    return hits, items, sizes


def query_asf_nisar(
    bbox: Tuple[float, float, float, float],
    processing_level: str,
) -> List[Dict[str, Any]]:
    """Query ASF Search API directly for NISAR granules over a bounding box."""
    w, s, e, n = bbox
    poly = f"POLYGON(({w} {s},{e} {s},{e} {n},{w} {n},{w} {s}))"
    params = {
        "platform": "NISAR",
        "processingLevel": processing_level,
        "intersectsWith": poly,
        "output": "json",
        "maxResults": "250",
    }
    url = "https://api.daac.asf.alaska.edu/services/search/param?" + urllib.parse.urlencode(params)
    try:
        data = http_get_json(url, timeout=30)
        if isinstance(data, list) and len(data) > 0 and isinstance(data[0], list):
            return data[0]
        if isinstance(data, list):
            return data
        return []
    except Exception as exc:
        return [{"error": str(exc)}]


def summarize_cmr_granules(
    items: List[Dict[str, Any]],
    sizes_map: Dict[str, float],
    asf_map: Dict[str, Dict[str, Any]],
    aoi_bbox: Tuple[float, float, float, float],
) -> Dict[str, Any]:
    """Summarize granule tracks, frames, orbit directions, polarizations, versions, dates, sizes."""
    groups: Dict[str, Dict[str, Any]] = {}
    total_size_mb = 0.0
    all_dates: List[str] = []
    sample_granules: List[Dict[str, Any]] = []

    for item in items:
        umm = item.get("umm", {})
        meta = item.get("meta", {})
        granule_ur = umm.get("GranuleUR", meta.get("native-id", "unknown"))
        parsed = parse_nisar_granule_id(granule_ur)
        asf_info = asf_map.get(granule_ur, {})
        nisar_sub = asf_info.get("nisar", {}) if isinstance(asf_info, dict) else {}

        size_mb = sizes_map.get(granule_ur, 0.0)
        total_size_mb += size_mb

        t_start = (
            umm.get("TemporalExtent", {})
            .get("RangeDateTime", {})
            .get("BeginningDateTime", parsed.get("start_datetime", ""))
        )
        date_str = t_start[:10] if t_start else "unknown"
        if date_str != "unknown":
            all_dates.append(date_str)

        track = parsed.get("relative_orbit_track", "?")
        frame = parsed.get("frame", "?")
        direction = parsed.get("direction", "?")
        pol_code = parsed.get("polarization_code", "?")
        main_pols = nisar_sub.get("mainBandPolarization") or []
        pol_display = f"{pol_code} ({'+'.join(main_pols)})" if main_pols else pol_code
        bandwidth = parsed.get("mode_bandwidth", "?")
        version = parsed.get("maturity", "?")
        pge_ver = nisar_sub.get("pgeVersion", "")
        if pge_ver:
            version = f"{version} / PGE {pge_ver}"
        frame_cov_flag = nisar_sub.get("frameCoverage") or parsed.get("frame_coverage_flag", "?")

        polys = extract_polygons_from_umm(umm)
        cov_frac = bbox_intersection_fraction(aoi_bbox, polys)

        urls = [
            u.get("URL")
            for u in umm.get("RelatedUrls", [])
            if u.get("URL", "").endswith(".h5") and not u.get("URL", "").endswith("_QA_STATS.h5")
        ]

        group_key = f"T{track}_F{frame}_{direction}_{pol_display}_{bandwidth}_{version}"
        if group_key not in groups:
            groups[group_key] = {
                "track": track,
                "frame": frame,
                "direction": direction,
                "polarization": pol_display,
                "mode_bandwidth": bandwidth,
                "version": version,
                "frame_coverage": frame_cov_flag,
                "dates": set(),
                "pairs": [],
                "granule_count": 0,
                "total_size_mb": 0.0,
                "max_aoi_coverage_pct": 0.0,
                "sample_granule_id": granule_ur,
                "sample_url": urls[0] if urls else "",
            }
        g = groups[group_key]
        if parsed.get("pair_label"):
            g["pairs"].append(parsed["pair_label"])
            g["dates"].add(parsed["pair_label"])
        else:
            g["dates"].add(date_str)
        g["granule_count"] += 1
        g["total_size_mb"] += size_mb
        g["max_aoi_coverage_pct"] = max(g["max_aoi_coverage_pct"], round(cov_frac * 100.0, 1))

        if len(sample_granules) < 5:
            sample_granules.append(
                {
                    "granule_id": granule_ur,
                    "date": parsed.get("pair_label") or date_str,
                    "track": track,
                    "frame": frame,
                    "direction": direction,
                    "polarization": pol_display,
                    "mode_bandwidth": bandwidth,
                    "version": version,
                    "frame_coverage": frame_cov_flag,
                    "size_mb": round(size_mb, 2),
                    "aoi_coverage_pct": round(cov_frac * 100.0, 1),
                    "url": urls[0] if urls else "",
                }
            )

    serializable_groups = []
    for k, g in sorted(groups.items(), key=lambda x: (-len(x[1]["dates"]), -x[1]["max_aoi_coverage_pct"], x[0])):
        dates_sorted = sorted(g["dates"])
        serializable_groups.append(
            {
                "group_key": k,
                "track": g["track"],
                "frame": g["frame"],
                "direction": g["direction"],
                "polarization": g["polarization"],
                "mode_bandwidth": g["mode_bandwidth"],
                "version": g["version"],
                "frame_coverage": g["frame_coverage"],
                "usable_dates_count": len(dates_sorted),
                "date_range": f"{dates_sorted[0]} to {dates_sorted[-1]}" if dates_sorted else "none",
                "dates": dates_sorted,
                "granule_count": g["granule_count"],
                "mean_size_mb": round(g["total_size_mb"] / max(1, g["granule_count"]), 1),
                "total_size_gb": round(g["total_size_mb"] / 1024.0, 2),
                "max_aoi_coverage_pct": g["max_aoi_coverage_pct"],
                "sample_granule_id": g["sample_granule_id"],
                "sample_url": g["sample_url"],
            }
        )

    return {
        "total_granules_returned": len(items),
        "total_size_gb": round(total_size_mb / 1024.0, 2),
        "overall_date_range": f"{min(all_dates)} to {max(all_dates)}" if all_dates else "none",
        "homogeneous_series": serializable_groups,
        "sample_granules": sample_granules,
    }


def main() -> None:
    """Run full Phase 0 audit and save raw JSON report."""
    project_root = Path(__file__).resolve().parent.parent
    print("=== PHASE 0 AUDIT: ENVIRONMENT & NISAR ARCHIVE AVAILABILITY ===")

    env_report = check_environment(project_root)
    print("\n[1] Environment Check:")
    print(json.dumps(env_report, indent=2))

    print("\n[2] Querying NASA CMR for NISAR Collections...")
    collections = query_cmr_nisar_collections()
    print(f"Found {len(collections)} NISAR-related collections in NASA CMR.")
    target_collections: List[Dict[str, Any]] = []
    for c in collections:
        sn = c["short_name"]
        title = c["title"]
        hits_global, _, _ = query_cmr_granules_for_collection(c["concept_id"], bbox=None, page_size=1)
        c["global_granule_hits"] = hits_global
        if hits_global > 0 and any(k in sn.upper() for k in ["GCOV", "GUNW"]):
            target_collections.append(c)
            print(
                f"  - {c['concept_id']} | {sn} (v{c['version']}) | Provider: {c['provider']} "
                f"| Global Granules: {hits_global} | Services: {c['associations'].get('services', [])}"
            )

    aoi_results: Dict[str, Any] = {}
    for aoi_name, bbox in AOIS.items():
        print(f"\n[3] Auditing AOI: {aoi_name} | BBOX={bbox}")
        aoi_results[aoi_name] = {"bbox": bbox, "cmr_collections": {}, "asf_direct": {}}

        # Query ASF API first so we can enrich CMR granules with exact polarizations & PGE versions
        asf_lookup: Dict[str, Dict[str, Any]] = {}
        for prod in ("GCOV", "GUNW"):
            asf_res = query_asf_nisar(bbox, prod)
            for rec in asf_res:
                if isinstance(rec, dict) and rec.get("granuleName"):
                    asf_lookup[rec["granuleName"]] = rec
            aoi_results[aoi_name]["asf_direct"][prod] = {
                "count": len(asf_res),
            }
            print(f"  ASF Direct ({prod}): {len(asf_res)} granules")

        for c in target_collections:
            cid = c["concept_id"]
            sn = f"{c['short_name']}_v{c['version']}"
            hits, items, sizes_map = query_cmr_granules_for_collection(cid, bbox=bbox, page_size=200)
            summary = summarize_cmr_granules(items, sizes_map, asf_lookup, bbox)
            summary["cmr_hits"] = hits
            summary["collection_concept_id"] = cid
            summary["short_name"] = c["short_name"]
            summary["version"] = c["version"]
            summary["services"] = c["associations"].get("services", [])
            aoi_results[aoi_name]["cmr_collections"][sn] = summary
            print(
                f"  CMR {sn} ({cid}): {hits} hits | Total Volume: {summary['total_size_gb']} GB | "
                f"{len(summary['homogeneous_series'])} homogeneous track/frame series"
            )
            for grp in summary["homogeneous_series"][:6]:
                print(
                    f"    * Track={grp['track']} Frame={grp['frame']} Dir={grp['direction']} "
                    f"Pol={grp['polarization']} BW={grp['mode_bandwidth']} Ver={grp['version']} "
                    f"CovFlag={grp['frame_coverage']} -> "
                    f"{grp['usable_dates_count']} dates/pairs ({grp['date_range']}), "
                    f"Mean={grp['mean_size_mb']} MB, Total={grp['total_size_gb']} GB, "
                    f"AOI BBox Overlap={grp['max_aoi_coverage_pct']}%"
                )

    out_dir = project_root / "data"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "phase0_audit_results.json"
    full_report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "environment": env_report,
        "nisar_collections": collections,
        "aoi_audit": aoi_results,
    }
    out_file.write_text(json.dumps(full_report, indent=2), encoding="utf-8")
    print(f"\nSaved complete raw Phase 0 audit JSON to: {out_file}")


if __name__ == "__main__":
    main()
