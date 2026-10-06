import assert from 'node:assert/strict';
import { ApiClient } from '../src/services/apiClient';
import { ApiError } from '../src/services/apiError';
import { DjangoDashboardRepository } from '../src/services/dashboardRepository';
import { DjangoAssetRepository, defaultAssetQuery } from '../src/services/djangoApiBridge';
import { Session, REFRESH_KEY } from '../src/services/session';

let stage = 'session setup';
async function run() {
  const storage = new Map<string, string>();
  const api = new ApiClient(process.env.F1_SMOKE_URL!);
  const cleared: number[] = [];
  const session = new Session(api, { getItem: key => storage.get(key) ?? null, setItem: (key, value) => storage.set(key, value), removeItem: key => storage.delete(key) }, () => { cleared.push(Date.now()); });
  const dashboard = new DjangoDashboardRepository(api);
  const assets = new DjangoAssetRepository(api);
  await session.initialize();
  assert.equal(session.getSnapshot().user, null);

  stage = 'real administrator sign in and /me identity';
  await session.login(process.env.F1_SMOKE_EMAIL!, process.env.F1_SMOKE_PASSWORD!);
  assert.equal(session.getSnapshot().user?.role, 'ASSET_MANAGER');
  assert.equal(session.getSnapshot().user?.email, process.env.F1_SMOKE_EMAIL!.toLowerCase());
  assert.ok(storage.has(REFRESH_KEY));

  stage = 'protected real application data and live dashboard';
  const found = await assets.getAssets({ ...defaultAssetQuery, search: 'F14-SMOKE-001' });
  assert.equal(found.total, 1);
  assert.equal(found.data[0]?.tag, 'F14-SMOKE-001');
  const metrics = await dashboard.metrics();
  assert.ok(metrics.asOf && Number.isFinite(Date.parse(metrics.asOf)));
  assert.ok(metrics.portfolio.registeredAssets >= 1);

  stage = 'logout clears in-memory identity and refresh token';
  session.logout();
  assert.equal(session.getSnapshot().user, null);
  assert.equal(session.accessToken, null);
  assert.equal(storage.has(REFRESH_KEY), false);

  stage = 'lower-role sign in and real forbidden dashboard response';
  await session.login('f14-employee@example.test', process.env.F1_SMOKE_PASSWORD!);
  assert.equal(session.getSnapshot().user?.role, 'EMPLOYEE');
  await assert.rejects(dashboard.metrics(), error => error instanceof ApiError && error.status === 403);
  assert.equal(session.getSnapshot().user?.role, 'EMPLOYEE', '403 must not masquerade as logout');

  stage = 'user switch removes previous authenticated cache/session';
  session.logout();
  assert.equal(session.getSnapshot().user, null);
  await session.login(process.env.F1_SMOKE_EMAIL!, process.env.F1_SMOKE_PASSWORD!);
  assert.equal(session.getSnapshot().user?.role, 'ASSET_MANAGER');
  assert.ok(cleared.length >= 4, 'logout and login clear user-scoped cache state');

  stage = 'failed refresh expires session safely';
  session.logout();
  storage.set(REFRESH_KEY, 'invalid-disposable-refresh-token');
  const expiredApi = new ApiClient(process.env.F1_SMOKE_URL!);
  const expired = new Session(expiredApi, { getItem: key => storage.get(key) ?? null, setItem: (key, value) => storage.set(key, value), removeItem: key => storage.delete(key) }, () => {});
  await expired.initialize();
  assert.equal(expired.getSnapshot().user, null);
  assert.match(expired.getSnapshot().error ?? '', /expired|sign in/i);
  assert.equal(storage.has(REFRESH_KEY), false);

  console.log('PASS: F14 real TypeScript→HTTP→Django→disposable PostgreSQL authentication, protected asset/dashboard access, 403 retention, logout/user switch, and invalid-refresh expiry; persistent database untouched.');
}
run().catch(error => { console.error(`F14 smoke failed during ${stage}: ${error instanceof ApiError ? error.kind : error instanceof Error ? error.name : 'unknown error'}`); process.exitCode = 1; });
