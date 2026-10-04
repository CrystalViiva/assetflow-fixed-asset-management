# F2: reference data, acquisition and capitalization

F2 extends the F1 browser to Django workflow for reference lookups, Asset Register filters, asset creation, acquisitions, capitalization, the Category Register read view, and acquisition data on Asset Detail. It preserves the React 19, TypeScript, Vite, Tailwind, hash routing and explicit source switch. See [F1 authentication and transport details](frontend-f1.md) for JWT storage, refresh, error envelopes, proxy and query-cache security.

## Source modes

Set `VITE_DATA_SOURCE=mock` to use the existing localStorage demo workflows. Set `VITE_DATA_SOURCE=django` to use the authenticated API. An invalid value fails during startup. Django mode never falls back to demo records. Configure `VITE_BACKEND_API_URL=/api/v1` and `DJANGO_DEV_PROXY_TARGET=http://127.0.0.1:8000` for local development; Vite proxies requests on the same origin, so development does not need broad CORS. Production should use an HTTPS reverse proxy or an explicitly restricted HTTPS API origin.

The F2 integrated Django screens are Asset Register, Asset Detail Overview and its real acquisition panel, asset creation/acquisition/capitalization, Category Register read view, and Acquisitions Ledger. F3 subsequently integrated the Asset Detail Depreciation tab and depreciation workflow; the other non-overview detail tabs and remaining organization/lifecycle/report views stay explicitly pending. Category write CRUD is not exposed. Mock mode retains its existing demo interactions and storage.

## Reference data and DTO boundary

Categories use the existing paginated `/api/v1/assets/categories/` contract. The F2 backend adds read-only, tenant-scoped `/api/v1/departments/` and `/api/v1/locations/` lists because no discovery endpoints existed. All use DRF `{count,next,previous,results}` pagination. The client requests pages of 100 sequentially until `next` is null, detects duplicate/non-advancing pages, and passes query cancellation through each page. Select controls use backend UUIDs, readable names/codes, active state and shared user/session-scoped TanStack Query keys. Asset Register category/department/location filters now send those UUIDs to Django.

`assetDtos.ts` validates category, department, location and acquisition response DTOs separately from view/domain records. Asset and acquisition creation use explicit request DTO mappers. The browser never supplies organization ownership; Django derives it from the authenticated user and validates all reference IDs against that organization. Backend validation remains authoritative, including foreign-tenant reference rejection and permission checks.

## Write workflow

Asset Manager and Administrator roles can create a DRAFT asset, then record or update its single acquisition, then capitalize through the backend action. Accountant and Department Manager roles can read the acquisition ledger and detail panel; Employee has no acquisition visibility. Django remains authoritative and all 403 responses are surfaced. Roles only shape the controls.

The asset request contains only serializer-supported identity, reference UUIDs, model/manufacturer/serial/description, acquisition date, available-for-use date, initial cost/residual/useful life and SLM policy fields. It does not send organization, status, book value, or capitalization date. Asset creation and acquisition creation are separate backend transactions. The acquisition POST sends purchase price, freight, installation, civil works, other directly attributable cost, vendor/invoice/reference/notes, acquisition date and optional capitalization date. The backend computes `total_cost`. The capitalization POST targets the existing acquisition action; its response and a subsequent asset read provide the resulting status and accounting state.

The write form uses decimal strings and integer minor-unit `BigInt` arithmetic for its display preview. It accepts at most 18 whole and two fractional digits per input, rejects negative values, separators, exponent notation, NaN and Infinity, and checks the combined amount against the backend Decimal(20,2) limit. Optional cost components normalize to `0.00`. The preview is not posted as an acquisition total and never replaces the server response. Only Straight Line (SLM) is offered because it is the only method supported by the current accounting calculation service. Residual value and useful life are checked for basic input validity; Django enforces the domain rules again.

The workflow state records each completed step. If a later operation fails, the UI retains the known asset/acquisition and offers reconcile/reload. Network, server or malformed-response failures after writes are treated as ambiguous; POSTs are never automatically retried. Reconciliation looks up the existing asset by its reserved tag or the acquisition by its one-to-one asset relation before allowing a retry. Existing assets require an explicit review/resume step. Definite validation, permission and conflict failures remain editable. Mutations have no automatic TanStack retry, and a synchronous workflow lock prevents double-click and Enter/click races. Capitalization is a separate action and cannot repeat after success.

TanStack mutation success invalidates only the current user's/session's asset and acquisition query scopes. The Register and detail query refetch backend truth. The Category Register, acquisition ledger and detail acquisition panel share user/session-scoped keys. A generation guard prevents late mutation completions after logout or user change from updating new-session state. Logout clears the F1 QueryClient and token/session state.

## Detail and pending screens

The real detail Overview reports lifecycle, acquisition/capitalization/available-for-use dates, purchase/book/residual values, useful life and method from the Asset API. Its Acquisition panel shows the actual component costs, backend total, currency, references, notes, vendor/invoice, dates and acquisition state. It does not create fake PO, invoice, approval or currency information. Non-overview tabs remain disabled while their real APIs are not integrated. The Acquisitions Ledger exposes only backend-supported fields and actual server pagination/search/status filters.

## Validation and isolated PostgreSQL smoke

```sh
npm test -- --maxWorkers=1
npm run typecheck
npm run lint
npm run build
npm run build -- --mode django
npm audit
python scripts/f1-smoke.py --f2
```

The F2 smoke uses configured PostgreSQL credentials only to create a random `assetflow_f2_<UUID>` disposable database through the maintenance database. It migrates and seeds only that database, runs the new reference API regression tests on a separately created temporary test database, launches Django locally, and uses the actual TypeScript ApiClient, Session, DjangoAssetRepository and AcquisitionWorkflow to log in, load lookups, create, acquire, capitalize, read register/detail and log out. It verifies resulting database values and audit events, then drops the disposable database. It never migrates the configured application database and does not print credentials or tokens.

There is no browser automation framework; React behavior is tested with Vitest and Testing Library. The backend reference endpoints are read-only, organization-scoped and add no migrations. F2 does not integrate depreciation posting or change its calculations, and does not integrate assignments, transfers, maintenance, disposal, assurance, verification, reports, exports, analytics, or AI.
