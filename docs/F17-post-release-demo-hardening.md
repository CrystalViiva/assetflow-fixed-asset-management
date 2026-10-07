# F17 post-release demo presentation hardening

This focused pass follows browser-rendered portfolio review that found mock screens overstating standards support and showing stale integration placeholders. It was completed after the F16 release gate and does not rewrite F16 history.

## Presentation corrections

- Replaced dashboard claims of IFRS certification, PwC FY24 audit clearance, and revaluation with an IAS 16-aligned workflow label, posted accounting records, and straight-line depreciation.
- Reworded asset detail badges as capitalized asset and configured residual value; corrected the schedule wording to depreciation.
- Removed unsupported statutory and IFRS 5 language from depreciation, disposal, and reporting screens. Tangible fixed-asset charges are labeled depreciation. The displayed formula remains depreciable amount = cost − residual value, with monthly straight-line depreciation over useful life in months.
- Removed audit/compliance statuses and unsupported claims about useful-life compliance. Kept the qualified IAS 16-aligned statement and the explicit disclaimer that this is not a claim of full IFRS compliance.
- Replaced fictional auditor and insurer authority in demo metadata, and made sample vendor/reviewer/evidence records clearly demonstrative.
- Added local-data mock verification and assurance screens with sample campaign observations, matching/mismatch/unregistered outcomes, exceptions, and evidence metadata context. Mock verification states that no evidence files are stored. The Django routes still use their existing backend views.
- Added a keyboard-accessible GitHub source link to the public landing navigation using the official repository URL and safe new-tab link attributes. Existing section links still target visible sections.

## Validation

Targeted component and route regression tests cover dashboard, asset detail, depreciation, disposal, report, verification, assurance, and landing claims. Full frontend tests, typecheck, lint, mock and Django builds, npm audit, and `git diff --check` were run for this pass. No browser automation package or browser executable is available in this environment, so screenshot validation could not be performed; responsive CSS and keyboard focus styling were reviewed in source.

No new business or accounting capability was added. Backend code, Django authorization, accounting calculations, Decimal handling, lifecycle transitions, snapshots/exports, private evidence security, assurance behavior, data-source separation, and the F16 release decision were not changed.
