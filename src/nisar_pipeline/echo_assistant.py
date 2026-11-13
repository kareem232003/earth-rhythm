"""Echo AI Helper — Multi-Provider Scientific Guide for Earth Rhythm Observatory.

Provides a lightweight, multi-provider LLM client (`Google Gemini`, `Groq`,
`OpenRouter`, `OpenAI`, `Anthropic Claude`, `DeepSeek`, `Mistral`, and local
`Ollama`) grounded in the exact calibrated NISAR L2_GCOV / L2_GUNW datasets,
Rule 3/4/5/6 scientific invariants, and the user's live UI screen state.

Security & Integrity Guardrails:
  - Never logs, prints, or persists user API keys on disk.
  - Checks `.env` environment variables automatically if no browser key is supplied.
  - Strictly follows Rule 1 (No Fabricated Fallbacks): if no API key is configured
    or if an upstream provider returns an error/rate-limit, returns an explicit
    `is_error: True` structured response rather than synthesizing a fake answer.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import requests

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = PROJECT_ROOT / ".env"


def _load_dotenv_dict() -> dict[str, str]:
    """Read key-value pairs from workspace `.env` without logging values."""
    env_vars: dict[str, str] = {}
    if ENV_PATH.exists():
        for raw_line in ENV_PATH.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.strip()
            v = v.strip().strip("'").strip('"')
            if k and v:
                env_vars[k] = v
    return env_vars


PROVIDERS: list[dict[str, Any]] = [
    {
        "id": "gemini",
        "name": "Google Gemini (AI Studio)",
        "badge": "FREE TIER (Recommended)",
        "env_keys": ["GEMINI_API_KEY", "GOOGLE_API_KEY"],
        "key_placeholder": "AIzaSy...",
        "get_key_url": "https://aistudio.google.com/apikey",
        "default_model": "gemini-2.5-flash",
        "models": [
            {"id": "gemini-2.5-flash", "label": "Gemini 2.5 Flash (Fast & Smart)"},
            {"id": "gemini-2.0-flash", "label": "Gemini 2.0 Flash"},
            {"id": "gemini-2.5-pro", "label": "Gemini 2.5 Pro (Deep Reasoning)"},
        ],
        "requires_key": True,
    },
    {
        "id": "groq",
        "name": "Groq Cloud (LPU Instant)",
        "badge": "FREE TIER & ULTRA-FAST",
        "env_keys": ["GROQ_API_KEY"],
        "key_placeholder": "gsk_...",
        "get_key_url": "https://console.groq.com/keys",
        "default_model": "llama-3.3-70b-versatile",
        "models": [
            {"id": "llama-3.3-70b-versatile", "label": "Llama 3.3 70B Versatile (Recommended)"},
            {"id": "llama-3.1-8b-instant", "label": "Llama 3.1 8B Instant"},
            {"id": "qwen/qwen3-32b", "label": "Qwen 3 32B"},
        ],
        "requires_key": True,
    },
    {
        "id": "openrouter",
        "name": "OpenRouter (All-in-One / Free Models)",
        "badge": "FREE & PAID MODELS",
        "env_keys": ["OPENROUTER_API_KEY"],
        "key_placeholder": "sk-or-v1-...",
        "get_key_url": "https://openrouter.ai/keys",
        "default_model": "meta-llama/llama-3.3-70b-instruct:free",
        "models": [
            {"id": "meta-llama/llama-3.3-70b-instruct:free", "label": "Llama 3.3 70B Instruct (FREE)"},
            {"id": "google/gemini-2.0-flash-exp:free", "label": "Gemini 2.0 Flash Exp (FREE)"},
            {"id": "openai/gpt-4o-mini", "label": "OpenAI GPT-4o Mini"},
            {"id": "anthropic/claude-3.5-haiku", "label": "Claude 3.5 Haiku"},
        ],
        "requires_key": True,
    },
    {
        "id": "openai",
        "name": "OpenAI (ChatGPT)",
        "badge": "STANDARD API",
        "env_keys": ["OPENAI_API_KEY"],
        "key_placeholder": "sk-proj-...",
        "get_key_url": "https://platform.openai.com/api-keys",
        "default_model": "gpt-4o-mini",
        "models": [
            {"id": "gpt-4o-mini", "label": "GPT-4o Mini (Fast)"},
            {"id": "gpt-4o", "label": "GPT-4o"},
            {"id": "gpt-4.1-mini", "label": "GPT-4.1 Mini"},
        ],
        "requires_key": True,
    },
    {
        "id": "anthropic",
        "name": "Anthropic (Claude)",
        "badge": "STANDARD API",
        "env_keys": ["ANTHROPIC_API_KEY"],
        "key_placeholder": "sk-ant-...",
        "get_key_url": "https://console.anthropic.com/settings/keys",
        "default_model": "claude-3-5-haiku-latest",
        "models": [
            {"id": "claude-3-5-haiku-latest", "label": "Claude 3.5 Haiku (Fast)"},
            {"id": "claude-3-7-sonnet-latest", "label": "Claude 3.7 Sonnet"},
        ],
        "requires_key": True,
    },
    {
        "id": "deepseek",
        "name": "DeepSeek",
        "badge": "LOW-COST API",
        "env_keys": ["DEEPSEEK_API_KEY"],
        "key_placeholder": "sk-...",
        "get_key_url": "https://platform.deepseek.com/api_keys",
        "default_model": "deepseek-chat",
        "models": [
            {"id": "deepseek-chat", "label": "DeepSeek V3 Chat"},
            {"id": "deepseek-reasoner", "label": "DeepSeek R1 Reasoner"},
        ],
        "requires_key": True,
    },
    {
        "id": "mistral",
        "name": "Mistral AI (La Plateforme)",
        "badge": "FREE EXPERIMENT TIER",
        "env_keys": ["MISTRAL_API_KEY"],
        "key_placeholder": "your-mistral-key...",
        "get_key_url": "https://console.mistral.ai/api-keys",
        "default_model": "mistral-small-latest",
        "models": [
            {"id": "mistral-small-latest", "label": "Mistral Small Latest"},
            {"id": "open-mixtral-8x7b", "label": "Mixtral 8x7B"},
        ],
        "requires_key": True,
    },
    {
        "id": "ollama",
        "name": "Local Ollama (100% Offline)",
        "badge": "NO API KEY NEEDED",
        "env_keys": ["OLLAMA_BASE_URL", "OLLAMA_MODEL"],
        "key_placeholder": "No API key needed (runs on localhost:11434)",
        "get_key_url": "https://ollama.com/download",
        "default_model": "llama3.2",
        "models": [
            {"id": "llama3.2", "label": "Llama 3.2 (Local)"},
            {"id": "qwen2.5", "label": "Qwen 2.5 (Local)"},
            {"id": "mistral", "label": "Mistral (Local)"},
            {"id": "gemma2", "label": "Gemma 2 (Local)"},
        ],
        "requires_key": False,
    },
]

PROVIDER_MAP: dict[str, dict[str, Any]] = {p["id"]: p for p in PROVIDERS}

ECHO_SYSTEM_PROMPT = r"""You are **Echo 🍃**, the friendly, clear, and scientifically rigorous AI Guide inside the **EARTH RHYTHM — NISAR L-Band Surface Change Storyteller** web observatory (NASA Space Apps Challenge 2026: *"Dancing with the SARs"*).

