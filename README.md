# Production Health Content Engine (Gemini + Pexels + GitHub Pages)

This repository publishes practical US-focused health content to `/docs` and produces a complete Pinterest draft pack daily.

## Core capabilities

- Gemini-only content pipeline (`gemini-2.0-flash`) with multi-key failover (`GEMINI_API_KEY_1..4`).
- SEO title ideation module that creates and filters 10 title candidates per run.
- Mixed publishing strategy: 70% informational and 30% affiliate-related content.
- Topic rotation across recipes, exercise, habits, natural remedies, gut health, sleep, weight loss lifestyle, anti-inflammatory foods, mental wellness, and longevity routines.
- Pexels hero image + Pinterest 1000x1500 image with title overlay.
- GitHub Pages publishing with automatic updates to `index.html`, `sitemap.xml`, and `robots.txt`.
- Pinterest draft generation every run (`CSV + JSON + image`) with optional API publishing.

## Environment variables

Required:

- `GEMINI_API_KEY_1` (and optionally `_2`, `_3`, `_4` for failover)
- `PEXELS_API_KEY`
- `BASE_URL`

Optional:

- `SITE_TITLE`
- `POSTS_PER_WEEK` (default `5`)
- `PINTEREST_ENABLE_PUBLISH` (`1` to enable API publishing)
- `PINTEREST_ACCESS_TOKEN`
- `PINTEREST_BOARD_ID`

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export GEMINI_API_KEY_1=...
export PEXELS_API_KEY=...
export BASE_URL=https://YOUR_GITHUB_USERNAME.github.io/YOUR_REPOSITORY
python -m src.app.run_daily
```

## Output locations

- `docs/*.html` generated post pages.
- `docs/index.html`, `docs/sitemap.xml`, `docs/robots.txt` maintained automatically.
- `generated/state.json` run history, topic memory, and recent slug storage.
- `generated/pinterest/*.png` Pinterest vertical images.
- `generated/pinterest/*_pins.csv` and `*_pins.json` Pinterest draft packs.
- `generated/logs/pinterest.log` optional publish logs.

## Content safety and policy approach

- Informational posts never include affiliate links.
- Offer posts include a soft recommendation and disclosure line:
  `Disclosure: This page may contain affiliate links.`
- Every article includes:
  - Intro
  - Structured H2/H3 sections
  - Practical tips/steps
  - FAQ
  - Closing encouragement
  - `Educational only — not medical advice.`
