# phy-analyzer — Backend

Flask + Python service that ingests daily fixtures from **API-Football (RapidAPI)**, runs a statistical/AI prediction pipeline across the configured popular markets, and exposes a JSON API consumed by the `pro-analyzer` Next.js frontend.

> Sister repo: [`pro-analyzer`](../pro-analyzer) (Next.js / React frontend).

Enter Virtual Environment
```bash
source venv/bin/activate
```

Run Flask development server
```bash
flask --app wsgi run --debug
```
---

## 1. What this service does

1. **Ingest** — every day at **00:00 Africa/Lagos** (and on a refresh cron during the day) fetch all fixtures, team form, H2H, injuries, and odds for the day.
2. **Analyze** — for every match, compute a probability for each of the supported markets:
   - `1` — Home win
   - `X` — Draw
   - `2` — Away win
   - `12` — Either team wins (no draw)
   - `O1.5` — Over 1.5 goals
   - `U3.5` — Under 3.5 goals
3. **Rank & select** — pick the daily slate (≤ 5 selections) whose **combined odds ≤ 5.0** and whose **individual confidence is highest**, optimizing total expected value while respecting the cap.
4. **Reconcile** — at end of day, fetch final scores and grade each pick as `won / lost / void`.
5. **Serve** — three REST endpoints power the three frontend tables (analyzer, daily-picks, history).

---

## 2. Architecture

```
                ┌────────────────────────┐
                │  API-Football (RapidAPI)│
                └───────────┬────────────┘
                            │ HTTPS
                            ▼
  ┌──────────────────────────────────────────────────┐
  │                  phy-analyzer                    │
  │                                                  │
  │  ┌──────────┐  ┌────────────┐  ┌──────────────┐  │
  │  │ ingest/  │─▶│ analyzer/  │─▶│ selector/    │  │
  │  │ provider │  │ (poisson + │  │ (≤5 picks,   │  │
  │  │  client  │  │  form/xG)  │  │  odds ≤ 5)   │  │
  │  └──────────┘  └────────────┘  └──────┬───────┘  │
  │       │              │                │          │
  │       ▼              ▼                ▼          │
  │  ┌─────────────────────────────────────────┐    │
  │  │        SQLite / Postgres (SQLAlchemy)    │    │
  │  └─────────────────────────────────────────┘    │
  │                                                  │
  │  ┌──────────────────────────────────────────┐   │
  │  │  Flask blueprints  →  /api/v1/...        │   │
  │  └──────────────────────────────────────────┘   │
  │                                                  │
  │  APScheduler jobs: 00:00 build, hourly refresh, │
  │                    23:59 reconcile               │
  └──────────────────────────────────────────────────┘
                            │
                            ▼
                     pro-analyzer (Next.js)
```

### Folder layout (target)

```
phy-analyzer/
├── app/
│   ├── __init__.py            # create_app() factory
│   ├── config.py              # env-driven config
│   ├── extensions.py          # db, scheduler, cache
│   ├── models/                # SQLAlchemy models
│   │   ├── fixture.py
│   │   ├── prediction.py
│   │   └── selection.py
│   ├── providers/
│   │   ├── base.py            # DataProvider interface
│   │   └── api_football.py    # RapidAPI implementation
│   ├── analyzer/
│   │   ├── poisson.py         # Dixon-Coles / bivariate Poisson
│   │   ├── form.py            # rolling form, xG, home/away splits
│   │   ├── markets.py         # map probs → 1/X/2/12/O1.5/U3.5
│   │   └── pipeline.py        # orchestration per fixture
│   ├── selector/
│   │   └── daily.py           # pick ≤5 with combined odds ≤ 5
│   ├── reconciler/
│   │   └── grader.py          # win/loss/void from final scores
│   ├── api/
│   │   ├── analyzer.py        # GET /api/v1/matches?date=...&page=...
│   │   ├── selections.py      # GET /api/v1/selections?date=...
│   │   └── history.py         # GET /api/v1/history?from=...&to=...
│   └── jobs/
│       └── scheduler.py       # APScheduler registrations
├── tests/
├── migrations/
├── .env.example
├── requirements.txt
├── wsgi.py
├── README.md
└── TODO.md
```

---

## 3. Prediction model (v1)

**Goal:** rigorous, explainable, no “magic LLM”. AI-driven means *data-driven statistical inference*; we may add an LLM layer later for narrative explanations only.

### Inputs (per fixture)
- Last N (default 10) matches per side, weighted exponentially (recent weighs more).
- Home/away splits.
- Goals for / against, shots, shots-on-target, xG (where API-Football provides it).
- H2H last 5.
- Injuries / suspensions count for key positions.
- League baseline goal averages (home/away) for context.

### Core: Dixon–Coles adjusted Poisson
- Estimate attack & defense strengths per team via MLE on rolling window.
- Predict expected goals λ_home, λ_away.
- Build the score matrix → derive 1X2 probabilities and over/under probabilities analytically.
- Apply Dixon–Coles low-score correlation correction.

### Market probabilities
| Market | Formula |
|---|---|
| `1` | Σ P(i,j) for i>j |
| `X` | Σ P(i,i) |
| `2` | Σ P(i,j) for j>i |
| `12` | 1 − P(X) |
| `O1.5` | 1 − P(0,0) − P(1,0) − P(0,1) |
| `U3.5` | Σ P(i,j) for i+j ≤ 3 |

### Confidence score
`confidence = model_prob × calibration_factor − implied_prob_from_odds_gap_penalty`

