# Public and identity navigation matrix

Route contract: the app uses hash routes. Homepage section hashes are namespaced with `section-` so they cannot collide with marketing pages. A direct `/#/login` is accepted as an alias for `/#login`. Unknown routes render a recovery page.

| Visible action | Source | Destination / result | Mock / static | Django, signed out | Django, signed in | Evidence |
| --- | --- | --- | --- | --- | --- | --- |
| AssetFlow logo | All public pages | `#/` homepage | Home | Home | Stays on public homepage; workspace CTA opens the app | `PublicLandingPage.test.tsx`; `ApplicationRootF14.test.tsx` |
| Features | Public header/footer | `#section-features` | Scroll to lifecycle | Scroll to lifecycle | Scroll to lifecycle | `PublicLandingPage.test.tsx`; `public-routing.spec.ts` |
| Solutions | Public header/footer | `#section-solutions` | Scroll to supported use cases | Scroll to supported use cases | Scroll to supported use cases | `PublicLandingPage.test.tsx`; `public-routing.spec.ts` |
| How it works | Public header/footer | `#section-how-it-works` | Scroll to onboarding steps | Scroll to onboarding steps | Scroll to onboarding steps | `PublicLandingPage.test.tsx` |
| Pricing | Public header/footer | `#section-pricing`; pricing route from marketing pages | Commercial pricing by discovery; no invented amount | Same | Same | `PublicLandingPage.test.tsx` |
| Request demo | Public CTA/footer | `#request-demo` | Explains live submission needs configured site; no false success | Lead form posts to Django public leads API | Lead form posts to Django public leads API | `MarketingPages.tsx`; existing `commercial.spec.ts` |
| Get started | Public CTA | `#get-started` | Managed onboarding/demo; no trial account creation | Trial signup only if public config enables it; otherwise managed onboarding | Same public config; the signed-in homepage remains public and its workspace CTA opens the app | `public-routing.spec.ts`; `CommercialViews.test.tsx` |
| Log in | Public header/footer | `#login` | Honest static-build explanation; demo/contact alternatives; no password form | Real login form with safe internal `next` handling | Redirects to validated destination/dashboard | `ApplicationRootF14.test.tsx`; `public-routing.spec.ts`; existing `commercial.spec.ts` |
| Create trial / signup | Get started or direct `#signup` | Signup or managed-onboarding state | Static explanation; no registration claim | Signup form follows backend self-service flag and email verification | Existing session preserved; signup route remains available per server policy | `ApplicationRootF14.test.tsx`; `CommercialViews.test.tsx`; existing `commercial.spec.ts` |
| Illustrative demo | Public footer | `#demo` | Read-only fictional records | Same | Same | Existing `commercial.spec.ts`; `public-routing.spec.ts` |
| Security | Public footer | `#section-security`; marketing-page route where linked | Actual control descriptions and deployment caveat | Same | Same | `PublicLandingPage.test.tsx` |
| Help / About | Public footer | `#help` / `#about` | Supported informational pages | Same | Same | Existing `commercial.spec.ts` |
| Forgot password | Django login | `#forgot-password` | Not offered as live recovery in static login explanation | Real recovery flow | Session-specific identity flow | `IdentityViews.tsx`; existing `commercial.spec.ts` |
| Verify email / invitation | Django account messages | `#verify-email` / `#accept-invitation` | Not available without Django | Existing signed-token routes | Existing signed-token routes | Existing `commercial.spec.ts` |
| Unknown route | Direct hash | Branded not-found recovery | Home action | Home action, no auth redirect loop | Home action, no auth redirect loop | `ApplicationRootF14.test.tsx`; `public-routing.spec.ts` |
| Mobile menu | Public and marketing header | Same destinations as desktop, menu closes after selection | Keyboard and pointer operable | Same | Same | `PublicLandingPage.test.tsx`; `public-routing.spec.ts` |

The Playwright test covers mock-mode render, route changes, section links, back/forward, mobile menu, invalid route, viewport overflow and client errors. Django end-to-end registration, login, recovery, lead persistence, invitations and protected navigation remain covered by the disposable-service suite in `e2e/commercial.spec.ts` / `scripts/commercial-smoke.py`; they require its PostgreSQL/Django setup.
