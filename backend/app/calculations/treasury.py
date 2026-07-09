"""Treasury curve construction: bootstrap zero curve from par yields and
interpolate at arbitrary tenors.

Convention: semiannual coupon par bonds for tenors >= 1y; money-market tenors
(< 1y) treated as zero-coupon. Rates are decimals (0.045 = 4.5%).
"""

import math
from bisect import bisect_left
from dataclasses import dataclass

STANDARD_TENORS: list[float] = [1 / 12, 0.25, 0.5, 1, 2, 3, 5, 7, 10, 20, 30]
STANDARD_TENOR_LABELS: list[str] = ["1M", "3M", "6M", "1Y", "2Y", "3Y", "5Y", "7Y", "10Y", "20Y", "30Y"]


@dataclass(frozen=True)
class ZeroCurve:
    """Continuously-compounded zero curve defined by (tenor, zero_rate) knots."""

    tenors: tuple[float, ...]
    zero_rates: tuple[float, ...]

    def zero_rate(self, t: float) -> float:
        """Linear interpolation on zero rates; flat extrapolation beyond knots."""
        if t <= 0:
            return self.zero_rates[0]
        tenors, rates = self.tenors, self.zero_rates
        if t <= tenors[0]:
            return rates[0]
        if t >= tenors[-1]:
            return rates[-1]
        i = bisect_left(tenors, t)
        t0, t1 = tenors[i - 1], tenors[i]
        r0, r1 = rates[i - 1], rates[i]
        w = (t - t0) / (t1 - t0)
        return r0 + w * (r1 - r0)

    def discount_factor(self, t: float) -> float:
        if t <= 0:
            return 1.0
        return math.exp(-self.zero_rate(t) * t)

    def par_equivalent_yield(self, t: float) -> float:
        """Semiannual-pay par yield implied by the zero curve at maturity t."""
        if t <= 0.5:
            df = self.discount_factor(max(t, 1e-6))
            return 2.0 * (1.0 / df - 1.0) / max(2.0 * t, 1e-6) if t < 0.5 else 2.0 * (1.0 / df - 1.0)
        n = max(1, round(t * 2))
        times = [(i + 1) / 2 for i in range(n)]
        annuity = sum(self.discount_factor(ti) for ti in times)
        df_final = self.discount_factor(times[-1])
        return 2.0 * (1.0 - df_final) / annuity


def bootstrap_zero_curve(par_yields: dict[float, float]) -> ZeroCurve:
    """Bootstrap continuously-compounded zero rates from par yields.

    par_yields: {tenor_years: par_yield_decimal}, e.g. {0.5: 0.043, 10: 0.045}.
    Money-market tenors (< 1y) are converted directly; coupon tenors are
    bootstrapped sequentially with fixed-point iteration on the final discount
    factor (intermediate coupon dates interpolated on zero rates).
    """
    if not par_yields:
        raise ValueError("par_yields is empty")
    items = sorted(par_yields.items())
    known_tenors: list[float] = []
    known_zeros: list[float] = []

    def interp_zero(t: float) -> float:
        if not known_tenors:
            return items[0][1]
        return ZeroCurve(tuple(known_tenors), tuple(known_zeros)).zero_rate(t)

    for tenor, y in items:
        if tenor <= 0:
            raise ValueError(f"Invalid tenor {tenor}")
        if tenor < 1.0 - 1e-9:
            # Money market: simple-interest quote -> continuous zero.
            z = math.log(1.0 + y * tenor) / tenor
        else:
            n = max(1, round(tenor * 2))
            coupon = y / 2.0
            z = known_zeros[-1] if known_zeros else y  # initial guess
            for _ in range(100):
                pv_coupons = 0.0
                for i in range(n - 1):
                    ti = (i + 1) / 2
                    zi = interp_zero(ti) if ti <= (known_tenors[-1] if known_tenors else 0) else \
                        _blend(known_tenors, known_zeros, ti, tenor, z)
                    pv_coupons += coupon * math.exp(-zi * ti)
                df_final = (1.0 - pv_coupons) / (1.0 + coupon)
                if df_final <= 0:
                    raise ValueError(f"Bootstrap failed at tenor {tenor}: negative discount factor")
                z_new = -math.log(df_final) / tenor
                if abs(z_new - z) < 1e-12:
                    z = z_new
                    break
                z = z_new
        known_tenors.append(tenor)
        known_zeros.append(z)

    return ZeroCurve(tuple(known_tenors), tuple(known_zeros))


def _blend(known_tenors: list[float], known_zeros: list[float], t: float, tenor: float, z_guess: float) -> float:
    """Interpolate a zero rate between the last bootstrapped knot and the
    current tenor's guess, for intermediate coupon dates."""
    if not known_tenors:
        return z_guess
    t_last, z_last = known_tenors[-1], known_zeros[-1]
    if t <= t_last:
        return ZeroCurve(tuple(known_tenors), tuple(known_zeros)).zero_rate(t)
    w = (t - t_last) / (tenor - t_last)
    return z_last + w * (z_guess - z_last)


def curve_to_points(curve: ZeroCurve, tenors: list[float] | None = None) -> list[dict[str, float]]:
    ts = tenors or STANDARD_TENORS
    return [
        {"tenor": t, "zero_rate": curve.zero_rate(t), "par_yield": curve.par_equivalent_yield(t)}
        for t in ts
    ]