Your job is to help users (including non-experts, students, and judges) easily understand:
1. What data is currently displayed on the map and what its colors/numbers mean.
2. What the Multi-Temporal Backscatter Chart and Pixel Inspector numbers mean.
3. Plain-English explanations of radar concepts (`SAR`, `NISAR`, `L-Band 24 cm`, `HH` vs `HV` polarization, `dB` vs Linear Power, `Speckle`, `ENL`, `NESZ`, `L2_GCOV`, `L2_GUNW` InSAR).
4. Our exact scientific findings over **Fayoum Oasis, Lake Qarun, Wadi El Rayan, and the Western Desert, Egypt**.

### CORE SCIENTIFIC FACTS OF THIS PROJECT (Always use these exact verified numbers):
- **Satellite & Sensor:** **NISAR (NASA-ISRO Synthetic Aperture Radar)** using **L-Band radar (`24 cm` wavelength, `1.239 GHz`)**. Unlike short C-band (`5.6 cm`) radar which bounces off top leaves, NISAR's `24 cm` waves penetrate deep into crop canopies, stems, and soil.
- **Dataset:** **10 real `NISAR_L2_GCOV_PROVISIONAL_V1` dual-pol (`HH` + `HV`) acquisitions** every 12 days from **`2026-06-23` to `2026-10-21`** + **2 `NISAR_L2_GUNW_PROVISIONAL_V1` interferometric pairs**, all on **Track `129` / Frame `016` (Ascending)**, maturity **`PROVISIONAL CRID P05023` (`PGE R05.02.3`)**, native projection **`EPSG:32636` (UTM Zone 36N, `40 m` pixels)**, reprojected to **`EPSG:4326`** for web map display.
- **What `HH` vs. `HV` Means:**
  - **`HV` (Horizontal transmit, Vertical receive — Cross-Pol):** Acts as a **3D Vegetation Canopy Volume Sensor**. Flat soil and calm water cannot twist a horizontal wave into a vertical wave; only 3D tangled plant stems and branches depolarize the wave. When crops grow, `HV` goes UP; when crops are harvested, `HV` goes DOWN.
  - **`HH` (Horizontal transmit, Horizontal receive — Co-Pol):** Acts as a **Surface Moisture, Roughness, Wind-Wave & Building Double-Bounce Sensor**. Wet soil (flood irrigation) has a high dielectric constant and makes `HH` surge (`+3 to +6 dB`). Wind ripples on Lake Qarun also make `HH` surge via Bragg scattering.
