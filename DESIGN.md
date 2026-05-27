# CityScout — Design Document

**Last updated:** 2026-05-27
**Status:** Live at https://cityscout-g399.onrender.com — curated directory of 42 cities, pre-built cache architecture (see Pivot section below for why).

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

## Source choice: why Reddit (and not Instagram or other platforms)?

CityScout's recommendations are only as credible as their source. We evaluated several alternatives before committing to Reddit — the reasoning below explains the trade.

### Why Reddit wins

- **Free, unauthenticated JSON API.** `https://www.reddit.com/r/<sub>/top.json` and `search.json` return structured data without authentication. No app review, no business account, no API key, no per-call cost.
- **Text-first, discussion-rich.** Comments are where the actual "go here, not there" wisdom lives — long-form, detailed, with follow-up Q&A. That's exactly the raw material Claude needs to extract specific recommendations from.
- **Natural topical organization.** Subreddits give us a built-in city/topic hierarchy (`r/<city>`, `r/travel`, `r/solotravel`). No need to invent our own categorization layer or stitch together hashtag/keyword soup.
- **Voting as a free quality signal.** Upvotes act as community-driven filtering — "top posts of the year" is roughly "what people consistently agreed was useful." We get a credibility signal without building it.
- **Lower brand and marketing pollution.** Compared to most social platforms, Reddit has stronger community norms against overt self-promotion. Recommendations are more likely from real visitors than paid influencers or sponsored content.
- **Time filtering for free.** Reddit's `t=year` / `t=month` / `t=week` parameters let us trade off recency vs. signal volume with zero custom logic.

### Why not Instagram

- **API is heavily restricted.** Instagram's Graph API requires a Facebook Business account, app review, and explicit use-case justification for meaningful data access. High friction even to prototype.
- **Visual-first medium.** Captions are short, often emoji- and hashtag-heavy. The actual recommendation signal (what's there, why it's good) lives in the *image*, which would require multimodal vision processing — significantly more complex and expensive than text extraction.
- **Heavy influencer / sponsored content.** Instagram is among the most monetized platforms; many "recommendations" are paid placements or brand partnerships. The credibility floor is lower.
- **Geotagging is patchy.** Many posts aren't location-tagged, and when they are, the tag is often coarse (city or country level) and gameable.
- **Discovery via hashtags is noisy.** `#tokyo` returns millions of unrelated posts (selfies, close-up food shots, generic memes). Signal-to-noise is poor without heavy pre-filtering.

### Why not other options we considered

- **Google Reviews / Google Maps Places API.** Pay-per-call pricing, and review style is performative ("amazing experience!!!") with limited specific, actionable recommendations.
- **TripAdvisor.** Public API was deprecated/restricted; well-known concerns about paid placements and review-bombing.
- **TikTok.** Video-first, restrictive API, would require transcription. High cost, low margin for our use case.
- **YouTube travel vlogs.** Long-form video → expensive to transcribe and analyze per query. Many vlogs are sponsored.
- **General travel blogs (web scraping).** Heterogeneous formats, often SEO-optimized listicle content, frequently stale, plus ToS and legal risk.

### Tradeoffs we accept by choosing Reddit

- **English-language Reddit dominates.** CityScout's recommendations skew toward English-speaking traveler perspectives. Cities with primarily non-English Reddit activity get thinner coverage.
- **Long-tail cities suffer.** A small city without an active subreddit has limited coverage. We partially mitigate via `r/travel` / `r/solotravel` searches, but it's not a full substitute for a thriving city-specific community.
- **No images.** Many Reddit posts have images, but we don't extract from them. A future multimodal upgrade could pull representative photos from linked sources.
- **Rate limits without auth.** Unauthenticated Reddit access is capped around 60 requests/minute. Sufficient for current use given our caching, but registering a Reddit OAuth app becomes necessary if traffic scales.

---

## 2. How it works (data flow)

### Runtime flow (deployed app)

```
User types a city name
       │
       ▼
Look up cache/<city>.json  ───►  Hit  ───►  Format & display
       │
       ▼ Miss
"This city isn't in our directory yet" page
```

The deployed app does **not** call Reddit or Claude. It only reads pre-built JSON files from `cache/`, which are committed to the repo.

### Build-time flow (seed_cities.py, local)

```
Operator runs python seed_cities.py
       │
       ▼
For each city in the curated list:
  - fetch_top_posts(r/<city>)                            ─┐
  - fetch_top_comments() for each post                    ├─ requires Reddit access
  - search_posts in r/travel, r/solotravel                ─┘
       │
       ▼
Send to Claude (Haiku 4.5) with forced tool call
       │
       ▼
Receive structured dict (shape enforced by tool schema)
       │
       ▼
Write cache/<city>.json  ───►  git commit + push  ───►  Render auto-deploys
```

The seed script runs from a **residential IP** (your laptop). Reddit's unauthenticated JSON endpoints work from residential IPs but return `403 Blocked` from cloud-provider IPs like Render's. The pivot section below explains why we adopted this split.

---

## 3. Components

