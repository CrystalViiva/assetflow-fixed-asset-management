# F15 — Production UX, performance, and accessibility hardening

## Scope

F15 improves the F1–F14 frontend without adding business behavior or changing backend domain contracts. Django/PostgreSQL remain authoritative; routing/session fencing, financial DTOs, mutation reconciliation, private evidence, and the mock/Django split are unchanged.

## Baseline audit and measurements

Before changes, the production build emitted a 605.50 kB minified `App` chunk (119.84 kB gzip) and Vite's 500 kB advisory. `App.tsx` statically imported the dashboard, every domain screen, and all four action modals, so a successful login downloaded screens unrelated to the route being opened. The application shell used a fixed 16/64-column sidebar and matching left margin at every viewport width. The action panels used generic overlay `div`s without dialog roles, focus management, or Escape behavior. Global focus styling was uneven, while the shell had no skip-to-main link. Most data screens already had localized loading/error/empty states and overflow wrappers around dense tables; F15 preserves those contracts.

The build now emits a 102.29 kB `App` chunk (24.84 kB gzip), down 83% raw and 79% gzip from baseline, with no >500 kB chunk advisory. The auth-only shell chunk dropped from 93.61 to 32.37 kB by separating authentication bootstrap from domain repository construction. Dashboard and feature views load on demand; the largest individual route module is Asset Detail at 80.65 kB. The four mock action panels load only when opened. No analytics library or bundle analyzer was added.

`@google/genai` and `motion` were declared dependencies but had no source imports. They were removed with their unused transitive packages. This removes an unused AI SDK dependency without implementing or advertising AI behavior.

## UX and accessibility changes

- The authenticated application shell now provides a mobile navigation toggle and off-canvas navigation. The drawer closes after route navigation, backdrop activation, or Escape; it receives focus on open, traps Tab navigation, and returns focus to the menu trigger on Escape. Desktop collapse behavior remains available.
- Navigation uses named landmarks, current-page state on primary destinations, and expanded state for the Assets and Organization groups.
- The application provides a skip-to-main link and the main region is focusable.
- Shared focus-visible outlines, reduced-motion-aware route scrolling, and reduced-motion CSS preferences make keyboard/motion behavior consistent.
- Action panels have dialog names and modal semantics, initial focus, focus containment, Escape dismissal, backdrop dismissal, focus restoration, and bounded viewport scrolling. Close controls have accessible names. Pending form submission prevents backdrop dismissal for the consequential transfer, maintenance, and disposal mock actions.
- Lazy route failures render a reload recovery state rather than a blank view. Route loading remains localized to the content region.
- Toast announcements use a polite live region and icon-only dismiss controls have accessible names.
- No new table rendering contract was introduced; existing report and workflow tables retain their horizontal-scroll wrappers.

## Preserved behavior

- Public landing and login stay outside the authenticated application bundle path until login succeeds. The authenticated App still mounts behind the existing session bootstrap and generation key.
- No role, tenant, API, financial, accounting, verification, assurance, reporting, evidence, or audit semantics changed. No mock fallback was introduced for Django screens.
- No new dependencies were added. No backend files, migrations, domain endpoints, or business capabilities were changed.

## Validation

`npm test`, `npm run typecheck`, mock production build, Django-mode production build, `npm audit`, and `git diff --check` are run for F15. The existing Edge/Chrome executables did not run their headless CLI in this environment, and the temporary Playwright Chromium download timed out at the browser CDN, so browser screenshots at 1440/1024/768/390 px could not be captured. Source-level responsive checks and jsdom keyboard/component tests are not represented as a substitute for actual browser rendering review.

## Remaining limitations

F15 is not a full WCAG audit and makes no accessibility conformance claim. It does not replace a screen-reader review, a full manual review of every screen and field, or cross-browser testing. F16 remains the full-system final audit milestone. No backend performance or database query changes were made.
