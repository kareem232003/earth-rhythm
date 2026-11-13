import React, { useEffect, useRef, useState } from 'react';
import { ExternalLink, KeyRound, Send, Settings, Sparkles, Trash2, X } from 'lucide-react';

export interface EchoUiContext {
  map_mode: string;
  active_date?: string;
  compare_dates?: string;
  active_interval?: string;
  active_pol_or_metric?: string;
  active_layer_title?: string;
  active_layer_id?: string;
  active_layer_units?: string;
  active_layer_epistemic_tag?: string;
  significance_filter_on?: boolean;
  active_workbench_tab?: string;
  story_step?: string;
  selected_roi_or_stratum?: string;
  inspected_patch?: string;
}

interface ProviderModel {
  id: string;
  label: string;
}

interface ProviderSpec {
  id: string;
  name: string;
  badge: string;
  env_keys: string[];
  key_placeholder: string;
  get_key_url: string;
  default_model: string;
  models: ProviderModel[];
  requires_key: boolean;
}

interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  providerName?: string;
  model?: string;
  isError?: boolean;
  needsKey?: boolean;
}

const STORAGE_KEYS_MAP = 'earth_rhythm_echo_keys_v1';
const STORAGE_PROVIDER = 'earth_rhythm_echo_provider_v1';
const STORAGE_MODELS_MAP = 'earth_rhythm_echo_models_v1';

// Baked-in provider catalog so the dropdown is 100% populated immediately on load
const DEFAULT_PROVIDERS: ProviderSpec[] = [
  {
    id: 'gemini',
    name: 'Google Gemini (AI Studio)',
    badge: 'FREE TIER (Recommended)',
    env_keys: ['GEMINI_API_KEY', 'GOOGLE_API_KEY'],
    key_placeholder: 'AIzaSy...',
    get_key_url: 'https://aistudio.google.com/apikey',
    default_model: 'gemini-2.5-flash',
    models: [
      { id: 'gemini-2.5-flash', label: 'Gemini 2.5 Flash (Fast & Smart)' },
      { id: 'gemini-2.0-flash', label: 'Gemini 2.0 Flash' },
      { id: 'gemini-2.5-pro', label: 'Gemini 2.5 Pro (Deep Reasoning)' },
    ],
    requires_key: true,
  },
  {
    id: 'groq',
    name: 'Groq Cloud (LPU Instant)',
    badge: 'FREE TIER & ULTRA-FAST',
    env_keys: ['GROQ_API_KEY'],
    key_placeholder: 'gsk_...',
    get_key_url: 'https://console.groq.com/keys',
    default_model: 'llama-3.3-70b-versatile',
    models: [
      { id: 'llama-3.3-70b-versatile', label: 'Llama 3.3 70B Versatile (Recommended)' },
      { id: 'llama-3.1-8b-instant', label: 'Llama 3.1 8B Instant' },
      { id: 'qwen/qwen3-32b', label: 'Qwen 3 32B' },
    ],
    requires_key: true,
  },
  {
    id: 'openrouter',
    name: 'OpenRouter (All-in-One / Free Models)',
    badge: 'FREE & PAID MODELS',
    env_keys: ['OPENROUTER_API_KEY'],
    key_placeholder: 'sk-or-v1-...',
    get_key_url: 'https://openrouter.ai/keys',
    default_model: 'meta-llama/llama-3.3-70b-instruct:free',
    models: [
      { id: 'meta-llama/llama-3.3-70b-instruct:free', label: 'Llama 3.3 70B Instruct (FREE)' },
      { id: 'google/gemini-2.0-flash-exp:free', label: 'Gemini 2.0 Flash Exp (FREE)' },
      { id: 'openai/gpt-4o-mini', label: 'OpenAI GPT-4o Mini' },
      { id: 'anthropic/claude-3.5-haiku', label: 'Claude 3.5 Haiku' },
    ],
    requires_key: true,
  },
  {
    id: 'openai',
    name: 'OpenAI (ChatGPT)',
    badge: 'STANDARD API',
    env_keys: ['OPENAI_API_KEY'],
    key_placeholder: 'sk-proj-...',
    get_key_url: 'https://platform.openai.com/api-keys',
    default_model: 'gpt-4o-mini',
    models: [
      { id: 'gpt-4o-mini', label: 'GPT-4o Mini (Fast)' },
      { id: 'gpt-4o', label: 'GPT-4o' },
      { id: 'gpt-4.1-mini', label: 'GPT-4.1 Mini' },
    ],
    requires_key: true,
  },
  {
    id: 'anthropic',
    name: 'Anthropic (Claude)',
    badge: 'STANDARD API',
    env_keys: ['ANTHROPIC_API_KEY'],
    key_placeholder: 'sk-ant-...',
    get_key_url: 'https://console.anthropic.com/settings/keys',
    default_model: 'claude-3-5-haiku-latest',
    models: [
      { id: 'claude-3-5-haiku-latest', label: 'Claude 3.5 Haiku (Fast)' },
      { id: 'claude-3-7-sonnet-latest', label: 'Claude 3.7 Sonnet' },
    ],
    requires_key: true,
  },
  {
    id: 'deepseek',
    name: 'DeepSeek',
    badge: 'LOW-COST API',
    env_keys: ['DEEPSEEK_API_KEY'],
    key_placeholder: 'sk-...',
    get_key_url: 'https://platform.deepseek.com/api_keys',
    default_model: 'deepseek-chat',
    models: [
      { id: 'deepseek-chat', label: 'DeepSeek V3 Chat' },
      { id: 'deepseek-reasoner', label: 'DeepSeek R1 Reasoner' },
    ],
    requires_key: true,
  },
  {
    id: 'mistral',
    name: 'Mistral AI (La Plateforme)',
    badge: 'FREE EXPERIMENT TIER',
    env_keys: ['MISTRAL_API_KEY'],
    key_placeholder: 'your-mistral-key...',
    get_key_url: 'https://console.mistral.ai/api-keys',
    default_model: 'mistral-small-latest',
    models: [
      { id: 'mistral-small-latest', label: 'Mistral Small Latest' },
      { id: 'open-mixtral-8x7b', label: 'Mixtral 8x7B' },
    ],
    requires_key: true,
  },
  {
    id: 'ollama',
    name: 'Local Ollama (100% Offline)',
    badge: 'NO API KEY NEEDED',
    env_keys: ['OLLAMA_BASE_URL', 'OLLAMA_MODEL'],
    key_placeholder: 'No API key needed (runs on localhost:11434)',
    get_key_url: 'https://ollama.com/download',
    default_model: 'llama3.2',
    models: [
      { id: 'llama3.2', label: 'Llama 3.2 (Local)' },
      { id: 'qwen2.5', label: 'Qwen 2.5 (Local)' },
      { id: 'mistral', label: 'Mistral (Local)' },
      { id: 'gemma2', label: 'Gemma 2 (Local)' },
    ],
    requires_key: false,
  },
];

