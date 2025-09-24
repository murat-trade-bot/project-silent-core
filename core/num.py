from __future__ import annotations
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP
from typing import Optional

_D = Decimal


def quantize_to_step(value: float, step: float) -> float:
    """
    stepSize kuralına göre tabana yuvarla (floor).
    0.001 step -> 1e-3 hassasiyet gibi düşün.
    """
    if step <= 0:
        return float(value)
    dval = _D(str(value))
    dstep = _D(str(step))
    units = (dval / dstep).to_integral_value(rounding=ROUND_DOWN)
    return float(units * dstep)


def round_to_tick(price: float, tick: float) -> float:
    """
    tickSize kuralına göre en yakın seviyeye yuvarla.
    """
    if tick <= 0:
        return float(price)
    dprice = _D(str(price))
    dtick = _D(str(tick))
    units = (dprice / dtick).to_integral_value(rounding=ROUND_HALF_UP)
    return float(units * dtick)


def safe_mul(a: Optional[float], b: Optional[float]) -> Optional[float]:
    if a is None or b is None:
        return None
    return float(_D(str(a)) * _D(str(b)))

from decimal import Decimal as _Dec, ROUND_UP


def ceil_to_step(value: float, step: float) -> float:
    """
    stepSize'a göre tavana yuvarla (ceil). minNotional autoscale için kullanılır.
    """
    if step <= 0:
        return float(value)
    dval = _Dec(str(value))
    dstep = _Dec(str(step))
    units = (dval / dstep).to_integral_value(rounding=ROUND_UP)
    return float(units * dstep)
