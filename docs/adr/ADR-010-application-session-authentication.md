# ADR-010: Application-owned session authentication

**Status:** Accepted  
**Date:** 2026-07-26

## Context

The alpha was originally documented as a local, single-user app with no auth. It
is now available through a public Cloudflare and Traefik hostname and exposes
source credentials, LLM configuration, pipeline actions, reports, and costs. An
interim Traefik BasicAuth prompt protects production but does not fit the product.

## Decision

Niche Radar owns a single-operator login:

- project-native `/login` UI;
- credentials and session key from fixed Docker secrets;
- short-lived HMAC session in a host-only secure Cookie;
- backend middleware protecting the complete `/api` surface except status/login;
- bounded failed-login throttling;
- explicit Cookie propagation through the Next server proxy;
- fail-closed production secret loading.

No credential value is committed. This supersedes the no-auth deployment
assumption without introducing user accounts or multi-tenancy.

## Consequences

- The temporary Traefik BasicAuth middleware disappears after this release.
- Logout clears the browser Cookie; signing-key rotation invalidates every
  stateless session.
- API scripts must log in and retain the Cookie.
- The public status endpoint remains intentionally non-sensitive.
