# Application authentication specification

Status: Approved for the single-operator production deployment.

## Contract

- Production reads `username:password` from
  `/run/secrets/apps_login_credentials` and at least 32 bytes from
  `/run/secrets/apps_session_secret`. There is no source-code, `.env`, or default
  credential fallback.
- Missing or malformed production secrets fail closed.
- `GET /api/status` and `POST /api/auth/login` are public. Every other `/api`
  operation, including current-session and logout, requires a valid Cookie.
- Credential checks run in constant time and use a bounded failed-attempt limiter.
- Per-client identity comes only through the trusted proxy chain: Traefik trusts
  forwarded headers solely from Cloudflare's official networks, and Radar
  resolves `X-Forwarded-For` from right to left after removing Cloudflare/private
  proxy hops. A spoofed leftmost value cannot select the limiter key.
- Sessions are HMAC-SHA256 signed, contain subject, issue/expiry time and nonce,
  and expire after eight hours.
- The Cookie is named `__Host-niche_radar_session` and is Secure, HttpOnly,
  SameSite=Lax, Path=/, with no Domain.
- Logout clears the Cookie. Signing-secret rotation invalidates all sessions.
- The Next catch-all proxy forwards Cookie upstream and Set-Cookie downstream,
  strips hop-by-hop headers, refuses unsafe proxy paths, and exports GET, POST,
  PUT, and DELETE.
- The login screen follows `docs/DESIGN.md`, is responsive and keyboard
  accessible, shows inline loading/invalid/rate-limit states, and accepts only a
  same-origin `next` target.
- Credentials and sessions never enter Web Storage.

## Local and test behavior

Existing tests provide deterministic temporary secret files. Production Compose
mounts the real server secret files read-only and removes all app/data host ports.

## Acceptance checks

1. Public allowlist is exact and every other discovered API returns `401`.
2. Missing secrets return a safe `503` and never reveal filesystem details.
3. Signature tampering, expiry, issue-time skew, malformed tokens, Cookie flags,
   and rate limiting are tested.
4. Proxy contract tests cover headers, Set-Cookie, methods, query strings, and
   invalid paths.
5. Production Compose contains no BasicAuth middleware or published app ports.
6. Direct-origin forwarded-header spoofing is discarded while a real
   client-to-Cloudflare chain resolves to the client limiter key.
