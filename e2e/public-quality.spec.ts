import { expect, test } from '@playwright/test';
import { mkdirSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import AxeBuilder from '@axe-core/playwright';

const django = process.env.VITE_DATA_SOURCE === 'django';
const captureRoot = join(process.env.E2E_AUDIT_DIR || '.codex-ux-audit/final', django ? 'django' : 'mock');

test('public and identity visual inventory', async ({ page }) => {
  test.setTimeout(120_000);
  mkdirSync(captureRoot, { recursive: true });
  const inventory: unknown[] = [];
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  const capture = async (route: string, width: number) => {
    await page.setViewportSize({ width, height: width < 600 ? 844 : 1000 });
    await page.goto(`/#${route}`);
    await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
    await page.locator('text=Loading onboarding options').waitFor({ state: 'hidden' });
    await page.getByRole('heading', { name: 'Checking trial availability' }).waitFor({ state: 'hidden' });
    await page.evaluate(() => document.fonts.ready);
    const name = `${route === '/' ? 'home' : route}-${width}`;
    await page.screenshot({ path: join(captureRoot, `${name}.png`), fullPage: true, animations: 'disabled' });
    if (['/', 'login', 'signup'].includes(route)) await page.screenshot({ path: join(captureRoot, `${name}-viewport.png`), animations: 'disabled' });
    inventory.push(await page.evaluate(({ name }) => ({
      name,
      overflow: document.documentElement.scrollWidth > innerWidth,
      smallText: [...document.querySelectorAll('p, label, a, button, input, small')]
        .filter(el => el.getClientRects().length && parseFloat(getComputedStyle(el).fontSize) < 14)
        .map(el => ({ text: el.textContent?.trim().slice(0, 70), size: getComputedStyle(el).fontSize, color: getComputedStyle(el).color })),
    }), { name }));
  };
  for (const width of [1440, 1024, 768, 390, 360]) await capture('/', width);
  for (const route of ['features', 'solutions', 'how-it-works', 'pricing', 'get-started', 'request-demo', 'contact-sales', 'demo', 'security', 'about', 'help', 'login', 'signup', ...(django ? ['forgot-password', 'reset-password', 'verify-email', 'accept-invitation'] : [])]) {
    for (const width of [1440, 390]) await capture(route, width);
  }
  await page.goto('/?menu-capture#/');
  await page.getByRole('button', { name: 'Open navigation' }).click();
  await expect(page.getByRole('navigation', { name: 'Mobile navigation' })).toBeVisible();
  await page.screenshot({ path: join(captureRoot, 'mobile-menu-390.png'), animations: 'disabled' });
  writeFileSync(join(captureRoot, 'inventory.json'), JSON.stringify(inventory, null, 2));
  expect(errors).toEqual([]);
});

test('public accessibility, readable controls and reflow', async ({ page, browser }) => {
  test.setTimeout(240_000);
  const violations: unknown[] = [];
  const routes = ['/', 'features', 'solutions', 'how-it-works', 'pricing', 'get-started', 'demo', 'request-demo', 'contact-sales', 'security', 'help', 'about', 'login', 'signup', 'not-a-page', ...(django ? ['forgot-password', 'reset-password', 'verify-email', 'accept-invitation'] : [])];
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: 1000 });
    for (const route of routes) {
      await page.goto(`/#${route}`);
      await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
      await page.locator('text=Loading onboarding options').waitFor({ state: 'hidden' });
      await page.getByRole('heading', { name: 'Checking trial availability' }).waitFor({ state: 'hidden' });
      const result = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa', 'wcag22aa']).analyze();
      violations.push(...result.violations.map(item => ({ route, width, id: item.id, nodes: item.nodes.map(node => ({ target: node.target, summary: node.failureSummary })) })));
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `${route} overflow at ${width}`).toBe(true);
      const unreadable = await page.locator('input:not([type=checkbox]), select, .auth-card label, .auth-links a, .auth-recovery-link, .landing-header a, button').evaluateAll(elements => elements.filter(el => el.getClientRects().length && parseFloat(getComputedStyle(el).fontSize) < 14).map(el => el.outerHTML.slice(0, 200)));
      expect(unreadable, `${route}: functional text smaller than 14px`).toEqual([]);
    }
  }
  writeFileSync(join(captureRoot, 'accessibility.json'), JSON.stringify(violations, null, 2));
  expect(violations).toEqual([]);

  // A 1440px display at 200% browser zoom has a 720 CSS-pixel layout viewport.
  const zoom = await browser.newContext({ viewport: { width: 720, height: 500 }, deviceScaleFactor: 2 });
  const zoomPage = await zoom.newPage();
  for (const route of ['/', 'features', 'pricing', 'demo', 'login', 'signup', ...(django ? ['forgot-password', 'verify-email'] : [])]) {
    await zoomPage.goto(`http://127.0.0.1:3007/#${route}`);
    await expect(zoomPage.getByRole('heading', { level: 1 })).toBeVisible();
    expect(await zoomPage.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `${route} reflow at 200%`).toBe(true);
    // Text-only resizing is a separate, stricter check of the rem-based scale.
    await zoomPage.evaluate(() => { document.documentElement.style.fontSize = '200%'; });
    expect(await zoomPage.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `${route} text resize`).toBe(true);
  }
  await zoomPage.screenshot({ path: join(captureRoot, 'text-resize-200-percent.png'), fullPage: true });
  await zoom.close();
});

test('homepage payload and layout stability evidence', async ({ page }) => {
  await page.addInitScript(() => {
    const sample = { cls: 0 };
    Object.assign(window, { assetflowPerformanceSample: sample });
    new PerformanceObserver(list => {
      for (const entry of list.getEntries() as (PerformanceEntry & { value: number; hadRecentInput: boolean })[]) {
        if (!entry.hadRecentInput) sample.cls += entry.value;
      }
    }).observe({ type: 'layout-shift', buffered: true });
  });
  await page.goto('/');
  await expect(page.getByRole('heading', { name: /know your assets/i })).toBeVisible();
  await page.evaluate(() => document.fonts.ready);
  await page.waitForLoadState('networkidle');
  const result = await page.evaluate(() => ({
    scope: 'One local unthrottled Chromium navigation; not Lighthouse or field performance',
    ...((window as unknown as { assetflowPerformanceSample: { cls: number } }).assetflowPerformanceSample),
    resources: (performance.getEntriesByType('resource') as PerformanceResourceTiming[]).map(entry => ({ path: new URL(entry.name).pathname, decodedBytes: entry.decodedBodySize, encodedBytes: entry.encodedBodySize, transferBytes: entry.transferSize })),
  }));
  mkdirSync(captureRoot, { recursive: true });
  writeFileSync(join(captureRoot, 'performance.json'), JSON.stringify(result, null, 2));
  // Public browsing should not fetch the authenticated workspace bundle.
  expect(result.resources.filter(item => /\/assets\/App-[^/]+\.js$/.test(item.path))).toEqual([]);
});