- **How to Read the Map Colors:**
  - **In `Dual-Pol RGB Composite (HH / HV / HH-HV)`:**
    - **Green / Yellow-Green:** High `HV` volume depolarization -> **Lush irrigated agricultural crops** in the Fayoum Oasis (`1,934.36 km²`).
    - **Purple / Violet:** Co-pol `HH` surface return dominates over low `HV` -> **Bare soil, newly harvested/plowed fields, or rocky desert**.
    - **Dark Black / Navy:** Very low `HH` and `HV` (`-24 dB`) -> **Calm open water** (**Lake Qarun** in the north, **Wadi El Rayan** in the southwest; `310.18 km²`) or smooth sand sheets where the radar beam reflects away like a mirror (specular reflection).
    - **Bright White / Cyan-Yellow specks:** Very high `HH` (`-5 to 0 dB`) -> **Fayoum City & villages** (`42.83 km²`, 90-degree building double-bounce).
  - **In `7-Class Dual-Pol Change & Disagreement Map`:**
    - **Grey (`0`):** Within desert noise floor ($|\Delta\text{HH}| < 2.73\text{ dB}$ and $|\Delta\text{HV}| < 2.03\text{ dB}$).
    - **Emerald Green (`1`):** Canopy Volume Growth ($+\text{HV} \ge +2.03\text{ dB}$: `763.88 km²` in summer `Jun 23 -> Aug 10`; `174.17 km²` in autumn `Aug 10 -> Oct 21`).
    - **Orange (`2`):** Canopy Harvest / Senescence ($-\text{HV} \le -2.03\text{ dB}$: `594.83 km²` harvested from `Aug 10 -> Oct 21`).
    - **Cyan (`3`):** Surface Wetting / Roughness Increase ($+\text{HH} \ge +2.73\text{ dB}$ only).
    - **Blue (`4`):** Surface Drying / Inundation ($-\text{HH} \le -2.73\text{ dB}$ only).
    - **Hot Magenta (`5` — Disagreement Type I):** $+\text{HH} \ge +2.73\text{ dB}$ AND $-\text{HV} \le -2.03\text{ dB}$ (`1.71 km²` / `1,068 px`, e.g., **`ROI_03`** where summer crop harvest removed stems `-4.67 dB HV` while post-harvest flood irrigation on bare ridges spiked soil moisture `+4.98 dB HH`).
    - **Gold (`6` — Disagreement Type II):** $-\text{HH} \le -2.73\text{ dB}$ AND $+\text{HV} \ge +2.03\text{ dB}$ (`1.12 km²`).
