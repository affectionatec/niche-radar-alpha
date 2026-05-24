'use client';
import { useState, useEffect } from 'react';
import Link from 'next/link';
import useSWR from 'swr';
import { endpoints, fetcher, postSourceCredentials, postSourceTest } from '@/lib/api';
import { SourceStatus } from '@/lib/types';
import { color, font, sourceLabel } from '@/lib/tokens';

function Input({ value, onChange, placeholder, type = 'text', disabled = false, id }:
  { value: string; onChange: (v: string) => void; placeholder?: string; type?: string; disabled?: boolean; id?: string }
) {
  return (
    <input id={id} type={type} value={value} onChange={e => onChange(e.target.value)}
      placeholder={placeholder} disabled={disabled}
      style={{
        width: '100%', background: disabled ? color.surface : color.surfaceHover,
        border: `1px solid ${color.borderStrong}`, color: disabled ? color.fgGhost : color.fg,
        fontFamily: font.mono, fontSize: '12px',
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
          fontFamily: font.mono, fontSize: '12px',
          color: color.fgMuted, textDecoration: 'none',
          textTransform: 'uppercase' as const, letterSpacing: '0.8px',
        }}>
          ← DATA SOURCES
        </Link>
      </div>

      <h1 style={{ fontFamily: font.body, fontSize: '30px', fontWeight: 400, color: color.fg, marginBottom: '8px' }}>
        {sourceLabel[slug] || slug.toUpperCase()}
      </h1>
      <p style={{ fontFamily: font.body, fontSize: '13px', color: color.fgDisabled, marginBottom: '48px' }}>
        Configure credentials for this data source. Secrets are stored in the database and never exposed in plaintext.
      </p>

      {isLoading && <div style={{ color: color.fgDisabled, fontFamily: font.mono, fontSize: '12px' }}>LOADING...</div>}
      {error && <div style={{ color: color.error, fontFamily: font.mono, fontSize: '12px' }}>Failed to load source configuration</div>}

      {data && (
        <>
          {(data.schema || []).length === 0 && (
            <div style={{
              padding: '16px', border: `1px solid ${color.border}`,
              fontFamily: font.mono, fontSize: '12px',
              color: color.fgMuted, marginBottom: '32px',
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
                      fontFamily: font.body, fontSize: '11px', color: color.fgMuted,
                      textTransform: 'uppercase' as const, letterSpacing: '1px', marginBottom: '4px', display: 'block',
                    }}
                  >
                    {field.label}
                    {!field.optional && <span style={{ color: color.error, marginLeft: '4px' }}>*</span>}
                  </label>
                  {field.help && (
                    <div style={{ fontFamily: font.body, fontSize: '12px', color: color.fgGhost, marginBottom: '8px' }}>
                      {field.help}
                    </div>
                  )}
                  {field.secret && data.credentials_set[field.key] && !values[field.key] && (
                    <div style={{ fontFamily: font.mono, fontSize: '11px', color: color.successMuted, marginBottom: '6px' }}>
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
                  background: color.fg, border: 'none', color: color.bg,
                  fontFamily: font.mono, fontSize: '11px', fontWeight: 600,
                  letterSpacing: '1px', textTransform: 'uppercase' as const, padding: '0 24px',
                  height: '40px', cursor: saving ? 'not-allowed' : 'pointer', opacity: saving ? 0.5 : 1,
                }}>
                  {saving ? 'SAVING...' : 'SAVE'}
                </button>
                <button onClick={handleTest} disabled={testing} style={{
                  background: 'transparent', border: `1px solid ${color.borderStrong}`,
                  color: color.fgSecondary, fontFamily: font.mono,
                  fontSize: '11px', letterSpacing: '1px', textTransform: 'uppercase' as const,
                  padding: '0 20px', height: '40px', cursor: testing ? 'not-allowed' : 'pointer',
                }}>
                  {testing ? 'TESTING...' : 'TEST CONNECTION'}
                </button>
                {saved && (
                  <span style={{ fontFamily: font.mono, fontSize: '11px', color: color.fgMuted, letterSpacing: '0.5px' }}>
                    SAVED
                  </span>
                )}
                {saveError && (
                  <span style={{ fontFamily: font.mono, fontSize: '11px', color: color.error }}>
                    {saveError}
                  </span>
                )}
              </div>

              {testResult !== null && (
                <div role="alert" style={{
                  padding: '12px 16px', border: `1px solid ${testResult.ok ? color.successMuted : color.errorMuted}`,
                  fontFamily: font.mono, fontSize: '12px',
                  color: testResult.ok ? color.success : color.error,
                }}>
                  {testResult.ok ? `✓ ${testResult.message}` : `✗ ${testResult.message}`}
                </div>
              )}
            </div>
          )}

          {/* Status summary */}
          <div style={{ marginTop: '48px', paddingTop: '32px', borderTop: `1px solid ${color.surfaceActive}` }}>
            <div style={{ fontFamily: font.body, fontSize: '11px', color: color.fgGhost, textTransform: 'uppercase' as const, letterSpacing: '1px', marginBottom: '12px' }}>
              STATUS
            </div>
            <div style={{ display: 'flex', gap: '32px', flexWrap: 'wrap' }}>
              <div>
                <div style={{ fontFamily: font.mono, fontSize: '12px', color: data.configured ? color.success : color.warning }}>
                  {data.configured ? '✓ CONFIGURED' : '⚠ NEEDS SETUP'}
                </div>
                {(data.required_missing || []).length > 0 && (
                  <div style={{ fontFamily: font.body, fontSize: '11px', color: color.fgGhost, marginTop: '4px' }}>
                    Missing: {(data.required_missing || []).join(', ')}
                  </div>
                )}
              </div>
              {data.last_success && (
                <div>
                  <div style={{ fontFamily: font.mono, fontSize: '11px', color: color.fgGhost }}>LAST SUCCESSFUL RUN</div>
                  <div style={{ fontFamily: font.mono, fontSize: '12px', color: color.fgSecondary, marginTop: '2px' }}>
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
