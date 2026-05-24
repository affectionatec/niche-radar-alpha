<!-- generated: 2026-05-22 -->
# Product

## Problem

Entrepreneurs and indie hackers spend hours manually scanning Reddit, Hacker News, Twitter, and YouTube for emerging product ideas and unmet user needs. By the time a trend is obvious, the market is crowded. There is no automated, cross-platform system that continuously monitors public signals, extracts pain points, scores opportunity quality, and delivers actionable daily reports of high-potential niches.

## Users

- **Solo founders / indie hackers** — looking for validated product ideas with low build complexity
- **Side-project builders** — need quick signal on trending topics before committing weekends
- **Micro-SaaS operators** — monitoring for adjacent opportunities in their space
- **Content creators** — identifying trending topics for articles, videos, courses

## Core Features

- **Multi-source ingestion**: 12 collectors (Reddit, HN, GitHub, YouTube, Google Trends, Product Hunt, Twitter, Stack Overflow, G2, Indie Hackers, App Store, Play Store)
- **8-agent LLM pipeline**: Signal filtering, pain extraction, market research, opportunity scoring, feasibility analysis, go/no-go verdict, PRD generation, and briefing
- **Scored niche candidates**: 7-dimension scoring (0–100) with GO/NO-GO/PIVOT verdict and build complexity estimate
- **Web dashboard**: Dark-themed Next.js UI with opportunity table, niche detail, shortlist, pipeline control, and report viewer
- **Background automation**: APScheduler runs collection every 4h, analysis every 6h, cleanup daily
- **Pluggable LLM**: Works with OpenAI, DeepSeek, Groq, Ollama, or Anthropic — configurable via web UI

## Non-Goals

- Not a market research platform with paid data providers (all sources are free/public)
- Not a CRM or project management tool — stops at idea validation and PRD
- No user authentication or multi-tenancy — designed as a single-user self-hosted tool
- No real-time streaming — batch-oriented collection and analysis cycles

## Status

Active Development (alpha) — core pipeline functional, 12 collectors implemented, frontend dashboard operational, LLM analysis pipeline producing scored results. No stable release yet.
