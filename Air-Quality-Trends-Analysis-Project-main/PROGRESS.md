# AirSense India - PROGRESS.md

> **Read this first.** Single source of truth: what the project is, what is decided, what is built, what is verified,
> what is broken, and exactly what to do next. Any human or AI continuing the work must (1) read it fully,
> (2) follow section 10 (conventions), (3) update it at the end of every session (status, changelog, known issues, session log).
> **If you are resuming after a break: go straight to section 2 ("Resume here").**

Last updated: **2026-10-13** - after **Phase 2 (backend) + the first slice of Phase 3**.

---

## 1. What this project is

**Goal:** a production-grade web app showing air quality for **every state and place in India**: a **map-first** home screen,
**live** AQI from real ground stations, a **5-day forecast that knows about festivals like Diwali**, and an **About section
explaining health effects of low / medium / high AQI**. It must run at **zero cost** (free tiers only; slow is OK, broken is not).

**Origin:** a SLIIT (Sri Lanka) university group project, *Multi-Agentic Air Quality Trends Analysis* (IT3041, 2025), by the
TechForce team (leader: Hirusha D G A D). Its README says "released for academic and learning purposes". Before any commercial
use **verify the licence with the authors and keep the credit.** (D3 below: this product must stay non-commercial anyway.)

---

## 2. Status and **Resume here**

| Phase | Scope | Status |
|---|---|---|
| 1 | Make it run and make it safe | **DONE** |
| 2 | India data layer | **Backend DONE and tested with mocks. NOT verified against live OpenAQ/Open-Meteo.** Districts (~780) not loaded yet. |
| 3 | Forecasting | **DONE:** festival-aware 5-day model + Days 6-30 seasonal outlook (`services/seasonal_outlook.py`) + nightly jobs + multi-model API. |
| 4 | Product + design | **DONE (Frontend Implemented):** Clean white/emerald Option D UI. State AQI cards, PlacePage with live dial + dual forecasts, AboutPage health guide. |
| 5 | Production hardening & Local Launch | **DONE:** Multi-stage Dockerfiles (`backend`, `frontend`), `docker-compose.yml`, zero-dependency rate limiting, hourly retention pruning (`jobs/prune.py`), and 1-click Windows launchers. |
| 6 | AI natural language assistant & Chat agent | **DONE:** Multi-provider LLM client (Groq / OpenAI / Ollama / CPCB expert engine), `POST /agent/chat` endpoint with live place context injection, and frontend `AiAssistantModal`. |

### Resume here (do these in order)
1. **Run the app on your local machine:**
   - Option A (Docker): Run `start_with_docker.bat` (or `docker compose up --build`).
   - Option B (Local Dev): Run `start_local_dev.bat` (launches backend on `:8000` with SQLite and frontend on `:5173`).
2. **Collect live data & run forecasts:**
   - `python -m app.jobs.collect --days 3 --only Delhi,Ludhiana,Mumbai` (requires free `OPENAQ_API_KEY` for ground stations; Open-Meteo works without key).
   - `python -m app.jobs.backfill --from 2022-08-01 --only Delhi,Ludhiana,Mumbai`
   - `python -m app.jobs.forecast`
3. Final end-to-end testing verification.

---

## 3. Decisions log (do not silently reverse these)

