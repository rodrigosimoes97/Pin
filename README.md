# Daily US Health & Wellness Content System (GitHub Actions + GitHub Pages)

This repo is a zero-maintenance daily automation system for **US health & wellness affiliate marketing**.
It generates one post per day, updates a GitHub Pages site in `/docs`, and prepares Pinterest-ready draft assets in `/generated`.

## What it does daily

- Generates **1 post/day** via GitHub Actions.
- Maintains a target mix of approximately:
  - **70% informational** posts (no affiliate link)
  - **30% offer** posts (soft CTA + disclosure)
- Uses **OpenAI Responses API** (not ChatGPT Plus).
- Uses **Pexels API** for images.
- Publishes to GitHub Pages from `/docs`.
- Creates Pinterest draft pack files:
  - `generated/pinterest/YYYY-MM-DD_pins.csv`
  - `generated/pinterest/YYYY-MM-DD_pins.json`
  - `generated/pinterest/YYYY-MM-DD_slug.png` (1000x1500)
- Optionally attempts Pinterest API publish; if unavailable/forbidden it logs and continues.

---

## 10-minute setup

### 1) Add repository secrets

In GitHub: **Settings → Secrets and variables → Actions → New repository secret**.

Required:
- `OPENAI_API_KEY`
- `PEXELS_API_KEY`
- `BASE_URL` (example: `https://YOUR_GITHUB_USERNAME.github.io/YOUR_REPO_NAME`)

Optional Pinterest publish:
- `PINTEREST_ACCESS_TOKEN`
- `PINTEREST_BOARD_ID`
- `PINTEREST_ENABLE_PUBLISH` = `1`

If Pinterest write access is not available (common in trial apps), keep Pinterest secrets unset and the workflow still succeeds with draft output only.

### 2) Enable GitHub Pages from `/docs`

In GitHub: **Settings → Pages**
- Source: **Deploy from a branch**
- Branch: your main branch
- Folder: `/docs`

Your site will be served from the `BASE_URL` you configured.

### 3) Enable Actions schedule

The workflow is in `.github/workflows/daily.yml` and runs daily plus manual trigger.

### 4) Run once manually

Go to **Actions → Daily Content Automation → Run workflow**.

---

## Output structure

- `docs/index.html` — homepage listing posts newest-first.
- `docs/{slug}.html` — generated post pages.
- `docs/sitemap.xml`, `docs/robots.txt`, `docs/404.html`.
- `docs/assets/*.jpg` — hero images.
- `generated/state.json` — run counters + recent topic memory (last 30).
- `generated/logs/YYYY-MM-DD.log` — daily run log.
- `generated/logs/pinterest.log` — Pinterest API errors/status.
- `generated/pinterest/*` — draft packs and vertical pin images.

---

## How content safety is handled

Prompts enforce:
- educational tone only
- no cure/treatment promises
- no fabricated studies
- include exact line: **“Educational only — not medical advice.”**
- offer posts include exact disclosure line: **“Disclosure: This page may contain affiliate links.”**

---

## Local run (optional)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export OPENAI_API_KEY=...
export PEXELS_API_KEY=...
export BASE_URL=https://YOUR_GITHUB_USERNAME.github.io/YOUR_REPO_NAME
python -m src.app.run_daily
```

---

## How to add offers

Edit `offers.json` and add objects with:
- `name` (offer name)
- `link` (affiliate URL)
- `tags` (topic matching tags like `anti-inflammatory`, `sleep`, `gut`, `weight`, `meal-prep`, `us`)

The runner chooses a tag-compatible offer for offer-mode posts.

---

## How to bulk upload Pinterest drafts (manual)

When API publishing is unavailable:

1. Open `generated/pinterest/YYYY-MM-DD_pins.csv`.
2. Open Pinterest bulk pin creation/import tool (or scheduler you use).
3. Upload the CSV and corresponding image files from `generated/pinterest/*.png`.
4. Verify destination board and schedule.

Notes:
- Links in draft files always point to your post page on GitHub Pages.
- Offer posts intentionally link to your post page first (not direct affiliate URLs), reducing platform policy friction.

---

## Reliability notes

- Pinterest API publish is **best-effort** and never crashes the daily pipeline.
- GitHub Action commits generated outputs automatically (`docs/`, `generated/`).
- System is Python 3.11 compatible and runs via:

```bash
python -m src.app.run_daily
```
