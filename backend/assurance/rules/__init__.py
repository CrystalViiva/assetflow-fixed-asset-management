"""Deterministic, side-effect-free reconciliation controls."""

from assurance.models import AssuranceRunType
from assurance.rules import (
    book_value,
    condition,
    custody,
    department,
    depreciation,
    disposal,
    evidence,
    lifecycle,
    location,
    open_workflow,
    physical,
    stale_records,
)

ALL_RULES = (
    location.evaluate,
    department.evaluate,
    custody.evaluate,
    physical.evaluate,
    condition.evaluate,
    lifecycle.evaluate,
    disposal.evaluate,
    depreciation.evaluate,
    book_value.evaluate,
    evidence.evaluate,
    stale_records.evaluate,
    open_workflow.evaluate,
)

RULES_BY_RUN_TYPE = {
    AssuranceRunType.FULL: ALL_RULES,
    AssuranceRunType.PHYSICAL: (
        location.evaluate,
        department.evaluate,
        custody.evaluate,
        physical.evaluate,
        condition.evaluate,
        evidence.evaluate,
    ),
    AssuranceRunType.FINANCIAL: (
        disposal.evaluate,
        depreciation.evaluate,
        book_value.evaluate,
    ),
    AssuranceRunType.OPERATIONAL: (
        location.evaluate,
        department.evaluate,
        custody.evaluate,
        physical.evaluate,
        condition.evaluate,
        lifecycle.evaluate,
        evidence.evaluate,
        stale_records.evaluate,
        open_workflow.evaluate,
    ),
}