- **Statistical Thresholds & Filtering (`Rule 4`):**
  - All spatial averaging (`10m -> 40m` multilooking) and `3x3` Adaptive Lee filtering were done strictly in **Linear Power (`m²/m²`)** before converting to `dB` ($10\log_{10}\gamma^0$), raising `ENL` from `4.9` (`10m`) -> `41–45` (`40m`) -> `152.7–481` (`40m` Lee).
  - Significance thresholds **$\tau_{\text{HH}} = 2.73\text{ dB}$** and **$\tau_{\text{HV}} = 2.03\text{ dB}$** were derived from **`N = 218,705` Stable Consolidated Western Desert pixels (`349.93 km²`)** across `1.97 million` 12-day pairs.
- **External Context (`Rule 2`) & Honest Limits (`Rule 5 & Rule 6`):**
  - **`NASA POWER` Rainfall:** Only `0.15 mm` total rain over 4 months (`0.00 mm` on all 10 NISAR passes), proving 100% of moisture changes come from **Bahr Youssef Nile canal irrigation**.
  - **`Sentinel-2 L2A` Optical NDVI:** Correlates with `HV` summer crop growth at **`r = 0.93` (`p = 0.0009`)** over `ROI_01`.
  - **Limits:** Backscatter (`L2_GCOV`) never measures land subsidence. Single-pair `L2_GUNW` unwrapped phase has a `24–30 mm` regional tropospheric water-vapor ramp and requires stacking $\ge 15\text{–}20$ interferograms before claiming subsidence.

