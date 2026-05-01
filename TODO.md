# phy-analyzer — Implementation TODO

Track progress with checkboxes. Each phase ends with a passing test or runnable demo.

## Phase 0 — Scaffold
- [x] `README.md` with architecture, API contract, model design
- [x] `TODO.md` (this file)
- [ ] `requirements.txt`, `.env.example`, `.gitignore`, `wsgi.py`
- [ ] `app/__init__.py` factory + `app/config.py`
- [ ] `app/extensions.py` (db, migrate, scheduler, cache, cors)
- [ ] Bare `flask --app wsgi run` boots and `/healthz` returns 200
- [ ] Pre-commit: black, ruff, isort

## Phase 1 — Data ingestion
- [x] `providers/base.py` defining `DataProvider` interface (fixtures, stats, h2h, odds, scores)
- [x] `providers/api_football.py` — RapidAPI client with retry/backoff and per-day caching
- [x] SQLAlchemy models: `League`, `Team`, `Fixture`, `TeamStatsSnapshot`, `H2H`, `Odds`
- [x] CLI: `flask ingest fixtures --date=YYYY-MM-DD` populates DB
- [x] Unit tests with recorded HTTP cassettes (vcrpy/responses)

> **Phase 1 status:** code complete; awaiting end-to-end smoke run.

## Phase 2 — Analyzer
- [x] `analyzer/form.py` rolling form & xG aggregation per team
- [x] `analyzer/poisson.py` Dixon–Coles fit + score-matrix predictor
- [x] `analyzer/markets.py` derive 1, X, 2, 12, O1.5, U3.5 probabilities from score matrix
- [x] `analyzer/pipeline.py` run end-to-end for a fixture → `Prediction` row
- [x] CLI: `flask --app wsgi phy analyze --date=YYYY-MM-DD`
- [x] Backtest harness (`app/backtest/runner.py`) with `--sweep` threshold calibration
- [x] Provider disk cache to make backtests & reruns free
- [ ] Run live sweep on 60–90 days of data and commit chosen threshold to `.env`

## Phase 3 — Daily selector
- [ ] `selector/daily.py` — pick ≤ 5 with combined odds ≤ 5.0, max confidence
- [ ] Persist to `Selection` table with `rank`, `status=pending`
- [ ] CLI: `flask select --date=YYYY-MM-DD`

## Phase 4 — REST API
- [ ] `api/analyzer.py`     → `GET /api/v1/matches`     (paginated 20/page)
- [ ] `api/selections.py`   → `GET /api/v1/selections`
- [ ] `api/history.py`      → `GET /api/v1/history`
- [ ] CORS for `http://localhost:3000`
- [ ] OpenAPI doc via `apispec` or `flask-smorest`

## Phase 5 — Scheduling
- [x] APScheduler jobs in `app/jobs/scheduler.py`
- [x] Cron @ 00:05 `build_daily_slate` (today-in-TZ)
- [x] Cron hourly `refresh_predictions`
- [x] Cron @ 23:59 `reconcile_results` (today + yesterday for late kickoffs)
- [x] Gated behind `SCHEDULER_ENABLED=1` so dev reload doesn't trigger jobs
- [x] All jobs idempotent and safe to re-run (upsert semantics throughout)

## Phase 6 — Backtesting
- [ ] `scripts/backtest.py --from --to` replays history through the pipeline
- [ ] Reports: hit-rate per market, ROI, calibration curve, Brier score
- [ ] Tune `CONFIDENCE_THRESHOLD` from backtest (don't hardcode)

## Phase 7 — Production
- [ ] Switch to Postgres + Alembic migrations
- [ ] Dockerfile + docker-compose (web, worker-cron, db)
- [ ] Gunicorn + Nginx config
- [ ] Sentry + structured logging (structlog)
- [ ] Deploy target decided (Fly.io / Railway / VPS)

## Stretch
- [ ] LLM narrative explainer endpoint: `POST /api/v1/explain` returns a 2-sentence reasoning per pick using the model outputs (no LLM in the prediction path itself).
- [ ] Bookmaker-line scraper for Bet9ja / Sportybet to compare model odds vs offered odds (value bets).
- [ ] Telegram/WhatsApp daily digest of the 5 picks at 06:00.
- [ ] Bankroll/Kelly sizing per pick.