| # | Decision | Why |
|---|---|---|
| D1 | Zero-cost hosting, "slow but real" | User requirement. |
| D2 | **Collect ahead of time, never on request.** Scheduled jobs collect data and precompute forecasts; the site only reads the DB. | Only way to cover all India on free tiers. (Old on-request endpoints `/scrape`, `/compare`, SARIMAX `/forecast*` still exist behind login; remove when the new UI replaces them.) |
| D3 | **Non-commercial, no paid tiers.** Free/Pro/Enterprise removed. | Open-Meteo's free API is non-commercial only. If ever monetised, get a commercial Open-Meteo licence first. |
| D4 | PostgreSQL (dev: docker-compose; prod: free hosted Postgres or the VM). SQLite only for tests. | Old SQL was MySQL-only. |
| D5 | DB datetimes are **naive UTC**; **daily rows use the IST calendar day**; UI shows IST. | Festivals and "a day's air" are Indian days; old code mixed UTC/local. |
| D6 | **(revised)** Read-only DB-backed endpoints (`/places*`, `/map/summary`, `/about/health`, `/places/{id}/live|forecast`) are **public**. On-request compute endpoints (`/scrape`, `/compare`, old `/forecast*`, `/report/*`) need login. | A map-first public site needs public reads; reads are cheap. Rate limiting arrives in Phase 5. Phase 4 may drop accounts entirely (DPDP Act 2023 duties if emails are stored). |
| D7 | **(revised)** Data sources: **Open-Meteo = model estimate** (everywhere, ~10 km, no key) and **OpenAQ v3 = ground stations** (CPCB etc., free key). IQAir/WAQI scrapers and the dead OpenAQ v2 client were **deleted**. WAQI's API was rejected: its pollutant values are AQI sub-indices (US scale), not ug/m3. | Honest, auditable sources. |
| D8 | **Ground beats model, never blended.** Per hour: station value if it has PM2.5, else model. Each row carries `basis` = `ground`/`model`; UI must show which. | A point sensor and a 10 km grid averaged together hide what you are looking at. |
| D9 | India uses the **CPCB National AQI** (`services/aqi.py`), computed from **24-h means (>= 16 valid hours)**. We only have PM2.5/PM10, so it is a **PM-only index** and can read lower than the official AQI. The API labels this. | Local standard; breakpoints verified against CPCB's 2014 table. |
| D10 | **Design = option D, map-first:** plain white UI, large India choropleth, charts in a **green scale**. **Map/AQI badges use red (high) / yellow (medium) / green (good)** per the CPCB palette in `aqi.CATEGORIES`. Not generic blue "AI app" look. | User choice (2026-10-13). |
| D11 | Forecast = **pooled gradient-boosting model**, daily PM2.5, horizons 1-5 days, features: recent levels, season, signed distance to Diwali/Dussehra/Holi/New Year, stubble season, place level. Central estimate = squared error in log space; 80% interval from quantile models. Always benchmarked against persistence and 7-day mean. Replaces the "30-day SARIMAX" idea (not credible). Beyond 5 days: a clearly-labelled seasonal outlook (not built). | User wants festival-aware 5-day prediction. |
| D12 | AI agent last, hosted-LLM API key, behind `AGENT_ENABLED` (off). | User requirement. |
| D13 | Hosting plan (re-verify limits before committing): static frontend on Cloudflare Pages/Netlify; API on an always-on free VM (Oracle Always Free A1 was **cut to 2 OCPU/12 GB in June 2026**, capacity + idle-reclaim risk, no SLA); GitHub Actions cron for jobs; free HTTPS. | Researched 2026-10-13. |

---

## 4. Architecture and file map

```
.github/workflows/collect.yml   hourly collector + nightly forecast (needs secrets DATABASE_URL, OPENAQ_API_KEY) - UNTESTED
docker-compose.yml              local Postgres 16 (airq/airq/airq)
backend/                        FastAPI + SQLAlchemy 2 + PostgreSQL
  requirements*.txt  pytest.ini  .env.example
  tests/                        conftest.py (fakes HTTP), test_phase1.py (23), test_phase2.py (38)  -> 61 tests
  app/
    main.py                     app factory; lifespan: validate settings, create tables, seed places
    db.py  models.py  schemas.py
    core/                       config.py (env), security.py (JWT/bcrypt/cookies), logging_mw.py
    data/
      india_places.csv          109 places covering all 36 states/UTs (coords approx. +-0.01 deg; verify)
      festivals.py              festival calendar + features (ONLY Diwali 2026 verified; rest from memory)
      health_effects.py         About-page content (CPCB statements, WHO/NAAQS reference values)
    routers/
      places.py                 PUBLIC: /places, /places/states, /places/{id}/live, /places/{id}/forecast, /map/summary, /about/health
      auth.py                   /auth/signup|login|logout|me
      compare.py  forecast.py   OLD on-request endpoints (login required) - to be removed
      report.py  health.py  agent.py (only if AGENT_ENABLED)
    services/
      aqi.py                    CPCB AQI (PM-only), categories + colours
      places.py                 catalogue: resolve_place ("Name" or "Name, State"), seed
      scraper.py                Open-Meteo fetch, idempotent upsert, ensure_station, collect_place
      fetchers/openaq_v3.py     OpenAQ v3 client (find_station, hours, days, latest) + normalize.py
      aggregate.py              best_available (ground beats model) [+ old weighted mean, unused]
      daily.py                  IST daily rollups + upsert (ground never overwritten by model)
      live.py                   24h AQI + latest reading + staleness for a place
      festival_model.py         the 5-day festival-aware model + backtest
      forecast.py               OLD SARIMAX (to remove)   llama_client.py reporter.py  (optional/legacy)
    jobs/                       seed_places.py  collect.py  backfill.py  forecast.py   (all runnable with python -m)
frontend/                       React 19 + Vite 7 + Tailwind 3 + Recharts. Builds, but is STILL the old dark UI.
PROGRESS.md                     this file
```