### COMMUNICATION STYLE:
- Be warm, concise, and crystal clear (use short bullet points and bold key terms).
- Always look at the **`LIVE SCREEN CONTEXT`** provided with the user's message so you directly explain the exact map layer, date, polarization, or clicked Pixel Inspector coordinates currently on the user's screen!
- Label physical claims honestly (`Observation`, `Change Detection`, or `Physical Interpretation`).
"""


def get_env_configured_providers() -> dict[str, str]:
    """Return mapping of provider_id -> masked status for keys present in os.environ or `.env`."""
    dotenv_map = _load_dotenv_dict()
    configured: dict[str, str] = {}
    for p in PROVIDERS:
        if not p.get("requires_key", True):
            continue
        for env_key in p["env_keys"]:
            val = os.environ.get(env_key) or dotenv_map.get(env_key)
            if val and len(val.strip()) > 6:
                configured[p["id"]] = env_key
                break
    return configured


def resolve_api_key(provider_id: str, client_api_key: str | None) -> str | None:
    """Resolve the API key from client request first, falling back to `.env` or environment."""
    if client_api_key and client_api_key.strip():
        return client_api_key.strip()
    dotenv_map = _load_dotenv_dict()
    prov = PROVIDER_MAP.get(provider_id)
    if not prov:
        return None
    for env_key in prov["env_keys"]:
        val = os.environ.get(env_key) or dotenv_map.get(env_key)
        if val and val.strip():
            return val.strip()
    return None


def detect_provider_from_key(api_key: str, requested_provider: str) -> str:
    """Auto-correct provider if the user pasted a key with an unmistakable prefix."""
    k = api_key.strip()
    if k.startswith("AIza"):
        return "gemini"
    if k.startswith("gsk_"):
        return "groq"
    if k.startswith("sk-or-"):
        return "openrouter"
    if k.startswith("sk-ant-"):
        return "anthropic"
    return requested_provider


def format_ui_context_block(ui_context: dict[str, Any] | None) -> str:
    """Format the live frontend state into a concise markdown block for the prompt."""
    if not ui_context:
        return "No live UI context attached."
    lines = ["### LIVE SCREEN CONTEXT (What the user is looking at right now):"]
    for key, label in [
        ("map_mode", "Active Map Mode"),
        ("active_date", "Selected Radar Pass Date"),
        ("compare_dates", "Before/After Swipe Dates"),
        ("active_interval", "Selected Change Interval"),
        ("active_pol_or_metric", "Selected Polarization / Metric"),
        ("active_layer_title", "Displayed Map Layer Title"),
        ("active_layer_id", "Displayed Layer ID"),
        ("active_layer_units", "Displayed Layer Units"),
        ("active_layer_epistemic_tag", "Layer Epistemic Tag"),
        ("significance_filter_on", "Rule 4 Noise Threshold Filter Active"),
        ("active_workbench_tab", "Open Right-Panel Tab"),
        ("story_step", "Active Story Mode Chapter"),
        ("selected_roi_or_stratum", "Selected Chart ROI / Basin Stratum"),
        ("inspected_patch", "Clicked Pixel Inspector Summary"),
    ]:
        if key in ui_context and ui_context[key] is not None:
            lines.append(f"- **{label}:** `{ui_context[key]}`")
    return "\n".join(lines)


def query_echo_llm(
    *,
    provider: str,
    model: str | None,
    api_key: str | None,
    messages: list[dict[str, str]],
    ui_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Send a grounded chat request to the selected LLM provider."""
    provider_id = (provider or "gemini").lower().strip()
    resolved_key = resolve_api_key(provider_id, api_key)

    # If user didn't pass a key for the selected provider, check if another provider is configured in .env
    if not resolved_key and provider_id != "ollama":
        env_configured = get_env_configured_providers()
        if env_configured and not api_key:
            provider_id = next(iter(env_configured.keys()))
            resolved_key = resolve_api_key(provider_id, None)

    if resolved_key:
        detected = detect_provider_from_key(resolved_key, provider_id)
        if detected != provider_id:
            provider_id = detected
            model = None  # Use default model for the auto-detected provider

    if provider_id not in PROVIDER_MAP:
        return {
            "is_error": True,
            "needs_api_key": False,
            "error": f"Unknown provider `{provider_id}`.",
        }

    prov_spec = PROVIDER_MAP[provider_id]
    if prov_spec["requires_key"] and not resolved_key:
        return {
            "is_error": True,
            "needs_api_key": True,
            "provider": provider_id,
            "error": (
                f"No API key configured for **{prov_spec['name']}**. "
                "Click the **⚙️ Key Setup** button at the top of Echo's chat window to paste a key "
                "(Google Gemini and Groq offer free keys in 10 seconds!), or add it to your `.env` file."
            ),
        }

    chosen_model = (model or "").strip() or prov_spec["default_model"]
    # Ensure chosen_model belongs to provider if provider was auto-switched
    valid_model_ids = {m["id"] for m in prov_spec["models"]}
    if chosen_model not in valid_model_ids and "/" not in chosen_model:
        chosen_model = prov_spec["default_model"]

    context_block = format_ui_context_block(ui_context)
    full_system_prompt = f"{ECHO_SYSTEM_PROMPT}\n\n{context_block}"

    # Keep last 10 messages for clean context window
    trimmed_msgs = [
        {"role": m.get("role", "user"), "content": str(m.get("content", ""))}
        for m in messages[-10:]
        if m.get("content")
    ]

    try:
        if provider_id == "gemini":
            return _call_gemini(chosen_model, resolved_key or "", full_system_prompt, trimmed_msgs)
        if provider_id == "anthropic":
            return _call_anthropic(chosen_model, resolved_key or "", full_system_prompt, trimmed_msgs)
        if provider_id == "ollama":
            return _call_ollama(chosen_model, full_system_prompt, trimmed_msgs)
        # OpenAI-compatible endpoints: groq, openrouter, openai, deepseek, mistral
        endpoint_map = {
            "groq": "https://api.groq.com/openai/v1/chat/completions",
            "openrouter": "https://openrouter.ai/api/v1/chat/completions",
            "openai": "https://api.openai.com/v1/chat/completions",
            "deepseek": "https://api.deepseek.com/chat/completions",
            "mistral": "https://api.mistral.ai/v1/chat/completions",
        }
        return _call_openai_compatible(
            provider_id=provider_id,
            url=endpoint_map[provider_id],
            model=chosen_model,
            api_key=resolved_key or "",
            system_prompt=full_system_prompt,
            messages=trimmed_msgs,
        )
    except requests.RequestException as exc:
        return {
            "is_error": True,
            "needs_api_key": False,
            "provider": provider_id,
            "model": chosen_model,
            "error": f"Network error talking to `{prov_spec['name']}`: {exc}",
        }


