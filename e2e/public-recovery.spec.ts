import { expect, test } from '@playwright/test';

test('missing entry script retains an honest recovery shell', async ({ page }) => {
  const entry = /\/(?:src\/main\.tsx|assets\/index-[^/]+\.js)(?:\?.*)?$/;
  await page.route(entry, route => route.abort('failed'));
  await page.goto('/#pricing');
  await expect(page.getByRole('status')).toContainText('Opening your asset workspace');
  await page.unroute(entry);
  await page.getByRole('link', { name: 'reload the homepage' }).click();
  await expect(page.getByRole('heading', { name: /know your assets/i })).toBeVisible();
});

if (process.env.E2E_NGINX === '1') {
  test('nginx revalidates the HTML entry and returns a real 404 for missing chunks', async ({ request }) => {
    const html = await request.get('/index.html');
    expect(html.headers()['cache-control']).toContain('no-cache');
    const missing = await request.get('/assets/synthetic-missing-chunk.js');
    expect(missing.status()).toBe(404);
    expect(await missing.text()).not.toContain('<div id="root">');
  });
}

test('startup recovery returns home after a missing module becomes available', async ({ page }) => {
  const module = /\/(?:src\/auth\/ApplicationRoot\.tsx|assets\/ApplicationRoot-[^/]+\.js)(?:\?.*)?$/;
  await page.route(module, route => route.abort('failed'));
  await page.goto('/#pricing');
  await expect(page.getByRole('heading', { name: 'AssetFlow could not start.' })).toBeVisible();
  await page.unroute(module);
  await page.getByRole('link', { name: 'Return home' }).click();
  await expect(page.getByRole('heading', { name: /know your assets/i })).toBeVisible();
});

test('public render recovery returns home without retaining the failed boundary', async ({ page }) => {
  await page.addInitScript(() => {
    const uuid = crypto.randomUUID.bind(crypto);
    crypto.randomUUID = () => {
      if (location.hash.includes('request-demo')) throw new Error('Synthetic public render failure');
      return uuid();
    };
  });
  await page.goto('/#request-demo');
  await expect(page.getByRole('heading', { name: 'This page could not be loaded.' })).toBeVisible();
  await page.getByRole('link', { name: 'Return home' }).click();
  await expect(page.getByRole('heading', { name: /know your assets/i })).toBeVisible();
});

test('section aliases scroll on a direct load and reload', async ({ page }) => {
  await page.goto('/#/section-features');
  await expect(page.locator('#section-features')).toBeInViewport();
  await page.reload();
  await expect(page.locator('#section-features')).toBeInViewport();
});

test('mobile menus close on Escape and restore focus', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  for (const path of ['/', 'features']) {
    await page.goto(`/#${path}`);
    await page.getByRole('button', { name: 'Open navigation' }).focus();
    await page.keyboard.press('Enter');
    await expect(page.getByRole('navigation', { name: 'Mobile navigation' })).toBeVisible();
    await page.keyboard.press('Tab');
    await page.keyboard.press('Escape');
    await expect(page.getByRole('navigation', { name: 'Mobile navigation' })).toHaveCount(0);
    await expect(page.getByRole('button', { name: 'Open navigation' })).toBeFocused();
  }
});

if (process.env.VITE_DATA_SOURCE !== 'django') {
  test('workspace aliases use the same normalized route as the public router', async ({ page }) => {
    await page.goto('/#/all-assets');
    await expect(page.getByRole('heading', { name: 'Asset Register', exact: true })).toBeVisible();
    await page.reload();
    await expect(page.getByRole('heading', { name: 'Asset Register', exact: true })).toBeVisible();
  });
}
