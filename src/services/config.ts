export type DataSource = 'mock' | 'django';

export function parseDataSource(value: string | undefined): DataSource {
  if (value === undefined || value === 'mock') return 'mock';
  if (value === 'django') return 'django';
  throw new Error('Invalid VITE_DATA_SOURCE. Expected "mock" or "django".');
}

export function parseApiBase(value: string | undefined): string {
  const base = (value || '/api/v1').replace(/\/+$/, '');
  if (/[\\\s]/.test(base)) throw new Error('VITE_BACKEND_API_URL contains invalid characters.');
  if (/^\/(?!\/)[^?#]*$/.test(base)) return base;
  const url = new URL(base);
  if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password || url.search || url.hash) {
    throw new Error('VITE_BACKEND_API_URL must be an HTTP(S) API base URL without credentials, query, or fragment.');
  }
  return base;
}

export const dataSource = parseDataSource(import.meta.env.VITE_DATA_SOURCE);
export const apiBase = parseApiBase(import.meta.env.VITE_BACKEND_API_URL);
