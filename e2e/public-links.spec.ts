import { expect, test } from '@playwright/test';
import { mkdirSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';

test('every public link has a meaningful destination, including reload and skip navigation', async ({ page }) => {
  test.setTimeout(180_000);
  const inventory: { source: string; label: string; href: string }[] = [];
  const pageErrors: string[] = [];
  const consoleErrors: string[] = [];
  const failed: string[] = [];
  page.on('pageerror', error => pageErrors.push(error.message));
  page.on('console', message => { if (message.type() === 'error') consoleErrors.push(message.text()); });
  page.on('requestfailed', request => failed.push(`${request.method()} ${request.url()}`));
  page.on('response', response => { if (response.status() >= 400) failed.push(`${response.status()} ${response.url()}`); });
  for (const source of ['/', 'features', 'solutions', 'how-it-works', 'pricing', 'security', 'help', 'about', 'get-started', 'demo', 'request-demo', 'contact-sales', 'login', 'signup']) {
    await page.goto(`/#${source}`);
    await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
    await page.getByRole('heading', { name: 'Checking trial availability' }).waitFor({ state: 'hidden' });
    inventory.push(...await page.locator('a[href]').evaluateAll((anchors, source) => anchors
      .filter(el => el.getClientRects().length)
      .map(el => ({ source, label: el.textContent?.trim() || el.getAttribute('aria-label') || '', href: el.getAttribute('href')! })), source));
  }
  // Shared header/footer instances are inventoried on every page; traverse each distinct action.
  const unique = [...new Map(inventory.map(link => [`${link.href}:${link.label}`, link])).values()];
  for (const { source, href, label } of unique) {
    expect(href, `${source}: ${label}`).not.toBe('#');
    if (!href.startsWith('#') || href === '#public-main') continue;
    await page.goto(`/#${source}`);
    await page.locator(`a[href="${href}"]`).first().click();
    await expect(page).toHaveURL(new RegExp(href.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '$'));
    await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
    await expect(page.getByRole('heading', { name: /This page isn't here|could not be loaded|could not start/ })).toHaveCount(0);
    if (href.startsWith('#section-')) await expect(page.locator(href)).toBeInViewport();
    else await expect(page.getByRole('heading', { level: 1 })).toBeInViewport();
    await page.reload();
    await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
    await expect(page.getByRole('heading', { name: /This page isn't here|could not be loaded|could not start/ })).toHaveCount(0);
  }
  await page.goto('/?skip-link-check#/');
  await page.keyboard.press('Tab');
  await expect(page.getByRole('link', { name: 'Skip to content' })).toBeFocused();
  await page.keyboard.press('Enter');
  await expect(page.locator('#public-main')).toBeFocused();
  await expect(page).toHaveURL(/#\/$/);
  const dir = process.env.E2E_OUTPUT_DIR || '.codex-browser-results';
  mkdirSync(dir, { recursive: true });
  writeFileSync(join(dir, 'public-links.json'), JSON.stringify({ mode: process.env.VITE_DATA_SOURCE || 'mock', actions: inventory, distinctActions: unique.length, pageErrors, consoleErrors, failed }, null, 2));
  expect(pageErrors).toEqual([]);
  expect(consoleErrors).toEqual([]);
  expect(failed).toEqual([]);
});
