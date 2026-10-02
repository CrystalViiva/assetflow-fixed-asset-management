import { ApiError } from './apiError';

const MAX_MINOR_UNITS = 10n ** 20n - 1n; // Backend Decimal(max_digits=20, decimal_places=2).

export function normalizeMoney(input: string, optional = false): string {
  const text = input.trim();
  if (!text && optional) return '0.00';
  if (!/^\d{1,18}(?:\.\d{1,2})?$/.test(text)) {
    throw new ApiError('validation', 'Enter a non-negative amount with up to 18 whole digits and 2 decimal places.');
  }
  const [whole, fraction = ''] = text.split('.');
  return `${BigInt(whole)}.${fraction.padEnd(2, '0')}`;
}

export function minorUnits(input: string): bigint {
  return BigInt(normalizeMoney(input).replace('.', ''));
}

export function sumMoney(values: string[]): string {
  const total = values.reduce((sum, value) => sum + minorUnits(value), 0n);
  if (total > MAX_MINOR_UNITS) throw new ApiError('validation', 'The combined cost exceeds the supported maximum.');
  return `${total / 100n}.${String(total % 100n).padStart(2, '0')}`;
}
