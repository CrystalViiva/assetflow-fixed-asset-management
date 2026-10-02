import type { AssetDto } from '../services/assetDtos';

export const assetDto: AssetDto = {
  id: 'c942f6c8-581c-430d-b234-b6853a4e7c94', organization_id: '9d3e6ed1-af85-4543-b3f4-45445f1292f1',
  organization_name: 'Test Organization', asset_tag: 'REAL-001', name: 'Office generator', description: 'Backup power',
  category_id: '1ce54080-a0ce-4872-b385-dd2f25598c28', category_name: 'Equipment', category_code: 'EQ',
  department_id: null, department_name: null, department_code: null, location_id: null, location_name: null, location_code: null,
  serial_number: 'SER-1', model_number: 'GEN-2', manufacturer: 'Example', status: 'ACTIVE', condition: 'GOOD',
  acquisition_date: '2026-01-01', capitalization_date: null, available_for_use_date: null,
  purchase_cost: '999999999999999999.99', residual_value: '0.00', current_book_value: '1234.50', accumulated_depreciation: '10.50',
  useful_life_months: null, depreciation_method: 'SLM', created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-02T00:00:00Z',
  created_by_email: null, updated_by_email: null,
};
export const identity = { id: 1, email: 'one@example.test', role: 'ACCOUNTANT' };
export const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
export const envelope = (code: string, message: string) => ({ success: false, error: { code, message, details: {} } });
export function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}