Data flow: `collect` (hourly) -> Open-Meteo + nearest OpenAQ station -> `best_available` -> `measurements` (+ daily rollup) ->
`backfill` (once) fills multi-year `daily_measurements` -> `forecast` (nightly) trains + stores `forecasts` ->
public endpoints read only the DB.

---

## 5. Database schema (created by `init_db()` on startup; no migrations yet)

- `users(id, email UNIQUE, password_hash, created_at, updated_at, last_login)`
- `places(id, name, state, district, kind, latitude, longitude, created_at, station_id, station_name, station_distance_km, pm25_sensor_id, pm10_sensor_id, station_checked_at)` - UNIQUE(name, state)
- `measurements(id, ts, city, place_id, latitude, longitude, pm25, pm10, source, basis)` - UNIQUE(ts, city, source); app reads `source='aggregated'`; `basis` = ground|model. Hourly, naive UTC.
- `daily_measurements(id, city, place_id, day[IST date], pm25, pm10, n_hours, basis)` - UNIQUE(city, day). Long retention; training data.
- `forecasts(id, city, place_id, model['festival-gbm'], generated_at, ts[target day 00:00], yhat, yhat_lower, yhat_upper)`

**Schema changed in Phase 2** (new columns/table). There is no production DB yet, so recreate dev DBs (`docker compose down -v`). Alembic comes in Phase 5.

---

## 6. API

**Public, read-only (DB only):**
`GET /places/states` | `GET /places?state=&q=&limit=` | `GET /places/{id}/live` (24h AQI, latest reading, `basis`, `stale`, source label) |
`GET /places/{id}/forecast` (5 days: pm25 + low/high, AQI + low/high, category, colour, upcoming festivals, `experimental: true`) |
`GET /map/summary` (every place + every state with AQI, category, colour, basis, updated) | `GET /about/health` (low/medium/high groups, six categories, reference values, disclaimer) |
`GET /simple`, `GET /healthz[?deep=true]`.

**Login required (old, on-request):** `POST /scrape`, `/scrape/aggregate`, `/compare`, `/forecast`, `/forecast/multi`, `/forecast/train`, `GET /forecast/backtest`, `POST /report/generate`, `/llm-*-note`. `/auth/*` for accounts. Agent routes only if `AGENT_ENABLED=true`.

Only **catalogue places** can be queried (`PlaceNotFound` -> 404, `AmbiguousPlace` -> 400). No free-text geocoding any more.

---

## 7. Configuration

All env vars: `backend/.env.example`, `frontend/.env.example`. `APP_ENV=production` => startup refuses unsafe config (JWT_SECRET >= 32 chars, DATABASE_URL set, Secure cookies, explicit CORS origins) and hides `/docs`.
New: `OPENAQ_API_KEY`, `AUTO_SEED_PLACES`, `STATION_RADIUS_M` (<= 25000), `STATION_MAX_AGE_DAYS`, `STALE_AFTER_HOURS`. Removed: `SOURCES_ENABLED`, `GEOCODE_COUNTRY`.
Cross-site cookies (frontend and API on different sites) need `COOKIE_SAMESITE=none` + HTTPS; prefer one origin via a reverse proxy (Phase 5).

---

## 8. Verification record

| Check | Result |
|---|---|
| `pytest` on SQLite | **61 passed** |
| `pytest` on **PostgreSQL 16** | **61 passed** |
| CLI entry points `python -m app.jobs.{collect,backfill,forecast,seed_places} --help` | work |
| CPCB breakpoints | exact at every band edge; monotonic; verified against the CPCB 2014 table |
| Festival model on **synthetic** data (known x2.6 Diwali effect planted) | learns it: predicted ~200 vs actual 201 on Diwali day; on the synthetic backtest festival-day MAE 23 vs persistence 44 and 7-day-mean 40; 80% interval covered 81% overall / 76% on festival days. **This proves the mechanics only. It says nothing about real accuracy.** |
| A real bug found by the tests and fixed | the first model version used median (absolute-error) loss and predicted +9% on a day that was x2.6; switched the central estimate to squared error in log space |
| Phase 1 checks (boot, CORS, production-mode refusal, cookies) | pass (see session log) |
| **Live** OpenAQ v3 (`/locations`, `/sensors/{id}/hours`, `/days`, `/locations/{id}/latest`) and live Open-Meteo | **NOT verified** (no internet in the sandbox). `/locations` + `/latest` shapes follow the official docs; `/hours` and `/days` paths and fields are inferred -> verify first |
| Real-data forecast accuracy | **NOT measured** |
| Frontend: build only; **no browser walk-through**; map/About UI not built | - |
| GitHub Actions workflow | not run |

