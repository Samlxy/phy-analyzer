from __future__ import annotations

"""APScheduler wiring — Phase 5.

Three jobs, all scoped to the app's configured TIMEZONE:
  • build_daily_slate   @ 00:05  — ingest + analyze + select for today
  • refresh_predictions @ every hour — re-run analyze so odds/probs stay fresh
  • reconcile_results   @ 23:59  — grade pending selections via provider.final_score

Implementation notes:
- BackgroundScheduler is used (not AsyncIO) because Flask runs sync.
- Jobs are registered with `replace_existing=True` so reloads during dev don't duplicate.
- Each job opens its own `app.app_context()` because APScheduler threads have none.
- If `SCHEDULER_ENABLED` is false (default under tests / CLI invocations), nothing starts.
"""

import logging
from datetime import date, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

log = logging.getLogger(__name__)


def _provider(app):
    from ..providers.api_football import ApiFootballProvider
    cfg = app.config
    return ApiFootballProvider(
        base_url=cfg["API_FOOTBALL_BASE"],
        api_key=cfg["RAPIDAPI_KEY"],
        host=cfg["RAPIDAPI_HOST"],
    )


def build_daily_slate(app) -> None:
    """Ingest + analyze + select for today in the app's timezone."""
    from ..services.analyze import analyze_day
    from ..services.ingest import ingest_fixtures
    from ..services.select import build_slate

    with app.app_context():
        today = date.today()
        log.info("scheduler: build_daily_slate start date=%s", today)
        try:
            provider = _provider(app)
            n_ing = ingest_fixtures(provider, today)
            n_ana = analyze_day(provider, today)
            slate = build_slate(
                today,
                threshold=app.config["CONFIDENCE_THRESHOLD"],
                max_picks=app.config["MAX_DAILY_PICKS"],
                max_combined=app.config["MAX_COMBINED_ODDS"],
            )
            log.info("scheduler: build_daily_slate done ingested=%d analyzed=%d picks=%d",
                     n_ing, n_ana, len(slate))
        except Exception:
            log.exception("scheduler: build_daily_slate failed")


def refresh_predictions(app) -> None:
    """Re-run analyze so odds/probabilities stay fresh through the day."""
    from ..services.analyze import analyze_day

    with app.app_context():
        today = date.today()
        try:
            n = analyze_day(_provider(app), today)
            log.info("scheduler: refresh_predictions analyzed=%d", n)
        except Exception:
            log.exception("scheduler: refresh_predictions failed")


def reconcile_results(app) -> None:
    """Grade pending selections for today and yesterday (late kickoffs span midnight)."""
    from ..services.reconcile import reconcile_day

    with app.app_context():
        try:
            provider = _provider(app)
            for day in (date.today(), date.today() - timedelta(days=1)):
                graded, skipped = reconcile_day(provider, day)
                log.info("scheduler: reconcile %s graded=%d skipped=%d", day, graded, skipped)
        except Exception:
            log.exception("scheduler: reconcile_results failed")


def init_scheduler(app) -> BackgroundScheduler | None:
    if not app.config.get("SCHEDULER_ENABLED"):
        return None
    if not app.config.get("RAPIDAPI_KEY"):
        log.warning("scheduler: RAPIDAPI_KEY missing; skipping startup")
        return None

    tz = app.config.get("TIMEZONE", "UTC")
    sched = BackgroundScheduler(timezone=tz)

    sched.add_job(
        build_daily_slate, CronTrigger(hour=0, minute=5, timezone=tz),
        args=[app], id="build_daily_slate", replace_existing=True,
    )
    sched.add_job(
        refresh_predictions, CronTrigger(minute=0, timezone=tz),
        args=[app], id="refresh_predictions", replace_existing=True,
    )
    sched.add_job(
        reconcile_results, CronTrigger(hour=23, minute=59, timezone=tz),
        args=[app], id="reconcile_results", replace_existing=True,
    )

    sched.start()
    log.info("scheduler: started with tz=%s jobs=%s", tz, [j.id for j in sched.get_jobs()])
    app.extensions["apscheduler"] = sched
    return sched
