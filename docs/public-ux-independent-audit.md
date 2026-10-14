# Independent public UX audit

Baseline: `49f6dc4b8b86485c10a6f20f347ff13beb41741f`, fetched from `origin/main` with a clean worktree. This audit builds on that release; accounting, tenant authorization, and billing behavior are outside the change scope.

## Initial findings from rendered screens

Baseline screenshots are retained locally under `.codex-ux-audit/baseline/{mock,django}/`. The homepage was captured at 360, 390, 768, 1024 and 1440px. Each marketing/account screen was captured at 390 and 1440px. `inventory.json` records actual computed typography and document overflow. The existing mock route test and all five existing Django journeys reproduced successfully against disposable PostgreSQL and synthetic accounts.

| Screen | Preserve | Confirmed weakness |
| --- | --- | --- |
| Homepage, desktop | Navy/cobalt identity, clear headline, lifecycle structure, truthful product scope | Many descriptions are 10–12px; footer links are 9px. Preview currency is rendered as `...`; six chart bars have four labels. |
| Homepage, tablet | Product information remains present | 768px keeps the desktop menu, wraps its items, and compresses preview numbers to ellipses. |
| Homepage, mobile | Correct content order and no document overflow | Body and CTA text shrink further; product disclaimer and financial illustration are hard to read. |
| Features/Solutions/Pricing | Clear headings and useful supported-feature descriptions | Repeated white cards, a different logo treatment and minimal footer make these feel disconnected from the homepage. Pricing includes unnecessary provider/seed terminology. |
| Get started / lead forms | Honest mode separation and genuine Django submission | A config request failure is represented as disabled signup. Static enquiry state has no useful onward product action. |
| Illustrative demo | Synthetic records are clearly identified | On mobile the table requires sideways scrolling to see location/custody; visible columns lose context. |
| Login / recovery / signup | Brand continuity, correctly labelled inputs, server-backed flows | 11px labels, 12px inputs, 10px account links; 7px decorative text. The password toggle is 33×32px. Mobile places a 220px promotional panel before the form. |

## Reproduced functional failures

The baseline production build failed all four newly added `public-recovery.spec.ts` tests. Traces/screenshots remain in `.codex-ux-audit/baseline/recovery/`.

1. Missing startup module: recovery renders, but its home link only changes the hash and never retries the failed import.
2. Public render exception: the outer React boundary retains its failed state when the hash changes, so its home link is stuck.
3. Direct `/#/section-features`: routing accepts the alias, but browser anchor lookup uses the unnormalized fragment and never scrolls to the section.
4. Escape does not close either public mobile navigation or restore focus.

These are additional failures beyond the ambiguous-route corrections in the baseline. Fault injection deliberately produces browser/network errors; successful recovery must be checked without suppressing those errors.

## Refinement approach

Preserve the homepage composition and accurate feature content. Introduce a shared public header/footer, readable 16px body/input and 14px supporting/control text, a 12px decorative caption scale, larger hit areas, a tablet breakpoint, and compact mobile account presentation. Keep preview artwork in local HTML/CSS and give the mobile demo table a labelled stacked layout. Distinguish unavailable configuration from disabled signup, reload the document for catastrophic recovery, retain an initial HTML recovery shell, and defer account/operator route bundles until requested.

