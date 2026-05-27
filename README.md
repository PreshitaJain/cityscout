# CityScout

> Travel recommendations grounded in real Reddit discussion, powered by Claude.

CityScout is a curated directory of travel guides, distilled by Claude (Haiku 4.5) from real Reddit threads and comments. Each city in the directory is hand-seeded — fetched fresh, analyzed, and committed — so what visitors see on the live site is real-Reddit material, not made-up AI guesses.

**Live:** https://cityscout-g399.onrender.com

---

## Why CityScout?

Most travel guides are editorial — slow to update, written by a handful of voices, and easy to game with paid placements. CityScout pulls from active Reddit threads and comments, so recommendations come from people who actually went there recently.

For each city in our directory, you get up to 5 places in each of four categories:

- **Where to Eat** — restaurants, food markets, street food
- **Into the Wild** — parks, nature, outdoor spots
- **Gram-Worthy Spots** — cafés, viewpoints, photogenic locations
- **Off the Beaten Path** — hidden gems, local secrets

## Design thinking: why Reddit?

We evaluated several alternatives before picking Reddit. Short version:

- **Free, unauthenticated JSON API** — no app review, no business account, no per-call cost.
- **Text-rich discussion** in comments — where the real "go here, not there" wisdom lives.
- **Natural topical organization** via subreddits, plus upvotes as a free quality signal.
- **Lower brand/influencer pollution** than most social platforms.

Alternatives we considered and ruled out: **Instagram** (restrictive API, visual-first, heavy sponsored content), **Google Reviews / Maps API** (pay-per-call, performative reviews), **TikTok** (restrictive API, requires transcription), **YouTube vlogs** (expensive transcription, often sponsored), **general blog scraping** (heterogeneous, often stale, ToS risk).

See [`DESIGN.md`](./DESIGN.md) → "Source choice" for the full evaluation including Instagram-specific reasoning and the tradeoffs we accept.

## Features

- **Curated directory of 42 cities.** Each guide is built ahead of time and committed to the repo; the deployed app is essentially a static reader, so it never fails on rate limits or network issues.
- **Multi-source Reddit data** during build — `r/<city>` posts *and* their top comments, plus searches in `r/travel` and `r/solotravel`. Comments are where the real "go here, not there" recommendations live.
- **Structured output via tool use** — uses Anthropic's tool-use API so the model returns a guaranteed-valid Python dict, never free-form text.
- **Resilient seed pipeline** — exponential backoff retries on 429s and transient errors (via `tenacity`); failures logged to `errors.log` with full context.
- **CLI and web app** — same core logic, two entry points.
- **JSON API** — `GET /api/city/{name}` returns the raw dict; ready for future frontend integrations.

## Tech stack

- **Python 3.9+**
- **Claude Haiku 4.5** via the official `anthropic` SDK
- **FastAPI + Jinja2** for the web layer
- **Reddit JSON endpoints** (unauthenticated) for source data
- **Tenacity** for retry/backoff
- **Deployed on Render** with auto-deploy from `main`

## Available cities

