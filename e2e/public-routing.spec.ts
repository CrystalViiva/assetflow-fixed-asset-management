import { expect, test } from '@playwright/test';
import { mkdirSync } from 'node:fs';

const outputDir = process.env.E2E_OUTPUT_DIR || '.codex-public-browser-results';
const djangoMode = process.env.VITE_DATA_SOURCE === 'django';
mkdirSync(outputDir, { recursive: true });

test('public routes, CTAs, browser history, responsive layout and recovery', async ({ page }) => {
  const pageErrors: string[] = [];
  const consoleErrors: string[] = [];
  const failedRequests: string[] = [];
  page.on('pageerror', error => pageErrors.push(error.message));
  page.on('console', message => { if (message.type() === 'error') consoleErrors.push(message.text()); });
  page.on('requestfailed', request => failedRequests.push(`${request.method()} ${request.url()} ${request.failure()?.errorText}`));

  for (const width of [360, 390, 768, 1024, 1440]) {
    await page.setViewportSize({ width, height: width < 600 ? 820 : 960 });
    await page.goto('/#/');
    await expect(page.getByRole('heading', { name: /know your assets.*control their value/i })).toBeVisible();
    await expect(page.getByRole('img', { name: /illustrative assetflow workspace with fictional asset records/i })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), `horizontal overflow at ${width}px`).toBe(true);
  }

  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto('/#/');
  await page.getByRole('navigation', { name: 'Main navigation' }).getByRole('link', { name: 'Features' }).click();
  await expect(page).toHaveURL(/#section-features$/);
  await expect(page.locator('#section-features')).toBeInViewport();
  await page.goBack();
  await expect(page).toHaveURL(/#\/$/);
  await page.goForward();
  await expect(page).toHaveURL(/#section-features$/);

  await page.goto('/#/request-demo');
  await expect(page.getByRole('heading', { name: /see your asset workflows in action/i })).toBeVisible();
  if (djangoMode) {
    await expect(page.getByRole('button', { name: 'Request a demonstration' })).toBeVisible();
  } else {
    await expect(page.getByText(/contact submission is available on the configured customer website/i)).toBeVisible();
  }
  await page.goto('/#/demo');
  await expect(page.getByRole('heading', { name: 'A clear operating record.' })).toBeVisible();
  await expect(page.getByText(/fictional data, no customer records/i)).toBeVisible();
  await page.goto('/#/get-started');
  await expect(page.getByRole('heading', { name: 'Get started with AssetFlow' })).toBeVisible();
  if (djangoMode) {
    await expect(page.getByRole('link', { name: 'Continue to secure signup' })).toBeVisible();
    await page.goto('/#/signup');
    await expect(page.getByRole('heading', { name: 'Create your company workspace' })).toBeVisible();
    await expect(page.getByLabel('Business email')).toBeVisible();
  } else {
    await expect(page.getByText(/static demonstration build cannot create a live workspace/i)).toBeVisible();
    await page.goto('/#/signup');
    await expect(page.getByRole('heading', { name: /live trial needs the configured assetflow service/i })).toBeVisible();
  }
  await page.goto('/#/login');
  if (djangoMode) {
    await expect(page.getByRole('heading', { name: 'Sign in to your workspace' })).toBeVisible();
    await expect(page.getByLabel('Password')).toBeVisible();
  } else {
    await expect(page.getByRole('heading', { name: /sign in to your assetflow workspace/i })).toBeVisible();
    await expect(page.getByLabel('Password')).toHaveCount(0);
  }
  await page.goto('/#/unknown-route');
  await expect(page.getByRole('heading', { name: /this page.*here/i })).toBeVisible();
  await page.getByRole('link', { name: 'Return to AssetFlow' }).click();
  await expect(page.getByRole('heading', { name: /know your assets.*control their value/i })).toBeVisible();

  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/#/');
  await page.getByRole('button', { name: 'Open navigation' }).focus();
  await page.keyboard.press('Enter');
  await expect(page.getByRole('navigation', { name: 'Mobile navigation' })).toBeVisible();
  await page.getByRole('navigation', { name: 'Mobile navigation' }).getByRole('link', { name: 'Solutions' }).click();
  await expect(page).toHaveURL(/#section-solutions$/);
  await expect(page.getByRole('navigation', { name: 'Mobile navigation' })).toHaveCount(0);
  await page.goto('/#/features');
  await page.getByRole('button', { name: 'Open navigation' }).focus();
  await page.keyboard.press('Enter');
  await page.getByRole('navigation', { name: 'Mobile navigation' }).getByRole('link', { name: 'Pricing' }).click();
  await expect(page).toHaveURL(/#pricing$/);
  await expect(page.getByRole('heading', { name: /choose a service that fits your organization/i })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.evaluate(() => window.scrollTo({ top: 0, behavior: 'instant' }));
  await page.screenshot({ path: `${outputDir}/assetflow-mobile-pricing-390.png`, fullPage: true, animations: 'disabled' });
  await page.goto('/#/login');
  if (djangoMode) {
    await expect(page.getByRole('heading', { name: 'Sign in to your workspace' })).toBeVisible();
    await expect(page.getByLabel('Password')).toBeVisible();
  } else {
    await expect(page.getByRole('heading', { name: /sign in to your assetflow workspace/i })).toBeVisible();
    await expect(page.getByLabel('Password')).toHaveCount(0);
  }
  await page.goto('/#/');
  await page.evaluate(() => window.scrollTo({ top: 0, behavior: 'instant' }));
  await page.screenshot({ path: `${outputDir}/assetflow-mobile-390.png`, fullPage: true, animations: 'disabled' });

  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto('/#/');
  await page.screenshot({ path: `${outputDir}/assetflow-desktop-1440.png`, fullPage: true, animations: 'disabled' });

  expect(pageErrors).toEqual([]);
  expect(consoleErrors).toEqual([]);
  expect(failedRequests).toEqual([]);
});