The [Asset Panda public site](https://www.assetpanda.com/) informed the audit's emphasis on product substance, readable hierarchy and clear conversion paths. No branding, artwork, testimonials or claims were reused.

## Validation

### Additional causes corrected during iteration

- The outer router normalized `/#/all-assets`, while the workspace read the raw hash and selected the wrong view. Both now use the same parser; a before-fix failure is retained in `.codex-ux-audit/workspace-alias-before/`.
- Footer navigation retained the previous page's scroll position. A link back to the current route also generated no hashchange, leaving its heading offscreen. Route transitions and repeated public links now explicitly restore page position. Section links retain their own scrolling behavior.
- An authenticated platform operator's public workspace link pointed at the tenant dashboard. Shared public navigation now chooses the operator or tenant destination from the existing authenticated role.
- Failed public-config requests looked like disabled signup. Get started and signup now show an explicit error, retry and contact path. A real disabled configuration remains managed onboarding; no backend policy changed.
- Failure of the initial entry script preceded all React boundaries and left an empty root. Initial HTML now retains a branded loading/reload shell. Missing hashed files return a real nginx 404; the entry HTML revalidates instead of retaining stale chunk references.

### Visual comparison

All screenshot paths below are local, ignored artifacts relative to the repository root. The full inventory includes homepage widths **360, 390, 768, 1024 and 1440px**, and each public/account route at **390 and 1440px**. Final screenshots were recaptured from the final UI, after the fixes and second visual review; PNGs are not committed.

| Screen | Before | After | Visual result |
| --- | --- | --- | --- |
| Homepage desktop | `.codex-ux-audit/baseline/django/home-1440-viewport.png` | `.codex-ux-audit/final/django/home-1440-viewport.png` | Preserved navy/cobalt composition; larger product framing, legible body/CTA/caption text, real currency glyphs and consistent chart categories. |
| Homepage mobile | `.codex-ux-audit/baseline/django/home-360-viewport.png` | `.codex-ux-audit/final/django/home-360-viewport.png` | Deliberate two-line headline, full-width controls and readable preview composition. |
| Homepage tablet | `.codex-ux-audit/baseline/django/home-768-viewport.png` | `.codex-ux-audit/final/django/home-768-viewport.png` | Collapsed navigation removes crowding; wide preview no longer truncates the sample amounts. |
| Features | `.codex-ux-audit/baseline/django/features-1440.png` | `.codex-ux-audit/final/django/features-1440.png` | Shared brand/header/footer; numbered feature sections replace repetitive cards. Solutions, security, pricing, help and about use the same treatment. |
| Mobile demo | `.codex-ux-audit/baseline/django/demo-390.png` | `.codex-ux-audit/final/django/demo-390.png` | Labelled stacked records expose every column without sideways scrolling. |
| Mobile login | `.codex-ux-audit/baseline/django/login-390.png` | `.codex-ux-audit/final/django/login-390.png` | Form first, 16px inputs, 14px labels/links, 44px password toggle and clear recovery. |
| Desktop login | `.codex-ux-audit/baseline/django/login-1440.png` | `.codex-ux-audit/final/django/login-1440.png` | Readable split composition, stronger heading, consistent account footer. Signup, recovery, verification and invitations share the shell. |

Open navigation: `.codex-ux-audit/final/{mock,django}/mobile-menu-390.png`. Full-page screenshots include the closing CTA/footer. `inventory.json` records measured text sizes and overflow. Functional text is at least 14px in the browser checks; decorative miniature-preview labels may be 10–12px, accompanied by a readable fictional-data caption. Body/input text is generally 16px; hero supporting copy is 18px.

### Reproducible checks and results

Commands were executed from PowerShell with Chrome at `C:\Program Files\Google\Chrome\Application\chrome.exe`. PostgreSQL 17 ran in the dedicated local disposable cluster on port 55432. Every browser runner database was synthetic and removed by its runner after the tests. No customer data or production service was used.

| Check | Command / setup | Result |
| --- | --- | --- |
| TypeScript | `npm.cmd run typecheck` | Pass |
| Repository lint command | `npm.cmd run lint` (currently invokes `tsc --noEmit`) | Pass |
| Complete frontend regressions | `npm.cmd test -- --reporter=dot --maxWorkers=2` | **247 passed, 23 files**; `.codex-ux-audit/frontend-tests-final.log` |
| Mock production build | `$env:VITE_DATA_SOURCE='mock'; node node_modules/vite/bin/vite.js build` | Pass; `.codex-ux-audit/mock-build.log` |
| Mock browser suite | Vite preview on 3007, then `node node_modules/@playwright/test/cli.js test e2e/public-routing.spec.ts e2e/public-links.spec.ts e2e/public-quality.spec.ts e2e/public-recovery.spec.ts` with `VITE_DATA_SOURCE=mock` | **11 passed**, no skips/failures; `.codex-ux-audit/final/mock-results/report.json` |
| Django build + browser/API journeys | `.\venv\Scripts\python.exe scripts/commercial-smoke.py --port 55432 --nginx .codex-commercial-tools/nginx/nginx-1.30.5/nginx.exe` | **17 passed**, no skips/flakes/failures; `.codex-browser-7da9659f/results/report.json`; build/evidence JSON in the same run directory |
| Real disabled signup policy | Same runner plus `--self-service-disabled --tests e2e/public-service.spec.ts` | **1 passed**; `.codex-browser-fa4b9c64/results/report.json` |
| Dependency audit | `npm.cmd audit --fetch-retries=0 --fetch-timeout=15000` | **0 vulnerabilities** |
| Whitespace | `git diff --check` | Pass |

For screenshot runs set `E2E_AUDIT_DIR=.codex-ux-audit/final` and `E2E_BROWSER_EXECUTABLE` to the installed Chrome binary. Mock runs set `E2E_OUTPUT_DIR=.codex-ux-audit/final/mock-results`; the Django runner assigns its own output directory. The disabled-policy test must use its selected file because other existing commercial journeys intentionally require enabled signup.

The initial unlimited-worker frontend rerun exhausted worker startup time while browser checks were running. The isolated two-worker rerun completed all 247 tests. One existing presentation-claims test still emits React's empty image `src` warning from its fixture; public browser checks report no such error. An initial dependency-audit DNS failure was retried successfully. There are no unresolved final test failures. Backend application code was unchanged; full backend regression tests were not rerun. Existing commercial browser tests still exercise real API persistence and identity behavior.

### Functional evidence

- Luna's original mock route test and five Django browser journeys were reproduced before refinement. The expanded suites retain those tests.
- The final link inventories contain **405 visible anchor instances / 32 distinct actions in mock** and **352 / 34 in Django**. Reused header/footer links are inventoried on each page. Normal navigation reports **zero page errors, console errors, failed network requests or HTTP error responses** in both inventories. The deliberate module/render/503/invalid-login injections produce expected errors and assert visible recovery; they are not counted as error-free ordinary browsing.
- Real enabled signup sends a captured email, verifies its token, creates a company workspace and authenticates its synthetic owner. Real disabled signup returns 403. No mock account success is simulated.
- Password reset, invitation acceptance, managed provisioning, protected redirects, valid/invalid login, refresh-token rotation, expiration and logout are exercised against the local backend. Demo requests and contact-sales enquiries are checked for persistence. Failed requests never claim success.
- [The navigation matrix](public-navigation-matrix.md) maps the shared header/footer, page CTAs, form controls, static limitations and recovery actions to their tests.

### Accessibility and performance

- Axe WCAG A/AA scans (including applicable 2.1/2.2 tags) found **zero automated violations** on 15 mock routes and 19 Django routes at both 390 and 1440px: **68 page/viewport scans**. Results: `.codex-ux-audit/final/{mock,django}/accessibility.json`.
- Keyboard menu opening, Escape/focus restoration, skip navigation, visible focus, labelled controls, error announcements, reduced motion and mobile targets were reviewed. Browser checks also verify no document overflow at the requested five widths.
- Reflow was checked at a 720 CSS-pixel viewport representing a 1440px screen at 200% browser zoom, plus an independent 200% text-size increase. This is layout-equivalent coverage, not a claim of native-browser zoom testing on every browser. Screenshot: `text-resize-200-percent.png` in each final mode folder.
- Final nginx homepage sample: **317,095 bytes decoded JavaScript / 99,388 bytes gzip**, **105,331 bytes CSS / 20,890 bytes gzip**, one **48,256-byte local font**, and **CLS 0**. Measurements are one local unthrottled Chromium visit, not Lighthouse scores or field performance. Full resource timings are in `.codex-ux-audit/final/django/performance.json`.
- Account/operator pages are lazy-loaded. Public browsing does not fetch the authenticated `App` bundle. The naira glyph uses the system-font currency styling, avoiding an extra 85KB extended font. No runtime dependency or bitmap image was added; axe is a development-only dependency.

### Independent verdict and remaining limits

The site now approaches a credible commercial SaaS presentation: the original visual identity is retained, typography is comfortable, public pages are cohesive, and the account journey is readable on mobile. The largest verified gaps were readability and recovery/navigation behavior, rather than a need for another wholesale redesign.

The product visuals remain clearly labelled HTML/CSS illustrations. They explain supported workflows but are not screenshots of real customer records or a substitute for an operator-led demonstration. There are no fabricated customers, awards, prices or certification claims. Automated accessibility and Chromium coverage do not constitute a complete assistive-technology or cross-browser certification; no Safari/Firefox or throttled Lighthouse run was performed.

The static site is suitable for marketing and illustrative demonstrations, with explicit limitations on enquiries/login/trials. A live customer conversion funnel still requires configured Django hosting, HTTPS/DNS, PostgreSQL and real identity-email delivery. Backups, restore acceptance, monitoring and owner-approved service terms remain deployment responsibilities described in the commercial readiness documents. Local validation does not establish that a publicly deployed service is live.
