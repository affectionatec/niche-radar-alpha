'use client';
import { Suspense, useState, useEffect } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import useSWR from 'swr';
import { endpoints, fetcher, postSettings, postSettingsTest, fetchProviderModels, fetchScoringWeights, saveScoringWeights } from '@/lib/api';
import { LLMSettings } from '@/lib/types';
import { color, font, fontSize, button as btnStyle, LLM_PROVIDERS, LLMProvider, SCORING_DIMENSIONS } from '@/lib/tokens';

function resolveProvider(backendProvider: string, baseUrl: string): LLMProvider {
  // Try to match a specific provider by base URL first
  if (backendProvider === 'openai_compat' && baseUrl) {
    const match = LLM_PROVIDERS.find(
      p => p.id !== 'custom' && p.baseUrl && baseUrl.startsWith(p.baseUrl.replace(/\/+$/, ''))
    );
    if (match) return match;
  }
  if (backendProvider === 'anthropic') {
    return LLM_PROVIDERS.find(p => p.id === 'anthropic')!;
  }
  // OpenAI: empty base URL
  if (backendProvider === 'openai_compat' && !baseUrl) {
    return LLM_PROVIDERS.find(p => p.id === 'openai')!;
  }
  return LLM_PROVIDERS.find(p => p.id === 'custom')!;
}

export default function SettingsPage() {
  return (
    <Suspense>
      <SettingsContent />
    </Suspense>
  );
}

function SettingsContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const isOnboarding = searchParams.get('onboarding') === '1';

  const { data: current, mutate } = useSWR<LLMSettings>(endpoints.settings, fetcher);

  const [selectedProvider, setSelectedProvider] = useState<LLMProvider>(LLM_PROVIDERS[0]);
  const [apiKey, setApiKey] = useState('');
  const [model, setModel] = useState('');
  const [baseUrl, setBaseUrl] = useState('');
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState('');
  const [testResult, setTestResult] = useState<{ ok: boolean; message: string } | null>(null);
  const [testing, setTesting] = useState(false);
  const [liveModels, setLiveModels] = useState<string[]>([]);
  const [fetchingModels, setFetchingModels] = useState(false);

  useEffect(() => {
    if (current) {
      const resolved = resolveProvider(current.llm_provider, current.llm_base_url);
      setSelectedProvider(resolved);
      setModel(current.llm_model || resolved.defaultModel);
      setBaseUrl(current.llm_base_url || resolved.baseUrl);
    }
  }, [current]);

  function switchProvider(p: LLMProvider) {
    setSelectedProvider(p);
    setModel(p.defaultModel);
    setBaseUrl(p.baseUrl);
    setLiveModels([]);
  }

  async function handleFetchModels() {
    setFetchingModels(true);
    try {
      const result = await fetchProviderModels();
      if (result.models.length > 0) {
        setLiveModels(result.models);
      }
    } catch {
      // Silently fail — hardcoded list remains
    } finally {
      setFetchingModels(false);
    }
  }

  async function handleSave() {
    setError('');
    setSaving(true);
    try {
      const body: Record<string, string> = {
        llm_provider: selectedProvider.backendProvider,
        llm_model: model,
        llm_base_url: baseUrl,
      };
      if (apiKey) body.llm_api_key = apiKey;
      await postSettings(body);
      setSaved(true);
      setApiKey('');
      mutate();
      if (isOnboarding) { router.push('/'); return; }
      setTimeout(() => setSaved(false), 3000);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Save failed');
    } finally {
      setSaving(false);
    }
  }

  async function handleTest() {
    setTestResult(null);
    setTesting(true);
    try {
      const result = await postSettingsTest();
      setTestResult(result);
    } catch (e) {
      setTestResult({ ok: false, message: e instanceof Error ? e.message : 'Request failed' });
    } finally {
      setTesting(false);
      setTimeout(() => setTestResult(null), 5000);
    }
  }

  const canTest = current?.llm_api_key_set === true || apiKey.length > 0;

  return (
    <div style={{ maxWidth: '640px' }}>
      {/* Data Sources link */}
      <Link href="/settings/sources" style={{ textDecoration: 'none', display: 'block', marginBottom: '32px' }}>
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '16px 20px', border: `1px solid ${color.borderStrong}`,
          background: color.surface,
        }}
          onMouseEnter={e => (e.currentTarget.style.background = color.surfaceHover)}
          onMouseLeave={e => (e.currentTarget.style.background = color.surface)}
        >
          <div>
            <div style={{ fontFamily: font.mono, fontSize: fontSize.lg, color: color.fg, marginBottom: '4px' }}>
              DATA SOURCES
            </div>
            <div style={{ fontFamily: font.body, fontSize: fontSize.md, color: color.fgDisabled }}>
              Configure credentials for all 12 data sources
            </div>
          </div>
          <span style={{ color: color.fgDisabled, fontSize: '18px' }}>›</span>
        </div>
      </Link>

      {isOnboarding && (
        <div style={{
          background: 'rgba(251,191,36,0.12)', border: '1px solid rgba(251,191,36,0.35)',
          padding: '14px 18px', marginBottom: '32px', fontFamily: font.mono,
          fontSize: fontSize.md, color: color.warning, letterSpacing: '0.3px',
        }}>
          No LLM API key configured. Enter your key below to start using Niche Radar.
        </div>
      )}

      <h1 style={{ fontFamily: font.body, fontSize: fontSize['5xl'], fontWeight: 400, color: color.fg, marginBottom: '8px' }}>
        SETTINGS
      </h1>
      <p style={{ fontFamily: font.body, fontSize: fontSize.lg, color: color.fgDisabled, marginBottom: '48px' }}>
        Configure which LLM provider analyzes your collected data. Settings take effect immediately.
      </p>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '36px' }}>
        {/* ── Provider selector ────────────────────────────────────── */}
        <Field label="LLM PROVIDER">
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(120px, 1fr))',
            gap: '1px',
            background: color.border,
            border: `1px solid ${color.border}`,
          }}>
            {LLM_PROVIDERS.map((p) => {
              const isActive = selectedProvider.id === p.id;
              return (
                <button
                  key={p.id}
                  onClick={() => switchProvider(p)}
                  style={{
                    background: isActive ? color.surfaceSelected : color.bg,
                    border: 'none',
                    color: isActive ? color.fg : color.fgMuted,
                    fontFamily: font.mono,
                    fontSize: fontSize.base,
                    letterSpacing: '0.5px',
                    padding: '12px 8px',
                    cursor: 'pointer',
                    textAlign: 'center',
                    position: 'relative',
                  }}
                >
                  {p.label}
                  {isActive && (
                    <div style={{
                      position: 'absolute', bottom: 0, left: 0, right: 0,
                      height: '2px', background: color.fg,
                    }} />
                  )}
                </button>
              );
            })}
          </div>
        </Field>

        {/* ── Base URL (conditional) ──────────────────────────────── */}
        {(selectedProvider.needsBaseUrl || selectedProvider.id === 'custom') && (
          <Field label="BASE URL" hint={selectedProvider.id === 'ollama' ? 'Ollama server address' : 'OpenAI-compatible API endpoint'} htmlFor="base-url">
            <Input
              id="base-url"
              value={baseUrl}
              onChange={setBaseUrl}
              placeholder="https://api.example.com/v1"
            />
          </Field>
        )}

        {/* ── Model selector ──────────────────────────────────────── */}
        <Field label="MODEL" htmlFor="model-input">
          {/* Preset models from hardcoded registry */}
          {selectedProvider.models.length > 0 && (
            <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginBottom: '10px' }}>
              {selectedProvider.models.map((m) => (
                <button
                  key={m}
                  onClick={() => setModel(m)}
                  style={{
                    background: model === m ? color.surfaceSelected : 'transparent',
                    border: `1px solid ${model === m ? color.borderStrong : color.border}`,
                    color: model === m ? color.fg : color.fgMuted,
                    fontFamily: font.mono,
                    fontSize: fontSize.sm,
                    letterSpacing: '0.3px',
                    padding: '5px 12px',
                    cursor: 'pointer',
                  }}
                >
                  {m}
                </button>
              ))}
            </div>
          )}

          {/* Live models from provider API */}
          {liveModels.length > 0 && (
            <div style={{ marginBottom: '10px' }}>
              <div style={{
                fontFamily: font.mono, fontSize: fontSize.xs, color: color.fgGhost,
                letterSpacing: '1px', textTransform: 'uppercase', marginBottom: '6px',
              }}>
                FROM API ({liveModels.length} models)
              </div>
              <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', maxHeight: '120px', overflowY: 'auto' }}>
                {liveModels.map((m) => (
                  <button
                    key={m}
                    onClick={() => setModel(m)}
                    style={{
                      background: model === m ? color.surfaceSelected : 'transparent',
                      border: `1px solid ${model === m ? color.borderStrong : color.border}`,
                      color: model === m ? color.fg : color.fgMuted,
                      fontFamily: font.mono,
                      fontSize: fontSize.sm,
                      letterSpacing: '0.3px',
                      padding: '5px 12px',
                      cursor: 'pointer',
                    }}
                  >
                    {m}
                  </button>
                ))}
              </div>
            </div>
          )}

          <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
            <div style={{ flex: 1 }}>
              <Input
                value={model}
                onChange={setModel}
                placeholder={selectedProvider.id === 'custom' ? 'Enter model name' : 'Or type a custom model name'}
                id="model-input"
              />
            </div>
            {selectedProvider.id !== 'custom' && (current?.llm_api_key_set || !selectedProvider.needsApiKey) && (
              <button
                onClick={handleFetchModels}
                disabled={fetchingModels}
                title="Fetch available models from the provider API"
                style={{
                  ...btnStyle.ghost,
                  whiteSpace: 'nowrap',
                  opacity: fetchingModels ? 0.5 : 1,
                  cursor: fetchingModels ? 'not-allowed' : 'pointer',
                }}
              >
                {fetchingModels ? '...' : '↻ REFRESH'}
              </button>
            )}
          </div>
        </Field>

        {/* ── API Key ─────────────────────────────────────────────── */}
        {selectedProvider.needsApiKey && (
          <Field
            label="API KEY"
            hint={current?.llm_api_key_set ? 'A key is already saved. Enter a new one to replace it.' : `Required for ${selectedProvider.label}.`}
            htmlFor="api-key"
          >
            <Input
              id="api-key"
              value={apiKey}
              onChange={setApiKey}
              placeholder={current?.llm_api_key_set ? '••••••••••••••••' : 'sk-...'}
              type="password"
            />
          </Field>
        )}

        {/* ── Actions ─────────────────────────────────────────────── */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
            <button onClick={handleSave} disabled={saving} style={{ ...btnStyle.primary, opacity: saving ? 0.5 : 1, cursor: saving ? 'not-allowed' : 'pointer' }}>
              {saving ? 'SAVING...' : 'SAVE SETTINGS'}
            </button>
            <button
              onClick={handleTest}
              disabled={testing || !canTest}
              style={{ ...btnStyle.secondary, color: canTest ? color.fgSecondary : color.fgGhost, cursor: testing || !canTest ? 'not-allowed' : 'pointer' }}
            >
              {testing ? 'TESTING...' : 'TEST CONNECTION'}
            </button>
            {saved && (
              <span role="status" style={{ fontFamily: font.mono, fontSize: fontSize.base, color: color.fgMuted, letterSpacing: '0.5px' }}>
                SAVED
              </span>
            )}
            {error && (
              <span role="alert" style={{ fontFamily: font.mono, fontSize: fontSize.base, color: color.error }}>
                {error}
              </span>
            )}
          </div>
          {testResult !== null && (
            <span style={{
              fontFamily: font.mono, fontSize: fontSize.base, letterSpacing: '0.3px',
              color: testResult.ok ? color.success : color.error,
            }}>
              {testResult.ok ? `✓ ${testResult.message}` : `✗ ${testResult.message}`}
            </span>
          )}
          {canTest && (
            <span style={{ fontFamily: font.body, fontSize: fontSize.sm, color: color.fgGhost }}>
              Connection test uses currently saved settings, not unsaved form values.
            </span>
          )}
        </div>
      </div>

      {/* ── SCORING WEIGHTS SECTION ──────────────────────────────────── */}
      <ScoringWeightsSection />

      {/* ── PROMPT PACKS SECTION ──────────────────────────────────────── */}
      <PromptPacksSection />
    </div>
  );
}