We keep only picks where `confidence ≥ THRESHOLD` (env-tunable, default 0.62) and (optionally) the **bookmaker implied probability is meaningfully lower** (positive expected value).

### Daily selector (≤ 5 odds total)
Greedy + branch-and-bound:
1. Filter picks with confidence ≥ threshold.
2. Sort by confidence desc.
3. Iteratively add picks while `Π odds ≤ 5.0` and `count ≤ 5`.
4. Tie-break by lowest variance (prefer Under 3.5 / 12 over riskier 1/2 when comparable).

---

## 4. API contract (consumed by frontend)

All responses: `application/json`. All times: ISO-8601 UTC.

### `GET /api/v1/matches`
Query: `date=YYYY-MM-DD` (default today, Africa/Lagos), `page=1`, `page_size=20`.
```json
{
  "date": "2026-05-01",
  "page": 1,
  "page_size": 20,
  "total": 137,
  "items": [
    {
      "fixture_id": 1182733,
      "league": {"id": 39, "name": "Premier League", "country": "England", "logo": "..."},
      "kickoff": "2026-05-01T14:00:00Z",
      "home": {"name": "Arsenal", "logo": "..."},
      "away": {"name": "Chelsea", "logo": "..."},
      "markets": {
        "1":     {"prob": 0.58, "odds": 1.85, "pick": true},
        "X":     {"prob": 0.23, "odds": 3.60, "pick": false},
        "2":     {"prob": 0.19, "odds": 4.20, "pick": false},
        "12":    {"prob": 0.77, "odds": 1.28, "pick": false},
        "O1.5":  {"prob": 0.84, "odds": 1.22, "pick": false},
        "U3.5":  {"prob": 0.71, "odds": 1.45, "pick": false}
      },
      "best_market": "1",
      "confidence": 0.74
    }
  ]
}
```

### `GET /api/v1/selections`
Query: `date=YYYY-MM-DD` (default today).
```json
{
  "date": "2026-05-01",
  "combined_odds": 4.62,
  "stake_suggestion_pct": 100,
  "items": [
    {
      "rank": 1,
      "fixture_id": 1182733,
      "match": "Arsenal vs Chelsea",
      "league": "Premier League",
      "kickoff": "2026-05-01T14:00:00Z",
      "market": "O1.5",
      "odds": 1.22,
      "confidence": 0.86,
      "status": "pending"
    }
  ]
}
```

### `GET /api/v1/history`
Query: `from=YYYY-MM-DD&to=YYYY-MM-DD&page=1&page_size=20`.
```json
{
  "items": [
    {
      "date": "2026-04-30",
      "fixture_id": 118260,
      "match": "Real Madrid vs Sevilla",
      "market": "1",
      "odds": 1.40,
      "confidence": 0.81,
      "predicted": "1",
      "actual_score": "3-1",
      "result": "won"
    }
  ],
  "summary": {
    "total": 142, "won": 96, "lost": 41, "void": 5,
    "hit_rate": 0.676, "roi_pct": 18.4
  }
}
```

---

## 5. Tech stack

- **Python 3.11+**
- **Flask 3** + **Flask-SQLAlchemy** + **Flask-Migrate**
- **APScheduler** (in-process cron) — graduate to Celery/Redis if it outgrows
- **httpx** for the API-Football client (async-friendly)
- **numpy / scipy** for Poisson math
- **pandas** for stats wrangling
- **pydantic** for response schemas
- **pytest** + **responses** for testing
- **SQLite** locally, **Postgres** in production
- **Flask-Cors** for the Next.js dev origin

---

## 6. Setup

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # fill in RAPIDAPI_KEY
flask --app wsgi db upgrade
flask --app wsgi run --debug
```

Environment variables (see `.env.example`):

| Name | Description |
|---|---|
| `FLASK_ENV` | `development` / `production` |
| `DATABASE_URL` | SQLAlchemy URL |
| `RAPIDAPI_KEY` | API-Football key from RapidAPI |
| `RAPIDAPI_HOST` | `api-football-v1.p.rapidapi.com` |
| `TIMEZONE` | `Africa/Lagos` |
| `CONFIDENCE_THRESHOLD` | default `0.62` |
| `MAX_DAILY_PICKS` | default `5` |
| `MAX_COMBINED_ODDS` | default `5.0` |

---

## 7. Implementation phases

See [`TODO.md`](./TODO.md). High-level:

1. **Phase 0** — repo scaffolding, env, CI lint.
2. **Phase 1** — API-Football client + fixtures ingest + DB models.
3. **Phase 2** — Poisson analyzer + market mapping + tests on fixtures from real past days.
4. **Phase 3** — Daily selector (≤5, odds ≤ 5).
5. **Phase 4** — REST API for the three tables.
6. **Phase 5** — Scheduler (00:00 build, hourly refresh, 23:59 reconcile).
7. **Phase 6** — Backtesting harness (replay last 90 days, measure hit-rate, calibrate threshold).
8. **Phase 7** — Production hardening (Postgres, Sentry, Docker, deploy).

---

## 8. Honest disclaimer

No model produces “sure odds”. The selector caps risk by:
- Capping combined odds at 5.0 (never chasing huge accumulators).
- Preferring high-prob markets (Over 1.5, 12, Under 3.5) over coinflip 1X2 when confidence is similar.
- Backtest-calibrated thresholds, not gut feel.

This is a tool to **inform** bets, not guarantee them. Bet responsibly.
