"""Free corporate bond universe source: SPDR (SSGA) daily ETF holdings XLSX.

SPBO = SPDR Portfolio Corporate Bond ETF (investment grade, broad)
SPHY = SPDR Portfolio High Yield Bond ETF

Files are published daily with: name, ISIN, coupon, par value, market value,
maturity. Price is derived as market_value / par_value * 100. No API key.
"""

import io
import logging
import re
from dataclasses import dataclass
from datetime import date, datetime

import openpyxl
import requests

logger = logging.getLogger(__name__)

FUND_URLS = {
    "SPBO": "https://www.ssga.com/library-content/products/fund-data/etfs/us/holdings-daily-us-en-spbo.xlsx",
    "SPHY": "https://www.ssga.com/library-content/products/fund-data/etfs/us/holdings-daily-us-en-sphy.xlsx",
}

HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}

# Seniority markers inside SSGA bond names; the issuer name is everything before.
SENIORITY_MARKERS: list[tuple[str, str]] = [
    ("SR UNSECURED", "Senior Unsecured"),
    ("SR SECURED", "Senior Secured"),
    ("1ST LIEN", "Senior Secured"),
    ("SECURED", "Senior Secured"),
    ("SUBORDINATED", "Subordinated"),
    ("JR SUBORDINATED", "Junior Subordinated"),
    ("COMPANY GUAR", "Senior Unsecured"),
    ("SR GLOBAL", "Senior Unsecured"),
    ("GLOBAL", "Senior Unsecured"),
    ("SR NOTE", "Senior Unsecured"),
]


@dataclass(frozen=True)
class EtfHolding:
    cusip: str
    isin: str
    issuer_name: str
    description: str
    seniority: str
    coupon: float  # decimal
    maturity: date
    par_value: float
    market_value: float
    price: float  # per 100 face
    weight_pct: float
    source_fund: str
    is_high_yield: bool


def _split_issuer(name: str) -> tuple[str, str]:
    upper = name.upper()
    for marker, seniority in SENIORITY_MARKERS:
        idx = upper.find(f" {marker} ")
        if idx > 0:
            return name[:idx].strip(), seniority
    # fallback: strip trailing "MM/YY coupon" tail
    m = re.search(r"\s\d{2}/\d{2,4}\s", upper)
    return (name[: m.start()].strip() if m else name.strip()), "Senior Unsecured"


def fetch_fund_holdings(fund: str) -> tuple[date, list[EtfHolding]]:
    """Download and parse one fund's holdings file. Returns (as_of, holdings)."""
    resp = requests.get(FUND_URLS[fund], headers=HEADERS, timeout=120)
    resp.raise_for_status()
    wb = openpyxl.load_workbook(io.BytesIO(resp.content), read_only=True)
    ws = wb.active

    as_of = date.today()
    header: list[str] | None = None
    col: dict[str, int] = {}
    holdings: list[EtfHolding] = []

    for row in ws.iter_rows(values_only=True):
        cells = list(row)
        if header is None:
            first = str(cells[0] or "")
            if first.startswith("Holdings"):
                m = re.search(r"(\d{2}-\w{3}-\d{4})", str(cells[1] or first))
                if m:
                    as_of = datetime.strptime(m.group(1), "%d-%b-%Y").date()
            if first == "Name":
                header = [str(c) for c in cells if c is not None]
                col = {h: i for i, h in enumerate(header)}
            continue

        try:
            name = str(cells[col["Name"]] or "").strip()
            identifier = str(cells[col["Identifier"]] or "").strip()
            coupon = cells[col["Coupon"]]
            par = cells[col["Par Value"]]
            mv = cells[col["Market Value"]]
            weight = cells[col["Weight"]]
            maturity_raw = cells[col["Maturity"]]
        except (KeyError, IndexError):
            continue

        # Keep plain fixed-coupon USD corporates: US ISIN, parseable maturity,
        # positive coupon/par; drop floaters (VAR) and cash/money-market lines.
        if not identifier.startswith("US") or len(identifier) != 12:
            continue
        if "VAR" in name.upper() or not name:
            continue
        if not isinstance(coupon, (int, float)) or coupon <= 0:
            continue
        if not isinstance(par, (int, float)) or par <= 0:
            continue
        if not isinstance(mv, (int, float)) or mv <= 0:
            continue
        try:
            maturity = (
                maturity_raw.date()
                if isinstance(maturity_raw, datetime)
                else datetime.strptime(str(maturity_raw), "%m/%d/%Y").date()
            )
        except ValueError:
            continue
        if maturity <= date.today():
            continue

        issuer_name, seniority = _split_issuer(name)
        price = mv / par * 100.0
        if not 20.0 <= price <= 200.0:  # sanity: filter data glitches
            continue
        holdings.append(
            EtfHolding(
                cusip=identifier[2:11],
                isin=identifier,
                issuer_name=issuer_name,
                description=name,
                seniority=seniority,
                coupon=float(coupon) / 100.0,
                maturity=maturity,
                par_value=float(par),
                market_value=float(mv),
                price=price,
                weight_pct=float(weight) if isinstance(weight, (int, float)) else 0.0,
                source_fund=fund,
                is_high_yield=fund == "SPHY",
            )
        )

    logger.info("%s: %d usable bond holdings as of %s", fund, len(holdings), as_of)
    return as_of, holdings


def fetch_bond_universe(funds: list[str] | None = None) -> tuple[date, list[EtfHolding]]:
    """Merge holdings across funds, dedup by CUSIP (first fund wins)."""
    all_holdings: dict[str, EtfHolding] = {}
    as_of = date.today()
    for fund in funds or ["SPBO", "SPHY"]:
        fund_as_of, holdings = fetch_fund_holdings(fund)
        as_of = min(as_of, fund_as_of)
        for h in holdings:
            all_holdings.setdefault(h.cusip, h)
    return as_of, list(all_holdings.values())
