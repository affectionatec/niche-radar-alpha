# Monetization & Hosted Deployment

> Strategic paths for taking Niche Radar from open-source alpha to a sustainable product.

---

## Current State

Niche Radar is 100% self-hosted: users need Docker knowledge, a server or always-on machine, and their own LLM API keys. This limits the addressable market to technical users.

## Three Monetization Paths

### Path A · Hosted SaaS (Recommended Long-Term)

Full-service hosted version — users sign up, configure sources, and receive scored niches.

| Tier | Price | Sources | Analysis Runs | LLM | Extras |
|------|-------|---------|---------------|-----|--------|
| **Free** | $0 | 3 sources | 1/week | BYOK | — |
| **Pro** | $29/mo | All 12 | 1/day | Included | Email + Slack alerts, custom weights |
| **Team** | $99/mo | All 12 | 4/day | Included | Shared shortlist, API access, prompt packs |

**Architecture changes needed:**
- Multi-tenant database (tenant_id on all tables)
- Auth layer (OAuth / magic link)
- Billing integration (Stripe)
- Rate limiting per tier
- Isolated LLM key management

**Estimated effort:** 2–4 weeks for MVP

### Path B · Data Subscription (Low-Ops, Recommended First)

Sell the output, not the tool. Weekly digest email with curated niches.

| Tier | Price | Delivery | Content |
|------|-------|----------|---------|
| **Starter** | $19/mo | Weekly email | Top 10 niches with scores |
| **Pro** | $49/mo | Weekly email + dashboard | PRD-level detail, agent reasoning |
| **Enterprise** | $99/mo | Above + API | Raw data, source links, custom filters |

**Architecture changes needed:**
- Email delivery (Resend / SendGrid)
- Subscription management (Stripe)
- Curation workflow (shortlist → digest)

**Estimated effort:** 3–5 days

**Why start here:** No architecture rewrite. Validates PMF (product-market fit) before investing in multi-tenancy. Early stage can use manual curation to boost quality.

### Path C · Open Source + Paid Plugins

Keep the open-source core; monetize with premium extensions.

| Plugin Type | Examples | Price |
|-------------|----------|-------|
| Premium sources | LinkedIn, TikTok, Discord | $9/mo each |
| Expert prompt packs | VC Scout, Indie Hacker, Enterprise | $19/mo |
| Integrations | Push to Notion, Linear, Asana | $9/mo each |

**Architecture changes needed:**
- Plugin registry and loading system
- License key validation
- Plugin marketplace (could be a simple Gumroad page initially)

**Estimated effort:** 1–2 weeks for plugin framework

---

## Recommended Strategy

**Phase 1 (Weeks 1–2):** Launch Path B (data subscription) to validate demand.
- Add email digest generation to the existing report pipeline
- Set up Stripe for subscriptions
- Manually curate the first 4 digests

**Phase 2 (Weeks 3–6):** If Path B validates PMF, build Path A (hosted SaaS).
- Start with single-tenant hosted instance behind auth
- Gradually add multi-tenancy

**Phase 3 (Months 2–3):** Add Path C (plugins) for power-user retention.
- Ship 2–3 prompt packs (see [Prompt Packs](../docs/AGENTS.md))
- Build integration framework

---

## Deployment Guide (Hosted Setup)

For operators deploying a hosted instance:

### Infrastructure Requirements

| Component | Recommendation | Notes |
|-----------|---------------|-------|
| Compute | 2 vCPU / 4GB RAM | Scales to ~50 concurrent users |
| Database | PostgreSQL 15+ | Use the `db` Docker Compose profile |
| Storage | 10GB SSD | Grows ~100MB/month with 12 sources |
| LLM API | DeepSeek v4-flash | Best cost/quality ratio (~$15/mo at 4 runs/day) |
| Email | Resend or SendGrid | For digest delivery |
| Domain | Custom domain + HTTPS | Via Caddy or nginx reverse proxy |

### Docker Compose (Production)

```bash
# Use the production profile with PostgreSQL
docker compose --profile db up -d

# Set production environment
cp .env.example .env
# Edit .env with production values:
#   DATABASE_URL=postgresql://user:pass@db:5432/niche_radar
#   LLM_API_KEY=your-key
#   LLM_MODEL=deepseek-v4-flash
```

### Cost Projections

| Scale | Sources | Runs/Day | LLM Cost/Mo | Infra Cost/Mo | Total |
|-------|---------|----------|-------------|---------------|-------|
| Solo | 5 | 1 | ~$4 | $5 (VPS) | ~$9 |
| Small team | 12 | 4 | ~$15 | $10 (VPS) | ~$25 |
| Hosted (50 users) | 12 | 4 | ~$15 | $30 (cloud) | ~$45 |

---

*This document is a living strategy guide. Update as the product evolves.*
