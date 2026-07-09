from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.calculations.merton import solve_merton
from app.database import get_db
from app.schemas.bond import (
    AlertCreate,
    AlertOut,
    AlertTriggered,
    BondDetail,
    BondRow,
    CurveResponse,
    DashboardSummary,
    MertonDetail,
    MertonRequest,
    ScreenRequest,
    SearchResult,
)
from app.services import alert_service, bond_service, curve_service, dashboard_service, screen_service, search_service

router = APIRouter(prefix="/api")


@router.get("/bonds", response_model=list[BondRow])
def list_bonds(db: Session = Depends(get_db)) -> list[BondRow]:
    return dashboard_service.get_bonds_cached(db)


@router.get("/bond/{cusip}", response_model=BondDetail)
def bond_detail(cusip: str, db: Session = Depends(get_db)) -> BondDetail:
    detail = bond_service.get_bond_detail(db, cusip.upper())
    if detail is None:
        raise HTTPException(status_code=404, detail=f"Bond {cusip} not found")
    return detail


@router.get("/dashboard", response_model=DashboardSummary)
def dashboard(db: Session = Depends(get_db)) -> DashboardSummary:
    summary = dashboard_service.get_dashboard(db)
    if summary is None:
        raise HTTPException(status_code=503, detail="No data loaded — run the seed script")
    return summary


@router.get("/curves", response_model=CurveResponse)
def curves(as_of: date | None = None, db: Session = Depends(get_db)) -> CurveResponse:
    curve = curve_service.get_curve(db, as_of)
    if curve is None:
        raise HTTPException(status_code=404, detail="No curve data")
    return curve


@router.get("/curves/history")
def curve_history(
    tenors: str = Query(default="2,5,10,30"), db: Session = Depends(get_db)
) -> list[dict]:
    tenor_list = [float(t) for t in tenors.split(",") if t.strip()]
    return curve_service.get_curve_history(db, tenor_list)


@router.post("/merton", response_model=MertonDetail)
def merton(req: MertonRequest) -> MertonDetail:
    try:
        result = solve_merton(
            equity_value=req.equity_value,
            equity_volatility=req.equity_volatility,
            debt_face=req.debt_face,
            risk_free_rate=req.risk_free_rate,
            maturity=req.maturity,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return MertonDetail(
        asset_value=result.asset_value,
        asset_volatility=result.asset_volatility,
        distance_to_default=result.distance_to_default,
        default_probability=result.default_probability,
        equity_value=req.equity_value,
        equity_volatility=req.equity_volatility,
        debt_face=req.debt_face,
        risk_free_rate=req.risk_free_rate,
        maturity=req.maturity,
        converged=result.converged,
        iterations=result.iterations,
    )


@router.post("/screen", response_model=list[BondRow])
def screen(req: ScreenRequest, db: Session = Depends(get_db)) -> list[BondRow]:
    return screen_service.screen_bonds(db, req)


@router.get("/search", response_model=list[SearchResult])
def global_search(q: str = Query(min_length=1), db: Session = Depends(get_db)) -> list[SearchResult]:
    return search_service.search(db, q)


@router.get("/alerts", response_model=list[AlertOut])
def alerts(db: Session = Depends(get_db)) -> list[AlertOut]:
    return alert_service.list_alerts(db)


@router.post("/alerts", response_model=AlertOut, status_code=201)
def create_alert(payload: AlertCreate, db: Session = Depends(get_db)) -> AlertOut:
    valid_types = {
        "becomes_cheap", "becomes_rich", "spread_widens",
        "spread_tightens", "pd_spike", "liquidity_drop",
    }
    if payload.alert_type not in valid_types:
        raise HTTPException(status_code=422, detail=f"alert_type must be one of {sorted(valid_types)}")
    if not payload.cusip and not payload.ticker:
        raise HTTPException(status_code=422, detail="Provide cusip or ticker")
    return alert_service.create_alert(db, payload)


@router.delete("/alerts/{alert_id}", status_code=204)
def delete_alert(alert_id: int, db: Session = Depends(get_db)) -> None:
    if not alert_service.delete_alert(db, alert_id):
        raise HTTPException(status_code=404, detail="Alert not found")


@router.post("/alerts/evaluate", response_model=list[AlertTriggered])
def evaluate_alerts(db: Session = Depends(get_db)) -> list[AlertTriggered]:
    return alert_service.evaluate_alerts(db)