| File / Module           | Responsibility                                                                |
|-------------------------|-------------------------------------------------------------------------------|
| `cityscout.py`          | Core library: Reddit fetch, Claude analysis, cache I/O, CLI entry point       |
| `app.py`                | FastAPI web app. Serves only from `cache/`; no live Reddit or Claude calls    |
| `seed_cities.py`        | Local build-time script: fetches Reddit + Claude for the curated city list   |
| `templates/`            | Jinja2 templates (base / index / city)                                       |
| `cache/<city>.json`     | Per-city result, committed to the repo. Source of truth for the deployed app |
| `.env`                  | Local secrets (Anthropic API key); never committed                            |
| `errors.log`            | Append-only log of seed-time failures (Claude parse errors, Reddit blocks)   |
| `.gitignore`            | Excludes `.env`, `errors.log`, `venv/`, `.claude/`, Python cache files       |

**Runtime dependencies:** `requests`, `anthropic`, `python-dotenv`, `tenacity`, `fastapi`, `uvicorn[standard]`, `jinja2`. Pinned in `requirements.txt`.

---

## 4. Configuration knobs

All tunable from constants at the top of `cityscout.py`:

| Constant                 | Default                       | What it controls                                              |
|--------------------------|-------------------------------|---------------------------------------------------------------|
| `POSTS_FROM_CITY_SUB`    | `10`                          | Top posts read from `r/<city>` during seed                    |
| `POSTS_FROM_SEARCH`      | `5`                           | Search results per additional subreddit during seed           |
| `COMMENTS_PER_POST`      | `3`                           | Top comments harvested per `r/<city>` post during seed        |
| `ADDITIONAL_SUBREDDITS`  | `["travel", "solotravel"]`    | Cross-subreddit search sources                                |

In `seed_cities.py`, `SLEEP_BETWEEN_CITIES = 25` throttles the seed to stay under Reddit's effective rate limit. The list of cities to seed lives in the same file.

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

## Pivot: from live fetch to pre-built cache

After shipping the FastAPI web app to Render, fresh-city searches started failing in production with `403 Blocked`. **Reddit aggressively blocks cloud-provider IP ranges** (Render, AWS, GCP, etc.) on its unauthenticated JSON endpoints — even though the same endpoints work fine from residential IPs. Our laptop-side tests passed, the deployed app didn't.

The standard workaround is OAuth-authenticated Reddit access (the rate-limited 60/min unauth endpoints have a more permissive OAuth twin). But Reddit's **2024 Responsible Builder Policy** restricts new Data API app approvals to "valid moderation use cases" only. CityScout — a travel recommendation tool — does not qualify. Re-attempting registration would be a TOS violation. (See memory entry `cityscout-reddit-api-blocked.md`.)

That closed every direct Reddit fix. We considered:

- **Run the fetcher from a residential IP (e.g. an always-on home machine):** kept "search any city" feel, but brittle — your laptop sleeps and the site breaks.
- **Paid residential-IP proxy** (ScraperAPI etc.): cleanest technically, ~$30/mo ongoing cost.
- **Pre-build the cache locally and commit it:** lowest moving parts, zero ongoing cost, scope reduces from "any city" → "curated directory."

We picked the third. The reframe — "carefully curated travel guides for 42 cities" — is honestly a *stronger* product positioning than "type anything, hope it works," and removes a class of production failures entirely. The deployed app reads only from committed JSON; it can never get blocked by Reddit because it never calls Reddit.

**What this means architecturally:**
- The web app at `app.py` calls `get_recommendations(city)`, which reads `cache/<city>.json` and returns the dict — nothing else. Cache misses return a friendly directory message.
- `seed_cities.py` is the build-time process: run locally, fetch + analyze each city, write cache files, commit, push. Render auto-deploys with the new cache.
- `CACHE_TTL_DAYS` was removed — cache is canonical, refreshed manually by re-running `seed_cities.py`.
- New cities are added by editing the `CITIES` list in `seed_cities.py` and re-running.

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

- **Curated directory only.** The deployed app serves 42 hand-seeded cities. Cache misses get a friendly "not in directory" page, not a live result. Adding a new city requires running `seed_cities.py` locally and pushing the resulting cache file.
- **No live refresh.** Cache files don't auto-update — recommendations age with the cache. Re-running `seed_cities.py` (and committing the new cache) is the only refresh path.
- **Reddit IP block in production.** The deployed app cannot fetch from Reddit at all; that's why we pre-build. If we ever obtain authenticated Reddit access (currently denied by Reddit's policy), live fetch could return.
- **Single-city interaction.** No flow for multi-city trips, comparisons, or itineraries.
- **English Reddit only.** Cities with primarily non-English Reddit activity yield thinner results during seed.
- **No personalization.** All users see the same recommendations for a given city.
- **Fixed category set.** Four categories — fine for now; may be too narrow for some segments (e.g. families, business travelers).
- **No feedback loop.** No "I went here" or thumbs-up signals — we don't know yet which recommendations are actually good.

---

## 11. Open questions (worth answering before / during step 5)

- **Cold start UX on Render free tier.** First request after 15 min idle takes ~30s. Acceptable for early demos? If not, upgrade to $7/mo always-on early.
- **What URL structure?** `/city/lisbon` (clean) vs. `/?city=lisbon` (simple). Clean URLs are SEO gold but require routing.
- **Public vs. private launch.** Open to the world day 1, or share with friends/Reddit first to gather feedback?
- **Analytics from the start.** Plausible / PostHog / nothing? Cheaper to bake in now than add later.
- **Pricing on day 1.** Free for everyone (build audience), or freemium from launch?
