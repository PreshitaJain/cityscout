# CityScout — Design Document

**Last updated:** 2026-05-20
**Status:** Production-ready CLI. Web deployment pending (step 5).

---

## 1. What CityScout is

CityScout turns real Reddit discussion about a city into curated, categorized travel recommendations. Where most travel sites publish editorial content that ages quickly, CityScout grounds its suggestions in what locals and recent visitors are actually saying — making the recommendations more current, more authentic, and harder to game.

For any city the user enters, CityScout returns up to 5 specific places in four categories:

- **Where to Eat** — restaurants, food markets, street food
- **Into the Wild** — parks, nature, outdoor spots
- **Gram-Worthy Spots** — cafes, viewpoints, photogenic locations
- **Off the Beaten Path** — hidden gems, local secrets, lesser-known spots

Each place has a name and a 1-2 sentence description.

---

## 2. How it works (data flow)

```
User types a city name
       │
       ▼
Check local cache  ─────►  Hit (< 30 days old)  ─────►  Format & display
       │                                                       │
       ▼ Miss                                                   │
Fetch Reddit content:                                           │
  - Top 10 posts from r/<city>                                  │
  - Top 3 comments per r/<city> post                            │
  - Top 5 search results for <city> in r/travel                 │
  - Top 5 search results for <city> in r/solotravel             │
       │                                                        │
       ▼                                                        │
Send to Claude (Haiku 4.5) with a forced tool call:             │
  extract_recommendations(city, categories)                     │
       │                                                        │
       ▼                                                        │
Receive structured dict (shape enforced by tool schema)         │
       │                                                        │
       ▼                                                        │
Save to cache, then format & display ◄──────────────────────────┘
```

---

## 3. Components

| File / Module           | Responsibility                                                                |
|-------------------------|-------------------------------------------------------------------------------|
| `cityscout.py`          | All application logic (single file)                                           |
| `.env`                  | Local secrets (Anthropic API key); never committed                            |
| `cache/<city>.json`     | Per-city cached results with timestamp; auto-expires at 30 days               |
| `errors.log`            | Append-only log of failures (Claude parse errors, Reddit failures, retries)   |
| `.gitignore`            | Excludes `.env`, `cache/`, `errors.log`, `venv/`, Python cache files          |

**Runtime dependencies:** `requests`, `anthropic`, `python-dotenv`, `tenacity`. (TODO: pin in a `requirements.txt` before deploy in step 5.)

---

## 4. Configuration knobs

All tunable from constants at the top of `cityscout.py`:

| Constant                 | Default                       | What it controls                                              |
|--------------------------|-------------------------------|---------------------------------------------------------------|
| `CACHE_TTL_DAYS`         | `30`                          | Days before a cached city result is considered stale          |
| `POSTS_FROM_CITY_SUB`    | `10`                          | Top posts read from `r/<city>`                                |
| `POSTS_FROM_SEARCH`      | `5`                           | Search results per additional subreddit                       |
| `COMMENTS_PER_POST`      | `3`                           | Top comments harvested per `r/<city>` post                    |
| `ADDITIONAL_SUBREDDITS`  | `["travel", "solotravel"]`    | Cross-subreddit search sources                                |

Internally, the model (`claude-haiku-4-5-20251001`) and `max_tokens` (`2048`) sit inside `analyze_with_claude` and can be lifted to constants if we start tuning them.

---

## 5. What we built — timeline

