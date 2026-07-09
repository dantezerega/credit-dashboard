"""Global search across CUSIPs, tickers, issuer names, and bond descriptions."""

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, joinedload

from app.models import Bond, BondMetricsDaily, Issuer
from app.schemas.bond import SearchResult
from app.services.bond_service import latest_metrics_date


def search(db: Session, query: str, limit: int = 20) -> list[SearchResult]:
    q = query.strip()
    if not q:
        return []
    pattern = f"%{q}%"

    results: list[SearchResult] = []

    issuers = db.scalars(
        select(Issuer)
        .where(or_(Issuer.ticker.ilike(pattern), Issuer.name.ilike(pattern)))
        .limit(limit)
    ).all()
    for issuer in issuers:
        results.append(
            SearchResult(
                kind="issuer", ticker=issuer.ticker, issuer=issuer.name,
                description=f"{issuer.sector} · {issuer.rating}",
            )
        )

    as_of = latest_metrics_date(db)
    labels: dict[str, str] = {}
    bonds = db.scalars(
        select(Bond)
        .options(joinedload(Bond.issuer))
        .where(
            or_(
                Bond.cusip.ilike(pattern),
                Bond.description.ilike(pattern),
                Bond.issuer.has(or_(Issuer.ticker.ilike(pattern), Issuer.name.ilike(pattern))),
            )
        )
        .limit(limit)
    ).all()
    if bonds and as_of:
        metrics = db.execute(
            select(BondMetricsDaily.cusip, BondMetricsDaily.rv_label).where(
                BondMetricsDaily.as_of_date == as_of,
                BondMetricsDaily.cusip.in_([b.cusip for b in bonds]),
            )
        ).all()
        labels = dict(metrics)
    for b in bonds:
        results.append(
            SearchResult(
                kind="bond", cusip=b.cusip, ticker=b.issuer.ticker, issuer=b.issuer.name,
                description=b.description, rv_label=labels.get(b.cusip),
            )
        )

    return results[:limit]
