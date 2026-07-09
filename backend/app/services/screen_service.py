"""Screening: filter and sort the bond universe."""

from datetime import date

from sqlalchemy.orm import Session

from app.schemas.bond import BondRow, ScreenRequest
from app.services.dashboard_service import get_bonds_cached

SORTABLE = {
    "rv_score", "residual", "observed_spread", "z_spread", "g_spread", "oas", "ytm",
    "price", "duration", "convexity", "liquidity_score", "merton_pd", "market_implied_pd",
    "coupon", "maturity_date", "rv_percentile", "issuer", "ticker", "rating",
}


def screen_bonds(db: Session, req: ScreenRequest) -> list[BondRow]:
    rows = get_bonds_cached(db)
    today = date.today()

    def keep(r: BondRow) -> bool:
        if req.sectors and r.sector not in req.sectors:
            return False
        if req.industries and r.industry not in req.industries:
            return False
        if req.ratings and r.rating not in req.ratings:
            return False
        if req.tickers and r.ticker not in req.tickers:
            return False
        if req.min_duration is not None and r.duration < req.min_duration:
            return False
        if req.max_duration is not None and r.duration > req.max_duration:
            return False
        spread_bps = r.observed_spread * 10_000
        if req.min_spread_bps is not None and spread_bps < req.min_spread_bps:
            return False
        if req.max_spread_bps is not None and spread_bps > req.max_spread_bps:
            return False
        if req.min_yield is not None and r.ytm < req.min_yield:
            return False
        if req.max_yield is not None and r.ytm > req.max_yield:
            return False
        if req.min_liquidity is not None and r.liquidity_score < req.min_liquidity:
            return False
        if req.max_pd is not None and r.merton_pd > req.max_pd:
            return False
        if req.rv_labels and r.rv_label not in req.rv_labels:
            return False
        years = (r.maturity_date - today).days / 365.25
        if req.min_maturity_years is not None and years < req.min_maturity_years:
            return False
        if req.max_maturity_years is not None and years > req.max_maturity_years:
            return False
        return True

    filtered = [r for r in rows if keep(r)]
    sort_key = req.sort_by if req.sort_by in SORTABLE else "rv_score"
    filtered.sort(key=lambda r: getattr(r, sort_key), reverse=req.sort_dir == "desc")
    return filtered[: req.limit]