1. **Structured output via tool use.** Replaced fragile JSON-via-prompt with the Anthropic SDK's `tool_choice` feature. The API enforces output shape server-side — markdown fences, preambles, and other Claude habits become impossible.
2. **Secrets management.** API key in `.env`, auto-loaded via `python-dotenv`, ignored by git. Mirrors how secrets will be handled on Render.
3. **Per-city caching.** Results saved as JSON to `cache/<city>.json` with a timestamp. Same-city lookups within 30 days return instantly with zero API cost.
4. **Richer Reddit input.** Multi-subreddit fetches plus top comments from `r/<city>` posts. Significantly more credible output (specific addresses, hidden gems, day-trip ideas) at the cost of ~13 Reddit requests per fresh query — fully absorbed by the cache.
5. **Resilience.** Reddit calls retry with exponential backoff on 429/5xx/network errors via `tenacity` (up to 4 attempts, 1s → 2s → 4s → 8s). Final failures log to `errors.log` and return empty results so partial outages never crash the flow. Anthropic SDK retries bumped from 2 to 5.
6. **Observability (phase 1).** All failures land in `errors.log` with timestamp, context, and offending response. Production observability (Sentry) deferred — see roadmap.

---

## 6. Output contract (don't break this)

The dict shape returned by `analyze_with_claude` is the stable contract every downstream consumer (display, future website, future analytics) depends on:

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

Cache files wrap this with metadata:

```json
{
  "cached_at": "2026-05-20T13:00:00",
  "data": { ...the dict above... }
}
```

Any future changes (new fields, new categories) should be additive — never remove or rename existing keys.

---

## 7. Design principles applied

- **Enforce structure at the API layer, not in prompts.** Tool use, not "please return JSON."
- **Cache aggressively; let TTL handle staleness.** Don't reach for sophisticated invalidation until simple expiration breaks.
- **Fail closed, log openly.** Helpers return empty results on failure; details go to `errors.log` so we can diagnose without crashing on users.
- **Don't optimize what doesn't measure.** Prompt caching was on the roadmap but the math didn't support it yet — better to skip than to add complexity for show.
- **Lock the output shape early.** Everything downstream depends on it; changes should be additive only.

---

## 8. Roadmap

### Step 5 — Web deployment (next, immediate)

- Wrap the core in **FastAPI**. Expose `GET /api/city/{name}` that returns the existing dict shape. Add a small server-rendered frontend (or static HTML + fetch) to render results.
- Deploy to **Render** — free tier to start, $7/mo for always-on once we want no cold starts.
- `ANTHROPIC_API_KEY` set as a Render secret env var; `.env` stays local-only.
- Cache on Render: keep file-based to start. Render's free tier disk is ephemeral, but the cache will repopulate cheaply on cold starts. Upgrade to Render's hosted Postgres once usage justifies the cost.
- Pin dependencies in `requirements.txt`.
- Add a `Procfile` (or Render-native config) for the start command.

### Wired-up but deferred — Anthropic prompt caching

Our static prompt content (tool schema + system instructions) is ~350 tokens. Haiku 4.5's minimum cache block is 2,048 tokens — caching wouldn't activate today. Revisit when **any** of the following becomes true:

- We move the analysis model to Sonnet 4.6 (1,024-token minimum).
- The static prompt grows past 2K tokens (most likely by adding few-shot examples).
- We add a second cacheable layer (per-city context reused across calls).

Expected savings once active: ~90% on cached input tokens.

### Production observability

- Add **Sentry** (free tier) inside `log_failure()`. Same call site, real-time email/Slack alerts on errors.
- Lightweight per-stage timing logs once on Render — early warning for performance regressions.

---

## 9. Future opportunities (product side)

Not on the immediate roadmap, but worth filing for later.

### Data quality / credibility

- **Source attribution.** Save the Reddit post or comment each recommendation came from. Display as "Source: r/<city>, post by u/example" — builds trust and unlocks the "show me why" UX.
- **Recency weighting.** Bias toward newer posts for cities with fast-changing scenes (food, nightlife).
- **Dynamic subreddit detection.** Auto-discover city-specific subs (`r/AskNYC`, `r/londonfood`) instead of relying on the static `r/travel` / `r/solotravel` list.
- **De-duplication.** Same place mentioned in multiple posts/comments — collapse into one entry with combined evidence as a credibility signal.
- **Authenticated Reddit access.** Register a Reddit app for OAuth and higher rate limits (~100 req/min vs. 60). Required once traffic grows.

