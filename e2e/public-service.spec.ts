import { expect, test } from '@playwright/test';

if (process.env.VITE_DATA_SOURCE === 'django' && process.env.SELF_SERVICE_ENABLED !== 'false') {
  test('service failures are honest, retryable, and never report a successful lead', async ({ page }) => {
    const errors: string[] = [];
    page.on('pageerror', error => errors.push(error.message));
    const config = '**/api/v1/public/config/';
    await page.route(config, route => route.fulfill({ status: 503, json: { detail: 'Synthetic service outage' } }));
    await page.goto('/#get-started');
    await expect(page.getByRole('alert')).toContainText('could not reach the service');
    await expect(page.getByText('Self-service signup is not enabled for this service.', { exact: false })).toHaveCount(0);
    await page.unroute(config);
    await page.getByRole('button', { name: 'Check again' }).click();
    await expect(page.getByRole('link', { name: 'Continue to secure signup' })).toBeVisible();
    await page.route(config, route => route.abort('failed'));
    await page.goto('/#signup');
    await page.reload(); // Discard the previous successful config cached in this document.
    await expect(page.getByRole('alert')).toContainText('Unable to reach AssetFlow');
    await page.unroute(config);
    await page.getByRole('button', { name: 'Try again' }).click();
    await expect(page.getByLabel('Business email')).toBeVisible();

    await page.route('**/api/v1/public/leads/', route => route.fulfill({ status: 503, json: {} }));
    await page.goto('/#request-demo');
    await page.getByLabel('Name', { exact: true }).fill('Synthetic outage enquiry');
    await page.getByLabel('Business email').fill('outage@example.test');
    await page.getByLabel('Company', { exact: true }).fill('Synthetic Company');
    await page.getByLabel('Business requirements').fill('A synthetic failed request for UI validation.');
    await page.getByRole('checkbox').check();
    await page.getByRole('button', { name: 'Request a demonstration' }).click();
    await expect(page.getByRole('alert')).toContainText('could not complete');
    await expect(page.getByText(/Request received/)).toHaveCount(0);
    await expect(page.getByLabel('Business email')).toHaveValue('outage@example.test');

    await page.route('**/api/v1/auth/token/', route => route.abort('failed'));
    await page.goto('/#login');
    await page.getByLabel('Email', { exact: true }).fill('outage@example.test');
    await page.getByLabel('Password', { exact: true }).fill('Synthetic-invalid-password!');
    await page.getByRole('button', { name: 'Show password' }).click();
    await expect(page.getByLabel('Password', { exact: true })).toHaveAttribute('type', 'text');
    await page.getByRole('button', { name: 'Hide password' }).click();
    await page.getByRole('button', { name: 'Sign in', exact: true }).click();
    await expect(page.getByRole('alert')).toContainText('Unable to reach AssetFlow');
    expect(errors).toEqual([]);
  });

  test('real login errors, protected redirect, rotated session recovery and sign out', async ({ page }) => {
    await page.goto('/?session-recovery-check#reports');
    await expect(page).toHaveURL(/#login\?next=reports/);
    await page.getByLabel('Email', { exact: true }).fill('nobody@example.test');
    await page.getByLabel('Password', { exact: true }).fill('Synthetic-invalid-password!');
    await page.getByRole('button', { name: 'Sign in', exact: true }).click();
    await expect(page.getByRole('alert')).toContainText('Check your email and password');
    await page.getByLabel('Email', { exact: true }).fill('browser-operator@example.test');
    await page.getByLabel('Password', { exact: true }).fill(process.env.SMOKE_PASSWORD!);
    await page.getByRole('button', { name: 'Sign in', exact: true }).click();
    await expect(page.getByRole('heading', { name: 'Platform operations' })).toBeVisible();
    const refresh = page.waitForResponse(response => response.url().endsWith('/auth/token/refresh/') && response.status() === 200);
    await page.reload();
    await refresh;
    await expect(page.getByRole('heading', { name: 'Platform operations' })).toBeVisible();
    await page.goto('/#/');
    await expect(page.getByRole('heading', { name: /know your assets/i })).toBeVisible();
    await page.getByRole('link', { name: 'Open workspace' }).first().click();
    await expect(page.getByRole('heading', { name: 'Platform operations' })).toBeVisible();
    await page.getByRole('button', { name: 'Sign out', exact: true }).click();
    await expect(page.getByRole('heading', { name: /know your assets/i })).toBeVisible();
    await page.evaluate(() => sessionStorage.setItem('assetflow_refresh', 'synthetic-expired-refresh'));
    await page.goto('/?expired-session-check#reports');
    await expect(page.getByRole('heading', { name: 'Sign in to your workspace' })).toBeVisible();
    await expect(page).toHaveURL(/#login\?next=reports&expired=1/);
  });
}

if (process.env.VITE_DATA_SOURCE === 'django' && process.env.SELF_SERVICE_ENABLED === 'false') {
  test('disabled self-service is enforced by the real Django service', async ({ page, request }) => {
    const config = await request.get('/api/v1/public/config/');
    expect((await config.json()).self_service_enabled).toBe(false);
    for (const route of ['signup', 'verify-email']) {
      await page.goto(`/#${route}`);
      await expect(page.getByRole('link', { name: 'Contact sales', exact: true })).toBeVisible();
      await expect(page.getByRole('button', { name: /verification email|Verify & create/ })).toHaveCount(0);
    }
    await page.goto('/#get-started');
    await expect(page.getByText(/Self-service signup is not enabled/)).toBeVisible();
    const denied = await request.post('/api/v1/auth/signup/', { data: { email: 'disabled@example.test', company_name: 'Synthetic Disabled', currency: 'NGN', timezone_name: 'Africa/Lagos' } });
    expect(denied.status()).toBe(403);
  });
}