const QUICK_PROMPTS = [
  '🗺️ What data is displayed on the map right now, and what do the colors mean?',
  '📈 Explain the chart and the pixel patch I currently have selected.',
  '📡 What is the difference between HH and HV polarization in simple words?',
  '⚡ Why do HH and HV disagree after summer crop harvest in Fayoum Oasis?',
  '🏜️ How did you use the Western Desert to prove changes are not just radar noise?',
];

const CLIENT_FALLBACK_SYSTEM_PROMPT = `You are Echo 🍃, the friendly AI Guide inside the EARTH RHYTHM — NISAR L-Band Surface Change Storyteller web observatory (NASA Space Apps 2026: "Dancing with the SARs").
Explain what is currently displayed on the map, what the colors and dB numbers mean, and how NISAR L-band (24 cm) HH (surface moisture, roughness, double-bounce, wind waves) and HV (3D vegetation canopy volume scattering) work over Fayoum Oasis, Lake Qarun, and the Western Desert, Egypt (10 L2_GCOV passes from 2026-06-23 to 2026-10-21, Track 129 / Frame 016 Ascending, CRID P05023; desert noise thresholds tau_HH=2.73 dB, tau_HV=2.03 dB from N=218,705 pixels).
In the Dual-Pol RGB Composite: Green = high HV crop canopy volume; Purple = bare soil / rocky desert where HH dominates over HV; Dark Black = specular calm water (Lake Qarun / Wadi El Rayan) or smooth sand near the -24.5 dB NESZ floor; Bright White/Yellow = urban double-bounce in Fayoum City. Be concise, warm, and use bullet points.`;

interface EchoHelperProps {
  uiContext: EchoUiContext;
  isOpen: boolean;
  onToggleOpen: () => void;
}

