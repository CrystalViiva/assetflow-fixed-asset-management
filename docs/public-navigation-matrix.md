# Public and identity navigation matrix

## Contract and evidence

Hash routes are normalized by `src/routing/hash.ts` in both the public router and workspace. `/#/login` and `/#login` are equivalent. Homepage section identifiers use `section-`; marketing pages have separate routes. Navigation to a page starts at the top, including repeated links to the current page. Section navigation scrolls on direct load, reload and internal navigation. Unknown routes have a branded not-found page.

This matrix was independently rechecked against production builds in mock mode and Django mode with disposable PostgreSQL, synthetic accounts, captured email and nginx. Exact runs, screenshots and limitations are recorded in [the independent audit](public-ux-independent-audit.md).

Test abbreviations: **links** = `e2e/public-links.spec.ts`; **routes** = `e2e/public-routing.spec.ts`; **recovery** = `e2e/public-recovery.spec.ts`; **service** = `e2e/public-service.spec.ts`; **commercial** = `e2e/commercial.spec.ts`; **quality** = `e2e/public-quality.spec.ts`. The link audit inventories every rendered public anchor and traverses every distinct internal action plus reload. Form/button journeys are separate browser tests.

| Visible action | Source / destination | Mock or static result | Django signed out | Django authenticated | Test reference | Status |
| --- | --- | --- | --- | --- | --- | --- |
| AssetFlow logo / Back to AssetFlow | Public/account screens to `#/` | Homepage | Homepage | Public homepage; session preserved | links, commercial, service | Pass |
| Features / Explore features | Home header/footer/closing to `#section-features`; other pages to `#features` | Correct section or feature page | Same | Same | links, routes, recovery | Pass |
| Solutions | Header/footer to home section or `#solutions` | Supported use cases | Same | Same | links, routes | Pass |
| How it works | Header/footer to home section or `#how-it-works` | Onboarding explanation | Same | Same | links, routes | Pass |
| Pricing / Request pricing | Header/footer to home section or `#pricing`; pricing CTA to `#request-demo` in static mode | Discovery-based pricing; no invented charges | Pricing and onboarding path | Same | links, commercial | Pass |
| Explore the product | Hero to `#section-product-preview` | Labelled fictional preview | Same | Same | links, routes | Pass |
| Explore asset features | Finance section to `#section-features-detail` | Custody/workflow showcase | Same | Same | links | Pass |
| Request demo / Request a demo / Request a demonstration / Talk through your rollout / Talk to our team | Header, hero, pages, footer to `#request-demo` | Explicit live-submission limitation; working fictional-demo alternative | Real public leads form | Same public form | links, commercial, service | Pass |
| Contact sales | Footer/account/onboarding to `#contact-sales` | Same honest static limitation | Real lead form with sales intent | Same | links, commercial | Pass |
| Submit demonstration/sales request | Lead form | No nonfunctional submit form | Success only after API accepts request; real persistence checked; failures retain input and show error | Same endpoint | commercial, service | Pass |
| Consent checkbox / form fields | Lead form | Not offered | Required consent and browser/server validation | Same | commercial, service | Pass |
| Get started / Set up a workspace | Public/account links to `#get-started` | Managed onboarding explanation and illustrative demo | Server config selects trial or managed options | Same policy; no session replacement | links, service, commercial | Pass |
| Continue to secure signup / trial entry | Get started to `#signup` | Direct signup shows static explanation; no account created | Real signup only when server enables it | Server policy remains authoritative | links, commercial, service | Pass |
| Send verification email / Verify & create workspace | Signup / tokenized `#verify-email` | Not offered as live functionality | Captured email link, real verification and isolated workspace creation | Existing session handling retained | commercial | Pass |
| Trial disabled state | `#signup`, `#verify-email`, `#get-started` | Static explanation | Managed onboarding/contact sales; real API returns 403 | Same backend flag | service with `--self-service-disabled` | Pass |
| Check again / Try again | Config unavailable on Get started/signup | Not applicable | Retry real config request; outage is distinct from disabled signup | Same | service | Pass |
| Log in / Sign in | Public/account links to `#login` | Designed explanation; demo/contact alternatives, no password form | Real authentication, useful invalid/offline errors | Safe internal destination; operator goes to platform | links, service, commercial; `ApplicationRootF14.test.tsx` | Pass |
| Show password / Hide password | Login form | Not offered | Keyboard/pointer button toggles input visibility | Same login component | service, quality | Pass |
| Open workspace | Signed-in public header/footer | Not offered | Login required for protected routes | Operator to `#platform`; tenant to `#dashboard` | service, commercial; `ApplicationRootF14.test.tsx` | Pass |
| Sign out / session restore | Private workspace | Mock demo remains illustrative | Protected routes redirect to login with safe `next` | Logout returns home; reload rotates refresh token; expired token returns login | service, commercial | Pass |
| Forgot password / Send reset link | Login to `#forgot-password` | Not offered as live recovery | Real recovery submission and captured email | Identity flow preserves server validation | commercial | Pass |
| Set password / Continue | Tokenized `#reset-password`, `#accept-invitation` | Not offered | Valid links submit; missing/invalid token gets useful error | Existing token/session isolation retained | commercial, quality | Pass |
| Illustrative demo / Explore the illustrative demo / See a fictional asset register | Page/footer links to `#demo` | Read-only labelled fictional records | Same | Same | links, commercial, quality | Pass |
| Security / Review security controls | Home section/detail or `#security` | Actual controls plus hosting caveat | Same | Same | links | Pass |
| Customer guide / About AssetFlow | Footer to `#help` / `#about` | Informational pages | Same | Same | links | Pass |
| Open/Close navigation / Escape / menu links | Shared header at mobile/tablet widths | Opens/closes, Escape restores focus, selection closes | Same | Same destinations; workspace link follows role | routes, recovery, quality | Pass |
| Skip to content | First keyboard link to focused main | Focus/scroll without changing route | Same | Same public layout | links | Pass |
| Return to AssetFlow | Invalid route | Branded 404 to home | Same, no auth loop | Same | routes, quality; `ApplicationRootF14.test.tsx` | Pass |
| Return home / Reload application | Startup or React render failure | Document reload clears failed import/boundary | Same | Auth session restored normally | recovery | Pass |
| Reload the homepage | Initial HTML if entry script is missing | Visible before JavaScript; reload works after asset returns | Same | Same | recovery | Pass |
| Source repository | Footer to configured GitHub repository | Valid public external destination, new-tab label | Same | Same | Link inventory + verified Git remote; external click not automated | Pass |
| Back/forward / direct reload / normalized aliases | Browser navigation | Correct public routes/sections; workspace aliases agree with outer router | Correct public pages, identity and protected routes | Session remains scoped | routes, recovery, commercial, service | Pass |

Static builds cannot persist leads, authenticate customers, send identity email or create database-backed trials. No separate hosted application URL is guessed. The Django tests use real local APIs and disposable records; injected 503/network failures test recovery, not hosted availability. External email delivery, hosting and production operations require deployment-specific acceptance.
