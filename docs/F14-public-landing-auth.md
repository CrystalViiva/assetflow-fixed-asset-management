# F14 — Public landing and authentication experience

## Route model

The application keeps its existing hash router. `#/` is the public AssetFlow landing page, `#login` is sign in, and existing application routes such as `#dashboard`, `#all-assets`, `#verification`, and `#reports` remain protected in Django mode. An unauthenticated protected route is retained as an internal `next` value and returned to after sign in; invalid, external, protocol-relative, encoded-control, login-loop, and unsupported destinations fall back to the dashboard. An authenticated visit to the landing root or login route opens the dashboard or a validated intended route. Public section anchors remain on the landing page. The mock build keeps its mock application entry and uses the landing CTA to open the demonstration dashboard.

The landing route makes no authenticated requests. Its product-interface visual is clearly marked illustrative, uses no organization data, and uses empty preview values rather than invented portfolio totals.

## Product claims

The page describes the implemented lifecycle: acquisition, capitalization, straight-line depreciation, custody and transfers, maintenance, physical verification, deterministic assurance, disposal, reporting, audit events, and private verification evidence. Accounting copy says “IAS 16-aligned straight-line depreciation workflows”; it does not claim full IAS 16 or IFRS compliance. It explicitly says impairment accounting and other depreciation methods are not represented as available workflows.

The reporting section distinguishes the live Django/PostgreSQL operational dashboard from durable report snapshots and exports, and from Airflow extraction, versioned JSONL, PySpark, and curated Parquet marts. The browser dashboard does not read the batch marts. The page makes no AI, anomaly-detection, predictive-maintenance, malware-scanning, MFA, SSO, cryptographic-ledger, multi-currency, SaaS signup, billing, certification, or customer-reference claim.

## Authentication behavior

The F1 session remains authoritative: access JWT stays in memory; the rotating refresh token stays in `sessionStorage`; one refresh flight is shared; generation checks fence stale work; logout advances the generation, removes refresh material, and clears the QueryClient. The login form submits email/password directly to the existing session method, keeps the password only in component state, clears it after completion, and does not place it in the URL, query cache, or logs. There is no signup, password reset, invitation, SSO, or MFA flow.

Authentication bootstrap blocks protected routes until restoration completes, while the public root can render immediately without protected requests. A failed refresh/final 401 clears session material and routes a protected request to sign in with a session-expired message and safe return route. A 403 remains an authorization error and does not invalidate the session; the dashboard presents an allowed Asset Register destination for a role without analytics access. Logout leads to the public landing page. Application controls do not claim server-side JWT revocation; token expiry and backend authorization remain authoritative.

## UI, responsiveness, and access

The landing page has a responsive header and keyboard-operable mobile menu, lifecycle and capability sections, accounting/control details, reporting architecture, a product UI preview, and a sign-in CTA. Labels, landmarks, heading order, focus rings, reduced-motion handling, and login error/status announcements are present. This is an accessibility baseline, not a certification. No animation or new UI dependency was added.

## Smoke and validation

`python scripts/f1-smoke.py --f14` uses the repository's disposable PostgreSQL runner and a throwaway F14-named database. It seeds an Asset Manager, an Employee, and an asset, then exercises real HTTP login, `/me`, an organization-scoped asset lookup, live dashboard access, employee 403 behavior, logout, user switching, and invalid-refresh expiry using the TypeScript `ApiClient` and `Session`. The runner checks the fixture and removes the disposable database. Frontend tests separately cover safe redirects, no protected request on public root, protected route redirect, login return behavior, and mock/Django application behavior.

Remaining boundaries: there is no browser-driven cross-engine screenshot automation in this repository; responsive layout is implemented and covered by production builds and component tests. Full responsive/accessibility hardening remains outside F14.
