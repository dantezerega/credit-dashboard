"""Free treasury par-yield source: home.treasury.gov daily CSV (no API key)."""

import csv
import io
import logging
from datetime import date, datetime

import requests

logger = logging.getLogger(__name__)

URL = (
    "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/"
    "daily-treasury-rates.csv/{year}/all?type=daily_treasury_yield_curve"
    "&field_tdr_date_value={year}&page&_format=csv"
)

# CSV column -> tenor in years
TENOR_COLUMNS: dict[str, float] = {
    "1 Mo": 1 / 12,
    "3 Mo": 0.25,
    "6 Mo": 0.5,
    "1 Yr": 1,
    "2 Yr": 2,
    "3 Yr": 3,
    "5 Yr": 5,
    "7 Yr": 7,
    "10 Yr": 10,
    "20 Yr": 20,
    "30 Yr": 30,
}

HEADERS = {"User-Agent": "credit-rv-dashboard/1.0 (research)"}


def fetch_treasury_history(years: list[int]) -> dict[date, dict[float, float]]:
    """Fetch daily par yield curves for the given years.

    Returns {date: {tenor_years: par_yield_decimal}}, oldest first.
    """
    out: dict[date, dict[float, float]] = {}
    for year in years:
        resp = requests.get(URL.format(year=year), headers=HEADERS, timeout=60)
        resp.raise_for_status()
        reader = csv.DictReader(io.StringIO(resp.text))
        for row in reader:
            try:
                d = datetime.strptime(row["Date"], "%m/%d/%Y").date()
            except (KeyError, ValueError):
                continue
            curve: dict[float, float] = {}
            for col, tenor in TENOR_COLUMNS.items():
                raw = (row.get(col) or "").strip()
                if raw:
                    try:
                        curve[tenor] = float(raw) / 100.0
                    except ValueError:
                        pass
            if len(curve) >= 8:  # skip days with too many gaps
                out[d] = curve
        logger.info("treasury.gov: %d curve dates for %d", len(out), year)
    return dict(sorted(out.items()))
