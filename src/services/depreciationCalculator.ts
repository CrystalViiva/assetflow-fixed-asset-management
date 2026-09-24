/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 * Financial Depreciation Engine - Fixed Asset Accounting
 * Implements IAS 16 Straight-Line Amortization & Residual Value computations.
 * Designed to avoid floating-point drift by working with integer kobo (cents) equivalents.
 */

import { DepreciationScheduleItem } from '../types';

/**
 * Format a number into Nigerian Naira currency format (e.g. ₦44,000,000 or ₦44,000,000.00)
 */
export function formatNaira(amount: number, showDecimals: boolean = false): string {
  if (isNaN(amount) || amount === null || amount === undefined) {
    return '₦0';
  }
  const rounded = Math.round(amount);
  if (showDecimals) {
    return '₦' + amount.toLocaleString('en-NG', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }
  return '₦' + rounded.toLocaleString('en-NG');
}

/**
 * Compact format for badges and charts (e.g. ₦1.12B, ₦680.0M, ₦49.0M)
 */
export function formatNairaCompact(amount: number): string {
  if (isNaN(amount) || amount === 0) return '₦0';
  const abs = Math.abs(amount);
  const sign = amount < 0 ? '-' : '';

  if (abs >= 1_000_000_000) {
    return `${sign}₦${(abs / 1_000_000_000).toFixed(2)}B`;
  }
  if (abs >= 1_000_000) {
    return `${sign}₦${(abs / 1_000_000).toFixed(1)}M`;
  }
  if (abs >= 1_000) {
    return `${sign}₦${(abs / 1_000).toFixed(0)}K`;
  }
  return `${sign}₦${Math.round(abs)}`;
}

/**
 * Clean integer math conversions (Naira to Kobo and Kobo to Naira)
 */
export function toKobo(naira: number): number {
  return Math.round(naira * 100);
}

export function fromKobo(kobo: number): number {
  return kobo / 100;
}

export interface DepreciationCalculationInput {
  cost: number;
  residualRatePct?: number;
  residualValue?: number;
  usefulLifeMonths: number;
  capitalizationDate?: string;
  asOfDate?: string;
}

export interface DepreciationCalculationResult {
  cost: number;
  residualRatePct: number;
  salvageValue: number;
  depreciableBase: number;
  usefulLifeMonths: number;
  usefulLifeYears: number;
  monthlyDepreciation: number;
  annualDepreciation: number;
  monthsElapsed: number;
  accumulatedDepreciation: number;
  netBookValue: number;
  carryingRatePct: number;
}

/**
 * Calculates straight line depreciation per IAS 16 rules:
 * Depreciable Amount = Cost − Residual Value
 * Monthly Depreciation = Depreciable Amount / Useful Life in Months
 */
export function calculateStraightLine(input: DepreciationCalculationInput): DepreciationCalculationResult {
  const costKobo = toKobo(Math.max(0, input.cost || 0));
  const usefulLifeMonths = Math.max(1, input.usefulLifeMonths || 12);
  const usefulLifeYears = +(usefulLifeMonths / 12).toFixed(1);

  let salvageKobo: number;
  let residualRatePct: number;

  if (input.residualValue !== undefined && input.residualValue !== null) {
    salvageKobo = toKobo(Math.min(input.cost, Math.max(0, input.residualValue)));
    residualRatePct = costKobo > 0 ? +((salvageKobo / costKobo) * 100).toFixed(2) : 0;
  } else {
    residualRatePct = Math.min(100, Math.max(0, input.residualRatePct ?? 10));
    salvageKobo = Math.round((costKobo * residualRatePct) / 100);
  }

  const depreciableKobo = Math.max(0, costKobo - salvageKobo);
  const monthlyDepKobo = Math.floor(depreciableKobo / usefulLifeMonths);
  const annualDepKobo = monthlyDepKobo * 12;

  // Calculate elapsed months if dates provided
  let monthsElapsed = 0;
  if (input.capitalizationDate) {
    const capDate = new Date(input.capitalizationDate);
    const asOf = input.asOfDate ? new Date(input.asOfDate) : new Date();
    if (!isNaN(capDate.getTime()) && !isNaN(asOf.getTime()) && asOf >= capDate) {
      const yearDiff = asOf.getFullYear() - capDate.getFullYear();
      const monthDiff = asOf.getMonth() - capDate.getMonth();
      monthsElapsed = Math.min(usefulLifeMonths, Math.max(0, yearDiff * 12 + monthDiff));
    }
  }

  const accumulatedDepKobo = Math.min(depreciableKobo, monthlyDepKobo * monthsElapsed);
  const netBookValueKobo = Math.max(salvageKobo, costKobo - accumulatedDepKobo);
  const carryingRatePct = costKobo > 0 ? +((netBookValueKobo / costKobo) * 100).toFixed(1) : 0;

  return {
    cost: fromKobo(costKobo),
    residualRatePct,
    salvageValue: fromKobo(salvageKobo),
    depreciableBase: fromKobo(depreciableKobo),
    usefulLifeMonths,
    usefulLifeYears,
    monthlyDepreciation: fromKobo(monthlyDepKobo),
    annualDepreciation: fromKobo(annualDepKobo),
    monthsElapsed,
    accumulatedDepreciation: fromKobo(accumulatedDepKobo),
    netBookValue: fromKobo(netBookValueKobo),
    carryingRatePct,
  };
}

/**
 * Generates an exhaustive multi-period depreciation schedule for display
 */
export function generateDepreciationSchedule(
  cost: number,
  salvageValue: number,
  usefulLifeMonths: number,
  startDateStr?: string
): DepreciationScheduleItem[] {
  const schedule: DepreciationScheduleItem[] = [];
  const costKobo = toKobo(cost);
  const salvageKobo = toKobo(salvageValue);
  const depreciableKobo = Math.max(0, costKobo - salvageKobo);
  const monthlyKobo = Math.floor(depreciableKobo / usefulLifeMonths);

  const startDate = startDateStr ? new Date(startDateStr) : new Date(2022, 5, 15);
  let currentBookValueKobo = costKobo;
  let totalAccKobo = 0;

  for (let i = 1; i <= usefulLifeMonths; i++) {
    const periodDate = new Date(startDate);
    periodDate.setMonth(startDate.getMonth() + i);

    const isLast = i === usefulLifeMonths;
    // On last period, round off remaining depreciable amount to hit exact salvage value
    const expenseKobo = isLast ? depreciableKobo - totalAccKobo : monthlyKobo;
    totalAccKobo += expenseKobo;
    const openingKobo = currentBookValueKobo;
    currentBookValueKobo = costKobo - totalAccKobo;

    const monthName = periodDate.toLocaleString('default', { month: 'short' });
    const yearNum = periodDate.getFullYear();

    schedule.push({
      period_index: i,
      year: yearNum,
      month: periodDate.getMonth() + 1,
      period_label: `${monthName} ${yearNum}`,
      opening_book_value: fromKobo(openingKobo),
      depreciation_expense: fromKobo(expenseKobo),
      accumulated_depreciation: fromKobo(totalAccKobo),
      closing_book_value: fromKobo(currentBookValueKobo),
    });
  }

  return schedule;
}

/**
 * Calculates Gain / Loss on Disposal per IAS 16
 * Gain/Loss = Disposal Proceeds − Book Value
 */
export function calculateDisposalGainLoss(proceeds: number, bookValue: number): {
  gainOrLoss: number;
  isGain: boolean;
} {
  const proceedsKobo = toKobo(proceeds);
  const bookValueKobo = toKobo(bookValue);
  const diffKobo = proceedsKobo - bookValueKobo;
  return {
    gainOrLoss: fromKobo(diffKobo),
    isGain: diffKobo >= 0,
  };
}
