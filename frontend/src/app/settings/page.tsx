'use client';
import { Suspense, useState, useEffect } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import useSWR from 'swr';
import { endpoints, fetcher, postSettings, postSettingsTest } from '@/lib/api';
import { LLMSettings } from '@/lib/types';
import { color, font, fontSize, button as btnStyle, LLM_PROVIDERS, LLMProvider } from '@/lib/tokens';

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
          <Input
            value={model}
            onChange={setModel}
            placeholder={selectedProvider.id === 'custom' ? 'Enter model name' : 'Or type a custom model name'}
            id="model-input"
          />
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
