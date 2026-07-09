"""Free equity + fundamentals source: Yahoo Finance via yfinance (no API key).

Provides: issuer-name -> ticker resolution (cached on disk), market cap,
realized volatility from 1y price history, beta, sector, shares outstanding,
balance sheet debt/cash, income statement summary, daily price history.
"""

import json
import logging
import math
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import yfinance as yf

logger = logging.getLogger(__name__)

CACHE_PATH = Path(__file__).resolve().parent.parent.parent / ".cache" / "ticker_map.json"

# Yahoo sector names -> premium table keys in calculations.relative_value
SECTOR_MAP = {
    "Technology": "Technology",
    "Communication Services": "Communications",
    "Healthcare": "Healthcare",
    "Financial Services": "Financials",
    "Consumer Cyclical": "Consumer Discretionary",
    "Consumer Defensive": "Consumer Staples",
    "Industrials": "Industrials",
    "Energy": "Energy",
    "Utilities": "Utilities",
    "Basic Materials": "Materials",
    "Real Estate": "Real Estate",
}


@dataclass
class EquityData:
    ticker: str
    name: str
    sector: str
    industry: str
    market_cap: float
    equity_volatility: float
    beta: float
    shares_outstanding: float
    total_debt: float
    short_term_debt: float
    long_term_debt: float
    cash: float
    revenue: float
    ebitda: float
    net_income: float
    free_cash_flow: float
    interest_expense: float
    total_assets: float
    total_equity: float
    price_history: list[tuple[date, float, float]]  # (date, close, volume)


def _load_cache() -> dict[str, str | None]:
    if CACHE_PATH.exists():
        return json.loads(CACHE_PATH.read_text())
    return {}


def _save_cache(cache: dict[str, str | None]) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache, indent=1, sort_keys=True))


def resolve_tickers(issuer_names: list[str]) -> dict[str, str]:
    """Map bond-file issuer names to listed equity tickers via Yahoo search.
    Results (including misses, stored as null) are cached on disk."""
    cache = _load_cache()
    out: dict[str, str] = {}
    dirty = False
    for name in issuer_names:
        if name in cache:
            if cache[name]:
                out[name] = cache[name]  # type: ignore[assignment]
            continue
        symbol: str | None = None
        try:
            results = yf.Search(name, max_results=5).quotes
            for q in results:
                if q.get("quoteType") == "EQUITY" and not q.get("symbol", "").count("."):
                    symbol = q["symbol"]
                    break
        except Exception as exc:  # network hiccup / rate limit: skip, don't cache
            logger.warning("ticker search failed for %s: %s", name, exc)
            continue
        cache[name] = symbol
        dirty = True
        if symbol:
            out[name] = symbol
        logger.info("resolved %-40s -> %s", name, symbol)
    if dirty:
        _save_cache(cache)
    return out


def _bs_value(bs, keys: list[str]) -> float:
    """First non-null value among row labels in a yfinance balance sheet frame."""
    if bs is None or bs.empty:
        return 0.0
    for key in keys:
        if key in bs.index:
            series = bs.loc[key].dropna()
            if not series.empty:
                return float(series.iloc[0])
    return 0.0


def fetch_equity_data(ticker: str) -> EquityData | None:
    """Pull one issuer's market data + fundamentals. Returns None when the
    listing lacks the essentials (market cap or price history)."""
    t = yf.Ticker(ticker)
    try:
        info = t.info or {}
    except Exception as exc:
        logger.warning("%s: info fetch failed: %s", ticker, exc)
        return None

    market_cap = float(info.get("marketCap") or 0)
    if market_cap <= 0:
        return None

    try:
        hist = t.history(period="1y", auto_adjust=True)
    except Exception as exc:
        logger.warning("%s: history fetch failed: %s", ticker, exc)
        return None
    if hist is None or len(hist) < 60:
        return None

    closes = hist["Close"].tolist()
    rets = [math.log(b / a) for a, b in zip(closes, closes[1:]) if a > 0 and b > 0]
    mean = sum(rets) / len(rets)
    vol = math.sqrt(sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)) * math.sqrt(252)
    vol = min(max(vol, 0.10), 1.50)

    bs = None
    try:
        bs = t.balance_sheet
    except Exception:
        pass
    fin = None
    try:
        fin = t.income_stmt
    except Exception:
        pass
    cf = None
    try:
        cf = t.cash_flow
    except Exception:
        pass

    total_debt = _bs_value(bs, ["Total Debt"]) or float(info.get("totalDebt") or 0)
    current_debt = _bs_value(bs, ["Current Debt And Capital Lease Obligation", "Current Debt"])
    long_debt = _bs_value(bs, ["Long Term Debt And Capital Lease Obligation", "Long Term Debt"])
    if total_debt <= 0:
        total_debt = current_debt + long_debt
    if total_debt <= 0:
        return None  # Merton needs a default barrier

    price_history = [
        (idx.date(), float(row.Close), float(row.Volume))
        for idx, row in hist.iterrows()
    ]

    sector = SECTOR_MAP.get(str(info.get("sector") or ""), str(info.get("sector") or "Other"))

    return EquityData(
        ticker=ticker,
        name=str(info.get("shortName") or info.get("longName") or ticker),
        sector=sector,
        industry=str(info.get("industry") or "—"),
        market_cap=market_cap,
        equity_volatility=vol,
        beta=float(info.get("beta") or 1.0),
        shares_outstanding=float(info.get("sharesOutstanding") or 0),
        total_debt=total_debt,
        short_term_debt=current_debt,
        long_term_debt=long_debt if long_debt > 0 else max(total_debt - current_debt, 0.0),
        cash=_bs_value(bs, ["Cash And Cash Equivalents", "Cash Cash Equivalents And Short Term Investments"])
        or float(info.get("totalCash") or 0),
        revenue=_bs_value(fin, ["Total Revenue"]) or float(info.get("totalRevenue") or 0),
        ebitda=_bs_value(fin, ["EBITDA", "Normalized EBITDA"]) or float(info.get("ebitda") or 0),
        net_income=_bs_value(fin, ["Net Income"]) or float(info.get("netIncomeToCommon") or 0),
        free_cash_flow=_bs_value(cf, ["Free Cash Flow"]) or float(info.get("freeCashflow") or 0),
        interest_expense=abs(_bs_value(fin, ["Interest Expense"])),
        total_assets=_bs_value(bs, ["Total Assets"]),
        total_equity=_bs_value(bs, ["Stockholders Equity", "Total Equity Gross Minority Interest"]),
        price_history=price_history,
    )