export const EchoHelper: React.FC<EchoHelperProps> = ({ uiContext, isOpen, onToggleOpen }) => {
  const [providers, setProviders] = useState<ProviderSpec[]>(DEFAULT_PROVIDERS);
  const [envConfigured, setEnvConfigured] = useState<Record<string, string>>({});
  const [selectedProvider, setSelectedProvider] = useState<string>(
    () => localStorage.getItem(STORAGE_PROVIDER) || 'gemini'
  );
  const [savedKeys, setSavedKeys] = useState<Record<string, string>>(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEYS_MAP);
      return raw ? JSON.parse(raw) : {};
    } catch {
      return {};
    }
  });
  const [savedModels, setSavedModels] = useState<Record<string, string>>(() => {
    try {
      const raw = localStorage.getItem(STORAGE_MODELS_MAP);
      return raw ? JSON.parse(raw) : {};
    } catch {
      return {};
    }
  });

  const [showSettings, setShowSettings] = useState<boolean>(false);
  const [showFullArt, setShowFullArt] = useState<boolean>(false);
  const [keyInput, setKeyInput] = useState<string>('');
  const [keySavedToast, setKeySavedToast] = useState<string | null>(null);

  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      role: 'assistant',
      content:
        "Hi! I'm **Echo 🍃**, your Earth Rhythm SAR Guide! I can see whichever NISAR layer, date, or pixel you're inspecting right now.\n\nAsk me anything about **what's on the map**, **what the colors or dB numbers mean**, or **how L-band HH & HV radar works**!",
    },
  ]);
  const [input, setInput] = useState<string>('');
  const [sending, setSending] = useState<boolean>(false);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  // Sync optional backend .env status if backend supports /api/echo/providers
  useEffect(() => {
    fetch('/api/echo/providers')
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (data && Array.isArray(data.providers) && data.providers.length > 0) {
          setProviders(data.providers);
          setEnvConfigured(data.env_configured_providers || {});
          if (!localStorage.getItem(STORAGE_PROVIDER) && data.default_provider) {
            setSelectedProvider(data.default_provider);
          }
        }
      })
      .catch(() => {
        // Uses DEFAULT_PROVIDERS seamlessly
      });
  }, []);

  // Sync keyInput when switching provider tab
  useEffect(() => {
    setKeyInput(savedKeys[selectedProvider] || '');
  }, [selectedProvider, savedKeys]);

  // Auto-scroll to newest message
  useEffect(() => {
    if (isOpen && !showSettings) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, isOpen, sending, showSettings]);

  const currentProviderSpec =
    providers.find((p) => p.id === selectedProvider) || DEFAULT_PROVIDERS[0];
  const currentModel =
    savedModels[selectedProvider] || currentProviderSpec.default_model || 'gemini-2.5-flash';

  const hasKeyConfigured =
    selectedProvider === 'ollama' ||
    Boolean(savedKeys[selectedProvider]?.trim()) ||
    Boolean(envConfigured[selectedProvider]);

  const handleKeyInputChange = (val: string) => {
    setKeyInput(val);
    const trimmed = val.trim();
    if (trimmed.startsWith('AIza') && selectedProvider !== 'gemini') {
      setSelectedProvider('gemini');
    } else if (trimmed.startsWith('gsk_') && selectedProvider !== 'groq') {
      setSelectedProvider('groq');
    } else if (trimmed.startsWith('sk-or-') && selectedProvider !== 'openrouter') {
      setSelectedProvider('openrouter');
    } else if (trimmed.startsWith('sk-ant-') && selectedProvider !== 'anthropic') {
      setSelectedProvider('anthropic');
    }
  };

  const handleSaveSettings = () => {
    const trimmed = keyInput.trim();
    let targetProv = selectedProvider;
    if (trimmed.startsWith('AIza')) targetProv = 'gemini';
    else if (trimmed.startsWith('gsk_')) targetProv = 'groq';
    else if (trimmed.startsWith('sk-or-')) targetProv = 'openrouter';
    else if (trimmed.startsWith('sk-ant-')) targetProv = 'anthropic';

    const nextKeys = { ...savedKeys, [targetProv]: trimmed };
    setSavedKeys(nextKeys);
    setSelectedProvider(targetProv);
    localStorage.setItem(STORAGE_KEYS_MAP, JSON.stringify(nextKeys));
    localStorage.setItem(STORAGE_PROVIDER, targetProv);
    setKeySavedToast('✓ Saved! Opening chat...');
    setTimeout(() => {
      setKeySavedToast(null);
      setShowSettings(false);
    }, 650);
  };

  const handleClearKey = () => {
    const nextKeys = { ...savedKeys };
    delete nextKeys[selectedProvider];
    setSavedKeys(nextKeys);
    setKeyInput('');
    localStorage.setItem(STORAGE_KEYS_MAP, JSON.stringify(nextKeys));
  };

  const handleModelChange = (modelId: string) => {
    const nextModels = { ...savedModels, [selectedProvider]: modelId };
    setSavedModels(nextModels);
    localStorage.setItem(STORAGE_MODELS_MAP, JSON.stringify(nextModels));
  };

  // Direct browser-side fallback in case the user hasn't restarted an older uvicorn process yet
  const callProviderDirectlyFromBrowser = async (
    provId: string,
    modelId: string,
    apiKey: string,
    history: ChatMessage[]
  ) => {
    const contextText = `LIVE SCREEN CONTEXT:\n${JSON.stringify(uiContext, null, 2)}`;
    const fullSystem = `${CLIENT_FALLBACK_SYSTEM_PROMPT}\n\n${contextText}`;

    if (provId === 'gemini') {
      if (!apiKey) {
        return {
          is_error: true,
          needs_api_key: true,
          error: 'Please paste your Google Gemini API key (`AIzaSy...`) in the **🔑 API Key** settings panel!',
        };
      }
      const url = `https://generativelanguage.googleapis.com/v1beta/models/${modelId}:generateContent?key=${encodeURIComponent(
        apiKey
      )}`;
      const contents = history.slice(-10).map((m) => ({
        role: m.role === 'assistant' ? 'model' : 'user',
        parts: [{ text: m.content }],
      }));
      const r = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          systemInstruction: { parts: [{ text: fullSystem }] },
          contents,
          generationConfig: { temperature: 0.25, maxOutputTokens: 900 },
        }),
      });
      const j = await r.json();
      if (!r.ok) {
        return {
          is_error: true,
          needs_api_key: r.status === 400 || r.status === 401 || r.status === 403,
          error: j?.error?.message || `Gemini API Error (HTTP ${r.status})`,
        };
      }
      const reply =
        j?.candidates?.[0]?.content?.parts?.map((p: any) => p.text || '').join('') ||
        'No response returned.';
      return {
        is_error: false,
        provider_name: 'Google Gemini',
        model: modelId,
        reply,
      };
    }

    if (provId === 'ollama') {
      const r = await fetch('http://127.0.0.1:11434/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model: modelId,
          stream: false,
          messages: [
            { role: 'system', content: fullSystem },
            ...history.slice(-10).map((m) => ({ role: m.role, content: m.content })),
          ],
        }),
      });
      const j = await r.json();
      if (!r.ok) {
        return { is_error: true, error: `Ollama Error (HTTP ${r.status})` };
      }
      return {
        is_error: false,
        provider_name: 'Local Ollama',
        model: modelId,
        reply: j?.message?.content || '',
      };
    }

    // OpenAI-compatible browser endpoints (groq, openrouter, openai, deepseek, mistral)
    if (!apiKey) {
      return {
        is_error: true,
        needs_api_key: true,
        error: `Please paste your ${currentProviderSpec.name} API key in the **🔑 API Key** settings panel!`,
      };
    }
    const urlMap: Record<string, string> = {
      groq: 'https://api.groq.com/openai/v1/chat/completions',
      openrouter: 'https://openrouter.ai/api/v1/chat/completions',
      openai: 'https://api.openai.com/v1/chat/completions',
      deepseek: 'https://api.deepseek.com/chat/completions',
      mistral: 'https://api.mistral.ai/v1/chat/completions',
    };
    const targetUrl = urlMap[provId] || urlMap.openai;
    const r = await fetch(targetUrl, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${apiKey}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        model: modelId,
        temperature: 0.25,
        max_tokens: 900,
        messages: [
          { role: 'system', content: fullSystem },
          ...history.slice(-10).map((m) => ({ role: m.role, content: m.content })),
        ],
      }),
    });
    const j = await r.json();
    if (!r.ok) {
      return {
        is_error: true,
        needs_api_key: r.status === 401 || r.status === 403,
        error: j?.error?.message || `API Error (HTTP ${r.status})`,
      };
    }
    return {
      is_error: false,
      provider_name: currentProviderSpec.name,
      model: modelId,
      reply: j?.choices?.[0]?.message?.content || '',
    };
  };

  const sendMessage = async (textToSend?: string) => {
    const promptText = (textToSend ?? input).trim();
    if (!promptText || sending) return;

    // If settings drawer was open, switch back to chat stream so user sees the answer
    if (showSettings) setShowSettings(false);

    const nextUserMsg: ChatMessage = { role: 'user', content: promptText };
    const updatedHistory = [...messages, nextUserMsg];
    setMessages(updatedHistory);
    if (!textToSend) setInput('');
    setSending(true);

    try {
      const activeKey = (savedKeys[selectedProvider] || keyInput || '').trim();
      const res = await fetch('/api/echo/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          provider: selectedProvider,
          model: currentModel,
          api_key: activeKey || null,
          messages: updatedHistory.map((m) => ({ role: m.role, content: m.content })),
          ui_context: uiContext,
        }),
      });

      let data: any;
      if (res.status === 404) {
        // Fallback if backend server hasn't been restarted since adding /api/echo/chat
        data = await callProviderDirectlyFromBrowser(
          selectedProvider,
          currentModel,
          activeKey,
          updatedHistory
        );
      } else {
        data = await res.json();
      }

      if (data.is_error) {
        setMessages((prev) => [
          ...prev,
          {
            role: 'assistant',
            content: data.error || `Request failed.`,
            isError: true,
            needsKey: Boolean(data.needs_api_key),
          },
        ]);
      } else {
        setMessages((prev) => [
          ...prev,
          {
            role: 'assistant',
            content: data.reply,
            providerName: data.provider_name,
            model: data.model,
          },
        ]);
      }
    } catch (err: any) {
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: `Connection error: ${err.message || 'Unknown error'}`,
          isError: true,
        },
      ]);
    } finally {
      setSending(false);
    }
  };

  const renderFormattedContent = (text: string) => {
    const lines = text.split('\n');
    return lines.map((line, i) => {
      const trimmed = line.trim();
      if (!trimmed) return <div key={i} className="echo-spacer" />;
      const isBullet = trimmed.startsWith('- ') || trimmed.startsWith('* ');
      const cleanLine = isBullet ? trimmed.slice(2) : line;

      const tokens = cleanLine.split(/(\*\*[^*]+\*\*|`[^`]+`)/g);
      const renderedTokens = tokens.map((tok, j) => {
        if (tok.startsWith('**') && tok.endsWith('**')) {
          return <strong key={j}>{tok.slice(2, -2)}</strong>;
        }
        if (tok.startsWith('`') && tok.endsWith('`')) {
          return (
            <code key={j} className="echo-inline-code">
              {tok.slice(1, -1)}
            </code>
          );
        }
        return <React.Fragment key={j}>{tok}</React.Fragment>;
      });

      if (isBullet) {
        return (
          <div key={i} className="echo-bullet-line">
            <span className="echo-bullet-dot">•</span>
            <span>{renderedTokens}</span>
          </div>
        );
      }
      return (
        <p key={i} className="echo-paragraph">
          {renderedTokens}
        </p>
      );
    });
  };

  return (
    <>
      {/* FLOATING ECHO LAUNCHER BUTTON */}
      {!isOpen && (
        <button className="echo-fab" onClick={onToggleOpen} title="Ask Echo — Your Earth Rhythm AI Guide">
          <div className="echo-fab-avatar-wrap">
            <img src="/echo-avatar.png" alt="Echo AI Guide" className="echo-fab-avatar" />
            <span className="echo-status-dot" />
          </div>
          <div className="echo-fab-text">
            <span className="echo-fab-title">
              Ask Echo <Sparkles size={13} />
            </span>
            <span className="echo-fab-sub">Your Earth Rhythm Guide</span>
          </div>
        </button>
      )}

      {/* ECHO SLIDE-UP CHAT DRAWER */}
      {isOpen && (
        <div className="echo-window">
          {/* HEADER */}
          <div className="echo-header">
            <div className="echo-header-left">
              <img
                src="/echo-avatar.png"
                alt="Echo Avatar"
                className="echo-header-avatar"
                onClick={() => setShowFullArt((v) => !v)}
                title="Click to preview Echo's full portrait"
              />
              <div>
                <div className="echo-header-title">
                  Echo 🍃 <span className="echo-role-pill">Earth Rhythm AI Guide</span>
                </div>
                <div className="echo-header-meta">
                  {currentProviderSpec.name} •{' '}
                  <span className={hasKeyConfigured ? 'echo-key-ok' : 'echo-key-warn'}>
                    {hasKeyConfigured ? '✓ Key Ready' : '⚠️ Click API Key Setup →'}
                  </span>
                </div>
              </div>
            </div>

            <div className="echo-header-actions">
              <button
                className={`echo-icon-btn ${showSettings ? 'active' : ''}`}
                onClick={() => setShowSettings((s) => !s)}
                title="Configure API Key & AI Provider"
              >
                <KeyRound size={14} />
                <span>{showSettings ? 'Back to Chat' : 'API Key'}</span>
              </button>
              <button className="echo-close-btn" onClick={onToggleOpen} title="Minimize Echo">
                <X size={17} />
              </button>
            </div>
          </div>

          {/* OPTIONAL FULL ECHO ARTWORK PREVIEW */}
          {showFullArt && (
            <div className="echo-art-Showcase">
              <img src="/echo-full.jpg" alt="Echo Full Guide Illustration" className="echo-full-img" />
              <button className="echo-art-close" onClick={() => setShowFullArt(false)}>
                Hide Artwork
              </button>
            </div>
          )}

          {/* LIVE CONTEXT STRIP */}
          <div className="echo-context-bar">
            <span className="echo-context-dot" />
            <span className="echo-context-text">
              Watching: <strong>{uiContext.active_layer_title || uiContext.map_mode}</strong>
              {uiContext.active_date ? ` (${uiContext.active_date})` : ''}
            </span>
          </div>

          {/* FULL-HEIGHT SCROLLABLE API KEY & PROVIDER SETUP VIEW */}
          {showSettings ? (
            <div className="echo-settings-panel">
              <div className="echo-settings-header">
                <h4>
                  <Settings size={14} /> Easy AI Provider &amp; API Key Setup
                </h4>
                <span className="echo-privacy-badge">Stored in your browser</span>
              </div>

              <p className="echo-settings-help">
                Click any provider pill below (or use the dropdown), then paste your API key!{' '}
                <strong>Google Gemini</strong> and <strong>Groq</strong> give you free keys in 20 seconds.
              </p>

              {/* CLICKABLE PROVIDER PILLS (Never hidden by OS dropdown menus!) */}
              <div className="echo-provider-grid">
                {providers.map((p) => {
                  const isSel = p.id === selectedProvider;
                  const hasK = p.id === 'ollama' || Boolean(savedKeys[p.id]?.trim()) || Boolean(envConfigured[p.id]);
                  return (
                    <button
                      key={p.id}
                      type="button"
                      className={`echo-prov-pill ${isSel ? 'selected' : ''}`}
                      onClick={() => {
                        setSelectedProvider(p.id);
                        localStorage.setItem(STORAGE_PROVIDER, p.id);
                      }}
                    >
                      <div className="echo-prov-top">
                        <span className="echo-prov-name">{p.name.split(' (')[0]}</span>
                        {hasK && <span className="echo-prov-check">✓</span>}
                      </div>
                      <span className="echo-prov-badge">{p.badge}</span>
                    </button>
                  );
                })}
              </div>

              <div className="echo-field-row">
                <label>Selected Provider ({currentProviderSpec.name}):</label>
                <select
                  className="echo-select"
                  value={selectedProvider}
                  onChange={(e) => {
                    setSelectedProvider(e.target.value);
                    localStorage.setItem(STORAGE_PROVIDER, e.target.value);
                  }}
                >
                  {providers.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name} — [{p.badge}]
                    </option>
                  ))}
                </select>
              </div>

              <div className="echo-field-row">
                <label>Choose Model:</label>
                <select
                  className="echo-select"
                  value={currentModel}
                  onChange={(e) => handleModelChange(e.target.value)}
                >
                  {currentProviderSpec.models.map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.label}
                    </option>
                  ))}
                </select>
              </div>

              {currentProviderSpec.requires_key ? (
                <div className="echo-field-row">
                  <div className="echo-label-split">
                    <label>Paste {currentProviderSpec.name.split(' (')[0]} API Key:</label>
                    <a
                      href={currentProviderSpec.get_key_url}
                      target="_blank"
                      rel="noreferrer"
                      className="echo-get-key-link"
                    >
                      Get {currentProviderSpec.id === 'gemini' || currentProviderSpec.id === 'groq' ? 'FREE ' : ''}
                      Key Here <ExternalLink size={11} />
                    </a>
                  </div>
                  <div className="echo-key-input-group">
                    <input
                      type="password"
                      placeholder={
                        envConfigured[selectedProvider]
                          ? `✓ Pre-configured via server .env (${envConfigured[selectedProvider]})`
                          : `Paste key here (${currentProviderSpec.key_placeholder})`
                      }
                      value={keyInput}
                      onChange={(e) => handleKeyInputChange(e.target.value)}
                    />
                    {savedKeys[selectedProvider] && (
                      <button
                        type="button"
                        className="echo-clear-key-btn"
                        onClick={handleClearKey}
                        title="Clear saved key from browser"
                      >
                        <Trash2 size={14} />
                      </button>
                    )}
                  </div>
                  {envConfigured[selectedProvider] && !savedKeys[selectedProvider] && (
                    <div className="echo-env-detected">
                      ✓ Server <code>.env</code> already has <code>{envConfigured[selectedProvider]}</code> ready!
                    </div>
                  )}
                </div>
              ) : (
                <div className="echo-env-detected">
                  ✓ <strong>Local Ollama</strong> runs offline on your machine (<code>localhost:11434</code>) with no
                  API key required.
                </div>
              )}

              <div className="echo-settings-actions">
                <button type="button" className="echo-save-btn" onClick={handleSaveSettings}>
                  {keySavedToast || 'Save Key & Start Chatting'}
                </button>
                <button type="button" className="echo-cancel-btn" onClick={() => setShowSettings(false)}>
                  Back to Chat
                </button>
              </div>
            </div>
          ) : (
            <>
              {/* MESSAGES STREAM */}
              <div className="echo-messages">
                {messages.map((msg, idx) => (
                  <div key={idx} className={`echo-msg-row ${msg.role === 'user' ? 'user-row' : 'assistant-row'}`}>
                    {msg.role === 'assistant' && (
                      <img src="/echo-avatar.png" alt="Echo" className="echo-msg-avatar" />
                    )}
                    <div className={`echo-bubble ${msg.role} ${msg.isError ? 'error-bubble' : ''}`}>
                      <div className="echo-bubble-body">{renderFormattedContent(msg.content)}</div>
                      {msg.needsKey && (
                        <button className="echo-inline-key-btn" onClick={() => setShowSettings(true)}>
                          <KeyRound size={13} /> Open 1-Click API Key Setup
                        </button>
                      )}
                      {msg.providerName && (
                        <div className="echo-bubble-footer">
                          {msg.providerName} • <code>{msg.model}</code>
                        </div>
                      )}
                    </div>
                  </div>
                ))}

                {sending && (
                  <div className="echo-msg-row assistant-row">
                    <img src="/echo-avatar.png" alt="Echo" className="echo-msg-avatar" />
                    <div className="echo-bubble assistant typing-bubble">
                      <span className="typing-dot" />
                      <span className="typing-dot" />
                      <span className="typing-dot" />
                      <span className="typing-label">Echo is reading the active radar layer...</span>
                    </div>
                  </div>
                )}
                <div ref={messagesEndRef} />
              </div>

              {/* QUICK SUGGESTED QUESTIONS */}
              <div className="echo-quick-chips">
                {QUICK_PROMPTS.map((q, i) => (
                  <button
                    key={i}
                    className="echo-chip"
                    onClick={() => sendMessage(q)}
                    disabled={sending}
                    title={q}
                  >
                    {q}
                  </button>
                ))}
              </div>

              {/* INPUT BAR */}
              <form
                className="echo-input-bar"
                onSubmit={(e) => {
                  e.preventDefault();
                  sendMessage();
                }}
              >
                <input
                  type="text"
                  placeholder="Ask Echo what's on the map, what HH/HV means, or about this chart..."
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  disabled={sending}
                />
                <button type="submit" className="echo-send-btn" disabled={sending || !input.trim()}>
                  <Send size={15} />
                </button>
              </form>
            </>
          )}
        </div>
      )}
    </>
  );
};
