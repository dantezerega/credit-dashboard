"""Dashboard aggregation with Redis caching."""

from datetime import date

from sqlalchemy.orm import Session

from app.cache import cache_get, cache_set
from app.schemas.bond import BondRow, DashboardSummary
from app.services.bond_service import get_all_bond_rows, latest_metrics_date

CACHE_KEY = "dashboard:summary"


def get_dashboard(db: Session) -> DashboardSummary | None:
    cached = cache_get(CACHE_KEY)
    if cached:
        return DashboardSummary.model_validate(cached)

    as_of = latest_metrics_date(db)
    if as_of is None:
        return None
    rows = get_all_bond_rows(db, as_of)
    if not rows:
        return None

    by_score = sorted(rows, key=lambda r: r.rv_score, reverse=True)
    summary = DashboardSummary(
        as_of_date=as_of,
        bond_count=len(rows),
        cheap_count=sum(1 for r in rows if r.rv_label == "cheap"),
        rich_count=sum(1 for r in rows if r.rv_label == "rich"),
        fair_count=sum(1 for r in rows if r.rv_label == "fair"),
        avg_spread_bps=sum(r.observed_spread for r in rows) / len(rows) * 10_000,
        avg_rv_score=sum(r.rv_score for r in rows) / len(rows),
        stale_count=sum(1 for r in rows if r.is_stale),
        top_cheap=by_score[:5],
        top_rich=by_score[-5:][::-1],
    )
    cache_set(CACHE_KEY, summary.model_dump(mode="json"))
    return summary


def get_bonds_cached(db: Session) -> list[BondRow]:
    cached = cache_get("bonds:all")
    if cached:
        return [BondRow.model_validate(r) for r in cached]
    rows = get_all_bond_rows(db)
    cache_set("bonds:all", [r.model_dump(mode="json") for r in rows])
    return rows