### User experience

- **Multi-day trip planner.** "I have 3 days in Lisbon" → day-by-day itineraries grouped by neighborhood.
- **Preferences.** Foodie focus, outdoor focus, photographer focus — adjust category weights and detail level.
- **Save & share.** User accounts to save guides; shareable URLs drive SEO and viral growth simultaneously.
- **Maps integration.** Cluster recommendations on a Google Maps or Mapbox embed.
- **Photos.** Representative images per place via Unsplash, or AI-generated when broadly available.
- **Mobile app.** Once the web app validates demand.

### Business / growth

- **Shareable city pages.** Each `/city/<name>` becomes an SEO-friendly landing page. Tokyo, Lisbon, etc. attract organic traffic.
- **Freemium.** Free tier: 5 city lookups/day. Premium: unlimited + multi-day planner + saved trips + map view.
- **Affiliate partnerships.** Booking.com, OpenTable, Viator — commission on bookings made from CityScout pages.
- **White-label.** Boutique travel agencies pay to embed CityScout for their clients.
- **Differentiation:** vs. Lonely Planet (editorial, slow, single voice), vs. generic AI chatbots (no real-world grounding, no citations), CityScout = grounded in real, current, social-proof recommendations.

### Engineering

- **Switch to Sonnet 4.6 for extraction.** Likely produces more nuanced descriptions and better category placement. Side-by-side test, weigh the ~3× cost (~$0.02 per fresh query instead of ~$0.005).
- **Few-shot examples in the prompt.** Show Claude a couple of high-quality extractions for other cities. Usually improves output. Bonus: pushes static prompt above 2K tokens, unlocking prompt caching.
- **Background cache warming.** Pre-fetch popular cities nightly — first-time visitors never wait.
- **On-demand cache invalidation.** UI button: "Refresh recommendations." Bypasses the 30-day rule for cities that feel stale.
- **A/B prompt testing.** Once analytics exist, test prompt variants for output quality.
- **Structured (JSON) logging** beyond `errors.log`, once we move past a single-server setup.
- **Separate frontend layer.** v1 renders HTML server-side with Jinja2 templates. If we later want richer interactivity (live filtering, map clustering, animated transitions, offline-capable PWA), upgrade to a React / Vue / Svelte SPA consuming the existing `/api/city/{name}` JSON endpoint. The API contract is already shaped to support this — the frontend swap is layered, not destructive.

---

## 10. Known limitations (today)

- **Single-city interaction.** No flow for multi-city trips, comparisons, or itineraries.
- **English Reddit only.** Cities with primarily non-English Reddit activity yield thinner results.
- **Long-tail cities suffer.** A small city without a thriving subreddit relies almost entirely on `r/travel` and `r/solotravel` search hits, which can be sparse.
- **No personalization.** All users see the same recommendations for a given city.
- **Fixed category set.** Four categories — fine for now; may be too narrow for some segments (e.g. families, business travelers).
- **No feedback loop.** No "I went here" or thumbs-up signals — we don't know yet which recommendations are actually good.
- **Cache doesn't track who searched.** Fine while there's no concept of users; will need rethinking once accounts exist.

---

## 11. Open questions (worth answering before / during step 5)

- **Cold start UX on Render free tier.** First request after 15 min idle takes ~30s. Acceptable for early demos? If not, upgrade to $7/mo always-on early.
- **What URL structure?** `/city/lisbon` (clean) vs. `/?city=lisbon` (simple). Clean URLs are SEO gold but require routing.
- **Public vs. private launch.** Open to the world day 1, or share with friends/Reddit first to gather feedback?
- **Analytics from the start.** Plausible / PostHog / nothing? Cheaper to bake in now than add later.
- **Pricing on day 1.** Free for everyone (build audience), or freemium from launch?
