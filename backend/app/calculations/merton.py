"""Merton structural credit model.

Treats equity as a call option on firm assets with strike = face value of debt.
Solves the two-equation system for unobservable asset value V and asset
volatility sigma_V given observable equity value E and equity volatility sigma_E:

    E       = V * N(d1) - D * exp(-r*T) * N(d2)
    sigma_E = (V / E) * N(d1) * sigma_V

using the standard KMV-style iteration: Newton-solve V for a fixed sigma_V,
then update sigma_V from the volatility linkage, repeat to convergence.
"""

import math
from dataclasses import dataclass

from app.calculations.mathutils import norm_cdf


@dataclass(frozen=True)
class MertonResult:
    asset_value: float
    asset_volatility: float
    distance_to_default: float
    default_probability: float  # risk-neutral, horizon T
    d1: float
    d2: float
    equity_value: float
    debt_face: float
    maturity: float
    risk_free_rate: float
    converged: bool
    iterations: int


def _d1_d2(v: float, d: float, r: float, sigma_v: float, t: float) -> tuple[float, float]:
    sig_sqrt_t = sigma_v * math.sqrt(t)
    d1 = (math.log(v / d) + (r + 0.5 * sigma_v**2) * t) / sig_sqrt_t
    return d1, d1 - sig_sqrt_t


def _equity_from_assets(v: float, d: float, r: float, sigma_v: float, t: float) -> float:
    d1, d2 = _d1_d2(v, d, r, sigma_v, t)
    return v * norm_cdf(d1) - d * math.exp(-r * t) * norm_cdf(d2)


def _solve_asset_value(
    equity: float, d: float, r: float, sigma_v: float, t: float, v_init: float
) -> float:
    """Newton's method on E(V) = equity. dE/dV = N(d1) > 0, so well behaved."""
    v = max(v_init, equity + 1e-9)
    for _ in range(100):
        d1, _ = _d1_d2(v, d, r, sigma_v, t)
        f = _equity_from_assets(v, d, r, sigma_v, t) - equity
        deriv = norm_cdf(d1)
        if deriv < 1e-12:
            break
        step = f / deriv
        v_new = v - step
        if v_new <= equity:  # asset value can never be below equity value
            v_new = 0.5 * (v + equity)
        if abs(v_new - v) < 1e-10 * max(1.0, v):
            return v_new
        v = v_new
    return v


def solve_merton(
    equity_value: float,
    equity_volatility: float,
    debt_face: float,
    risk_free_rate: float,
    maturity: float = 1.0,
    tol: float = 1e-8,
    max_iter: int = 100,
) -> MertonResult:
    """Iteratively solve for firm asset value and volatility, then derive
    distance to default and risk-neutral default probability N(-d2)."""
    if equity_value <= 0:
        raise ValueError("equity_value must be positive")
    if equity_volatility <= 0:
        raise ValueError("equity_volatility must be positive")
    if maturity <= 0:
        raise ValueError("maturity must be positive")
    if debt_face <= 0:
        # No debt: default impossible under the model.
        return MertonResult(
            asset_value=equity_value, asset_volatility=equity_volatility,
            distance_to_default=math.inf, default_probability=0.0,
            d1=math.inf, d2=math.inf, equity_value=equity_value, debt_face=0.0,
            maturity=maturity, risk_free_rate=risk_free_rate, converged=True, iterations=0,
        )

    v = equity_value + debt_face * math.exp(-risk_free_rate * maturity)
    sigma_v = equity_volatility * equity_value / v

    converged = False
    iterations = 0
    for iterations in range(1, max_iter + 1):
        v = _solve_asset_value(equity_value, debt_face, risk_free_rate, sigma_v, maturity, v)
        d1, _ = _d1_d2(v, debt_face, risk_free_rate, sigma_v, maturity)
        nd1 = norm_cdf(d1)
        sigma_v_new = equity_volatility * equity_value / (v * nd1) if nd1 > 1e-12 else sigma_v
        # Dampen to avoid oscillation for deep out-of-the-money equity.
        sigma_v_new = 0.5 * sigma_v + 0.5 * sigma_v_new
        if abs(sigma_v_new - sigma_v) < tol:
            sigma_v = sigma_v_new
            converged = True
            break
        sigma_v = sigma_v_new

    d1, d2 = _d1_d2(v, debt_face, risk_free_rate, sigma_v, maturity)
    return MertonResult(
        asset_value=v,
        asset_volatility=sigma_v,
        distance_to_default=d2,
        default_probability=norm_cdf(-d2),
        d1=d1,
        d2=d2,
        equity_value=equity_value,
        debt_face=debt_face,
        maturity=maturity,
        risk_free_rate=risk_free_rate,
        converged=converged,
        iterations=iterations,
    )


def pd_to_horizon(pd_t: float, t: float, horizon: float) -> float:
    """Rescale a cumulative PD over t years to another horizon assuming a
    constant hazard rate: PD_h = 1 - (1 - PD_t)^(h/t)."""
    if pd_t >= 1.0:
        return 1.0
    if pd_t <= 0.0:
        return 0.0
    hazard = -math.log(1.0 - pd_t) / t
    return 1.0 - math.exp(-hazard * horizon)
