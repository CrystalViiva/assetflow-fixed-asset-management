export type ApiErrorKind = 'network' | 'authentication' | 'authorization' | 'validation' | 'not-found' | 'conflict' | 'server' | 'contract';

export class ApiError extends Error {
  constructor(
    public readonly kind: ApiErrorKind,
    message: string,
    public readonly status?: number,
    public readonly fields: Record<string, string[]> = {},
  ) { super(message); this.name = 'ApiError'; }
}

export function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

export function responseError(status: number, body: unknown): ApiError {
  const kind: ApiErrorKind = status === 401 ? 'authentication' : status === 403 ? 'authorization'
    : status === 404 ? 'not-found' : status === 409 ? 'conflict'
    : status === 400 || status === 422 ? 'validation' : 'server';
  const messages: Record<ApiErrorKind, string> = {
    network: 'Unable to reach AssetFlow. Check your connection and try again.',
    authentication: 'Your session has expired. Please sign in again.',
    authorization: 'You do not have permission to view this resource.',
    'not-found': 'The requested record was not found.',
    conflict: 'The request conflicts with the current record state.',
    validation: 'The request contains invalid fields.',
    server: 'AssetFlow could not complete the request. Please try again.',
    contract: 'The API returned an unsupported response.',
  };
  const envelope = isRecord(body) && isRecord(body.error) ? body.error : null;
  const fields: Record<string, string[]> = {};
  if (kind === 'validation' && envelope && isRecord(envelope.details)) {
    for (const [key, value] of Object.entries(envelope.details)) {
      if (Array.isArray(value) && value.every((item): item is string => typeof item === 'string')) fields[key] = value;
    }
  }
  // Only the backend's known public envelope is eligible for display; never HTML/debug bodies or 5xx details.
  const known = ['VALIDATION_ERROR', 'AUTHENTICATION_ERROR', 'PERMISSION_DENIED', 'NOT_FOUND', 'API_ERROR'];
  const message = status < 500 && envelope && typeof envelope.code === 'string' && known.includes(envelope.code)
    && typeof envelope.message === 'string' ? envelope.message : messages[kind];
  return new ApiError(kind, message, status, fields);
}

export function errorMessage(error: unknown): string {
  return error instanceof ApiError ? error.message : 'Unable to complete this request. Please try again.';
}
