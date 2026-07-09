"""Bond cash flow, pricing, yield, duration/convexity, and spread analytics.

Conventions: semiannual coupons, prices per 100 face, rates as decimals.
"""

import math
from dataclasses import dataclass

from app.calculations.mathutils import bisect
from app.calculations.treasury import ZeroCurve


@dataclass(frozen=True)
class CashFlow:
    time: float  # years from settlement
    amount: float  # per 100 face


def build_cashflows(coupon_rate: float, years_to_maturity: float) -> list[CashFlow]:
    """Semiannual coupon schedule with a short first stub if maturity is not
    on a half-year grid."""
    if years_to_maturity <= 0:
        raise ValueError("years_to_maturity must be positive")
    n = max(1, math.ceil(years_to_maturity * 2 - 1e-9))
    coupon = coupon_rate * 100 / 2.0
    flows: list[CashFlow] = []
    for i in range(n):
        t = years_to_maturity - (n - 1 - i) * 0.5
        amount = coupon + (100.0 if i == n - 1 else 0.0)
        flows.append(CashFlow(time=t, amount=amount))
    return flows


def price_from_yield(cashflows: list[CashFlow], ytm: float) -> float:
    """Dirty price under semiannual compounding."""
    return sum(cf.amount / (1 + ytm / 2) ** (2 * cf.time) for cf in cashflows)


def yield_from_price(cashflows: list[CashFlow], price: float) -> float:
    if price <= 0:
        raise ValueError("price must be positive")
    return bisect(lambda y: price_from_yield(cashflows, y) - price, -0.5, 5.0)


def macaulay_duration(cashflows: list[CashFlow], ytm: float) -> float:
    price = price_from_yield(cashflows, ytm)
    weighted = sum(cf.time * cf.amount / (1 + ytm / 2) ** (2 * cf.time) for cf in cashflows)
    return weighted / price


def modified_duration(cashflows: list[CashFlow], ytm: float) -> float:
    return macaulay_duration(cashflows, ytm) / (1 + ytm / 2)


def convexity(cashflows: list[CashFlow], ytm: float) -> float:
    """Standard convexity under semiannual compounding."""
    price = price_from_yield(cashflows, ytm)
    total = sum(
        cf.amount * (2 * cf.time) * (2 * cf.time + 1) / (1 + ytm / 2) ** (2 * cf.time + 2)
        for cf in cashflows
    )
    return total / (4 * price)


def price_from_zero_curve(cashflows: list[CashFlow], curve: ZeroCurve, spread: float = 0.0) -> float:
    """PV of cashflows discounted at zero curve plus a constant (Z-) spread,
    continuous compounding."""
    return sum(cf.amount * math.exp(-(curve.zero_rate(cf.time) + spread) * cf.time) for cf in cashflows)


def z_spread(cashflows: list[CashFlow], price: float, curve: ZeroCurve) -> float:
    """Constant spread over the zero curve that reprices the bond."""
    return bisect(lambda s: price_from_zero_curve(cashflows, curve, s) - price, -0.10, 1.0)


def g_spread(ytm: float, maturity: float, curve: ZeroCurve) -> float:
    """Yield spread over the interpolated par treasury yield at same maturity."""
    return ytm - curve.par_equivalent_yield(maturity)


def oas(cashflows: list[CashFlow], price: float, curve: ZeroCurve, option_cost: float = 0.0) -> float:
    """Option-adjusted spread. For bullet bonds option_cost is 0 and OAS equals
    the Z-spread; callable/putable support plugs in via option_cost (in spread
    terms) from a lattice or Monte Carlo model."""
    return z_spread(cashflows, price, curve) - option_cost


def market_implied_pd(spread: float, maturity: float, recovery_rate: float) -> float:
    """Cumulative risk-neutral PD implied by a credit spread under constant
    hazard: spread ≈ hazard * LGD  =>  PD_T = 1 - exp(-hazard * T)."""
    lgd = max(1.0 - recovery_rate, 1e-6)
    hazard = max(spread, 0.0) / lgd
    return 1.0 - math.exp(-hazard * maturity)


def spread_from_pd(pd: float, maturity: float, recovery_rate: float) -> float:
    """Inverse of market_implied_pd: credit spread consistent with a
    cumulative PD over the given horizon."""
    pd = min(max(pd, 0.0), 0.9999)
    lgd = max(1.0 - recovery_rate, 1e-6)
    hazard = -math.log(1.0 - pd) / maturity
    return hazard * lgd
