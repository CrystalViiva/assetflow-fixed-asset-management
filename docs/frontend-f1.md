# F1: authentication and real asset reads

F1 preserves the React 19 / TypeScript / Vite / Tailwind application, hash navigation, enterprise shell, mock workflows, modals and toast infrastructure. Django mode connects **Asset Register and Asset Detail Overview only**. All other routes explicitly show integration pending. This milestone does not add backend features, accounting calculations, M11 or AI.

## Running either source

Use Node 24.15 or newer in the Node 24 line (validated with 24.19). Install the tracked lockfile with `npm ci`.

```dotenv
# Local UI development; no authentication or backend required
VITE_DATA_SOURCE=mock

# To use Django instead, set VITE_DATA_SOURCE=django
VITE_BACKEND_API_URL=/api/v1
DJANGO_DEV_PROXY_TARGET=http://127.0.0.1:8000
```

Unset `VITE_DATA_SOURCE` defaults to mock for existing developers. Any other value, including an empty value or `DJANGO`, fails clearly; there is no automatic detection or fallback. Restart Vite after changing environment variables and rebuild for production. The entrypoint renders a configuration/startup error if configuration or application loading fails.

Run `npm run dev` and use an existing Django email/password account with organization membership. F1 does not provide registration, SSO, password reset, or account provisioning. Mock mode retains the localStorage demo repository; its navbar identifies it as mock data. The repository rejects accidental mock reads/writes in Django mode.

## Browser connectivity

Vite forwards `/api/v1` to `DJANGO_DEV_PROXY_TARGET` during development. The browser uses its own origin, so no backend CORS relaxation is needed. The target variable is server-side Vite configuration, not a `VITE_*` browser variable. Existing local `.env` files with an absolute `VITE_BACKEND_API_URL` should be changed to `/api/v1` to use the proxy.

For production, configure the web server/reverse proxy to serve `/api/v1` from Django over HTTPS, or provide a deliberate HTTPS API base URL and configure a restricted backend CORS allowlist in deployment. Vite's development proxy is not a production server or a preview proxy. No CORS settings were changed in Django. URLs containing embedded credentials, query strings, fragments, backslashes or whitespace are rejected.

## Architecture

`ApplicationRoot → AuthProvider → authenticated App shell → asset query hooks → DjangoAssetRepository → ApiClient → Django`.

- `config.ts` owns source/base selection. Existing Register/Detail components dispatch to their real or preserved mock implementation based on this configuration.
- `apiClient.ts` is the sole fetch boundary. It serializes JSON/query parameters, sets bearer authorization, handles error envelopes and network failures, rejects redirects, disables HTTP caching, supports request cancellation and bounds each attempt with a 20-second timeout. Methods GET/POST/PUT/PATCH/DELETE are supported; F1 asset operations are reads only.
- `session.ts` owns access/refresh tokens, identity, initialization, logout, refresh and subscriptions. `AuthProvider` exposes user, role, authenticated, initializing, login and logout using `useSyncExternalStore`.
- `runtime.ts` constructs one application QueryClient, transport, session and Django repository. Query data is never copied into React component state; component state holds filters, pagination and navigation only. Legacy demo views retain their existing mock state.
- `assetQueries.ts` owns stable list/detail query keys including user ID and session generation. Queries are fresh for 30 seconds, inactive cache expires after five minutes, window focus refetches stale data, and automatic error retries are disabled. A reusable scoped invalidation function is provided for future successful mutations; F1 has no remote asset mutations.
- `assetDtos.ts` validates unknown JSON into explicit wire DTOs, then maps DTOs into the read model `AssetRecord`. The historical mock `Asset` requires fabricated custody, insurance, money calculations and other fields; it is deliberately not used as the real asset contract. The wide `IAssetRepository` remains the demo workflow interface; `AssetReader` is the narrow real read interface replacing the speculative Django bridge.

## Actual contract map

Audited against Django URLs, models, serializers, filters, permissions, JWT settings, exception handler and generated/validated OpenAPI. No endpoint names are guessed.

