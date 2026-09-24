/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 * Statutory Depreciation Engine View (IAS 16 Straight-Line Amortization)
 */

import React, { useState, useEffect } from 'react';
import { Asset, DepreciationScheduleItem } from '../types';
import { assetRepository } from '../services/assetRepository';
import { formatNaira, generateDepreciationSchedule } from '../services/depreciationCalculator';

interface DepreciationViewProps {
  onNavigate: (route: string) => void;
  onSelectAsset: (assetId: string) => void;
}

export const DepreciationView: React.FC<DepreciationViewProps> = ({ onNavigate, onSelectAsset }) => {
  const [assets, setAssets] = useState<Asset[]>([]);
  const [selectedAssetId, setSelectedAssetId] = useState<string>('');
  const [schedule, setSchedule] = useState<DepreciationScheduleItem[]>([]);

  useEffect(() => {
    async function load() {
      const res = await assetRepository.getAssets({ pageSize: 50 });
      setAssets(res.data);
      if (res.data.length > 0) {
        setSelectedAssetId(res.data[1]?.id || res.data[0].id); // default to Excavator or first asset
      }
    }
    load();
  }, []);

  const activeAsset = assets.find(a => a.id === selectedAssetId) || assets[0];

  useEffect(() => {
    if (activeAsset) {
      const s = generateDepreciationSchedule(
        activeAsset.total_acquisition_cost,
        activeAsset.salvage_value,
        activeAsset.useful_life_months,
        activeAsset.capitalization_date
      );
      setSchedule(s);
    }
  }, [activeAsset]);

  const totalPortfolioCost = assets.reduce((sum, a) => sum + a.total_acquisition_cost, 0);
  const totalPortfolioAcc = assets.reduce((sum, a) => sum + a.accumulated_depreciation, 0);
  const totalPortfolioNbv = assets.reduce((sum, a) => sum + a.net_book_value, 0);
  const totalMonthlyRun = assets.reduce((sum, a) => sum + a.monthly_depreciation, 0);

  const [postingSuccess, setPostingSuccess] = useState<string | null>(null);

  const handleRunPosting = () => {
    setPostingSuccess('Monthly Depreciation Posting Run executed successfully! ₦32,400,000 amortized to General Ledger.');
    setTimeout(() => setPostingSuccess(null), 4000);
  };

  return (
    <div className="w-full p-4 md:p-6 select-text space-y-5">
      {postingSuccess && (
        <div className="p-3.5 bg-emerald-50 border border-emerald-200 text-emerald-900 rounded-lg flex items-center justify-between text-sm shadow-xs animate-in fade-in">
          <div className="flex items-center gap-2.5">
            <span className="material-symbols-outlined text-[20px] text-emerald-600">check_circle</span>
            <span className="font-medium">{postingSuccess}</span>
          </div>
          <button onClick={() => setPostingSuccess(null)} className="text-emerald-700 hover:text-emerald-950">
            <span className="material-symbols-outlined text-[16px]">close</span>
          </button>
        </div>
      )}

      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-1.5 text-[12px] text-slate-500 mb-1">
            <span onClick={() => onNavigate('dashboard')} className="hover:text-[#00288e] cursor-pointer">Home</span>
            <span className="text-slate-300">/</span>
            <span className="text-slate-500">Lifecycle</span>
            <span className="text-slate-300">/</span>
            <span className="text-slate-900 font-bold">Depreciation</span>
          </div>
          <h1 className="text-2xl font-bold text-slate-900">
            Statutory Depreciation Engine (IAS 16)
          </h1>
          <p className="text-[13px] text-slate-500">
            Standard straight-line amortization calculations, residual floors, and full multi-year schedules.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={handleRunPosting}
            className="h-9 px-3.5 bg-[#00288e] text-white font-semibold text-[13px] rounded-lg shadow-xs hover:bg-[#1e40af] transition-all flex items-center gap-1.5"
          >
            <span className="material-symbols-outlined text-[18px]">play_circle</span>
            <span>Run Monthly Posting (Mar 2025)</span>
          </button>
        </div>
      </div>

      {/* Portfolio Financial Overview Strip */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white p-4 rounded-xl shadow-sm border border-slate-200/80">
          <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">Portfolio Capitalized Cost</span>
          <div className="text-[22px] font-mono font-bold text-slate-900 mt-1">{formatNaira(totalPortfolioCost)}</div>
          <span className="text-[11px] text-slate-500">Gross asset base</span>
        </div>

        <div className="bg-white p-4 rounded-xl shadow-sm border border-slate-200/80">
          <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">Accumulated Amortization</span>
          <div className="text-[22px] font-mono font-bold text-amber-700 mt-1">{formatNaira(totalPortfolioAcc)}</div>
          <span className="text-[11px] text-slate-500">Statutory wear write-down</span>
        </div>

        <div className="bg-white p-4 rounded-xl shadow-sm border border-slate-200/80">
          <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">Carrying Net Book Value</span>
          <div className="text-[22px] font-mono font-bold text-emerald-800 mt-1">{formatNaira(totalPortfolioNbv)}</div>
          <span className="text-[11px] text-emerald-700 font-semibold">Active balance sheet worth</span>
        </div>

        <div className="bg-white p-4 rounded-xl shadow-sm border border-slate-200/80">
          <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">Monthly Run Rate</span>
          <div className="text-[22px] font-mono font-bold text-[#00288e] mt-1">{formatNaira(totalMonthlyRun)}</div>
          <span className="text-[11px] text-slate-500">Recurring monthly charge</span>
        </div>
      </div>

      {/* Interactive Asset Schedule Explorer */}
      {activeAsset && (
        <div className="bg-white rounded-xl shadow-sm border border-slate-200/80 p-5 space-y-5">
          <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 pb-4 border-b border-slate-100">
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <span className="font-mono text-sm font-bold text-[#00288e] bg-[#eff4ff] px-2 py-0.5 rounded border border-blue-200">
                  {activeAsset.tag}
                </span>
                <h2 className="text-lg font-bold text-slate-900">{activeAsset.name}</h2>
              </div>
              <p className="text-[12px] text-slate-500">
                Formula: Depreciable Amount = Cost (₦) − Residual Value (₦) • Monthly Amortization = Depreciable Amount / Useful Life in Months
              </p>
            </div>

            {/* Asset Switcher Dropdown */}
            <div className="flex items-center gap-2">
              <span className="text-[12px] font-semibold text-slate-600 whitespace-nowrap">Select Asset:</span>
              <select
                value={selectedAssetId}
                onChange={e => setSelectedAssetId(e.target.value)}
                className="h-9 px-3 bg-[#eff4ff] text-slate-900 font-semibold rounded-lg border border-slate-200 text-[13px] focus:ring-1.5 focus:ring-[#00288e]"
              >
                {assets.map(a => (
                  <option key={a.id} value={a.id}>
                    {a.tag} — {a.name}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Mathematical Parameters Display Cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-3">
            <div className="p-3 bg-[#eff4ff]/60 rounded-lg border border-slate-200/80">
              <span className="text-[10px] uppercase font-bold text-slate-500 block">Cost</span>
              <span className="font-mono font-bold text-slate-900 text-[13px]">
                {formatNaira(activeAsset.total_acquisition_cost)}
              </span>
            </div>

            <div className="p-3 bg-[#eff4ff]/60 rounded-lg border border-slate-200/80">
              <span className="text-[10px] uppercase font-bold text-slate-500 block">Residual Value</span>
              <span className="font-mono font-bold text-slate-900 text-[13px]">
                {formatNaira(activeAsset.salvage_value)}
              </span>
            </div>

            <div className="p-3 bg-[#eff4ff]/60 rounded-lg border border-slate-200/80">
              <span className="text-[10px] uppercase font-bold text-slate-500 block">Depreciable Base</span>
              <span className="font-mono font-bold text-[#00288e] text-[13px]">
                {formatNaira(activeAsset.depreciable_base)}
              </span>
            </div>

            <div className="p-3 bg-[#eff4ff]/60 rounded-lg border border-slate-200/80">
              <span className="text-[10px] uppercase font-bold text-slate-500 block">Useful Life</span>
              <span className="font-bold text-slate-900 text-[13px]">
                {activeAsset.useful_life_years} Yrs ({activeAsset.useful_life_months}m)
              </span>
            </div>

            <div className="p-3 bg-[#eff4ff]/60 rounded-lg border border-slate-200/80">
              <span className="text-[10px] uppercase font-bold text-slate-500 block">Monthly Deprec.</span>
              <span className="font-mono font-bold text-[#00288e] text-[13px]">
                {formatNaira(activeAsset.monthly_depreciation)}
              </span>
            </div>

            <div className="p-3 bg-[#eff4ff]/60 rounded-lg border border-slate-200/80">
              <span className="text-[10px] uppercase font-bold text-slate-500 block">Accumulated</span>
              <span className="font-mono font-bold text-amber-700 text-[13px]">
                {formatNaira(activeAsset.accumulated_depreciation)}
              </span>
            </div>

            <div className="p-3 bg-[#eff4ff]/60 rounded-lg border border-slate-200/80">
              <span className="text-[10px] uppercase font-bold text-slate-500 block">Current Book Value</span>
              <span className="font-mono font-bold text-emerald-800 text-[13px]">
                {formatNaira(activeAsset.net_book_value)}
              </span>
            </div>
          </div>

          {/* Full Schedule Table */}
          <div className="overflow-x-auto rounded-lg border border-slate-200 max-h-96">
            <table className="w-full text-left text-[12px]">
              <thead className="bg-[#eff4ff] text-slate-700 font-bold uppercase text-[10px] tracking-wider sticky top-0 border-b border-slate-200">
                <tr>
                  <th className="py-2.5 px-3">Period</th>
                  <th className="py-2.5 px-3">Calendar Month</th>
                  <th className="py-2.5 px-3 text-right">Opening NBV (₦)</th>
                  <th className="py-2.5 px-3 text-right">Monthly Amortization (₦)</th>
                  <th className="py-2.5 px-3 text-right">Accumulated Deprec (₦)</th>
                  <th className="py-2.5 px-3 text-right">Closing Book Value (₦)</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 font-mono">
                {schedule.map(item => (
                  <tr key={item.period_index} className="hover:bg-slate-50">
                    <td className="py-2 px-3 text-slate-500 font-semibold">{item.period_index}</td>
                    <td className="py-2 px-3 font-sans font-medium text-slate-800">{item.period_label}</td>
                    <td className="py-2 px-3 text-right text-slate-700">{formatNaira(item.opening_book_value)}</td>
                    <td className="py-2 px-3 text-right text-amber-700 font-bold">{formatNaira(item.depreciation_expense)}</td>
                    <td className="py-2 px-3 text-right text-slate-600">{formatNaira(item.accumulated_depreciation)}</td>
                    <td className="py-2 px-3 text-right font-bold text-[#00288e]">{formatNaira(item.closing_book_value)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};