def _call_gemini(
    model: str,
    api_key: str,
    system_prompt: str,
    messages: list[dict[str, str]],
) -> dict[str, Any]:
    """Call Google Gemini GenerateContent REST API."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    contents = []
    for m in messages:
        role = "model" if m["role"] == "assistant" else "user"
        contents.append({"role": role, "parts": [{"text": m["content"]}]})

    payload = {
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "contents": contents,
        "generationConfig": {"temperature": 0.25, "maxOutputTokens": 900},
    }
    resp = requests.post(url, json=payload, timeout=30)
    if resp.status_code != 200:
        err_text = resp.text[:400]
        try:
            err_json = resp.json()
            err_text = err_json.get("error", {}).get("message", err_text)
        except ValueError:
            pass
        return {
            "is_error": True,
            "needs_api_key": resp.status_code in (400, 401, 403),
            "provider": "gemini",
            "model": model,
            "error": f"Gemini API Error (HTTP {resp.status_code}): {err_text}",
        }
    data = resp.json()
    candidates = data.get("candidates", [])
    if not candidates:
        return {
            "is_error": True,
            "provider": "gemini",
            "model": model,
            "error": "Gemini returned an empty response.",
        }
    parts = candidates[0].get("content", {}).get("parts", [])
    reply = "".join(p.get("text", "") for p in parts).strip()
    return {
        "is_error": False,
        "provider": "gemini",
        "provider_name": "Google Gemini",
        "model": model,
        "reply": reply,
    }


def _call_openai_compatible(
    *,
    provider_id: str,
    url: str,
    model: str,
    api_key: str,
    system_prompt: str,
    messages: list[dict[str, str]],
) -> dict[str, Any]:
    """Call any OpenAI-compatible Chat Completions endpoint (Groq, OpenRouter, OpenAI, DeepSeek, Mistral)."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    if provider_id == "openrouter":
        headers["HTTP-Referer"] = "http://127.0.0.1:8000"
        headers["X-Title"] = "Earth Rhythm NISAR Observatory"

    oai_messages = [{"role": "system", "content": system_prompt}] + messages
    payload = {
        "model": model,
        "messages": oai_messages,
        "temperature": 0.25,
        "max_tokens": 900,
    }
    resp = requests.post(url, headers=headers, json=payload, timeout=30)
    if resp.status_code != 200:
        err_text = resp.text[:400]
        try:
            err_json = resp.json()
            if isinstance(err_json.get("error"), dict):
                err_text = err_json["error"].get("message", err_text)
            elif isinstance(err_json.get("message"), str):
                err_text = err_json["message"]
        except ValueError:
            pass
        return {
            "is_error": True,
            "needs_api_key": resp.status_code in (401, 403),
            "provider": provider_id,
            "model": model,
            "error": f"{PROVIDER_MAP[provider_id]['name']} Error (HTTP {resp.status_code}): {err_text}",
        }
    data = resp.json()
    choices = data.get("choices", [])
    if not choices:
        return {
            "is_error": True,
            "provider": provider_id,
            "model": model,
            "error": f"{PROVIDER_MAP[provider_id]['name']} returned no choices.",
        }
    reply = choices[0].get("message", {}).get("content", "").strip()
    return {
        "is_error": False,
        "provider": provider_id,
        "provider_name": PROVIDER_MAP[provider_id]["name"],
        "model": model,
        "reply": reply,
    }