| Concept | Endpoint / DTO | Frontend mapping |
| --- | --- | --- |
| Login | `POST /api/v1/auth/token/`, `{email,password}` → `{access,refresh}` | Session tokens, then identity lookup |
| Restore / refresh | `POST /api/v1/auth/token/refresh/`, `{refresh}` → rotated `{access,refresh}` | Single-flight token replacement |
| Identity | `GET /api/v1/auth/me/`, `{id,email,role}` | Integer user ID, email, exact backend role |
| Register | `GET /api/v1/assets/` | `PageDto<AssetDto>` → `AssetPage` |
| Detail | `GET /api/v1/assets/{UUID}/` | `AssetDto` → `AssetRecord`; invalid route UUID becomes a not-found state |
| Identity fields | `id`, `asset_tag`, `name`, `description` | UUID string, `tag`, `name`, `description` |
| Organization/category | Flat `*_id`, `*_name`, category code | Named relation objects, not invented nested wire data |
| Department/location | Nullable flat IDs/names/codes | Nullable relation objects |
| Serial/manufacturer/model | `serial_number`, `manufacturer`, `model_number` | `serialNumber`, `manufacturer`, `model` |
| Lifecycle/condition | Backend status/condition enums | Known values preserved; unknown values fail explicitly |
| Dates | Nullable `acquisition_date`, `capitalization_date`, `available_for_use_date` | Nullable date strings, no default dates |
| Policy | `useful_life_months`, `depreciation_method` | Nullable months, validated method |
| Amounts | `purchase_cost`, `residual_value`, `accumulated_depreciation`, `current_book_value` | Canonical Decimal strings |
| Timestamps | `created_at`, `updated_at` | `createdAt`, `updatedAt` |

The backend category lookup exists at `/api/v1/assets/categories/` and is paginated, but F1 does not fetch lookup lists. There are no department/location lookup endpoints. All three filters accept exact case-insensitive names or UUIDs through the asset endpoint, so F1 presents labeled text inputs. Category administration remains pending.

The backend supports DRAFT and PENDING_CAPITALIZATION in addition to the historical mock lifecycle states. Backend `DEPARTMENT_MANAGER` is preserved, not confused with mock `DEPT_MANAGER`. Unknown roles confer no frontend privileges. No claims are decoded to invent identity; `/auth/me/` is authoritative.

## Session and refresh behavior

Login posts credentials, validates the token pair, and fetches `/auth/me/` before mounting protected content. On reload, the session reads its refresh token, rotates it once, retrieves identity, and then opens the shell. React StrictMode shares the same initialization promise. With no token, startup immediately shows login. Invalid/expired refresh or failed identity validation clears the session.

Access tokens live only in memory. Only the refresh token is persisted under `assetflow_refresh` in **sessionStorage**, supporting reload in the same tab. It is not put in localStorage, a URL, logs or the query cache. Passwords are cleared from the login form after submission. This is pragmatic JSON bearer JWT authentication, **not XSS-proof storage**: same-origin malicious JavaScript can read sessionStorage and act as the user. Production needs HTTPS and normal XSS defenses. This milestone does not redesign the backend to HttpOnly cookies.

Multiple protected 401s await one in-flight refresh promise. Once it succeeds, each request retries once using the new token. A delayed 401 belonging to the previous access token reuses the already refreshed token. Refresh calls themselves never refresh recursively. A second 401 ends the session. Failure, malformed token response, persistence failure or timeout clears tokens/identity/cache and rejects waiters.

A generation counter invalidates work started before logout or a new login. Late token/identity/asset responses cannot revive a session, expose an old response or clear a newer user's session. Query keys also contain that generation and the user ID. Logout and user initialization clear the entire QueryClient, including in-flight queries and cached server data. The shell remounts for a new identity/session so transient UI state is also reset.

Logout is local: the backend has no logout/revoke endpoint. Its JWT settings use a 15-minute access lifetime and one-day rotating, blacklisted refresh tokens. An already stolen token remains subject to those backend lifetimes. Sessions are per tab, with no cross-tab synchronization. Browsers may copy sessionStorage when duplicating a tab; the first refresh then consumes that shared token and the other tab must sign in again. Do not use this as a cross-tab persistent-login design.

## Register and detail behavior

DRF's `{count,next,previous,results}` is mapped explicitly. Pages are one-based, default size is 25, and sizes cap at 100. Returned links become next/previous flags; the client never follows server-provided URLs with a bearer token. Empty results show page 1 of 1. Search, relation/status filters, sorting and page-size changes reset page to 1 atomically. Query keys and AbortSignals prevent a slow old search response from replacing the current result. Explicit Refresh and error retry controls are provided.

