'use client';

import { FormEvent, useState } from 'react';
import { login } from '@/lib/client';

function safeNext(value: string | null): string {
  if (!value) return '/';
  try {
    const base = new URL('https://radar.invalid/');
    const target = new URL(value, base);
    if (target.origin !== base.origin || !value.startsWith('/')) return '/';
    return `${target.pathname}${target.search}${target.hash}`;
  } catch {
    return '/';
  }
}

export default function LoginPage() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError('');
    setSubmitting(true);
    try {
      await login(username, password);
      const next = new URLSearchParams(window.location.search).get('next');
      window.location.assign(safeNext(next));
    } catch (reason) {
      const message =
        reason instanceof Error && reason.message.includes('429')
          ? 'TOO MANY ATTEMPTS. WAIT, THEN TRY AGAIN.'
          : 'CREDENTIAL NOT RECOGNIZED.';
      setError(message);
      setSubmitting(false);
    }
  }

  return (
    <section className="radar-login" aria-labelledby="radar-login-title">
      <header className="radar-login-header">
        <span>NICHE RADAR</span>
        <span>PRIVATE OPERATOR NODE</span>
      </header>

      <div className="radar-login-body">
        <div className="radar-login-manifest">
          <span className="radar-login-index">NR / 01</span>
          <h1 id="radar-login-title">
            <span>SIGNAL</span>
            <span>EVIDENCE</span>
            <span>VERDICT</span>
          </h1>
          <p>
            Enter the research instrument. Source credentials, pipeline actions,
            costs, and reports remain behind this checkpoint.
          </p>
        </div>

        <form className="radar-login-form" onSubmit={submit}>
          <div className="radar-login-form-title">
            <span>OPERATOR ACCESS</span>
            <span aria-hidden="true">↘</span>
          </div>

          <label htmlFor="radar-username">IDENTIFIER</label>
          <input
            id="radar-username"
            name="username"
            type="text"
            autoComplete="username"
            autoCapitalize="none"
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            disabled={submitting}
            required
            autoFocus
          />

          <label htmlFor="radar-password">PASSPHRASE</label>
          <input
            id="radar-password"
            name="password"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            disabled={submitting}
            required
          />

          <div className="radar-login-error" aria-live="polite">
            {error || 'SESSION COOKIE · SECURE · HTTPONLY'}
          </div>

          <button type="submit" disabled={submitting}>
            {submitting ? 'VERIFYING…' : 'ENTER RADAR'}
          </button>
        </form>
      </div>

      <footer className="radar-login-footer">
        <span>COLLECT → ANALYZE → SHORTLIST</span>
        <span>ALPHA / SINGLE OPERATOR</span>
      </footer>
    </section>
  );
}