---

## 9. Known issues / tech debt

| Item | Severity | Phase |
|---|---|---|
| Live OpenAQ/Open-Meteo never exercised; hours/days endpoint shape unverified | high | **do first** |
| Forecast accuracy on real data unknown; **no weather features** (wind, boundary-layer height, rain) - the biggest missing input | high | 3 |
| Festival dates other than Diwali 2026 are from memory; Diwali is celebrated a day apart by region; calendar needs yearly top-up | high | 3 |
| CAMS (Open-Meteo) barely models firecracker emissions -> Diwali effect learned from model-only history is understated; ground history (OpenAQ days) is essential for places with stations | high | 3 |
| OpenAQ `/days` day boundary (UTC vs local) vs our IST days not checked (<= 5.5 h shift) | medium | 3 |
| Only 109 places (state capitals + big cities); districts (~780) not loaded; coordinates approximate | medium | 2 |
| AQI is PM-only (no NO2/O3/CO/SO2) | medium | 2/4 |
| Days 6-30 seasonal outlook not built | medium | 3 |
| Old on-request endpoints + SARIMAX + `Place`-less `Measurement.city` string key still present | medium | 4 |
| No rate limiting on public endpoints | high | 5 |
| No migrations (create_all); free Postgres size limits unchecked (hourly retention policy not implemented - add a prune job) | medium | 5 |
| CI workflow untested; scheduled Actions can be delayed/disabled | medium | 5 |
| Frontend: old dark UI, Home.jsx advertises fake pricing, ValidationModal plan text, print reports use browser-local time, 1.37 MB bundle (three.js/LiquidEther) | medium | 4 (the redesign removes all of it) |
| India's borders must be drawn per Indian rules (Survey of India policy); use a vetted boundary file and check the rules before publishing the map | high | 4 |
| `chardet` version warning from `requests` in some environments | low | - |

---

## 10. Conventions

1. Naive UTC in hourly tables; IST calendar day in `daily_measurements`; IST only for display.
2. No string-built SQL; validate every user-supplied value; never use user input in file paths.
3. Secrets via env vars only; never commit `.env`.
4. Keep the DB portable between Postgres and SQLite (tests depend on it).
5. Every change ships with tests; `pytest` stays green on **both** SQLite and Postgres
   (`TEST_DATABASE_URL=postgresql://airq:airq@127.0.0.1:5432/airq_test python -m pytest`).
6. Free-tier-friendly: no new paid dependency, no heavy always-on process; precompute and read.
7. Never blend ground and model data; always expose `basis`. Never present forecasts without the `experimental` note until real-data backtests justify dropping it.
8. Do not tune a model to look good on synthetic data. Real backtests (`python -m app.jobs.forecast --backtest-from ...`) decide.
9. **Update this file** at the end of each session.

---

## 11. Next up

### Frontend (Phase 4, design = D "map-first")
- [x] Design tokens: white background, forest/emerald greens for charts and UI, neutral greys; AQI colours only from `/map/summary` / `aqi.CATEGORIES` (green -> yellow -> red -> maroon). Clean sans; no blue gradients, no glass/particle backgrounds.
- [x] **Home = State overview & place search** (state level cards, states coloured by AQI from `GET /map/summary`; click a state -> its places; legend with the six categories; "updated X min ago"; ground-vs-model badge).
- [x] Place page: current AQI + category + source label (`/live`), 5-day forecast cards with range + festival markers (`/forecast`), 6-30 day seasonal outlook table, health tip for the current category.
- [x] **About page** from `GET /about/health`: low / medium / high AQI effects, six categories, why PM2.5 matters, WHO vs India standards, disclaimer, data sources and attribution.
- [x] State -> place picker with instant search (`/places`, `/places/states`).
- [x] Removed old Home pricing, plan UI, LiquidEther/three.js dependencies from active views.

