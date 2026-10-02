import { describe, expect, it, vi } from 'vitest';
import { ApiClient, serializeQuery } from './apiClient';
import { Session, REFRESH_KEY } from './session';
import { deferred, envelope, identity, json } from '../test/fixtures';
import { responseError } from './apiError';

function setup() {
  const fetcher = vi.fn<typeof fetch>();
  const api = new ApiClient('/api/v1', fetcher);
  const clear = vi.fn();
  const session = new Session(api, sessionStorage, clear);
  return { fetcher, api, session, clear };
}
async function login(context: ReturnType<typeof setup>) {
  context.fetcher.mockResolvedValueOnce(json({ access: 'test-access-1', refresh: 'test-refresh-1' }))
    .mockResolvedValueOnce(json(identity));
  await context.session.login('one@example.test', 'test-password');
  context.fetcher.mockReset();
}
describe('session and transport', () => {
  it('logs in with email, obtains identity and sends bearer authorization only on protected requests', async () => {
    const c = setup();
    c.fetcher.mockResolvedValueOnce(json({ access: 'test-access-1', refresh: 'test-refresh-1' })).mockResolvedValueOnce(json(identity));
    await c.session.login(' ONE@example.test ', 'test-password');
    expect(c.session.getSnapshot().user).toEqual(identity);
    expect(c.fetcher.mock.calls[0][0]).toBe('/api/v1/auth/token/');
    expect(c.fetcher.mock.calls[0][1]?.body).toBe(JSON.stringify({ email: 'one@example.test', password: 'test-password' }));
    expect(c.fetcher.mock.calls[0][1]?.headers).not.toHaveProperty('Authorization');
    expect(c.fetcher.mock.calls[1][1]?.headers).toHaveProperty('Authorization', 'Bearer test-access-1');
    expect(sessionStorage.getItem(REFRESH_KEY)).toBe('test-refresh-1');
    expect(localStorage.length).toBe(0);
  });
  it('rejects invalid credentials and clears stale credentials', async () => {
    const c = setup(); await login(c);
    c.fetcher.mockResolvedValueOnce(json(envelope('AUTHENTICATION_ERROR','Valid authentication credentials are required.'),401));
    await expect(c.session.login('one@example.test','wrong')).rejects.toMatchObject({ kind: 'authentication' });
    expect(c.session.getSnapshot().user).toBeNull(); expect(sessionStorage.getItem(REFRESH_KEY)).toBeNull();
  });
  it('maps login network failure without exposing raw details', async () => {
    const c = setup(); c.fetcher.mockRejectedValue(new Error('private network details'));
    await expect(c.session.login('one@example.test','test')).rejects.toMatchObject({ kind: 'network' });
    expect(c.session.accessToken).toBeNull();
  });
  it('initializes an anonymous session without network calls', async () => {
    const c = setup(); await c.session.initialize(); expect(c.fetcher).not.toHaveBeenCalled();
    expect(c.session.getSnapshot()).toMatchObject({ user: null, initializing: false });
  });
  it('restores once under concurrent startup and persists the rotated refresh token', async () => {
    const c = setup(); sessionStorage.setItem(REFRESH_KEY, 'test-refresh-1');
    c.fetcher.mockResolvedValueOnce(json({ access: 'test-access-2', refresh: 'test-refresh-2' })).mockResolvedValueOnce(json(identity));
    await Promise.all([c.session.initialize(), c.session.initialize()]);
    expect(c.fetcher).toHaveBeenCalledTimes(2); expect(c.session.getSnapshot().user).toEqual(identity);
    expect(sessionStorage.getItem(REFRESH_KEY)).toBe('test-refresh-2');
  });
  it('clears an expired stored refresh and finishes initialization', async () => {
    const c = setup(); sessionStorage.setItem(REFRESH_KEY,'expired'); c.fetcher.mockResolvedValue(json({},401));
    await c.session.initialize(); expect(c.session.getSnapshot()).toMatchObject({ user: null, initializing: false });
    expect(sessionStorage.getItem(REFRESH_KEY)).toBeNull();
  });
  it('three simultaneous 401s share ONE refresh and all retry with the new token', async () => {
    const c = setup(); await login(c); const refresh = deferred<Response>();
    c.fetcher.mockImplementation(async (url, options) => {
      if (String(url).includes('/refresh/')) return refresh.promise;
      return new Headers(options?.headers).get('Authorization') === 'Bearer test-access-2' ? json({ ok: true }) : json({},401);
    });
    const requests = ['/a/','/b/','/c/'].map(path => c.api.request(path));
    await vi.waitFor(() => expect(c.fetcher.mock.calls.filter(([url]) => String(url).includes('/refresh/'))).toHaveLength(1));
    refresh.resolve(json({ access: 'test-access-2', refresh: 'test-refresh-2' }));
    expect(await Promise.all(requests)).toEqual([{ ok:true },{ ok:true },{ ok:true }]);
    expect(c.fetcher).toHaveBeenCalledTimes(7);
  });
  it('failed refresh logs out and rejects every waiting request', async () => {
    const c = setup(); await login(c); const refresh = deferred<Response>();
    c.fetcher.mockImplementation(async url => String(url).includes('/refresh/') ? refresh.promise : json({},401));
    const requests = Promise.allSettled(['/a/','/b/','/c/'].map(path => c.api.request(path)));
    await vi.waitFor(() => expect(c.fetcher).toHaveBeenCalledTimes(4)); refresh.resolve(json({},401));
    expect((await requests).every(result => result.status === 'rejected')).toBe(true);
    expect(c.session.getSnapshot().user).toBeNull(); expect(c.session.accessToken).toBeNull();
    expect(sessionStorage.getItem(REFRESH_KEY)).toBeNull(); expect(c.clear).toHaveBeenCalled();
  });
  it('retries the original request at most once and invalidates on a second 401', async () => {
    const c = setup(); await login(c);
    c.fetcher.mockResolvedValueOnce(json({},401)).mockResolvedValueOnce(json({ access:'test-access-2', refresh:'test-refresh-2' })).mockResolvedValueOnce(json({},401));
    await expect(c.api.request('/assets/')).rejects.toMatchObject({ kind: 'authentication' });
    expect(c.fetcher).toHaveBeenCalledTimes(3); expect(c.session.getSnapshot().user).toBeNull();
  });
  it('a delayed old-token 401 uses the already refreshed token without another refresh', async () => {
    const c = setup(); await login(c); const delayed = deferred<Response>();
    c.fetcher.mockResolvedValueOnce(json({},401)).mockReturnValueOnce(delayed.promise)
      .mockResolvedValueOnce(json({ access:'test-access-2', refresh:'test-refresh-2' })).mockResolvedValue(json({ ok: true }));
    const first = c.api.request('/a/'); const second = c.api.request('/b/');
    await first; delayed.resolve(json({},401)); await second;
    expect(c.fetcher.mock.calls.filter(([url]) => String(url).includes('/refresh/'))).toHaveLength(1);
  });
  it('logout during refresh cannot resurrect a session', async () => {
    const c = setup(); await login(c); const refresh = deferred<Response>(); c.fetcher.mockReturnValue(refresh.promise);
    const pending = c.session.refresh(); c.session.logout(); refresh.resolve(json({ access:'late',refresh:'late' }));
    await expect(pending).rejects.toMatchObject({ kind:'authentication' });
    expect(c.session.accessToken).toBeNull(); expect(c.session.getSnapshot().user).toBeNull();
  });
  it('logout rejects a late successful protected response', async () => {
    const c = setup(); await login(c); const response = deferred<Response>(); c.fetcher.mockReturnValue(response.promise);
    const pending = c.api.request('/assets/'); c.session.logout(); response.resolve(json({ secret: 'previous user' }));
    await expect(pending).rejects.toMatchObject({ kind:'authentication' });
  });
  it('logout during login cannot install tokens or identity', async () => {
    const c = setup(); const response = deferred<Response>(); c.fetcher.mockReturnValue(response.promise);
    const pending = c.session.login('one@example.test','test'); c.session.logout(); response.resolve(json({ access:'late',refresh:'late' }));
    await expect(pending).rejects.toMatchObject({ kind:'authentication' }); expect(c.session.accessToken).toBeNull();
  });
  it('refresh network failure releases waiters and clears the session', async () => {
    const c = setup(); await login(c); c.fetcher.mockRejectedValue(new TypeError('offline'));
    const result = await Promise.allSettled([c.session.refresh(), c.session.refresh()]);
    expect(result.every(item => item.status === 'rejected')).toBe(true); expect(c.fetcher).toHaveBeenCalledTimes(1);
    expect(c.session.getSnapshot().user).toBeNull();
  });
  it('preserves abort cancellation instead of mapping it to a server error', async () => {
    const c = setup(); await login(c); const controller = new AbortController(); controller.abort();
    await expect(c.api.request('/assets/', { signal: controller.signal })).rejects.toMatchObject({ name:'AbortError' });
    expect(c.fetcher).not.toHaveBeenCalled();
  });
  it('refuses absolute paths that could leak a bearer token', async () => {
    const c = setup(); await expect(c.api.request('https://elsewhere.test/')).rejects.toMatchObject({ kind:'contract' });
    expect(c.fetcher).not.toHaveBeenCalled();
  });
  it('an old refresh failure cannot log out a newly authenticated user', async () => {
    const c = setup(); await login(c); const old = deferred<Response>();
    c.fetcher.mockReturnValueOnce(old.promise);
    const pending = c.session.refresh();
    const rejected = expect(pending).rejects.toMatchObject({ kind:'authentication' });
    c.fetcher.mockResolvedValueOnce(json({ access:'test-access-b',refresh:'test-refresh-b' }))
      .mockResolvedValueOnce(json({ ...identity,id:2 }));
    await c.session.login('two@example.test','test-password'); old.resolve(json({},401)); await rejected;
    expect(c.session.getSnapshot().user?.id).toBe(2); expect(c.session.accessToken).toBe('test-access-b');
  });
  it('fails closed when refresh token persistence is denied', async () => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(json({ access:'test-access',refresh:'test-refresh' }));
    const storage = { getItem:() => null,setItem:() => { throw new Error('Storage disabled'); },removeItem:vi.fn() };
    const session = new Session(new ApiClient('/api/v1',fetcher),storage,vi.fn());
    await expect(session.login(identity.email,'test-password')).rejects.toThrow();
    expect(session.accessToken).toBeNull(); expect(session.getSnapshot().user).toBeNull(); expect(storage.removeItem).toHaveBeenCalled();
  });
  it('a timed-out refresh rejects all waiters and clears authentication', async () => {
    const c = setup(); await login(c); const timeout = new AbortController();
    vi.spyOn(AbortSignal,'timeout').mockReturnValue(timeout.signal);
    c.fetcher.mockImplementation((_url,options) => new Promise((_resolve,reject) => {
      options?.signal?.addEventListener('abort',() => reject(new DOMException('Timeout','TimeoutError')));
    }));
    const pending = Promise.allSettled([c.session.refresh(),c.session.refresh()]); timeout.abort();
    expect((await pending).every(result => result.status === 'rejected')).toBe(true);
    expect(c.fetcher).toHaveBeenCalledTimes(1); expect(c.session.getSnapshot().user).toBeNull();
  });
});
describe('public error boundary and query encoding', () => {
  it.each([[400,'validation'],[401,'authentication'],[403,'authorization'],[404,'not-found'],[409,'conflict'],[500,'server']])('maps HTTP %s to %s', (status, kind) => {
    expect(responseError(Number(status),{}).kind).toBe(kind);
  });
  it('preserves public validation messages and field errors', () => {
    const error = responseError(400,{ success:false, error:{ code:'VALIDATION_ERROR',message:'The request contains invalid fields.',details:{ name:['Required.'] } } });
    expect(error.fields).toEqual({ name:['Required.'] }); expect(error.message).toBe('The request contains invalid fields.');
  });
  it('does not expose a traceback or raw HTML server error', () => {
    expect(responseError(500,envelope('API_ERROR','secret traceback')).message).not.toContain('secret');
    expect(responseError(502,'<html>secret</html>').message).not.toContain('secret');
  });
  it('serializes query values once and excludes only absent values', () => {
    expect(serializeQuery({ search:'pump & motor', page:2, page_size:25, zero:0, flag:false, absent:undefined, empty:'' }))
      .toBe('?search=pump+%26+motor&page=2&page_size=25&zero=0&flag=false');
  });
});