Search covers tag, name, serial/model, manufacturer and description. Ordering maps frontend concepts to backend allowlisted fields. Supported relation/status filters run on Django. Custody, warranty, audit quick filters and cost ranges are not shown as functional filters in real mode. F1 sends searches immediately; it does not debounce them.

Detail Overview shows real identity, relations, description, lifecycle/condition, serial/manufacturer/model, available dates, accounting values, policy and timestamps. Missing values display `—`. No custody, vendor, cost-component, insurance, health-score or currency fields are invented. The asset serializer exposes no currency, so amounts are displayed without an assumed currency symbol. String grouping preserves all Decimal digits, including values beyond JavaScript's safe numeric precision; there are no frontend accounting or depreciation calculations in Django mode.

The six other detail tabs are disabled and labeled **Integration pending**. Other screens, including dashboard, creation, categories, acquisitions, assignments, transfers, depreciation, maintenance, disposals, reports, organization, RBAC administration, audit and settings, show the pending state in Django mode. Mock mode keeps their original behavior. Real-mode header/sidebar/breadcrumbs omit demo alerts, asset counts, workflow badges, facility, period and currency claims.

F1 is read-only for every role: write actions are hidden, real role/email are displayed, and backend 403s produce an authorization error. Frontend visibility is not security; Django remains authoritative for organization, department and employee scope.

## Error and UX boundary

`ApiError` distinguishes network, authentication, authorization, validation, not-found, conflict, server and contract failures. Known public error-envelope messages and field-level validation arrays are retained. Unknown response bodies, HTML and 5xx details are never rendered as raw internals. Shared loading/error/empty states use status/alert roles. Login has labels, keyboard submission, busy state and distinct invalid-credential/network feedback. Protected content is withheld while initialization is pending.

## Validation

```sh
npm test
npm run typecheck
npm run lint
npm run build
npm audit
git diff --check
```

`npm run lint` is the repository's existing TypeScript check, not ESLint. There is no configured formatter/check command. Tests use Vitest, jsdom and React Testing Library, with transport mocks and behavior assertions rather than snapshots. On Windows environments that restrict worker IPC, run tests with appropriate process permissions and `npm test -- --maxWorkers=1`.

Tests cover login failures/success, restoration/StrictMode, bearer headers, single-flight and delayed 401 refresh, failed/timeout refresh, bounded retry, logout/login races, cache isolation between users, error envelopes, DTO/null/enum/Decimal handling, pagination, query serialization, search/filter resets and races, Register/Detail UX, real shell/source isolation and preserved mock persistence.

`python scripts/f1-smoke.py` uses configured PostgreSQL credentials to create a unique `assetflow_f1_<UUID>` database through the maintenance database. It migrates/seeds only that disposable database, starts Django on a temporary loopback port, and exercises the actual TypeScript transport/session/repository with native fetch. It terminates Django and drops only its own database in cleanup. No database dump or credentials are written. It needs permission to create databases and start/connect to local processes; it never migrates the configured application database. No browser E2E framework was introduced; the real API smoke plus deterministic React behavior tests are the F1 integration validation.

Known limits: two integrated read screens; no remote writes or lookup dropdowns; no currency in the asset contract; no persistent/cross-tab login; no server-side logout endpoint; legacy demo screens retain their original state architecture. No backend source or migration files were changed for F1.

### F1 completion validation

- 85 tests passed across four frontend test files, including the real-mode shell and user A → logout → user B cache-isolation path.
- Typecheck and the existing lint command passed. Both explicit mock and Django production builds passed. No formatter is configured.
- `npm audit` reported zero vulnerabilities. Existing locked dependency versions were preserved.
- Generated Django OpenAPI validation passed. The real TypeScript/Django/PostgreSQL smoke passed using a disposable database, which was removed afterward. No browser automation framework was added.
- Adversarial review removed real-mode demo sidebar counts/workflow badges and facility claims, corrected icon accessibility, rejected URL normalization edge cases, and added regressions for timeout, denied token storage, and an old refresh failing after a new login. Configuration failures now render an explicit startup error.