function ScoringWeightsSection() {
  const [weights, setWeights] = useState<Record<string, number>>({});
  const [loaded, setLoaded] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    fetchScoringWeights().then(w => { setWeights(w); setLoaded(true); }).catch(() => {
      const defaults: Record<string, number> = {};
      SCORING_DIMENSIONS.forEach(d => { defaults[d.key] = d.defaultWeight; });
      setWeights(defaults);
      setLoaded(true);
    });
  }, []);

  function updateWeight(key: string, value: number) {
    setWeights(prev => ({ ...prev, [key]: Math.round(value * 10) / 10 }));
    setSaved(false);
  }

  function resetDefaults() {
    const defaults: Record<string, number> = {};
    SCORING_DIMENSIONS.forEach(d => { defaults[d.key] = d.defaultWeight; });
    setWeights(defaults);
    setSaved(false);
  }

  async function handleSave() {
    setSaving(true);
    try {
      await saveScoringWeights(weights);
      setSaved(true);
    } catch {
      // silent
    } finally {
      setSaving(false);
    }
  }

  if (!loaded) return null;

  return (
    <div style={{ marginTop: '48px', borderTop: `1px solid ${color.border}`, paddingTop: '40px' }}>
      <div style={{
        fontFamily: font.mono, fontSize: fontSize.base, color: color.fgDisabled,
        textTransform: 'uppercase', letterSpacing: '1.5px', marginBottom: '8px',
      }}>
        SCORING WEIGHTS
      </div>
      <p style={{
        fontFamily: font.body, fontSize: fontSize.md, color: color.fgGhost,
        marginBottom: '24px', lineHeight: 1.6,
      }}>
        Adjust how each dimension contributes to the final opportunity score (0–100).
        Higher weight = more influence on the total.
      </p>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
        {SCORING_DIMENSIONS.map(dim => (
          <div key={dim.key} style={{
            display: 'grid', gridTemplateColumns: '150px 1fr 48px',
            gap: '12px', alignItems: 'center',
          }}>
            <div title={dim.description} style={{
              fontFamily: font.mono, fontSize: '10px', color: color.fgMuted,
              textTransform: 'uppercase', letterSpacing: '0.5px', whiteSpace: 'nowrap',
              cursor: 'help',
            }}>
              {dim.label}
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <input
                type="range"
                min="0.5"
                max="3.0"
                step="0.1"
                value={weights[dim.key] ?? dim.defaultWeight}
                onChange={e => updateWeight(dim.key, parseFloat(e.target.value))}
                style={{
                  width: '100%', height: '4px', appearance: 'none',
                  background: color.surface, outline: 'none',
                  accentColor: color.fg,
                }}
              />
            </div>
            <div style={{
              fontFamily: font.mono, fontSize: fontSize.md, color: color.fgSecondary,
              textAlign: 'right',
            }}>
              {(weights[dim.key] ?? dim.defaultWeight).toFixed(1)}
            </div>
          </div>
        ))}
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginTop: '20px', flexWrap: 'wrap' }}>
        <button onClick={handleSave} disabled={saving} style={{ ...btnStyle.primary, opacity: saving ? 0.5 : 1, cursor: saving ? 'not-allowed' : 'pointer' }}>
          {saving ? 'SAVING...' : 'SAVE WEIGHTS'}
        </button>
        <button onClick={resetDefaults} style={{ ...btnStyle.secondary, cursor: 'pointer' }}>
          RESET DEFAULTS
        </button>
        {saved && (
          <span style={{ fontFamily: font.mono, fontSize: fontSize.base, color: color.fgMuted, letterSpacing: '0.5px' }}>
            SAVED
          </span>
        )}
      </div>
    </div>
  );
}

