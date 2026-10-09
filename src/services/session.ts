import { ApiClient } from './apiClient';
import { ApiError, isRecord } from './apiError';

export interface SessionUser { id: number; email: string; role: string; isPlatformOperator?: boolean }
export interface SessionSnapshot { user: SessionUser | null; initializing: boolean; error: string | null }
export const REFRESH_KEY = 'assetflow_refresh';

function tokens(value: unknown): { access: string; refresh: string } {
  if (!isRecord(value) || typeof value.access !== 'string' || !value.access || typeof value.refresh !== 'string' || !value.refresh) {
    throw new ApiError('contract', 'The authentication service returned an invalid response.');
  }
  return { access: value.access, refresh: value.refresh };
}
function user(value: unknown): SessionUser {
  if (!isRecord(value) || !Number.isSafeInteger(value.id) || typeof value.id !== 'number'
    || typeof value.email !== 'string' || typeof value.role !== 'string') {
    throw new ApiError('contract', 'The session service returned an invalid response.');
  }
  // Preserve unfamiliar roles without granting any client-side privileges.
  return { id: value.id, email: value.email, role: value.role, ...(value.is_platform_operator === true ? { isPlatformOperator: true } : {}) };
}

export class Session {
  accessToken: string | null = null;
  generation = 0;
  private refreshToken: string | null = null;
  private flight: Promise<void> | null = null;
  private initialization: Promise<void> | null = null;
  private snapshot: SessionSnapshot = { user: null, initializing: true, error: null };
  private listeners = new Set<() => void>();

  constructor(private readonly api: ApiClient, private readonly storage: Pick<Storage, 'getItem' | 'setItem' | 'removeItem'>,
    private readonly clearCache: () => void) { api.session = this; }
  getSnapshot = () => this.snapshot;
  subscribe = (listener: () => void) => { this.listeners.add(listener); return () => { this.listeners.delete(listener); }; };
  private publish(snapshot: SessionSnapshot) { this.snapshot = snapshot; this.listeners.forEach(listener => listener()); }
  private check(generation: number) {
    if (this.generation !== generation) throw new ApiError('authentication', 'Your session has ended. Please sign in again.');
  }
  private save(value: { access: string; refresh: string }) {
    // Fail closed if rotation cannot be persisted. Never retain an obsolete refresh token.
    this.storage.setItem(REFRESH_KEY, value.refresh);
    this.accessToken = value.access;
    this.refreshToken = value.refresh;
  }
  invalidate = (error: string | null = null) => {
    this.generation++;
    this.accessToken = null;
    this.refreshToken = null;
    this.flight = null;
    try { this.storage.removeItem(REFRESH_KEY); } catch { /* Storage can be disabled by the browser. */ }
    this.clearCache();
    this.publish({ user: null, initializing: false, error });
  };
  logout = () => {
    // Capture the request before clearing local credentials. Local sign-out always completes.
    if (this.accessToken) void this.api.request('/auth/logout/', { method: 'POST', retryUnauthorized: false }).catch(() => {});
    this.invalidate('signed-out');
  };

  refresh = (): Promise<void> => {
    if (this.flight) return this.flight;
    const generation = this.generation;
    const token = this.refreshToken;
    const operation = (async () => {
      try {
        if (!token) throw new ApiError('authentication', 'Please sign in to AssetFlow.');
        const response = await this.api.request('/auth/token/refresh/', {
          method: 'POST', body: { refresh: token }, authenticated: false,
        });
        this.check(generation);
        this.save(tokens(response));
      } catch (error) {
        if (generation === this.generation) this.invalidate('Your session expired. Please sign in again.');
        throw error;
      }
    })();
    this.flight = operation;
    void operation.finally(() => { if (this.flight === operation) this.flight = null; }).catch(() => {});
    return operation;
  };

  initialize = (): Promise<void> => {
    // StrictMode must not consume a rotating refresh token twice.
    if (this.initialization) return this.initialization;
    const generation = this.generation;
    this.initialization = (async () => {
      try {
        this.refreshToken = this.storage.getItem(REFRESH_KEY);
        if (!this.refreshToken) { this.publish({ user: null, initializing: false, error: null }); return; }
        await this.refresh();
        const identity = user(await this.api.request('/auth/me/'));
        this.check(generation);
        this.clearCache();
        this.publish({ user: identity, initializing: false, error: null });
      } catch {
        // refresh may already have invalidated the session; never overwrite a newer login.
        if (this.generation === generation) this.invalidate();
      }
    })();
    return this.initialization;
  };

  login = async (email: string, password: string): Promise<void> => {
    this.invalidate();
    const generation = this.generation;
    try {
      const response = await this.api.request('/auth/token/', {
        method: 'POST', body: { email: email.trim().toLowerCase(), password }, authenticated: false,
      });
      this.check(generation);
      this.save(tokens(response));
      const identity = user(await this.api.request('/auth/me/'));
      this.check(generation);
      this.clearCache();
      this.publish({ user: identity, initializing: false, error: null });
    } catch (error) {
      if (this.generation === generation) this.invalidate();
      throw error;
    }
  };
}
