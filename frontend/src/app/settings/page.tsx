'use client';
import { useState, useEffect } from 'react';
import useSWR from 'swr';
import { endpoints, fetcher, postSettings } from '@/lib/api';
import { LLMSettings } from '@/lib/types';

const PROVIDERS = [
  { value: 'openai_compat', label: 'OpenAI-compatible (DeepSeek, Groq, OpenAI, Ollama)' },
  { value: 'anthropic', label: 'Anthropic (Claude)' },
];

const PRESET_MODELS: Record<string, string[]> = {
  openai_compat: ['deepseek-chat', 'deepseek-reasoner', 'gpt-4o', 'gpt-4o-mini', 'llama-3.3-70b-versatile'],
  anthropic: ['claude-haiku-4-5-20251001', 'claude-sonnet-4-6', 'claude-opus-4-7'],
};

const PRESET_BASE_URLS: { label: string; value: string }[] = [
  { label: 'DeepSeek', value: 'https://api.deepseek.com' },
  { label: 'Groq', value: 'https://api.groq.com/openai/v1' },
  { label: 'OpenAI', value: '' },
  { label: 'Ollama (local)', value: 'http://localhost:11434/v1' },
];

export default function SettingsPage() {
  const { data: current, mutate } = useSWR<LLMSettings>(endpoints.settings, fetcher);

  const [provider, setProvider] = useState('openai_compat');
  const [apiKey, setApiKey] = useState('');
  const [model, setModel] = useState('deepseek-chat');
  const [baseUrl, setBaseUrl] = useState('https://api.deepseek.com');
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (current) {
      setProvider(current.llm_provider || 'openai_compat');
      setModel(current.llm_model || 'deepseek-chat');
      setBaseUrl(current.llm_base_url || '');
    }
  }, [current]);

  async function handleSave() {
    setError('');
    setSaving(true);
    try {
      const body: Record<string, string> = { llm_provider: provider, llm_model: model, llm_base_url: baseUrl };
      if (apiKey) body.llm_api_key = apiKey;
      await postSettings(body);
      setSaved(true);
      setApiKey('');
      mutate();
      setTimeout(() => setSaved(false), 3000);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Save failed');
    } finally {
      setSaving(false);
    }
  }

  return (
    <div style={{ maxWidth: '600px' }}>
      <h1
        style={{
          fontFamily: 'var(--font-inter)',
          fontSize: '30px',
          fontWeight: 400,
          color: '#ffffff',
          marginBottom: '8px',
        }}
      >
        SETTINGS
      </h1>
      <p
        style={{
          fontFamily: 'var(--font-inter)',
          fontSize: '13px',
          color: 'rgba(255,255,255,0.35)',
          marginBottom: '48px',
        }}
      >
        Configure which LLM provider analyzes your collected data. Settings are saved to the database
        and take effect immediately — no restart required.
      </p>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '32px' }}>
        {/* Provider */}
        <Field label="LLM PROVIDER">
          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
            {PROVIDERS.map((p) => (
              <button
                key={p.value}
                onClick={() => {
                  setProvider(p.value);
                  setModel(PRESET_MODELS[p.value][0]);
                  if (p.value === 'anthropic') setBaseUrl('');
                }}
                style={{
                  background: provider === p.value ? '#ffffff' : 'transparent',
                  border: '1px solid rgba(255,255,255,0.25)',
                  color: provider === p.value ? '#1f2228' : 'rgba(255,255,255,0.7)',
                  fontFamily: 'var(--font-geist-mono)',
                  fontSize: '11px',
                  letterSpacing: '0.5px',
                  padding: '8px 16px',
                  cursor: 'pointer',
                }}
              >
                {p.label}
              </button>
            ))}
          </div>
        </Field>

        {/* Base URL (OpenAI-compatible only) */}
        {provider === 'openai_compat' && (
          <Field label="BASE URL" hint="Leave empty for OpenAI. Set for DeepSeek, Groq, Ollama, etc.">
            <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginBottom: '10px' }}>
              {PRESET_BASE_URLS.map((p) => (
                <button
                  key={p.label}
                  onClick={() => setBaseUrl(p.value)}
                  style={{
                    background: baseUrl === p.value ? 'rgba(255,255,255,0.12)' : 'transparent',
                    border: '1px solid rgba(255,255,255,0.15)',
                    color: 'rgba(255,255,255,0.6)',
                    fontFamily: 'var(--font-geist-mono)',
                    fontSize: '10px',
                    letterSpacing: '0.5px',
                    padding: '5px 12px',
                    cursor: 'pointer',
                  }}
                >
                  {p.label}
                </button>
              ))}
            </div>
            <Input
              value={baseUrl}
              onChange={setBaseUrl}
              placeholder="https://api.deepseek.com"
            />
          </Field>
        )}

        {/* Model */}
        <Field label="MODEL">
          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginBottom: '10px' }}>
            {PRESET_MODELS[provider].map((m) => (
              <button
                key={m}
                onClick={() => setModel(m)}
                style={{
                  background: model === m ? 'rgba(255,255,255,0.12)' : 'transparent',
                  border: '1px solid rgba(255,255,255,0.15)',
                  color: 'rgba(255,255,255,0.6)',
                  fontFamily: 'var(--font-geist-mono)',
                  fontSize: '10px',
                  letterSpacing: '0.5px',
                  padding: '5px 12px',
                  cursor: 'pointer',
                }}
              >
                {m}
              </button>
            ))}
          </div>
          <Input value={model} onChange={setModel} placeholder="model name" />
        </Field>

        {/* API Key */}
        <Field
          label="API KEY"
          hint={current?.llm_api_key_set ? 'A key is already saved. Enter a new one to replace it.' : 'Required to run analysis.'}
        >
          <Input
            value={apiKey}
            onChange={setApiKey}
            placeholder={current?.llm_api_key_set ? '••••••••••••••••' : 'sk-...'}
            type="password"
          />
        </Field>

        {/* Save */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <button
            onClick={handleSave}
            disabled={saving}
            style={{
              background: '#ffffff',
              border: 'none',
              color: '#1f2228',
              fontFamily: 'var(--font-geist-mono)',
              fontSize: '11px',
              fontWeight: 600,
              letterSpacing: '1px',
              textTransform: 'uppercase',
              padding: '0 24px',
              height: '40px',
              cursor: saving ? 'not-allowed' : 'pointer',
              opacity: saving ? 0.5 : 1,
            }}
          >
            {saving ? 'SAVING...' : 'SAVE SETTINGS'}
          </button>
          {saved && (
            <span
              style={{
                fontFamily: 'var(--font-geist-mono)',
                fontSize: '11px',
                color: 'rgba(255,255,255,0.5)',
                letterSpacing: '0.5px',
              }}
            >
              SAVED
            </span>
          )}
          {error && (
            <span
              style={{
                fontFamily: 'var(--font-geist-mono)',
                fontSize: '11px',
                color: 'rgba(255,80,80,0.85)',
              }}
            >
              {error}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}

function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <div
        style={{
          fontFamily: 'var(--font-inter)',
          fontSize: '11px',
          color: 'rgba(255,255,255,0.4)',
          textTransform: 'uppercase',
          letterSpacing: '1px',
          marginBottom: hint ? '6px' : '10px',
        }}
      >
        {label}
      </div>
      {hint && (
        <div
          style={{
            fontFamily: 'var(--font-inter)',
            fontSize: '12px',
            color: 'rgba(255,255,255,0.25)',
            marginBottom: '10px',
          }}
        >
          {hint}
        </div>
      )}
      {children}
    </div>
  );
}

function Input({
  value,
  onChange,
  placeholder,
  type = 'text',
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  type?: string;
}) {
  return (
    <input
      type={type}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      style={{
        width: '100%',
        background: 'rgba(255,255,255,0.06)',
        border: '1px solid rgba(255,255,255,0.15)',
        color: '#ffffff',
        fontFamily: 'var(--font-geist-mono)',
        fontSize: '12px',
        letterSpacing: '0.5px',
        padding: '10px 14px',
        outline: 'none',
        boxSizing: 'border-box',
      }}
    />
  );
}
