# Credit Relative Value Dashboard - Built by Dante Zerega

Institutional credit analytics platform: identifies corporate bonds trading **rich or cheap**
relative to their implied default risk by combining TRACE trade data, treasury curves,
issuer financials, equity market data, and a **Merton structural credit model**.

![stack](https://img.shields.io/badge/stack-React%2019%20·%20FastAPI%20·%20PostgreSQL%20·%20Redis-informational)

## How the RV score works

```
Fair spread = default component (Merton PD × LGD, constant-hazard)
            + liquidity premium (from TRACE liquidity score)
            + sector premium
            + rating premium

Residual    = observed Z-spread − fair spread
RV score    = cross-sectional z-score of residual
Signal      = cheap (z ≥ +0.75) · rich (z ≤ −0.75) · fair
```

The Merton model solves the two-equation system for unobservable firm asset value
and asset volatility (KMV-style iteration), yielding distance-to-default and a
risk-neutral PD per issuer per day.

## Quick start (Docker)

```bash
docker compose up -d --build        # postgres + redis + backend + frontend
docker compose run --rm seed        # generate synthetic universe (~1 min)
open http://localhost:8080
```

## Local development

```bash
# backend
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
docker compose up -d postgres redis
.venv/bin/python -m app.seed                       # seed database
.venv/bin/uvicorn app.main:app --reload            # http://localhost:8000/docs

# frontend
cd frontend
npm install
npm run dev                                        # http://localhost:5173 (proxies /api)
```

No Postgres handy? SQLite works for local dev:
`DASH_DATABASE_URL=sqlite:////tmp/dash.db .venv/bin/python -m app.seed` (same var for uvicorn).

## Tests

```bash
cd backend && .venv/bin/python -m pytest tests/ -v
```

Covers the Merton solver, treasury bootstrap/interpolation, bond math
(price/yield/duration/convexity/Z-spread/OAS), TRACE processing, and the RV engine.

## Data — two modes

### Real data (free, no API keys)

```bash
docker compose run --rm load-real          # or locally: python -m app.load_real
```

Everything with a free source is REAL; feeds that are licensed-only are DEMO data
generated *around* the real data and processed by the real pipeline:

| Data | Mode | Source / method |
|---|---|---|
| Treasury par + zero curves | **REAL** | home.treasury.gov daily CSV, ~1.5y history |
| Bond universe, coupons, maturities | **REAL** | SPDR ETF daily holdings (SPBO IG, SPHY HY) |
| Today's bond prices + spreads | **REAL** | ETF market value / par |
| Equity, vol, beta, fundamentals | **REAL** | Yahoo Finance, 1y history + balance sheet |
| Merton PD / DD history | **REAL** | real equity path × real daily treasury curves |
| Credit ratings | **REAL-derived** | market-implied from the bond's real spread (no free ratings feed) |
| TRACE trade tape | **DEMO** | synthetic prints around real prices, intensity from real position size; real TRACE module computes VWAP/bid-ask/liquidity/staleness from it |
| Bond spread history | **DEMO** | mean-reverting path anchored to END exactly at today's real spread, discounted on each day's real curve. Today's row is fully real |

Historical bond prices are licensed-only, so the past starts as demo backfill
(`--history-days`, default 90). Schedule `python -m app.load_real --update` daily
(cron) and real days accumulate, replacing demo over time — prior days are never
overwritten. Issuer-name→ticker resolution is cached in `backend/.cache/ticker_map.json`.

### Synthetic demo data (instant history)

The seed script (`backend/app/seed.py`) generates a deterministic synthetic universe —
40 issuers, ~145 bonds, ~130 business days of treasury curves, equity paths, and
TRACE-style prints — and runs the full analytics pipeline for every bond-day. Use it
to see all charts populated with history immediately.

## API

| Endpoint | Description |
|---|---|
| `GET /api/bonds` | Full universe with latest analytics |
| `GET /api/bond/{cusip}` | Detail: history, Merton, decomposition, cashflows, TRACE stats |
| `GET /api/dashboard` | Summary stats + top cheap/rich |
| `GET /api/curves` · `/api/curves/history` | Bootstrapped treasury zero/par curves |
| `POST /api/merton` | Ad-hoc Merton solve |
| `POST /api/screen` | Server-side screening |
| `GET /api/search?q=` | Global search (CUSIP / ticker / issuer / description) |
| `GET·POST·DELETE /api/alerts` · `POST /api/alerts/evaluate` | Alert management |

Interactive docs at `http://localhost:8000/docs`.

## UI keyboard shortcuts

`⌘K` or `/` search · `f` toggle filters · `g d` monitor · `g a` analytics · `g l` alerts

## Architecture

```
backend/app/
  calculations/   pure, reusable quant modules (merton, bond, treasury, trace, relative_value)
  models/         SQLAlchemy entities
  schemas/        Pydantic API contracts
  services/       query + assembly layer (Redis-cached)
  api/            FastAPI routes
  seed.py         synthetic data generator + pipeline runner
frontend/src/
  api/            typed client
  store/          Zustand (filters, UI)
  hooks/          TanStack Query wrappers, screening, shortcuts
  components/     table, filters, search palette, layout
  charts/         Recharts panels (history, curve, scatter, decomposition, cashflows)
  pages/          Monitor, Bond Detail, Analytics, Alerts
```

Designed for extension: hazard-curve/CDS pricers and OAS lattice models slot into
`calculations/`, new columns flow through `BondMetricsDaily` → `BondRow`, and live
updates can attach via a WebSocket route without touching the calculation layer.

## Author

**Dante Zerega** — design, models, and implementation.