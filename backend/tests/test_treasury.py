import math

import pytest

from app.calculations.treasury import ZeroCurve, bootstrap_zero_curve, curve_to_points


FLAT = {0.25: 0.04, 0.5: 0.04, 1: 0.04, 2: 0.04, 5: 0.04, 10: 0.04, 30: 0.04}


def test_flat_par_curve_gives_flat_zero_curve():
    curve = bootstrap_zero_curve(FLAT)
    # semiannual 4% par -> continuous zero ln(1.02)*2 ≈ 3.9605%
    expected = 2 * math.log(1.02)
    for t in [1, 2, 5, 10, 30]:
        assert curve.zero_rate(t) == pytest.approx(expected, abs=2e-4)


def test_bootstrap_reprices_par_bonds():
    par = {0.5: 0.043, 1: 0.044, 2: 0.0435, 5: 0.045, 10: 0.047, 30: 0.049}
    curve = bootstrap_zero_curve(par)
    for tenor, y in par.items():
        if tenor < 1:
            continue
        n = round(tenor * 2)
        coupon = y / 2 * 100
        pv = sum(coupon * curve.discount_factor((i + 1) / 2) for i in range(n))
        pv += 100 * curve.discount_factor(tenor)
        assert pv == pytest.approx(100.0, abs=0.05)


def test_upward_sloping_par_gives_higher_zeros_at_long_end():
    par = {1: 0.04, 5: 0.045, 10: 0.05, 30: 0.055}
    curve = bootstrap_zero_curve(par)
    # zero rates exceed par yields on an upward-sloping curve
    assert curve.zero_rate(30) > 0.055
    assert curve.zero_rate(1) < curve.zero_rate(10) < curve.zero_rate(30)


def test_interpolation_between_knots():
    curve = ZeroCurve(tenors=(1.0, 3.0), zero_rates=(0.03, 0.05))
    assert curve.zero_rate(2.0) == pytest.approx(0.04)
    assert curve.zero_rate(1.0) == 0.03
    assert curve.zero_rate(0.5) == 0.03  # flat extrapolation short end
    assert curve.zero_rate(10.0) == 0.05  # flat extrapolation long end


def test_discount_factor():
    curve = ZeroCurve(tenors=(1.0,), zero_rates=(0.05,))
    assert curve.discount_factor(1.0) == pytest.approx(math.exp(-0.05))
    assert curve.discount_factor(0.0) == 1.0


def test_par_equivalent_yield_roundtrip():
    par = {0.5: 0.042, 1: 0.043, 2: 0.044, 5: 0.0455, 10: 0.047}
    curve = bootstrap_zero_curve(par)
    for tenor in [1, 2, 5, 10]:
        assert curve.par_equivalent_yield(tenor) == pytest.approx(par[tenor], abs=5e-5)


def test_curve_to_points_standard_tenors():
    curve = bootstrap_zero_curve(FLAT)
    points = curve_to_points(curve)
    assert len(points) == 11
    assert {p["tenor"] for p in points} >= {1 / 12, 0.25, 0.5, 1, 2, 3, 5, 7, 10, 20, 30}


def test_empty_input_raises():
    with pytest.raises(ValueError):
        bootstrap_zero_curve({})