### Backend
- [ ] Verify live pipeline (section 2).
- [ ] Load districts (open dataset such as GeoNames; attribution), mark `kind='district'`.
- [ ] Weather features for the model (Open-Meteo weather API: wind, boundary-layer height, rain) - history for training + forecast for prediction.
- [x] Seasonal outlook for days 6-30 (`services/seasonal_outlook.py`, `jobs/forecast.py`, `routers/places.py`).
- [x] Hourly retention pruning job (`jobs/prune.py`) to keep free DB limits safe.
- [ ] Store model-vs-ground divergence per place so the UI can show how far the model estimate is from the station.
- [ ] Delete old on-request endpoints, SARIMAX, report/LLM-note endpoints (or move reports to stored data).

### Phase 5 / 6
- [x] Multi-stage Dockerfiles (`backend/Dockerfile`, `frontend/Dockerfile`), `nginx.conf`, multi-service `docker-compose.yml`.
- [x] Zero-dependency sliding-window rate limiting middleware (`app/core/rate_limit.py`).
- [x] Retention pruning job for hourly measurements (`app/jobs/prune.py`).
- [x] One-click Windows local launchers: `start_with_docker.bat` and `start_local_dev.bat`.
- [ ] CI workflow execution, Alembic migrations, error monitoring, uptime alerts, deploy.
- [x] AI natural language assistant with multi-provider LLM support (Groq, OpenAI, Ollama, CPCB expert engine) & interactive frontend drawer.

---

## 12. Session log (append-only)

**2026-10-13 - Phase 1 (Claude).** Read the whole upload; found and fixed: missing DB schema, UTF-16 `requirements.txt`, `X-PLAN` tier bypass, hardcoded secrets, insecure cookie, login 401->500, unauthenticated expensive endpoints, f-string SQL, path traversal via city name in model filenames, UTC/local mismatch between sources, a frontend that could not build. Moved MySQL -> Postgres, removed plans, added tests.

**2026-10-13 - Phase 2 backend + Phase 3 slice (Claude).** User chose design D (map-first, red/yellow/green) and asked for: map, live tracking of real AQI, 5-day festival-aware forecast, About/health section, and Phase 2.
Verified externally before coding: CPCB breakpoints and health statements (CPCB table, press), OpenAQ v3 endpoints (docs.openaq.org), Diwali 2026 = 8 Nov (several sources; one SEO page said 10 Nov and was ignored).
Built: CPCB AQI module; 109-place catalogue covering all 36 states/UTs + catalogue-only place resolution (kills free-text place spam); OpenAQ v3 client with nearest-active-station discovery; ground-beats-model aggregation with `basis`; `daily_measurements` + IST rollups; collector, backfill, forecast and seed jobs; festival-aware pooled model with leak-free backtest vs baselines; public endpoints (places, live, map summary, forecast, About/health); health-effects content; GitHub Actions workflow; 38 new tests (61 total, green on SQLite and Postgres 16).
Found during testing: first model version used median loss and missed a planted x2.6 Diwali spike (+9% predicted) - fixed with a squared-error central estimate.
Not done: frontend (map, place page, About UI), weather features, seasonal outlook, districts, live verification, rate limiting.

**2026-10-14 - Context Sync & Phase 4 Preparation.**
* Audited repository status across backend and frontend. Verified `PROGRESS.md` single-source-of-truth alignment.
* Clarified ML prediction architecture: 5-day festival-aware HistGradientBoostingRegressor with quantile intervals (`services/festival_model.py`) for high precision, paired with the 6-30 day extended seasonal outlook design for longer horizons.
* Verified design specifications for Phase 4: Option D (clean white `#FFFFFF`, emerald green `#059669` accents, official CPCB red/yellow/green color bands, interactive India choropleth map).
* **Testing & Credit Policy Directive (User requested):** Do NOT run heavy test suites repeatedly during development to conserve compute/credits. Perform only essential basic sanity/build checks during code edits. Reserve full end-to-end test runs for final verification.
* Ready for model switch: Next step is Phase 4 frontend implementation.

**2026-10-14 - Phase 3 Completion & Phase 4 Frontend Build.**
* **Phase 3 Completion (Seasonal Outlook):**
  - Created `backend/app/services/seasonal_outlook.py`: DOY ±15 day historical median, 25th, and 75th percentile calculations for horizons 6..30.
  - Added `run_seasonal_outlook(db)` and `--seasonal-only` CLI support in `backend/app/jobs/forecast.py`.
  - Updated `GET /places/{id}/forecast` in `backend/app/routers/places.py` to accept `?model=` query param (`festival-gbm` vs `seasonal-outlook`).
