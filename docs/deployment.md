# Niche Radar: development and production release

This is the operational contract for agents and humans changing Niche Radar.
Production is `https://radar.originbase.org`.

## Architecture

```text
Browser
  → Cloudflare → Traefik :443
  → Radar Next.js frontend :3000
  → same-origin /api catch-all
  → Radar FastAPI :8000 → SQLite/data/reports
```

Only ports 22, 80, and 443 are public. Production Compose removes Radar,
frontend, and optional PostgreSQL host ports. Traefik owns HTTPS; no Nginx is
required.

The app presents its dark, project-native `/login` page. Credentials and the
session signing key come from read-only Docker secrets at
`/run/secrets/apps_login_credentials` and
`/run/secrets/apps_session_secret`, not a repository `.env`. Every API route
except `/api/status` and login requires a valid session. The Next proxy preserves
Cookie and Set-Cookie for GET, POST, PUT, and DELETE.

Per-client login limiting depends on a trusted proxy chain. Traefik accepts
forwarded headers only from Cloudflare's official IPv4/IPv6 ranges. Radar walks
`X-Forwarded-For` from right to left, removes Cloudflare and private Docker proxy
hops, and uses the first remaining address. Never enable
`forwardedHeaders.insecure`; keep the Traefik ranges synchronized with
Cloudflare's official lists.

## Before writing code

1. Use `AGENTS.md` for project conventions and `docs/architecture.md` for technical context.
2. Use exact domain terms: Collector, Raw Item, Niche Candidate, Pipeline, Verdict.
3. Branch from `origin/main`; never commit directly to `main`.
4. Never commit, log, or disclose `.env`, source/LLM credentials, Docker
   secrets, databases, sensitive reports, or sessions.
5. Regression tests use mocked external services. Live collector behavior belongs in the non-gating
   canary.

```bash
git fetch origin
git switch -c feat/my-change origin/main
```

## Required local checks

```bash
python3 -m pytest
python3 -m niche_radar.eval.runner
(cd frontend && npm ci && npm test && npm run lint && \
  npm audit --omit=dev --audit-level=high && npm run build)
docker compose -f docker-compose.yml -f docker-compose.prod.yml config --quiet
docker compose --profile postgres \
  -f docker-compose.yml -f docker-compose.prod.yml config --quiet
git diff --check
```

Report the checks actually run, including pytest and golden-set counts and any
environment limitations.

## Push, PR, and automatic release

```bash
git add <explicit-files>
git commit -m "feat: describe the change"
git push -u origin HEAD
gh pr create --base main --fill
```

```text
feature branch → PR → CI → review → merge main → main CI → Deploy production
```

Merge requires owner authorization. Deployment follows only a successful trusted
`push` CI on `main`.

Markdown-only changes under `docs/` or other `*.md` files are excluded from CI
and cannot deploy. Workflow, Compose, Python, TypeScript, and dependency changes
must run CI.

## What the deployer does

GitHub's `production` Environment holds a restricted repository-specific SSH key.
It cannot open a shell and can request only `deploy <40-character SHA>`. The
server:

1. verifies the SHA belongs to `origin/main`;
2. refuses to overwrite tracked server edits and never runs `git clean`;
3. preserves `data/`, `reports/`, optional PostgreSQL data, and secrets;
4. validates/builds base plus production Compose;
5. checks public status plus authenticated UI/API;
6. rebuilds the previous commit if startup or health checks fail.

Server directory: `/home/ubuntu/projects/niche-radar-alpha`.
Deployment log: `/home/ubuntu/traefik/deployments.log`.

## Post-release checks

```bash
curl --fail https://radar.originbase.org/api/status
curl --fail https://radar.originbase.org/login >/dev/null
curl --output /dev/null --write-out '%{http_code}\n' \
  https://radar.originbase.org/api/settings
```

Expected: status and login `200`; protected API without a Cookie `401`. After
sign-in, check Settings, source credentials, Pipeline, scoring weights, Shortlist,
and one read-only report. A paid full pipeline is not a routine smoke test.

## Re-run or roll back

Prefer a reviewed `git revert` PR. For an operational re-run, use
**Actions → Deploy production → Run workflow** with a full SHA in `main` history
that has a successful completed `push` run of `CI` on `main`. The workflow
rejects an untested SHA, and the server independently rejects feature-branch
commits.

## Rotate the shared operator credential

Never edit a repository file or pass a password as a command-line argument.
From a trusted terminal, rotate both the shared credential and signing key using
the server-side no-echo prompt:

```bash
ssh -t oracle '/home/ubuntu/traefik/setup-originbase-app-secrets --rotate-session'
```

Then manually re-run the current successful-main SHA in **Deploy production**
for Finance, Producer, and Radar so all containers remount the atomically
replaced files. After recreation, rotation invalidates every Producer/Radar
session; Finance sessions must also be revoked through its authenticated
`POST /api/auth/logout?all=true` operation. The server helper contains no
default credential and never echoes the password.

## Troubleshooting

| Symptom | Check |
|---|---|
| Login succeeds then immediately returns | Next proxy Cookie/Set-Cookie forwarding |
| PUT/DELETE returns 405 | Catch-all route must export both methods |
| Settings returns 401 | Cookie expiry, signing secret, backend auth logs |
| Eval fails | Release blocker; never bypass the golden gate |
| `tracked-worktree-dirty` | Review server changes before deployment |

```bash
ssh oracle 'tail -n 100 /home/ubuntu/traefik/deployments.log'
ssh oracle 'cd /home/ubuntu/projects/niche-radar-alpha && docker compose ps'
```
