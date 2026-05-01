from __future__ import annotations

from datetime import date as date_cls, datetime

import click
from flask import current_app
from flask.cli import with_appcontext

from .extensions import db
from .providers.api_football import ApiFootballProvider
from .services.analyze import analyze_day
from .services.ingest import ingest_fixtures
from .services.reconcile import reconcile_day
from .services.select import build_slate


def _provider(mock: bool = False) -> ApiFootballProvider:
    cfg = current_app.config
    if mock:
        from .providers.mock import MockProvider
        return MockProvider()
    if not cfg.get("RAPIDAPI_KEY"):
        raise click.ClickException("RAPIDAPI_KEY is not set in .env (or use --mock)")
    return ApiFootballProvider(
        base_url=cfg["API_FOOTBALL_BASE"],
        api_key=cfg["RAPIDAPI_KEY"],
        host=cfg["RAPIDAPI_HOST"],
    )


def _parse_date(s: str | None) -> date_cls:
    if not s:
        return date_cls.today()
    return datetime.strptime(s, "%Y-%m-%d").date()


@click.group()
def phy():
    """phy-analyzer commands."""


@phy.command("init-db")
@with_appcontext
def init_db():
    """Create all tables (no Alembic yet)."""
    db.create_all()
    click.echo("DB tables created.")


@phy.command("ingest")
@click.option("--date", "date_str", default=None, help="YYYY-MM-DD; defaults to today")
@click.option("--mock", is_flag=True, help="Use the in-memory mock provider (no API calls)")
@with_appcontext
def ingest_cmd(date_str: str | None, mock: bool):
    day = _parse_date(date_str)
    n = ingest_fixtures(_provider(mock=mock), day)
    click.echo(f"Ingested {n} fixtures for {day.isoformat()}")


@phy.command("analyze")
@click.option("--date", "date_str", default=None)
@click.option("--mock", is_flag=True, help="Use the in-memory mock provider (no API calls)")
@with_appcontext
def analyze_cmd(date_str: str | None, mock: bool):
    day = _parse_date(date_str)
    n = analyze_day(_provider(mock=mock), day)
    click.echo(f"Analyzed {n} fixtures for {day.isoformat()}")


@phy.command("select")
@click.option("--date", "date_str", default=None)
@with_appcontext
def select_cmd(date_str: str | None):
    day = _parse_date(date_str)
    cfg = current_app.config
    rows = build_slate(
        day,
        threshold=cfg["CONFIDENCE_THRESHOLD"],
        max_picks=cfg["MAX_DAILY_PICKS"],
        max_combined=cfg["MAX_COMBINED_ODDS"],
    )
    click.echo(f"Picked {len(rows)} selections for {day.isoformat()}:")
    for r in rows:
        click.echo(f"  #{r.rank}  fixture={r.fixture_id}  {r.market} @ {r.odds:.2f}  conf={r.confidence:.2%}")

@phy.command("reconcile")
@click.option("--date", "date_str", default=None)
@click.option("--mock", is_flag=True, help="Use the in-memory mock provider (no API calls)")
@with_appcontext
def reconcile_cmd(date_str: str | None, mock: bool):
    day = _parse_date(date_str)
    graded, skipped = reconcile_day(_provider(mock=mock), day)
    click.echo(f"Graded {graded} selections, skipped {skipped} (no FT yet) for {day.isoformat()}")


@phy.command("daily")
@click.option("--date", "date_str", default=None)
@click.option("--mock", is_flag=True, help="Use the in-memory mock provider (no API calls)")
@click.pass_context
def daily_cmd(ctx, date_str: str | None, mock: bool):
    """Run ingest + analyze + select in sequence."""
    ctx.invoke(ingest_cmd, date_str=date_str, mock=mock)
    ctx.invoke(analyze_cmd, date_str=date_str, mock=mock)
    ctx.invoke(select_cmd, date_str=date_str)


@phy.command("backtest")
@click.option("--from", "frm_str", required=True, help="YYYY-MM-DD inclusive")
@click.option("--to", "to_str", required=True, help="YYYY-MM-DD inclusive")
@click.option("--threshold", type=float, default=None, help="Override CONFIDENCE_THRESHOLD")
@click.option("--sweep", is_flag=True, help="Sweep threshold 0.55..0.85 step 0.05")
@click.option("--output", "out_path", default="var/backtests", help="Directory to write JSON report")
@click.option("--mock", is_flag=True, help="Use the in-memory mock provider (no API calls)")
@with_appcontext
def backtest_cmd(frm_str: str, to_str: str, threshold: float | None, sweep: bool, out_path: str, mock: bool):
    """Replay a date range and report hit-rate + ROI. Read-only; uses provider cache."""
    import json
    from pathlib import Path

    from .backtest.runner import run_backtest, sweep_threshold

    frm = _parse_date(frm_str)
    to = _parse_date(to_str)
    cfg = current_app.config
    provider = _provider(mock=mock)

    Path(out_path).mkdir(parents=True, exist_ok=True)
    stamp = f"{frm.isoformat()}_{to.isoformat()}"

    if sweep:
        thresholds = [round(0.55 + 0.05 * i, 2) for i in range(7)]
        reports = sweep_threshold(
            provider, frm, to,
            thresholds=thresholds,
            max_picks=cfg["MAX_DAILY_PICKS"], max_combined=cfg["MAX_COMBINED_ODDS"],
        )
        Path(f"{out_path}/sweep_{stamp}.json").write_text(
            json.dumps([r.to_dict() for r in reports], indent=2)
        )
        click.echo(f"{'threshold':>10}  {'picks':>6}  {'hit%':>6}  {'roi%':>7}")
        for r in reports:
            click.echo(f"{r.threshold:>10.2f}  {r.total_picks:>6}  "
                       f"{r.hit_rate*100:>5.1f}%  {r.roi_pct:>6.2f}%")
        best = max(reports, key=lambda r: (r.roi_pct, r.hit_rate))
        click.echo(f"\nBest threshold by ROI: {best.threshold} (ROI {best.roi_pct}%, hit {best.hit_rate*100:.1f}%)")
        return

    t = threshold if threshold is not None else cfg["CONFIDENCE_THRESHOLD"]
    report = run_backtest(
        provider, frm, to,
        threshold=t, max_picks=cfg["MAX_DAILY_PICKS"], max_combined=cfg["MAX_COMBINED_ODDS"],
    )
    Path(f"{out_path}/backtest_{stamp}_t{t}.json").write_text(json.dumps(report.to_dict(), indent=2))
    click.echo(
        f"{report.total_days} days, {report.total_picks} picks: "
        f"{report.won}W / {report.lost}L / {report.void}V  "
        f"hit={report.hit_rate*100:.1f}%  ROI={report.roi_pct}%"
    )


def register(app):
    app.cli.add_command(phy)