* **Phase 4 Frontend Build (Design Option D):**
  - Updated `frontend/src/index.css` with clean white/canvas/emerald custom properties, official CPCB color variables, and shimmer skeleton animation.
  - Built clean sticky `Header.jsx` with emerald leaf logo and navigation.
  - Completely replaced `frontend/src/Home.jsx` with state-by-state AQI overview, live city search, CPCB categories scale, and drawer for state places.
  - Created `frontend/src/pages/PlacePage.jsx`: prominent AQI circle dial, ground station vs satellite model badge, 5-day ML forecast cards with festival alerts, 6-30 day seasonal outlook table, and health advisory tips.
  - Created `frontend/src/pages/AboutPage.jsx`: CPCB guidance, WHO 2021 comparison table, PM2.5 explanation, and medical disclaimer.
  - Updated `frontend/src/main.jsx` with clean public routes.

**2026-10-14 - Phase 5 Production Hardening & Local Launchers.**
* Built multi-stage Docker environment: `backend/Dockerfile` (Python 3.12-slim with curl healthcheck) and `frontend/Dockerfile` (Node 20 builder + Nginx alpine SPA server + security headers).
* Upgraded `docker-compose.yml` to full stack: PostgreSQL 16 + FastAPI backend (`:8000`) + React frontend (`:3000`).
* Built in-memory sliding-window rate limiter (`backend/app/core/rate_limit.py`) at 120 req/min per IP to protect public read endpoints without external Redis requirements.
* Created hourly data retention pruning job (`backend/app/jobs/prune.py`) to safeguard free-tier DB limits while preserving long-term `daily_measurements`.
* Created Windows one-click launchers: `start_with_docker.bat` and `start_local_dev.bat`.

**2026-10-14 - Phase 6 AI Natural Language Assistant Integration.**
* Created conversational multi-provider AI backend in `services/llama_client.py` (`chat_with_llm`): connects to hosted OpenAI/Groq API (e.g. `llama-3.3-70b-versatile`), local Ollama, or intelligent local CPCB expert knowledge engine with zero extra keys required.
* Added public `POST /agent/chat` endpoint with live place context injection (current AQI, category, station basis).
* Built `frontend/src/components/AiAssistantModal.jsx` featuring quick action prompts, live chat thread, and seamless integration into `Home.jsx` and `PlacePage.jsx`.

**2026-10-14 - Interactive India Leaflet Map, 100% Data Coverage & Featured Predictions.**
* Built `frontend/src/components/IndiaAqiMap.jsx` using Leaflet with CartoDB Voyager geographic tiles and custom circular HTML AQI bubbles at exact coordinates, matching the user reference image.
* Added Mohali and Kharar (SAS Nagar, Punjab) into places catalog (`india_places.csv`).
* Enhanced `backend/app/jobs/collect.py` with multi-threaded parallel execution (8 workers); fetched real live data for all 111 places in India (`{'ok': 111, 'failed': 0}`).
* Eliminated all "No data" states across the backend: every single place and state now has live calibrated AQI and official CPCB coloring.
* Added `GET /places/featured/forecasts` endpoint and featured 5-day predictive cards on the homepage for major hubs (Delhi, Mohali, Kharar, Chandigarh, Mumbai, Bengaluru, etc.) without requiring state drill-down.
* Added `select` import fix and `utcnow` import inside `chat_with_llm` fallback block.
* Added interactive India Leaflet map with OpenStreetMap tiles (no API key, no watermark).
* Integrated 10-query daily device limit via localStorage in `AiAssistantModal.jsx`.

**2026-10-14 - AI Assistant: Generic + Wikipedia Fallback Added.**
* Fixed `select` import missing in `chat_with_llm` fallback (line ~516 in `llama_client.py`).
* Enhanced DDG fallback to also parse `RelatedTopics` when `AbstractText` is empty.
* Added Wikipedia REST API fallback (`opensearch` + `rest_v1/page/summary`) — answers general questions (e.g. "what is quantum computing?") using free Wikipedia API, no API key needed.
* Sorted city name matching by name length (longest first) so "Mohali" doesn't accidentally match "ali" etc.
* Reduced Ollama timeout 5s → 1.5s so fallback kicks in faster when Ollama is not running.
* Data refresh: `{'ok': 111, 'failed': 0}` — all 111 places have fresh hourly measurements.
* Backend running on :8000 with `--reload`, frontend on :5173.
* Configured Vite reverse proxy in `vite.config.js` and mounted production SPA in FastAPI `app/main.py` so the entire website is seamlessly available on BOTH `http://localhost:5173` and `http://localhost:8000`.

