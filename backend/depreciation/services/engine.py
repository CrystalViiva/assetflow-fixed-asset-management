"""Deterministic Decimal straight-line calculations using two-decimal currency precision."""

from decimal import ROUND_HALF_UP, Decimal

from django.core.exceptions import ValidationError

from assets.models import DepreciationMethod

CENT = Decimal("0.01")


def money(value):
    if isinstance(value, float):
        raise TypeError("Accounting values must not be supplied as floats.")
    decimal_value = value if isinstance(value, Decimal) else Decimal(str(value))
    return decimal_value.quantize(CENT, rounding=ROUND_HALF_UP)


def straight_line_periodic_amount(*, capitalized_cost, residual_value, useful_life_months):
    """Return the nominal monthly SLM amount; the final posting absorbs prior rounding."""
    if useful_life_months is None or useful_life_months <= 0:
        raise ValidationError(
            {"useful_life_months": "Useful life must be a positive number of months."}
        )
    cost = money(capitalized_cost)
    residual = money(residual_value)
    if cost < 0 or residual < 0 or residual > cost:
        raise ValidationError("Capitalized cost and residual value are inconsistent.")
    return money((cost - residual) / Decimal(useful_life_months))


def calculate_period_amount(
    *,
    method,
    opening_book_value,
    residual_value,
    depreciable_base,
    periodic_depreciation,
    accumulated_depreciation,
):
    """Calculate one posted amount, applying the residual floor and final-period adjustment."""
    if method != DepreciationMethod.SLM:
        raise ValidationError({"method": f"Calculation method {method} is not implemented."})
    remaining = money(depreciable_base - accumulated_depreciation)
    if remaining == 0 and money(depreciable_base) == 0:
        return Decimal("0.00")
    if remaining <= 0:
        raise ValidationError({"asset": "The depreciable amount has been fully consumed."})
    return min(money(periodic_depreciation), remaining, money(opening_book_value - residual_value))
