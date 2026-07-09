"""Treasury curve retrieval."""

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.cache import cache_get, cache_set
from app.models import TreasuryYield
from app.schemas.bond import CurvePoint, CurveResponse


def latest_curve_date(db: Session) -> date | None:
    return db.scalar(select(func.max(TreasuryYield.as_of_date)))


def get_curve(db: Session, as_of: date | None = None) -> CurveResponse | None:
    as_of = as_of or latest_curve_date(db)
    if as_of is None:
        return None
    key = f"curve:{as_of.isoformat()}"
    cached = cache_get(key)
    if cached:
        return CurveResponse.model_validate(cached)

    points = db.scalars(
        select(TreasuryYield).where(TreasuryYield.as_of_date == as_of).order_by(TreasuryYield.tenor)
    ).all()
    if not points:
        return None
    resp = CurveResponse(
        as_of_date=as_of,
        points=[
            CurvePoint(tenor=p.tenor, tenor_label=p.tenor_label, par_yield=p.par_yield, zero_rate=p.zero_rate)
            for p in points
        ],
    )
    cache_set(key, resp.model_dump(mode="json"))
    return resp


def get_curve_history(db: Session, tenors: list[float]) -> list[dict]:
    """Time series of par yields for selected tenors (for curve animation)."""
    rows = db.execute(
        select(TreasuryYield.as_of_date, TreasuryYield.tenor, TreasuryYield.par_yield)
        .where(TreasuryYield.tenor.in_(tenors))
        .order_by(TreasuryYield.as_of_date)
    ).all()
    by_date: dict[date, dict] = {}
    for as_of, tenor, y in rows:
        by_date.setdefault(as_of, {"as_of_date": as_of.isoformat()})[f"y{tenor:g}"] = y
    return list(by_date.values())
