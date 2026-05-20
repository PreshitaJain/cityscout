# CityScout

> Travel recommendations grounded in real Reddit discussion, powered by Claude.

CityScout fetches what locals and recent visitors are saying about a city on Reddit, and uses Claude (Haiku 4.5) to extract specific, credible place recommendations across four categories.

**Live:** https://cityscout-g399.onrender.com

---

## Why CityScout?

Most travel guides are editorial — slow to update, written by a handful of voices, and easy to game with paid placements. CityScout pulls from active Reddit threads and comments, so recommendations come from people who actually went there recently.

For any city, it returns up to 5 places in each of four categories:

- **Where to Eat** — restaurants, food markets, street food
- **Into the Wild** — parks, nature, outdoor spots
- **Gram-Worthy Spots** — cafés, viewpoints, photogenic locations
- **Off the Beaten Path** — hidden gems, local secrets

## Features

- **Multi-source Reddit data** — `r/<city>` posts *and* their top comments, plus searches in `r/travel` and `r/solotravel`. Comments are where the real "go here, not there" recommendations live.
- **Structured output via tool use** — uses Anthropic's tool-use API so the model returns a guaranteed-valid Python dict, never free-form text.
- **Per-city disk cache** — 30-day TTL. Repeat queries cost $0 and return instantly.
- **Resilient Reddit fetching** — exponential backoff retries on 429s and transient errors (via `tenacity`).
- **Failure logging** — any error lands in `errors.log` with full context for debugging.
- **CLI and web app** — same core logic, two entry points.
- **JSON API** — `GET /api/city/{name}` returns the raw dict; ready for future frontend integrations.

## Tech stack

- **Python 3.9+**
- **Claude Haiku 4.5** via the official `anthropic` SDK
- **FastAPI + Jinja2** for the web layer
- **Reddit JSON endpoints** (unauthenticated) for source data
- **Tenacity** for retry/backoff
- **Deployed on Render** with auto-deploy from `main`

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

## Project structure

```
cityscout/
├── cityscout.py        # Core library + CLI entry point
├── app.py              # FastAPI web app
├── templates/          # Jinja2 templates
│   ├── base.html
│   ├── index.html
│   └── city.html
├── requirements.txt    # Pinned dependencies
├── DESIGN.md           # Full design + roadmap + future opportunities
└── .gitignore
```

`.env`, `cache/`, `errors.log`, and `venv/` are git-ignored.

## Configuration

All tunable knobs are constants at the top of `cityscout.py`:

| Constant                 | Default                       | What it controls                                          |
|--------------------------|-------------------------------|-----------------------------------------------------------|
| `CACHE_TTL_DAYS`         | `30`                          | Days before a cached city result is considered stale      |
| `POSTS_FROM_CITY_SUB`    | `10`                          | Top posts pulled from `r/<city>`                          |
| `POSTS_FROM_SEARCH`      | `5`                           | Search results per additional subreddit                   |
| `COMMENTS_PER_POST`      | `3`                           | Top comments harvested per `r/<city>` post                |
| `ADDITIONAL_SUBREDDITS`  | `["travel", "solotravel"]`    | Cross-subreddit search sources                            |

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
