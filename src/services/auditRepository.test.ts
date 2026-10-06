import { describe, expect, it } from 'vitest';
import { ApiError } from './apiError';
import { parseAuditEvent, safeAuditJson } from './auditRepository';

const event = {
  id: 'd4e5e2a9-361a-4b2c-b6cb-37c11580d118', timestamp: '2026-05-01T12:30:00Z', actor_email: null,
  action: 'FUTURE_DOMAIN_EVENT', entity_type: 'ASSET', entity_id: 'asset-123',
  changes: { location: { from: 'A', to: 'B' }, authorization: 'secret' },
  metadata: { nested: [{ refresh_token: 'hidden' }], text: '<script>alert(1)</script>', empty: null },
};

describe('audit event contract and display safety', () => {
  it('accepts unknown event identifiers without assigning a false meaning', () => {
    expect(parseAuditEvent(event).action).toBe('FUTURE_DOMAIN_EVENT');
    expect(parseAuditEvent(event).actorEmail).toBeNull();
  });
  it('redacts sensitive nested keys while preserving ordinary change metadata as text data', () => {
    const parsed = parseAuditEvent(event);
    expect(parsed.changes.authorization).toBe('[REDACTED]');
    expect(parsed.metadata.nested).toEqual([{ refresh_token: '[REDACTED]' }]);
    expect(parsed.metadata.text).toBe('<script>alert(1)</script>');
    expect(parsed.metadata.empty).toBeNull();
  });
  it('rejects malformed event identity, timestamps, and structures', () => {
    expect(() => parseAuditEvent({ ...event, id: 'not-a-uuid' })).toThrow(ApiError);
    expect(() => parseAuditEvent({ ...event, timestamp: 'yesterday' })).toThrow(ApiError);
    expect(() => parseAuditEvent({ ...event, changes: [] })).toThrow(ApiError);
  });
  it('keeps an explicit frontend redaction boundary', () => {
    expect(safeAuditJson({ api_key: 'private', ordinary_key: 'visible' })).toEqual({ api_key: '[REDACTED]', ordinary_key: 'visible' });
  });
});
