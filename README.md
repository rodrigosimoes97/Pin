# PinterestHealthAuto

PinterestHealthAuto is a full Python application repository for automating Pinterest affiliate marketing in the **US health & wellness niche** (weight loss, supplements, natural products, and healthy habits), with iHerb affiliate links.

## Features

- Topic discovery for trending US health/wellness ideas (Google Trends public endpoint + fallback seed list).
- Pin content generation optimized for Pinterest style:
  - 5–20 pin ideas per topic
  - title, description, alt text
  - 10 keyword tags
- SEO module:
  - board selection based on topic intent
  - keyword/tag enrichment for US audiences
- Image generation:
  - baixa imagens verticais da internet (Unsplash/Picsum)
  - salva localmente para uso imediato nos pins
  - fallback simples para não quebrar o fluxo
- iHerb affiliate link insertion via configurable referral code.
- Publishing:
  - Pinterest API integration with exponential backoff
  - automatic CSV export fallback when API is unavailable
- Scheduling:
  - daily publication limits
  - US prime posting hours
  - randomized intervals to reduce spam patterns
- Metrics tracking:
  - clicks and conversions (manual logging endpoint)
  - optional Pinterest view sync if API token is available
- SQLite data storage with audit logs for publishing.
- CLI for end-to-end workflow control.

## Project Layout

```text
.
├── src/pinterest_health_auto/
│   ├── affiliate.py
│   ├── cli.py
│   ├── config.py
│   ├── content_generation.py
│   ├── database.py
│   ├── image_generation.py
│   ├── metrics.py
│   ├── models.py
│   ├── pipeline.py
│   ├── publishing.py
│   ├── scheduler.py
│   ├── seo.py
│   └── topic_discovery.py
├── templates/
│   └── pin_template.txt
├── tests/
├── .env.example
├── pyproject.toml
├── requirements.txt
└── README.md
```

## Setup

1. Create and activate a virtualenv.
2. Install dependencies:

```bash
pip install -r requirements.txt
pip install -e .
```

3. Copy environment config:

```bash
cp .env.example .env
```

4. Set credentials:
   - `PINTEREST_ACCESS_TOKEN` for publishing + metrics (optional in MVP).
   - `IHERB_AFFILIATE_CODE` for affiliate tracking.

## Pinterest Business + API Setup

1. Create/upgrade to Pinterest Business account: https://business.pinterest.com/
2. Create app in Pinterest Developers portal.
3. Generate OAuth access token.
4. Add token to `.env` as `PINTEREST_ACCESS_TOKEN`.
5. If API limitations apply, run with CSV fallback and upload/schedule with approved tooling.

## iHerb Affiliate Setup

1. Join iHerb affiliate program.
2. Find your referral/affiliate code.
3. Add to `.env`:

```env
IHERB_AFFILIATE_CODE=YOUR_CODE
```

The app will create topic-based search URLs like:
`https://www.iherb.com/search?kw=metabolism+boosting+foods&rcode=YOUR_CODE`

## CLI Usage (simples)

Fluxo principal em **1 comando**:

```bash
pha quick-run --limit-topics 3 --pins-per-topic 5 --publish-now
```

Comandos opcionais (modo manual):

```bash
pha init-db
pha discover-topics --limit 10
pha generate-pins --topic-id 1 --topic-name "metabolism boosting foods" --count 10
pha publish-due
pha logs --limit 25
```

## SQLite Schema (MVP)

- `topics`: trending topic seeds with source + trend score.
- `affiliate_links`: maps keywords to affiliate URLs.
- `pins`: pin drafts, metadata, tags, board, scheduling/publish status.
- `pin_metrics`: event ledger for click/view/conversion signals.
- `publish_logs`: publishing outcomes and API/fallback messages.

## Example Output Artifacts

- Generated images in `generated_images/`
- CSV publish queue fallback in `pin_export_queue.csv`
- SQLite DB file at `pinterest_health_auto.db`

## Testing

Run unit tests:

```bash
pytest
```

The tests verify:
- pin idea generation count & structure
- board and tag SEO logic
- scheduler limits and timing
- DB schema + basic persistence
- image download and local output

## Notes

- Pinterest API payload fields (especially media upload) can differ by account/app capabilities.
- CSV fallback is included for robust MVP operations.
- Consider integrating production-grade observability and authenticated click redirect endpoints for attribution at scale.
