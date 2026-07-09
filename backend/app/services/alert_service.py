"""Alert CRUD and evaluation against the two most recent metric snapshots."""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Alert, Bond, BondMetricsDaily
from app.schemas.bond import AlertCreate, AlertOut, AlertTriggered
from app.services.bond_service import latest_metrics_date


def create_alert(db: Session, payload: AlertCreate) -> AlertOut:
    alert = Alert(
        cusip=payload.cusip,
        ticker=payload.ticker,
        alert_type=payload.alert_type,
        threshold=payload.threshold,
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return AlertOut.model_validate(alert)


def list_alerts(db: Session) -> list[AlertOut]:
    alerts = db.scalars(select(Alert).order_by(Alert.created_at.desc())).all()
    return [AlertOut.model_validate(a) for a in alerts]


def delete_alert(db: Session, alert_id: int) -> bool:
    alert = db.get(Alert, alert_id)
    if alert is None:
        return False
    db.delete(alert)
    db.commit()
    return True


def _cusips_for_alert(db: Session, alert: Alert) -> list[str]:
    if alert.cusip:
        return [alert.cusip]
    if alert.ticker:
        rows = db.execute(
            select(Bond.cusip).join(Bond.issuer).where(Bond.issuer.has(ticker=alert.ticker))
        ).all()
        return [r[0] for r in rows]
    return []


def evaluate_alerts(db: Session) -> list[AlertTriggered]:
    """Compare latest snapshot vs prior snapshot for each watched bond."""
    latest = latest_metrics_date(db)
    if latest is None:
        return []
    dates = db.execute(
        select(BondMetricsDaily.as_of_date)
        .distinct()
        .order_by(BondMetricsDaily.as_of_date.desc())
        .limit(2)
    ).all()
    prior = dates[1][0] if len(dates) > 1 else None

    triggered: list[AlertTriggered] = []
    alerts = db.scalars(select(Alert).where(Alert.active)).all()
    for alert in alerts:
        for cusip in _cusips_for_alert(db, alert):
            now = db.scalar(
                select(BondMetricsDaily).where(
                    BondMetricsDaily.cusip == cusip, BondMetricsDaily.as_of_date == latest
                )
            )
            if now is None:
                continue
            prev = (
                db.scalar(
                    select(BondMetricsDaily).where(
                        BondMetricsDaily.cusip == cusip, BondMetricsDaily.as_of_date == prior
                    )
                )
                if prior
                else None
            )
            message = _check(alert, now, prev)
            if message:
                alert.last_triggered_at = datetime.now(timezone.utc)
                alert.last_message = message
                triggered.append(
                    AlertTriggered(
                        alert_id=alert.id, cusip=cusip, ticker=alert.ticker,
                        alert_type=alert.alert_type, message=message,
                    )
                )
    db.commit()
    return triggered


def _check(alert: Alert, now: BondMetricsDaily, prev: BondMetricsDaily | None) -> str | None:
    t = alert.alert_type
    if t == "becomes_cheap" and now.rv_label == "cheap" and (prev is None or prev.rv_label != "cheap"):
        return f"{now.cusip} flagged CHEAP (RV z={now.rv_score:.2f})"
    if t == "becomes_rich" and now.rv_label == "rich" and (prev is None or prev.rv_label != "rich"):
        return f"{now.cusip} flagged RICH (RV z={now.rv_score:.2f})"
    if prev is not None:
        spread_move_bps = (now.observed_spread - prev.observed_spread) * 10_000
        if t == "spread_widens" and spread_move_bps >= alert.threshold:
            return f"{now.cusip} spread widened {spread_move_bps:.0f}bps"
        if t == "spread_tightens" and -spread_move_bps >= alert.threshold:
            return f"{now.cusip} spread tightened {-spread_move_bps:.0f}bps"
        pd_move = (now.merton_pd - prev.merton_pd) * 100
        if t == "pd_spike" and pd_move >= alert.threshold:
            return f"{now.cusip} PD spiked +{pd_move:.2f}pp to {now.merton_pd * 100:.2f}%"
        liq_drop = prev.liquidity_score - now.liquidity_score
        if t == "liquidity_drop" and liq_drop >= alert.threshold:
            return f"{now.cusip} liquidity dropped {liq_drop:.0f}pts to {now.liquidity_score:.0f}"
    return None
