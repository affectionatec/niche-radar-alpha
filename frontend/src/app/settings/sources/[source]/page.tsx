'use client';
import { useState, useEffect } from 'react';
import Link from 'next/link';
import useSWR from 'swr';
import { endpoints, fetcher, postSourceCredentials, postSourceTest } from '@/lib/api';
import { SourceStatus } from '@/lib/types';
import { sourceLabel } from '@/lib/tokens';

function Input({ value, onChange, placeholder, type = 'text', disabled = false, id }:
  { value: string; onChange: (v: string) => void; placeholder?: string; type?: string; disabled?: boolean; id?: string }
) {
  return (
    <input id={id} type={type} value={value} onChange={e => onChange(e.target.value)}
      placeholder={placeholder} disabled={disabled}
      style={{
        width: '100%', background: disabled ? 'rgba(255,255,255,0.02)' : 'rgba(255,255,255,0.06)',
        border: '1px solid rgba(255,255,255,0.15)', color: disabled ? 'rgba(255,255,255,0.3)' : '#ffffff',
        fontFamily: 'var(--font-geist-mono)', fontSize: '12px',
        letterSpacing: '0.5px', padding: '10px 14px', outline: 'none', boxSizing: 'border-box',
      }}
    />
  );
}

export default function SourceDetailPage({ params }: { params: Promise<{ source: string }> | { source: string } }) {
  // Next.js 14+ may pass params as a Promise in some configurations
  const resolvedParams = params as { source: string };
  const slug = resolvedParams.source;
  const { data, mutate, isLoading, error } = useSWR<SourceStatus>(
    endpoints.source(slug), fetcher
  );

  const [values, setValues] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [saveError, setSaveError] = useState('');
  const [testResult, setTestResult] = useState<{ ok: boolean; message: string } | null>(null);
  const [testing, setTesting] = useState(false);

  useEffect(() => {
    if (data && data.schema) {
      // Populate non-secret fields from what's stored; secrets stay blank (only write when changed)
      const initial: Record<string, string> = {};
      for (const field of (data.schema || [])) {
        if (!field.secret) {
          initial[field.key] = data.credentials_set[field.key] || '';
        } else {
          initial[field.key] = ''; // blank — user must re-enter to change
        }
      }
      setValues(initial);
    }
  }, [data]);

  async function handleSave() {
    setSaveError('');
    setSaving(true);
    try {
      const toSave: Record<string, string | null> = {};
      for (const [k, v] of Object.entries(values)) {
        const field = (data?.schema || []).find(f => f.key === k);
        if (field?.secret && !v) continue; // blank secret = don't overwrite
        toSave[k] = v || null;
      }
      await postSourceCredentials(slug, toSave);
      mutate();
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch (e) {
      setSaveError(e instanceof Error ? e.message : 'Save failed');
    } finally {
      setSaving(false);
    }
  }

  async function handleTest() {
    setTestResult(null);
    setTesting(true);
    try {
      const r = await postSourceTest(slug);
      setTestResult(r);
    } catch (e) {
      setTestResult({ ok: false, message: e instanceof Error ? e.message : 'Request failed' });
    } finally {
      setTesting(false);
      setTimeout(() => setTestResult(null), 6000);
    }
  }

  return (
    <div style={{ maxWidth: '600px' }}>
      <div style={{ marginBottom: '32px' }}>
        <Link href="/settings/sources" style={{
          fontFamily: 'var(--font-geist-mono)', fontSize: '12px',
          color: 'rgba(255,255,255,0.4)', textDecoration: 'none',
          textTransform: 'uppercase', letterSpacing: '0.8px',
        }}>
          ← DATA SOURCES
        </Link>
      </div>

      <h1 style={{ fontFamily: 'var(--font-inter)', fontSize: '30px', fontWeight: 400, color: '#ffffff', marginBottom: '8px' }}>
        {sourceLabel[slug] || slug.toUpperCase()}
      </h1>
      <p style={{ fontFamily: 'var(--font-inter)', fontSize: '13px', color: 'rgba(255,255,255,0.35)', marginBottom: '48px' }}>
        Configure credentials for this data source. Secrets are stored in the database and never exposed in plaintext.
      </p>

      {isLoading && <div style={{ color: 'rgba(255,255,255,0.35)', fontFamily: 'var(--font-geist-mono)', fontSize: '12px' }}>LOADING...</div>}
      {error && <div style={{ color: 'rgba(255,80,80,0.85)', fontFamily: 'var(--font-geist-mono)', fontSize: '12px' }}>Failed to load source configuration</div>}

      {data && (
        <>
          {(data.schema || []).length === 0 && (
            <div style={{
              padding: '16px', border: '1px solid rgba(255,255,255,0.1)',
              fontFamily: 'var(--font-geist-mono)', fontSize: '12px',
              color: 'rgba(255,255,255,0.4)', marginBottom: '32px',
            }}>
              No credentials needed — this source works without authentication.
            </div>
          )}

          {(data.schema || []).length > 0 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '28px' }}>
              {(data.schema || []).map(field => (
                <div key={field.key}>
                  <label
                    htmlFor={`field-${field.key}`}
                    style={{
                      fontFamily: 'var(--font-inter)', fontSize: '11px', color: 'rgba(255,255,255,0.4)',
                      textTransform: 'uppercase', letterSpacing: '1px', marginBottom: '4px', display: 'block',
                    }}
                  >
                    {field.label}
                    {!field.optional && <span style={{ color: 'rgba(255,80,80,0.85)', marginLeft: '4px' }}>*</span>}
                  </label>
                  {field.help && (
                    <div style={{ fontFamily: 'var(--font-inter)', fontSize: '12px', color: 'rgba(255,255,255,0.25)', marginBottom: '8px' }}>
                      {field.help}
                    </div>
                  )}
                  {field.secret && data.credentials_set[field.key] && !values[field.key] && (
                    <div style={{ fontFamily: 'var(--font-geist-mono)', fontSize: '11px', color: 'rgba(74,222,128,0.7)', marginBottom: '6px' }}>
                      ✓ Key is saved. Enter new value to replace.
                    </div>
                  )}
                  <Input
                    id={`field-${field.key}`}
                    value={values[field.key] || ''}
                    onChange={v => setValues(prev => ({ ...prev, [field.key]: v }))}
                    placeholder={field.secret && data.credentials_set[field.key] ? '••••••••••••' : field.label.toLowerCase()}
                    type={field.secret ? 'password' : 'text'}
                  />
                </div>
              ))}

              <div style={{ display: 'flex', alignItems: 'center', gap: '16px', flexWrap: 'wrap', paddingTop: '8px' }}>
                <button onClick={handleSave} disabled={saving} style={{
                  background: '#ffffff', border: 'none', color: '#1f2228',
                  fontFamily: 'var(--font-geist-mono)', fontSize: '11px', fontWeight: 600,
                  letterSpacing: '1px', textTransform: 'uppercase', padding: '0 24px',
                  height: '40px', cursor: saving ? 'not-allowed' : 'pointer', opacity: saving ? 0.5 : 1,
                }}>
                  {saving ? 'SAVING...' : 'SAVE'}
                </button>
                <button onClick={handleTest} disabled={testing} style={{
                  background: 'transparent', border: '1px solid rgba(255,255,255,0.25)',
                  color: 'rgba(255,255,255,0.7)', fontFamily: 'var(--font-geist-mono)',
                  fontSize: '11px', letterSpacing: '1px', textTransform: 'uppercase',
                  padding: '0 20px', height: '40px', cursor: testing ? 'not-allowed' : 'pointer',
                }}>
                  {testing ? 'TESTING...' : 'TEST CONNECTION'}
                </button>
                {saved && (
                  <span style={{ fontFamily: 'var(--font-geist-mono)', fontSize: '11px', color: 'rgba(255,255,255,0.5)', letterSpacing: '0.5px' }}>
                    SAVED
                  </span>
                )}
                {saveError && (
                  <span style={{ fontFamily: 'var(--font-geist-mono)', fontSize: '11px', color: 'rgba(255,80,80,0.85)' }}>
                    {saveError}
                  </span>
                )}
              </div>

              {testResult !== null && (
                <div role="alert" style={{
                  padding: '12px 16px', border: `1px solid ${testResult.ok ? 'rgba(74,222,128,0.3)' : 'rgba(255,80,80,0.3)'}`,
                  fontFamily: 'var(--font-geist-mono)', fontSize: '12px',
                  color: testResult.ok ? 'rgba(74,222,128,0.9)' : 'rgba(255,80,80,0.85)',
                }}>
                  {testResult.ok ? `✓ ${testResult.message}` : `✗ ${testResult.message}`}
                </div>
              )}
            </div>
          )}

          {/* Status summary */}
          <div style={{ marginTop: '48px', paddingTop: '32px', borderTop: '1px solid rgba(255,255,255,0.08)' }}>
            <div style={{ fontFamily: 'var(--font-inter)', fontSize: '11px', color: 'rgba(255,255,255,0.3)', textTransform: 'uppercase', letterSpacing: '1px', marginBottom: '12px' }}>
              STATUS
            </div>
            <div style={{ display: 'flex', gap: '32px', flexWrap: 'wrap' }}>
              <div>
                <div style={{ fontFamily: 'var(--font-geist-mono)', fontSize: '12px', color: data.configured ? 'rgba(74,222,128,0.85)' : 'rgba(251,191,36,0.85)' }}>
                  {data.configured ? '✓ CONFIGURED' : '⚠ NEEDS SETUP'}
                </div>
                {(data.required_missing || []).length > 0 && (
                  <div style={{ fontFamily: 'var(--font-inter)', fontSize: '11px', color: 'rgba(255,255,255,0.3)', marginTop: '4px' }}>
                    Missing: {(data.required_missing || []).join(', ')}
                  </div>
                )}
              </div>
              {data.last_success && (
                <div>
                  <div style={{ fontFamily: 'var(--font-geist-mono)', fontSize: '11px', color: 'rgba(255,255,255,0.3)' }}>LAST SUCCESSFUL RUN</div>
                  <div style={{ fontFamily: 'var(--font-geist-mono)', fontSize: '12px', color: 'rgba(255,255,255,0.6)', marginTop: '2px' }}>
                    {new Date(data.last_success).toLocaleString()}
                  </div>
                </div>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
