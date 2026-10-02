import { ApiError, responseError } from './apiError';

export type Query = Record<string, string | number | boolean | undefined | null>;
export function serializeQuery(query: Query = {}): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined && value !== null && value !== '') params.set(key, String(value));
  }
  const text = params.toString();
  return text ? `?${text}` : '';
}

export interface SessionTransport {
  accessToken: string | null;
  generation: number;
  refresh(): Promise<void>;
  invalidate(): void;
}
interface RequestOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';
  body?: unknown;
  query?: Query;
  signal?: AbortSignal;
  authenticated?: boolean;
}

export class ApiClient {
  session?: SessionTransport;
  constructor(private readonly base: string, private readonly fetcher: typeof fetch = (...args) => fetch(...args)) {}

  async request(path: string, options: RequestOptions = {}): Promise<unknown> {
    if (!path.startsWith('/') || path.startsWith('//') || /[\\?#\s]/.test(path)) {
      throw new ApiError('contract', 'Invalid API request path.');
    }
    const authenticated = options.authenticated !== false;
    const session = this.session;
    const generation = session?.generation;
    const ensureCurrent = () => {
      if (authenticated && (!session || session.generation !== generation)) {
        throw new ApiError('authentication', 'Your session has ended. Please sign in again.');
      }
      options.signal?.throwIfAborted();
    };
    const send = async (token: string | null): Promise<Response> => {
      ensureCurrent();
      const timeout = AbortSignal.timeout(20_000);
      const signal = options.signal ? AbortSignal.any([options.signal, timeout]) : timeout;
      const headers: Record<string, string> = { Accept: 'application/json' };
      if (options.body !== undefined) headers['Content-Type'] = 'application/json';
      if (authenticated && token) headers.Authorization = `Bearer ${token}`;
      try {
        return await this.fetcher(`${this.base}${path}${serializeQuery(options.query)}`, {
          method: options.method || 'GET', headers,
          body: options.body === undefined ? undefined : JSON.stringify(options.body),
          signal, credentials: 'omit', redirect: 'error', cache: 'no-store',
        });
      } catch (error) {
        if (options.signal?.aborted) throw error;
        throw new ApiError('network', 'Unable to reach AssetFlow. Check your connection and try again.');
      }
    };
    const originalToken = session?.accessToken || null;
    let response = await send(originalToken);
    ensureCurrent();
    if (response.status === 401 && authenticated && session) {
      // A delayed 401 may belong to the old token after another request finished refreshing.
      if (!session.accessToken || session.accessToken === originalToken) await session.refresh();
      ensureCurrent();
      response = await send(session.accessToken);
      ensureCurrent();
      if (response.status === 401) session.invalidate();
    }
    let body: unknown;
    try { body = response.status === 204 ? null : await response.json(); }
    catch { body = null; }
    if (!response.ok) throw responseError(response.status, body);
    ensureCurrent();
    return body;
  }
}
