# Fixed asset accounting behavior

This document describes the accounting rules implemented in the repository. The system supports IAS 16-aligned fixed-asset workflows; it does not claim a complete IAS 16 or IFRS implementation.

## Acquisition and capitalization

An acquisition records purchase price, freight, installation, civil works, and other capitalizable cost as separate two-decimal Decimal values. The backend derives total cost; callers cannot submit the authoritative total. Acquisition currency must match the organization's base currency because exchange-rate conversion is not implemented.

Capitalization is a controlled service transition. It checks required dates and asset state, locks the acquisition and asset rows, sets the asset cost basis and initial book value from the calculated total, sets accumulated depreciation to zero, changes acquisition state, and writes audit events in the same transaction. Repeating capitalization does not create another capitalization.

The available-for-use date may be set as part of capitalization and cannot precede the capitalization date. It determines the depreciation schedule start month.

## Straight-line depreciation

SLM is the only implemented method. The depreciable base is:

  capitalized cost - residual value

The nominal monthly amount is the depreciable base divided by useful life in months. The backend uses Python Decimal with two decimal places and ROUND_HALF_UP. No daily proration is performed: the calendar month containing the available-for-use date is a full schedule month.

Posting is sequential and requires an open accounting period. The service locks the period, asset, and schedule, checks the prior ledger balance, writes one entry, updates accumulated depreciation and book value, and writes the audit event transactionally. Database uniqueness prevents a second entry for the same asset and period.

Each amount is bounded by the remaining depreciable base and the amount above the residual floor. The final posting absorbs accumulated rounding so the schedule does not depreciate below residual value. A schedule cannot be silently regenerated after entries exist.

## Worked release-gate example

The F16 disposable golden fixture used:

- Purchase price: 1,000.01
- Freight: 0.99
- Capitalized cost: 1,001.00
- Residual value: 100.00
- Useful life: 36 months

Depreciable base is 1,001.00 - 100.00 = 901.00.

The exact monthly quotient is 901.00 / 36 = 25.027777... ROUND_HALF_UP to cents gives a posted first-month amount of 25.03.

First posting:

- Opening book value: 1,001.00
- Depreciation expense: 25.03
- Accumulated depreciation: 25.03
- Closing book value: 975.97

The balance identity at this checkpoint is 1,001.00 - 25.03 = 975.97.

On disposal for proceeds of 1,200.00, the release-gate fixture recorded carrying amount 975.97 and gain 1,200.00 - 975.97 = 224.03. Disposal completion preserves prior acquisition and depreciation history.

## Disposal and controls

Disposal passes through draft, pending approval, approved, and completed states. Approval and completion may require different authorized actors. Completion checks active custody, transfer, and work-order blockers; locks the asset/disposal; snapshots capitalized cost, accumulated depreciation, carrying amount, proceeds, and gain/loss; and sets the asset DISPOSED in one transaction.

Maintenance cost is recorded as operational history and does not change asset cost, residual value, useful life, method, accumulated depreciation, or book value. Verification and assurance likewise do not post accounting adjustments.

## Explicit limits

- Straight-line only; no reducing-balance, units-of-production, or sum-of-years-digits method.
- No component depreciation.
- No estimate revision workflow for residual value or useful life.
- No IAS 36 impairment accounting ledger; an IMPAIRED lifecycle label is not an impairment posting.
- No decommissioning/restoration obligation accounting.
- No foreign currency translation or multi-currency accounting.

For state transitions and transactional architecture, see [engineering decisions](engineering-decisions.md) and the [F16 release gate](F16-full-system-release-gate.md).
