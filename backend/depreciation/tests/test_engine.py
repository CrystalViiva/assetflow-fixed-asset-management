from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from assets.models import DepreciationMethod
from depreciation.services.engine import calculate_period_amount, straight_line_periodic_amount


def test_slm_nominal_monthly_amount_is_rounded_to_currency_precision():
    amount = straight_line_periodic_amount(
        capitalized_cost=Decimal("12000000.00"),
        residual_value=Decimal("2000000.00"),
        useful_life_months=60,
    )
    assert amount == Decimal("166666.67")


def test_final_period_absorbs_rounding_remainder():
    amount = calculate_period_amount(
        method=DepreciationMethod.SLM,
        opening_book_value=Decimal("2166666.47"),
        residual_value=Decimal("2000000.00"),
        depreciable_base=Decimal("10000000.00"),
        periodic_depreciation=Decimal("166666.67"),
        accumulated_depreciation=Decimal("9833333.53"),
    )
    assert amount == Decimal("166666.47")


def test_one_month_useful_life_recognizes_entire_depreciable_amount():
    assert straight_line_periodic_amount(
        capitalized_cost=Decimal("100.00"),
        residual_value=Decimal("10.00"),
        useful_life_months=1,
    ) == Decimal("90.00")


def test_zero_depreciation_base_posts_zero():
    amount = calculate_period_amount(
        method=DepreciationMethod.SLM,
        opening_book_value=Decimal("100.00"),
        residual_value=Decimal("100.00"),
        depreciable_base=Decimal("0.00"),
        periodic_depreciation=Decimal("0.00"),
        accumulated_depreciation=Decimal("0.00"),
    )
    assert amount == Decimal("0.00")


def test_unsupported_methods_are_rejected_not_calculated_as_slm():
    with pytest.raises(ValidationError, match="not implemented"):
        calculate_period_amount(
            method=DepreciationMethod.RBM,
            opening_book_value=Decimal("100.00"),
            residual_value=Decimal("0.00"),
            depreciable_base=Decimal("100.00"),
            periodic_depreciation=Decimal("10.00"),
            accumulated_depreciation=Decimal("0.00"),
        )


def test_money_rejects_floating_point_values():
    from depreciation.services.engine import money

    with pytest.raises(TypeError, match="must not be supplied as floats"):
        money(0.1)