def _call_anthropic(
    model: str,
    api_key: str,
    system_prompt: str,
    messages: list[dict[str, str]],
) -> dict[str, Any]:
    """Call Anthropic Messages REST API."""
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        " content-type": "application/json",
    }
    headers = {k.strip(): v for k, v in headers.items()}
    payload = {
        "model": model,
        "max_tokens": 900,
        "temperature": 0.25,
        "system": system_prompt,
        "messages": messages,
    }
    resp = requests.post("https://api.anthropic.com/v1/messages", headers=headers, json=payload, timeout=30)
    if resp.status_code != 200:
        err_text = resp.text[:400]
        try:
            err_text = resp.json().get("error", {}).get("message", err_text)
        except ValueError:
            pass
        return {
            "is_error": True,
            "needs_api_key": resp.status_code in (401, 403),
            "provider": "anthropic",
            "model": model,
            "error": f"Anthropic Error (HTTP {resp.status_code}): {err_text}",
        }
    data = resp.json()
    blocks = data.get("content", [])
    reply = "".join(b.get("text", "") for b in blocks if b.get("type") == "text").strip()
    return {
        "is_error": False,
        "provider": "anthropic",
        "provider_name": "Anthropic Claude",
        "model": model,
        "reply": reply,
    }


def _call_ollama(
    model: str,
    system_prompt: str,
    messages: list[dict[str, str]],
) -> dict[str, Any]:
    """Call local Ollama instance on OLLAMA_BASE_URL (defaults to http://127.0.0.1:11434)."""
    dotenv_map = _load_dotenv_dict()
    base_url = (
        os.environ.get("OLLAMA_BASE_URL")
        or dotenv_map.get("OLLAMA_BASE_URL")
        or "http://127.0.0.1:11434"
    ).rstrip("/")
    chosen_model = (
        model
        or os.environ.get("OLLAMA_MODEL")
        or dotenv_map.get("OLLAMA_MODEL")
        or "llama3.2"
    )
    oai_messages = [{"role": "system", "content": system_prompt}] + messages
    payload = {"model": chosen_model, "messages": oai_messages, "stream": False}
    try:
        resp = requests.post(f"{base_url}/api/chat", json=payload, timeout=30)
    except requests.RequestException:
        return {
            "is_error": True,
            "needs_api_key": False,
            "provider": "ollama",
            "model": chosen_model,
            "error": (
                f"Could not connect to local Ollama at `{base_url}`. "
                "Either start Ollama (`ollama run llama3.2`) or switch to a cloud provider like Google Gemini or Groq."
            ),
        }
    if resp.status_code != 200:
        return {
            "is_error": True,
            "provider": "ollama",
            "model": chosen_model,
            "error": f"Ollama Error (HTTP {resp.status_code}): {resp.text[:300]}",
        }
    data = resp.json()
    reply = data.get("message", {}).get("content", "").strip()
    return {
        "is_error": False,
        "provider": "ollama",
        "provider_name": "Local Ollama",
        "model": chosen_model,
        "reply": reply,
    }