interface PromptPackInfo {
  name: string;
  description: string;
  file: string;
  agents: string[];
}

function PromptPacksSection() {
  const { data: packs } = useSWR<PromptPackInfo[]>(endpoints.promptPacks, fetcher);

  if (!packs || packs.length === 0) return null;

  return (
    <div style={{
      marginTop: '48px',
      border: `1px solid ${color.border}`,
      padding: '32px',
      background: color.surface,
    }}>
      <h2 style={{
        fontFamily: font.mono, fontSize: fontSize.sm,
        letterSpacing: '1px', color: color.fgDisabled,
        textTransform: 'uppercase', margin: '0 0 8px 0',
      }}>
        PROMPT PACKS
      </h2>
      <p style={{ fontFamily: font.body, fontSize: fontSize.md, color: color.fgGhost, margin: '0 0 24px 0' }}>
        Prompt packs customize how agents evaluate niches for different audiences. Select a pack when running the pipeline to change scoring weights and verdict rules.
      </p>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
        {packs.map((pack) => (
          <div
            key={pack.name}
            style={{
              display: 'flex', justifyContent: 'space-between', alignItems: 'center',
              padding: '16px 20px', background: color.surfaceHover,
              border: `1px solid ${color.border}`,
            }}
          >
            <div style={{ flex: 1 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '4px' }}>
                <span style={{ fontFamily: font.mono, fontSize: fontSize.base, color: color.fg, textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                  {pack.name.replace(/_/g, ' ')}
                </span>
                <span style={{ fontFamily: font.mono, fontSize: fontSize.xs, color: color.fgGhost }}>
                  {pack.file}
                </span>
              </div>
              <div style={{ fontFamily: font.body, fontSize: fontSize.md, color: color.fgMuted, marginBottom: '6px' }}>
                {pack.description}
              </div>
              <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                {pack.agents.map(a => (
                  <span key={a} style={{
                    fontFamily: font.mono, fontSize: fontSize.xs, color: color.fgGhost,
                    background: 'rgba(255,255,255,0.05)', padding: '2px 8px',
                    letterSpacing: '0.5px', textTransform: 'uppercase',
                  }}>
                    {a}
                  </span>
                ))}
              </div>
            </div>
          </div>
        ))}
      </div>
      <p style={{ fontFamily: font.body, fontSize: fontSize.xs, color: color.fgGhost, marginTop: '16px' }}>
        Add custom packs to <code style={{ fontFamily: font.mono }}>prompt_packs/</code> as YAML files.
      </p>
    </div>
  );
}

function Field({ label, hint, children, htmlFor }: { label: string; hint?: string; children: React.ReactNode; htmlFor?: string }) {
  return (
    <div>
      <label
        htmlFor={htmlFor}
        style={{
          fontFamily: font.mono, fontSize: fontSize.sm, color: color.fgDisabled,
          textTransform: 'uppercase', letterSpacing: '1px',
          marginBottom: hint ? '6px' : '10px', display: 'block',
        }}
      >
        {label}
      </label>
      {hint && (
        <div style={{ fontFamily: font.body, fontSize: fontSize.md, color: color.fgGhost, marginBottom: '10px' }}>
          {hint}
        </div>
      )}
      {children}
    </div>
  );
}

function Input({ value, onChange, placeholder, type = 'text', id }: { value: string; onChange: (v: string) => void; placeholder?: string; type?: string; id?: string }) {
  return (
    <input
      id={id}
      type={type}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      style={{
        width: '100%', background: color.surfaceHover,
        border: `1px solid ${color.border}`, color: color.fg,
        fontFamily: font.mono, fontSize: fontSize.md,
        letterSpacing: '0.5px', padding: '10px 14px',
        outline: 'none', boxSizing: 'border-box' as const,
      }}
    />
  );
}
