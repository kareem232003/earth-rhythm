import React, { useEffect, useRef, useState } from 'react';
import { ExternalLink, KeyRound, MessageCircle, Send, Settings, Sparkles, Trash2, X } from 'lucide-react';

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

const QUICK_PROMPTS = [
  '🗺️ What data is displayed on the map right now, and what do the colors mean?',
  '📈 Explain the chart and the pixel patch I currently have selected.',
  '📡 What is the difference between HH and HV polarization in simple words?',
  '⚡ Why do HH and HV disagree after summer crop harvest in Fayoum Oasis?',
  '🏜️ How did you use the Western Desert to prove changes are not just radar noise?',
];

interface EchoHelperProps {
  uiContext: EchoUiContext;
  isOpen: boolean;
  onToggleOpen: () => void;
}

export const EchoHelper: React.FC<EchoHelperProps> = ({ uiContext, isOpen, onToggleOpen }) => {
  const [providers, setProviders] = useState<ProviderSpec[]>([]);
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

  // Load provider catalog from backend
  useEffect(() => {
    fetch('/api/echo/providers')
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (data && Array.isArray(data.providers)) {
          setProviders(data.providers);
          setEnvConfigured(data.env_configured_providers || {});
          if (!localStorage.getItem(STORAGE_PROVIDER) && data.default_provider) {
            setSelectedProvider(data.default_provider);
          }
        }
      })
      .catch(() => {
        // Ignore offline init
      });
  }, []);

  // Sync keyInput when switching provider tab
  useEffect(() => {
    setKeyInput(savedKeys[selectedProvider] || '');
  }, [selectedProvider, savedKeys]);

  // Auto-scroll to newest message
  useEffect(() => {
    if (isOpen) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, isOpen, sending]);

  const currentProviderSpec = providers.find((p) => p.id === selectedProvider) || providers[0];
  const currentModel =
    savedModels[selectedProvider] || currentProviderSpec?.default_model || 'gemini-2.5-flash';

  const hasKeyConfigured =
    selectedProvider === 'ollama' ||
    Boolean(savedKeys[selectedProvider]?.trim()) ||
    Boolean(envConfigured[selectedProvider]);

  const handleKeyInputChange = (val: string) => {
    setKeyInput(val);
    const trimmed = val.trim();
    // Smart auto-detection from key prefix
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
    if (trimmed.slice(0, 4) === 'AIza') targetProv = 'gemini';
    else if (trimmed.slice(0, 4) === 'gsk_') targetProv = 'groq';
    else if (trimmed.slice(0, 6) === 'sk-or-') targetProv = 'openrouter';
    else if (trimmed.slice(0, 7) === 'sk-ant-') targetProv = 'anthropic';

    const nextKeys = { ...savedKeys, [targetProv]: trimmed };
    setSavedKeys(nextKeys);
    setSelectedProvider(targetProv);
    localStorage.setItem(STORAGE_KEYS_MAP, JSON.stringify(nextKeys));
    localStorage.setItem(STORAGE_PROVIDER, targetProv);
    setKeySavedToast('Saved locally in browser!');
    setTimeout(() => {
      setKeySavedToast(null);
      setShowSettings(false);
    }, 900);
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

  const sendMessage = async (textToSend?: string) => {
    const promptText = (textToSend ?? input).trim();
    if (!promptText || sending) return;

    const nextUserMsg: ChatMessage = { role: 'user', content: promptText };
    const updatedHistory = [...messages, nextUserMsg];
    setMessages(updatedHistory);
    if (!textToSend) setInput('');
    setSending(true);

    try {
      const res = await fetch('/api/echo/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          provider: selectedProvider,
          model: currentModel,
          api_key: savedKeys[selectedProvider] || null,
          messages: updatedHistory.map((m) => ({ role: m.role, content: m.content })),
          ui_context: uiContext,
        }),
      });

      const data = await res.json();
      if (!res.ok || data.is_error) {
        setMessages((prev) => [
          ...prev,
          {
            role: 'assistant',
            content: data.error || `Request failed with HTTP ${res.status}.`,
            isError: true,
            needsKey: Boolean(data.needs_api_key),
          },
        ]);
        if (data.needs_api_key) {
          setShowSettings(true);
        }
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
          content: `Network error talking to Echo backend: ${err.message || 'Unknown error'}`,
          isError: true,
        },
      ]);
    } finally {
      setSending(false);
    }
  };

  // Simple lightweight markdown renderer for bold, inline code, and bullet lists
  const renderFormattedContent = (text: string) => {
    const lines = text.split('\n');
    return lines.map((line, i) => {
      const trimmed = line.trim();
      if (!trimmed) return <div key={i} className="echo-spacer" />;
      const isBullet = trimmed.startsWith('- ') || trimmed.startsWith('* ');
      const cleanLine = isBullet ? trimmed.slice(2) : line;

      // Split on **bold** and `code`
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
                  {currentProviderSpec ? currentProviderSpec.name : 'Multi-Provider AI'} •{' '}
                  <span className={hasKeyConfigured ? 'echo-key-ok' : 'echo-key-warn'}>
                    {hasKeyConfigured ? '✓ Key Ready' : '⚠️ Needs API Key'}
                  </span>
                </div>
              </div>
            </div>

            <div className="echo-header-actions">
              <button
                className={`echo-icon-btn ${showSettings ? 'active' : ''}`}
                onClick={() => setShowSettings((s) => !s)}
                title="Configure API Key & AI Provider (Gemini, Groq, OpenRouter, OpenAI, Claude, Ollama)"
              >
                <KeyRound size={15} />
                <span>API Key</span>
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

          {/* LIVE CONTEXT STRIP (Shows user that Echo sees what's on their screen) */}
          <div className="echo-context-bar">
            <span className="echo-context-dot" />
            <span className="echo-context-text">
              Watching: <strong>{uiContext.active_layer_title || uiContext.map_mode}</strong>
              {uiContext.active_date ? ` (${uiContext.active_date})` : ''}
            </span>
          </div>

          {/* 1-CLICK API KEY & PROVIDER SETUP DRAWER */}
          {showSettings && (
            <div className="echo-settings-panel">
              <div className="echo-settings-header">
                <h4>
                  <Settings size={14} /> Easy AI Provider &amp; API Key Setup
                </h4>
                <span className="echo-privacy-badge">Stored only in your browser</span>
              </div>

              <p className="echo-settings-help">
                Pick any AI provider below! Need a free key in 10 seconds? Choose{' '}
                <strong>Google Gemini (AI Studio)</strong> or <strong>Groq Cloud</strong>. (Or put your key in{' '}
                <code>.env</code>!)
              </p>

              <div className="echo-field-row">
                <label>1. Choose AI Provider:</label>
                <select
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

              {currentProviderSpec && (
                <>
                  <div className="echo-field-row">
                    <label>2. Choose Model:</label>
                    <select value={currentModel} onChange={(e) => handleModelChange(e.target.value)}>
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
                        <label>3. Paste {currentProviderSpec.name} API Key:</label>
                        <a
                          href={currentProviderSpec.get_key_url}
                          target="_blank"
                          rel="noreferrer"
                          className="echo-get-key-link"
                        >
                          Get a {currentProviderSpec.id === 'gemini' || currentProviderSpec.id === 'groq' ? 'FREE ' : ''}
                          Key <ExternalLink size={11} />
                        </a>
                      </div>
                      <div className="echo-key-input-group">
                        <input
                          type="password"
                          placeholder={
                            envConfigured[selectedProvider]
                              ? `✓ Pre-configured via server .env (${envConfigured[selectedProvider]})`
                              : `Paste key (${currentProviderSpec.key_placeholder}) — auto-detects provider!`
                          }
                          value={keyInput}
                          onChange={(e) => handleKeyInputChange(e.target.value)}
                        />
                        {savedKeys[selectedProvider] && (
                          <button
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
                </>
              )}

              <div className="echo-settings-actions">
                <button className="echo-save-btn" onClick={handleSaveSettings}>
                  {keySavedToast || 'Save & Start Chatting'}
                </button>
                <button className="echo-cancel-btn" onClick={() => setShowSettings(false)}>
                  Close
                </button>
              </div>
            </div>
          )}

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
        </div>
      )}
    </>
  );
};
