# F3: depreciation and accounting period integration

F3 connects the existing React frontend to Django's organization-scoped depreciation APIs. Django remains the accounting authority. The Django depreciation page and Asset Detail Depreciation tab read schedules, periods, posted entries, and asset balances from the backend; they do not use the demo calculator to produce accounting values.

## Actual API and accounting behavior

The existing API exposes paginated `GET/POST /api/v1/depreciation/periods/`, `POST /api/v1/depreciation/periods/{id}/close/`, paginated `GET/POST /api/v1/depreciation/schedules/`, paginated `GET /api/v1/depreciation/entries/`, and `POST /api/v1/depreciation/entries/post/`. The browser sends only `{ "asset_id": "…", "period_id": "…" }` for posting. It never sends an amount.

Periods are explicitly created for an organization and calendar month, start `OPEN`, and can be closed. The backend does not expose reopen. Period creation and closing create audit events. Posting requires an open period and an active capitalized asset with a schedule. The selected month must be the schedule start month plus the count of entries already posted. Schedule creation freezes the current asset's SLM assumptions and is separate from period creation and posting.

Only Straight Line (SLM) is implemented by the posting service. The schedule starts in the full calendar month containing `available_for_use_date`; there is no daily proration. Nominal periodic depreciation is calculated and quantized to two decimals using Decimal `ROUND_HALF_UP`. Posting applies the backend's residual floor and cannot exceed remaining depreciable base. When the remaining base is below the nominal periodic amount, including a rounded final posting, the backend posts only that remainder. The current backend does not expose per-period projected rows. The frontend reports frozen schedule assumptions as such and shows only actual ledger entries as `POSTED`.

The backend creates one entry per organization, asset, and period under a database uniqueness constraint and locks the period, asset, and schedule during posting. A duplicate POST is rejected with a validation response; it does not return the existing entry. Period close rejects subsequent posting. The frontend treats a failed or malformed POST response as potentially ambiguous, re-reads the asset/period ledger, and enables retry only after that read succeeds and proves no entry exists. If reconciliation fails, posting remains uncertain and disabled.

## Frontend boundary

`depreciationDtos.ts` validates the actual period, schedule, and entry shapes. Accounting amounts remain decimal strings end-to-end and are grouped for display without numeric conversion. `DjangoDepreciationRepository` owns transport and pagination; TanStack Query keys are scoped by authenticated user and session generation. A confirmed or reconciled posting invalidates depreciation reads and the current user's asset queries so accumulated depreciation and book value are refetched from Django.

The backend permission class allows ADMIN, ASSET_MANAGER, and ACCOUNTANT to create/close periods, create schedules, and post; those roles and DEPARTMENT_MANAGER can read, with department managers limited to their department. Django is authoritative and 403 responses remain visible. Logout clears the existing QueryClient; posting workflows also check the session generation before publishing results.

Mock mode keeps the original illustrative simulator. It is distinct from the Django operational screen. The old client calculator is not called by F3 Django routes and does not supply posting, schedule, projection, accumulated depreciation, or book-value values.

## Validation

Run the TypeScript/Django/PostgreSQL integration against a random disposable database with:

```sh
python scripts/f1-smoke.py --f3
```

The smoke creates an isolated organization and capitalized asset, opens January 2026, creates its backend schedule, posts once, verifies duplicate rejection and period close through the API, checks exact ledger and asset Decimal values and audit events in PostgreSQL, logs out, and drops only the generated database. It never uses the configured application database as its target.

Limitations: the current API provides no period-by-period projection endpoint or bulk posting endpoint. F3 posts one selected asset for one selected period. The backend's supported calculation is SLM only. Backend currently does not expose a dedicated duplicate-post response; the client reconciles by re-reading entries. Period creation is explicit, and period close is not conditioned on every asset being posted.