CityScout currently covers 42 cities. Visit the [live site](https://cityscout-g399.onrender.com) to browse, or jump directly to any guide via `https://cityscout-g399.onrender.com/city/<name>`.

- **Asia:** Tokyo, Bangkok, Singapore, Mumbai, Delhi, Pune, Bali, Hanoi, Taipei, Seoul, Hong Kong, Kuala Lumpur
- **Europe:** Lisbon, Paris, London, Barcelona, Berlin, Rome, Amsterdam, Prague, Vienna, Stockholm, Copenhagen, Dublin, Edinburgh, Istanbul
- **North America:** Chicago, Seattle, Vancouver, New York, San Francisco, Los Angeles, New Orleans, Anchorage
- **Latin America:** Mexico City, Buenos Aires, São Paulo, Rio de Janeiro
- **Africa:** Cairo, Cape Town
- **Oceania:** Sydney, Melbourne

To request a new city, [open an issue](https://github.com/PreshitaJain/cityscout/issues/new). For self-hosters who want to add cities themselves, see "Adding more cities" below.

## Quick start

### 1. Clone and install

```bash
git clone https://github.com/PreshitaJain/cityscout.git
cd cityscout
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Add your Anthropic API key

Create a `.env` file in the project root:

```
ANTHROPIC_API_KEY=sk-ant-...
```

Get a key at [console.anthropic.com](https://console.anthropic.com).

### 3. Run

CLI:

```bash
python cityscout.py
```

Web app:

```bash
uvicorn app:app --reload --port 8000
```

Then open http://localhost:8000.

### 4. (Optional) Add cities to the directory

The deployed app reads only from `cache/<city>.json` files committed to the repo. To add a new city:

1. Open `seed_cities.py` and add an entry to the `CITIES` list. Use `(display_name, None)` for single-word cities where the subreddit name matches; use `(display_name, "subreddit_slug")` when they differ (e.g., `("New York", "nyc")`).
2. Run:
   ```bash
   python seed_cities.py
   ```
   Already-cached cities are skipped; only the new city will be fetched. Takes ~30 seconds per fresh city.
3. Commit the new `cache/<your_city>.json` file and push to `main`. Render auto-deploys with the expanded directory.

The seed script **must run from a residential IP** (your laptop is fine). The deployed app cannot do this itself because Reddit blocks cloud-provider IPs from its unauthenticated endpoints — see [`DESIGN.md`](./DESIGN.md) § Pivot for the full story.

## Project structure

```
cityscout/
├── cityscout.py        # Core library + CLI entry point
├── app.py              # FastAPI web app (reads from cache/ only)
├── seed_cities.py      # Build-time script that populates cache/
├── templates/          # Jinja2 templates
│   ├── base.html
│   ├── index.html
│   └── city.html
├── cache/              # Pre-built city guides, committed to the repo
├── requirements.txt    # Pinned dependencies
├── DESIGN.md           # Full design + roadmap + future opportunities
├── README.md
└── .gitignore
```

`.env`, `errors.log`, `venv/`, `.claude/`, and Python cache files are git-ignored.

## Configuration

All tunable knobs are constants at the top of `cityscout.py`:

| Constant                 | Default                       | What it controls                                              |
|--------------------------|-------------------------------|---------------------------------------------------------------|
| `POSTS_FROM_CITY_SUB`    | `10`                          | Top posts pulled from `r/<city>` during seed                  |
| `POSTS_FROM_SEARCH`      | `5`                           | Search results per additional subreddit during seed           |
| `COMMENTS_PER_POST`      | `3`                           | Top comments harvested per `r/<city>` post during seed        |
| `ADDITIONAL_SUBREDDITS`  | `["travel", "solotravel"]`    | Cross-subreddit search sources                                |

## Endpoints

| Path                        | Method | Returns                                                  |
|-----------------------------|--------|----------------------------------------------------------|
| `/`                         | GET    | Landing page with search form                            |
| `/search?city=<name>`       | GET    | Redirects to `/city/<name>`                              |
| `/city/{name}`              | GET    | HTML guide for the city                                  |
| `/api/city/{name}`          | GET    | JSON response with the same data                         |

Example JSON shape:

```json
{
  "city": "lisbon",
  "categories": {
    "where_to_eat":        [{"name": "...", "description": "..."}],
    "into_the_wild":       [{"name": "...", "description": "..."}],
    "gram_worthy_spots":   [{"name": "...", "description": "..."}],
    "off_the_beaten_path": [{"name": "...", "description": "..."}]
  }
}
```

## Roadmap

See [`DESIGN.md`](./DESIGN.md) for the full design document — architecture, deferred decisions (prompt caching, separate SPA frontend, Sentry observability), future opportunities (source attribution, multi-day planner, affiliate partnerships), and known limitations.

## License

© 2026 Preshita Jain. All rights reserved.

This project is publicly viewable but **not licensed for forking, copying, modification, or redistribution.** If you'd like to use any part of CityScout, please open an issue to discuss.

## Acknowledgments

- Recommendations generated with [Claude](https://www.anthropic.com/claude) (Anthropic).
- Source data via the [Reddit JSON API](https://www.reddit.com/dev/api).
- Deployed on [Render](https://render.com).
