/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 * Executive Asset Dashboard View
 * Faithfully reproduces the Stitch Executive Asset Dashboard prototype with live reactive data.
 */

import React, { useState, useEffect } from 'react';
import { Asset, DashboardMetrics } from '../types';
import { assetRepository } from '../services/assetRepository';
import { formatNaira, formatNairaCompact } from '../services/depreciationCalculator';

interface DashboardViewProps {
  onNavigate: (route: string) => void;
  onSelectAsset: (assetId: string) => void;
  onOpenQuickAction: (action: string) => void;
}

export const DashboardView: React.FC<DashboardViewProps> = ({
  onNavigate,
  onSelectAsset,
  onOpenQuickAction,
}) => {
  const [metrics, setMetrics] = useState<DashboardMetrics | null>(null);
  const [recentAssets, setRecentAssets] = useState<Asset[]>([]);
  const [selectedFiscalPeriod, setSelectedFiscalPeriod] = useState<string>('Q1 2025 (Jan - Mar)');
  const [categoryMetricMode, setCategoryMetricMode] = useState<'value' | 'count'>('value');
  const [showPeriodDropdown, setShowPeriodDropdown] = useState<boolean>(false);
  const [hoveredBarIndex, setHoveredBarIndex] = useState<number | null>(null);

  useEffect(() => {
    async function loadData() {
      const m = await assetRepository.getDashboardMetrics();
      setMetrics(m);
      const paginated = await assetRepository.getAssets({ pageSize: 4 });
      setRecentAssets(paginated.data);
    }
    loadData();
  }, []);

  const fiscalPeriods = [
    'Q1 2025 (Jan - Mar)',
    'FY 2024 Audited',
    'Q4 2024 (Oct - Dec)',
    'Q3 2024 (Jul - Sep)',
  ];

  if (!metrics) {
    return (
      <div className="p-8 flex items-center justify-center min-h-[400px]">
        <div className="flex items-center gap-3 text-slate-500 font-medium">
          <span className="material-symbols-outlined text-[24px] animate-spin text-[#00288e]">
            refresh
          </span>
          <span>Loading Executive Ledger Metrics...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="w-full p-4 md:p-6 select-text">
      {/* Top Ambient Accent Background */}
      <div className="relative w-full overflow-hidden">
        <div className="absolute -top-16 -right-16 w-96 h-96 bg-blue-600/10 rounded-full blur-3xl pointer-events-none"></div>
        <div className="absolute -top-20 left-1/3 w-80 h-80 bg-slate-300/30 rounded-full blur-2xl pointer-events-none"></div>

        {/* Header Action Bar */}
        <div className="relative z-10 flex flex-col xl:flex-row xl:items-center justify-between gap-4 mb-6">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <span className="px-2 py-0.5 rounded text-[11px] font-bold uppercase bg-[#e5eeff] text-[#00288e] tracking-wider border border-[#d3e4fe]">
                IAS 16 / IFRS Certified
              </span>
              <span className="text-slate-500 text-[11px]">• Institutional Asset Ledger</span>
            </div>
            <h1 className="text-2xl md:text-[26px] font-bold text-slate-900 tracking-tight">
              Executive Asset Dashboard
            </h1>
            <p className="text-[13px] text-slate-500 max-w-3xl">
              Consolidated overview of fixed assets, capitalization, net book value, and lifecycle activity across Nigerian operating hubs.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2 self-start xl:self-auto">
            <button
              onClick={() => window.print()}
              className="h-9 px-3.5 bg-white text-slate-700 font-semibold text-[13px] rounded-lg shadow-2xs hover:bg-slate-50 border border-slate-200 transition-colors flex items-center gap-2"
            >
              <span className="material-symbols-outlined text-[18px] text-slate-500">
                picture_as_pdf
              </span>
              <span>Export Executive Brief (PDF)</span>
            </button>

            {/* Fiscal Period Selector */}
            <div className="relative">
              <button
                onClick={() => setShowPeriodDropdown(!showPeriodDropdown)}
                className="h-9 px-3.5 bg-white text-slate-800 font-semibold text-[13px] rounded-lg shadow-2xs hover:bg-slate-50 border border-slate-200 transition-colors flex items-center gap-2"
              >
                <span className="material-symbols-outlined text-[18px] text-[#00288e]">
                  calendar_today
                </span>
                <span>
                  Fiscal Period: <strong className="font-bold text-slate-900">{selectedFiscalPeriod}</strong>
                </span>
                <span className="material-symbols-outlined text-[16px] text-slate-400">
                  expand_more
                </span>
              </button>

              {showPeriodDropdown && (
                <div className="absolute right-0 mt-1 w-52 bg-white rounded-lg shadow-xl border border-slate-200 py-1 z-50 text-[13px]">
                  {fiscalPeriods.map(period => (
                    <button
                      key={period}
                      onClick={() => {
                        setSelectedFiscalPeriod(period);
                        setShowPeriodDropdown(false);
                      }}
                      className={`w-full text-left px-3.5 py-1.5 hover:bg-[#eff4ff] hover:text-[#00288e] transition-colors ${
                        selectedFiscalPeriod === period ? 'font-bold text-[#00288e] bg-[#eff4ff]/60' : 'text-slate-700'
                      }`}
                    >
                      {period}
                    </button>
                  ))}
                </div>
              )}
            </div>

            <button
              onClick={() => onNavigate('asset-create')}
              className="h-9 px-4 bg-[#00288e] text-white font-semibold text-[13px] rounded-lg shadow-sm hover:bg-[#1e40af] transition-all flex items-center gap-1.5 active:scale-[0.99]"
            >
              <span className="material-symbols-outlined text-[18px]">add</span>
              <span>Register Asset</span>
            </button>
          </div>
        </div>
      </div>

      {/* KPI Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4 mb-6">
        {/* KPI 1: Total Assets */}
        <div className="bg-white rounded-xl p-4 shadow-sm border border-slate-200/80 relative overflow-hidden flex flex-col justify-between hover:shadow-md transition-shadow">
          <div className="flex items-start justify-between">
            <div>
              <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">
                Total Assets
              </span>
              <div className="text-3xl font-extrabold text-slate-900 mt-1 leading-none">
                {metrics.total_assets.toLocaleString('en-NG')}
              </div>
            </div>
            <div className="w-10 h-10 rounded-lg bg-[#eff4ff] flex items-center justify-center text-[#00288e]">
              <span className="material-symbols-outlined text-[22px]">inventory_2</span>
            </div>
          </div>

          <div className="my-3 flex items-center justify-between">
            <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200/60">
              <span className="material-symbols-outlined text-[14px]">trending_up</span>
              +38 this quarter (+3.1%)
            </span>
            <svg className="w-20 h-6 text-emerald-600" fill="none" viewBox="0 0 100 30">
              <path
                d="M0 25 L20 22 L40 18 L60 20 L80 12 L100 4"
                stroke="currentColor"
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="2.5"
              />
              <path
                d="M0 25 L20 22 L40 18 L60 20 L80 12 L100 4 L100 30 L0 30 Z"
                fill="currentColor"
                fillOpacity="0.12"
              />
            </svg>
          </div>

          <div className="grid grid-cols-2 gap-1.5 text-[11px]">
            <div className="bg-[#eff4ff] px-2 py-1 rounded flex items-center justify-between">
              <span className="text-slate-600">Active</span>
              <span className="font-bold text-slate-900">{metrics.active_assets}</span>
            </div>
            <div className="bg-[#eff4ff] px-2 py-1 rounded flex items-center justify-between">
              <span className="text-slate-600">Maintenance</span>
              <span className="font-bold text-amber-700">{metrics.maintenance_assets}</span>
            </div>
            <div className="bg-[#eff4ff] px-2 py-1 rounded flex items-center justify-between">
              <span className="text-slate-600">Transferred</span>
              <span className="font-bold text-slate-900">{metrics.transferred_assets}</span>
            </div>
            <div className="bg-[#eff4ff] px-2 py-1 rounded flex items-center justify-between">
              <span className="text-slate-600">Impaired</span>
              <span className="font-bold text-rose-700">{metrics.impaired_assets}</span>
            </div>
          </div>
        </div>

        {/* KPI 2: Total Acquisition Cost */}
        <div className="bg-white rounded-xl p-4 shadow-sm border border-slate-200/80 relative overflow-hidden flex flex-col justify-between hover:shadow-md transition-shadow">
          <div className="flex items-start justify-between">
            <div>
              <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">
                Total Acquisition Cost
              </span>
              <div className="text-[21px] font-bold text-slate-900 mt-1 leading-none font-mono">
                {formatNaira(metrics.total_acquisition_cost)}
              </div>
              <span className="text-[11px] text-slate-500">₦2.43 Billion Capitalized Base</span>
            </div>
            <div className="w-10 h-10 rounded-lg bg-[#eff4ff] flex items-center justify-center text-[#00288e]">
              <span className="material-symbols-outlined text-[22px]">account_balance</span>
            </div>
          </div>

          <div className="my-3 flex items-center justify-between">
            <span className="inline-flex items-center gap-1 text-[11px] text-[#00288e] font-semibold bg-[#e5eeff] px-2 py-0.5 rounded border border-[#d3e4fe]">
              <span className="material-symbols-outlined text-[14px]">add_circle</span>
              +₦142.5M additions YTD
            </span>
            <svg className="w-20 h-6 text-[#00288e]" fill="none" viewBox="0 0 100 30">
              <path
                d="M0 26 L25 24 L50 17 L75 14 L100 6"
                stroke="currentColor"
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="2.5"
              />
              <path
                d="M0 26 L25 24 L50 17 L75 14 L100 6 L100 30 L0 30 Z"
                fill="currentColor"
                fillOpacity="0.12"
              />
            </svg>
          </div>

          <div className="bg-[#eff4ff] px-2.5 py-1.5 rounded flex items-center justify-between text-[11px]">
            <span className="text-slate-600 flex items-center gap-1">
              <span className="material-symbols-outlined text-[14px] text-emerald-700">verified</span>
              External Audit
            </span>
            <span className="font-semibold text-slate-900">PwC FY24 Cleared</span>
          </div>
        </div>

        {/* KPI 3: Current Net Book Value (NBV) */}
        <div className="bg-white rounded-xl p-4 shadow-sm border border-slate-200/80 relative overflow-hidden flex flex-col justify-between hover:shadow-md transition-shadow">
          <div className="flex items-start justify-between">
            <div>
              <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">
                Current Net Book Value (NBV)
              </span>
              <div className="text-[21px] font-bold text-[#00288e] mt-1 leading-none font-mono">
                {formatNaira(metrics.current_book_value)}
              </div>
              <span className="text-[11px] text-slate-500">₦1.71 Billion Carrying Worth</span>
            </div>
            <div className="w-10 h-10 rounded-lg bg-[#dce9ff] flex items-center justify-center text-[#00288e]">
              <span className="material-symbols-outlined text-[22px]">auto_graph</span>
            </div>
          </div>

          <div className="my-3 flex items-center justify-between">
            <span className="inline-flex items-center gap-1 text-[11px] text-slate-700 bg-slate-100 px-2 py-0.5 rounded font-medium">
              <span className="material-symbols-outlined text-[14px] text-[#00288e]">pie_chart</span>
              70.4% Carrying retention
            </span>
            <div className="w-20 bg-slate-200 h-2.5 rounded-full overflow-hidden">
              <div className="bg-[#00288e] h-full rounded-full" style={{ width: '70.4%' }}></div>
            </div>
          </div>

          <div className="bg-[#eff4ff] px-2.5 py-1.5 rounded flex items-center justify-between text-[11px]">
            <span className="text-slate-600">Standard</span>
            <span className="font-semibold text-[#00288e]">IAS 16 Revalued Method</span>
          </div>
        </div>

        {/* KPI 4: Accumulated Depreciation */}
        <div className="bg-white rounded-xl p-4 shadow-sm border border-slate-200/80 relative overflow-hidden flex flex-col justify-between hover:shadow-md transition-shadow">
          <div className="flex items-start justify-between">
            <div>
              <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">
                Accumulated Depreciation
              </span>
              <div className="text-[21px] font-bold text-slate-900 mt-1 leading-none font-mono">
                {formatNaira(metrics.accumulated_depreciation)}
              </div>
              <span className="text-[11px] text-slate-500">29.6% Amortized to date</span>
            </div>
            <div className="w-10 h-10 rounded-lg bg-[#dae2fd] flex items-center justify-center text-slate-800">
              <span className="material-symbols-outlined text-[22px]">calculate</span>
            </div>
          </div>

          <div className="my-3 flex items-center justify-between text-[12px]">
            <span className="text-slate-600">
              Monthly run rate: <strong className="text-slate-900 font-bold font-mono">₦32.4M</strong>
            </span>
            <span className="px-1.5 py-0.5 text-[10px] bg-[#dce9ff] text-[#00288e] rounded font-bold">
              Straight-Line
            </span>
          </div>

          <div className="bg-[#eff4ff] px-2.5 py-1.5 rounded flex items-center justify-between text-[11px]">
            <span className="text-slate-600 flex items-center gap-1">
              <span className="material-symbols-outlined text-[14px]">event_repeat</span>
              Next Scheduled Posting
            </span>
            <span className="font-semibold text-slate-900">March 31, 2025</span>
          </div>
        </div>
      </div>

      {/* Category vs Operating Hub Analytics Section */}
      <div className="grid grid-cols-1 xl:grid-cols-12 gap-4 mb-6">
        {/* Category & Valuation (7 Cols) */}
        <div className="xl:col-span-7 bg-white rounded-xl p-4 md:p-5 shadow-sm border border-slate-200/80 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-4">
              <div>
                <div className="flex items-center gap-2">
                  <span className="material-symbols-outlined text-[#00288e] text-[20px]">category</span>
                  <h2 className="text-[16px] font-bold text-slate-900">
                    Assets by Category & Valuation
                  </h2>
                </div>
                <p className="text-[12px] text-slate-500">
                  Distribution of capitalized acquisition cost by asset classification
                </p>
              </div>

              <div className="flex items-center gap-1 bg-[#eff4ff] p-0.5 rounded text-[11px]">
                <button
                  onClick={() => setCategoryMetricMode('value')}
                  className={`px-2.5 py-1 rounded font-semibold transition-all ${
                    categoryMetricMode === 'value'
                      ? 'bg-white text-[#00288e] shadow-xs'
                      : 'text-slate-600 hover:text-slate-900'
                  }`}
                >
                  Value (₦)
                </button>
                <button
                  onClick={() => setCategoryMetricMode('count')}
                  className={`px-2.5 py-1 rounded font-semibold transition-all ${
                    categoryMetricMode === 'count'
                      ? 'bg-white text-[#00288e] shadow-xs'
                      : 'text-slate-600 hover:text-slate-900'
                  }`}
                >
                  Unit Count
                </button>
              </div>
            </div>

            {/* Category Breakdown Bars */}
            <div className="space-y-3.5">
              {metrics.category_breakdown.map(cat => (
                <div key={cat.category_id} className="group">
                  <div className="flex items-center justify-between text-[13px] mb-1">
                    <div className="flex items-center gap-2">
                      <span
                        className="w-3 h-3 rounded"
                        style={{ backgroundColor: cat.color }}
                      ></span>
                      <span className="font-semibold text-slate-800">{cat.category_name}</span>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className="font-mono font-bold text-slate-900">
                        {categoryMetricMode === 'value'
                          ? formatNaira(cat.total_value)
                          : `${cat.unit_count.toLocaleString('en-NG')} units`}
                      </span>
                      <span className="text-[11px] text-slate-500 w-11 text-right font-medium">
                        {cat.percentage.toFixed(1)}%
                      </span>
                    </div>
                  </div>
                  <div className="w-full bg-[#e5eeff] h-2.5 rounded-full overflow-hidden">
                    <div
                      className="h-full rounded-full transition-all duration-700"
                      style={{
                        width: `${cat.percentage}%`,
                        backgroundColor: cat.color,
                      }}
                    ></div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="mt-4 pt-3 bg-[#eff4ff] p-3 rounded-lg flex items-center justify-between text-[12px]">
            <div className="flex items-center gap-2">
              <span className="material-symbols-outlined text-[#00288e] text-[18px]">verified</span>
              <span className="text-slate-700">
                Top growth class: <strong className="text-slate-900">Heavy Machinery</strong> (+₦68M Q1)
              </span>
            </div>
            <button
              onClick={() => onNavigate('asset-categories')}
              className="text-[#00288e] hover:text-[#1e40af] font-semibold flex items-center gap-0.5"
            >
              <span>View Class Register</span>
              <span className="material-symbols-outlined text-[14px]">arrow_forward</span>
            </button>
          </div>
        </div>

        {/* Assets by Operating Hub (5 Cols) */}
        <div className="xl:col-span-5 bg-white rounded-xl p-4 md:p-5 shadow-sm border border-slate-200/80 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-4">
              <div>
                <div className="flex items-center gap-2">
                  <span className="material-symbols-outlined text-[#00288e] text-[20px]">
                    location_city
                  </span>
                  <h2 className="text-[16px] font-bold text-slate-900">Assets by Operating Hub</h2>
                </div>
                <p className="text-[12px] text-slate-500">
                  Geographic capitalization across operational centers
                </p>
              </div>
              <span className="text-[11px] px-2 py-0.5 bg-[#eff4ff] rounded text-slate-600 font-semibold border border-slate-200/60">
                5 Hubs Active
              </span>
            </div>

            {/* Hub List */}
            <div className="space-y-2">
              {metrics.hub_breakdown.map((hub, idx) => {
                const bgColors = ['bg-[#00288e]', 'bg-[#1e40af]', 'bg-[#3755c3]', 'bg-[#565e74]', 'bg-[#757684]'];
                return (
                  <div
                    key={hub.code}
                    onClick={() => onNavigate('locations')}
                    className="p-2.5 bg-[#eff4ff]/60 hover:bg-[#eff4ff] rounded-lg transition-colors flex items-center justify-between cursor-pointer border border-transparent hover:border-slate-200"
                  >
                    <div className="flex items-center gap-3">
                      <div
                        className={`w-8 h-8 rounded ${bgColors[idx % bgColors.length]} text-white flex items-center justify-center font-bold text-[11px] shadow-2xs`}
                      >
                        {hub.code}
                      </div>
                      <div>
                        <div className="text-[13px] font-bold text-slate-900 leading-tight">
                          {hub.name}
                        </div>
                        <div className="text-[11px] text-slate-500">
                          {hub.asset_count} registered assets
                        </div>
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="font-mono text-[13px] font-bold text-slate-900">
                        {formatNairaCompact(hub.total_value)}
                      </div>
                      <span className="text-[11px] text-[#00288e] font-semibold">
                        {hub.percentage.toFixed(1)}%
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>

      {/* Full Width Trend Chart: Monthly Depreciation vs Capitalization */}
      <div className="bg-white rounded-xl p-4 md:p-5 shadow-sm border border-slate-200/80 mb-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="material-symbols-outlined text-[#00288e] text-[20px]">
                waterfall_chart
              </span>
              <h2 className="text-[16px] font-bold text-slate-900">
                Monthly Depreciation vs Capitalization Trend (Last 6 Months)
              </h2>
            </div>
            <p className="text-[12px] text-slate-500">
              Capital expenditure additions compared directly against recurring statutory amortization
            </p>
          </div>

          <div className="flex items-center gap-4 text-[12px]">
            <div className="flex items-center gap-1.5">
              <span className="w-3 h-3 rounded bg-[#00288e]"></span>
              <span className="text-slate-800 font-semibold">New Capitalization (Capex)</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-3 h-3 rounded bg-[#dae2fd]"></span>
              <span className="text-slate-800 font-semibold">Monthly Depreciation</span>
            </div>
          </div>
        </div>

        {/* Scaled Multi-Bar Visual Chart Container */}
        <div className="w-full h-64 relative bg-[#eff4ff]/40 rounded-lg p-4 flex flex-col justify-end border border-slate-100">
          {/* Background Grid Lines */}
          <div className="absolute inset-x-4 top-4 bottom-12 flex flex-col justify-between pointer-events-none opacity-40">
            <div className="w-full h-px bg-slate-300 flex items-center justify-between text-[10px] text-slate-500 font-mono">
              <span className="-mt-3">₦100M</span>
            </div>
            <div className="w-full h-px bg-slate-300 flex items-center justify-between text-[10px] text-slate-500 font-mono">
              <span className="-mt-3">₦75M</span>
            </div>
            <div className="w-full h-px bg-slate-300 flex items-center justify-between text-[10px] text-slate-500 font-mono">
              <span className="-mt-3">₦50M</span>
            </div>
            <div className="w-full h-px bg-slate-300 flex items-center justify-between text-[10px] text-slate-500 font-mono">
              <span className="-mt-3">₦25M</span>
            </div>
            <div className="w-full h-px bg-slate-300 flex items-center justify-between text-[10px] text-slate-500 font-mono">
              <span className="-mt-3">₦0</span>
            </div>
          </div>

          {/* Bars Container */}
          <div className="relative z-10 grid grid-cols-6 gap-3 sm:gap-6 h-44 items-end pl-8">
            {metrics.monthly_trend.map((item, idx) => {
              const capexPct = Math.min(100, Math.round((item.capitalization / 100_000_000) * 100));
              const depPct = Math.min(100, Math.round((item.depreciation / 100_000_000) * 100));
              const isHovered = hoveredBarIndex === idx;

              return (
                <div
                  key={item.month}
                  onMouseEnter={() => setHoveredBarIndex(idx)}
                  onMouseLeave={() => setHoveredBarIndex(null)}
                  className="flex flex-col items-center h-full justify-end group cursor-pointer relative"
                >
                  {/* Tooltip on hover */}
                  {isHovered && (
                    <div className="absolute -top-14 bg-slate-900 text-white text-[10px] rounded p-2 shadow-lg z-20 pointer-events-none whitespace-nowrap">
                      <div className="font-bold">{item.month}</div>
                      <div>Capex: {formatNaira(item.capitalization)}</div>
                      <div>Depreciation: {formatNaira(item.depreciation)}</div>
                      {item.notes && <div className="text-blue-300 mt-0.5">{item.notes}</div>}
                    </div>
                  )}

                  <div className="w-full flex items-end justify-center gap-1.5 h-full">
                    <div
                      className="w-5 sm:w-6 bg-[#00288e] rounded-t group-hover:bg-[#1e40af] transition-all"
                      style={{ height: `${capexPct}%` }}
                    ></div>
                    <div
                      className="w-5 sm:w-6 bg-[#dae2fd] rounded-t group-hover:bg-slate-300 transition-all"
                      style={{ height: `${depPct}%` }}
                    ></div>
                  </div>

                  <span className={`mt-2 text-[11px] ${item.month.includes('Dec') ? 'font-bold text-[#00288e]' : 'text-slate-600'}`}>
                    {item.month}
                  </span>
                  <span className={`font-mono text-[10px] font-bold ${item.month.includes('Dec') ? 'text-[#00288e]' : 'text-slate-900'}`}>
                    +₦{(item.capitalization / 1_000_000).toFixed(1)}M
                  </span>
                </div>
              );
            })}
          </div>
        </div>

        {/* Trend Footer Highlights */}
        <div className="mt-3 grid grid-cols-1 md:grid-cols-3 gap-3 pt-2 text-[13px] border-t border-slate-100">
          <div className="flex items-center gap-2 text-slate-600">
            <span className="material-symbols-outlined text-[18px] text-[#00288e]">insights</span>
            <span>
              Average Capex Run Rate: <strong className="text-slate-900 font-bold">₦49.0M / mo</strong>
            </span>
          </div>

          <div className="flex items-center gap-2 text-slate-600">
            <span className="material-symbols-outlined text-[18px] text-emerald-600">trending_flat</span>
            <span>
              Net Capital Growth: <strong className="text-emerald-700 font-bold">+₦98.6M Q1</strong>
            </span>
          </div>

          <button
            onClick={() => onNavigate('reports')}
            className="flex items-center md:justify-end gap-1 text-[#00288e] hover:underline text-[12px] font-semibold"
          >
            <span>Download Full Variance Analysis</span>
            <span className="material-symbols-outlined text-[14px]">download</span>
          </button>
        </div>
      </div>

      {/* Operational Activity and Control Split */}
      <div className="grid grid-cols-1 xl:grid-cols-12 gap-4">
        {/* Left Table: Recent Asset Activity & Movement (8 Cols) */}
        <div className="xl:col-span-8 bg-white rounded-xl p-4 md:p-5 shadow-sm border border-slate-200/80 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <span className="material-symbols-outlined text-[#00288e] text-[20px]">sync_alt</span>
                <div>
                  <h2 className="text-[16px] font-bold text-slate-900">
                    Recent Asset Activity & Movement
                  </h2>
                  <p className="text-[12px] text-slate-500">
                    Live audit ledger of transfers, capitalization, and lifecycle events
                  </p>
                </div>
              </div>

              <button
                onClick={() => onNavigate('audit-log')}
                className="text-[12px] text-[#00288e] hover:text-[#1e40af] font-semibold flex items-center gap-0.5"
              >
                <span>View All Asset History</span>
                <span className="material-symbols-outlined text-[14px]">chevron_right</span>
              </button>
            </div>

            {/* Responsive Table Container */}
            <div className="overflow-x-auto">
              <table className="w-full text-left text-[13px]">
                <thead>
                  <tr className="bg-[#eff4ff] text-slate-600 uppercase text-[11px] font-bold tracking-wider">
                    <th className="py-2.5 px-3">Asset Tag</th>
                    <th className="py-2.5 px-3">Description</th>
                    <th className="py-2.5 px-3">Department & Location</th>
                    <th className="py-2.5 px-3">Status / Event</th>
                    <th className="py-2.5 px-3 text-right">Timestamp</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {/* Row 1: Toyota Hilux */}
                  <tr
                    onClick={() => onSelectAsset('ast-001')}
                    className="hover:bg-[#eff4ff]/60 transition-colors cursor-pointer"
                  >
                    <td className="py-3 px-3">
                      <span className="font-mono font-bold text-[#00288e]">AST-000001</span>
                    </td>
                    <td className="py-3 px-3">
                      <div className="font-semibold text-slate-900 leading-tight">
                        Toyota Hilux 2.8 GD-6 4x4
                      </div>
                      <div className="text-[11px] text-slate-500">Fleet • SN: TH-99482-NG</div>
                    </td>
                    <td className="py-3 px-3">
                      <div className="text-slate-900 font-medium">Operations</div>
                      <div className="text-[11px] text-slate-500">Port Harcourt Base</div>
                    </td>
                    <td className="py-3 px-3">
                      <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[11px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200/60">
                        <span className="w-1.5 h-1.5 rounded-full bg-emerald-600"></span>
                        Transfer Completed
                      </span>
                    </td>
                    <td className="py-3 px-3 text-right text-slate-500 font-mono text-[12px]">
                      2 hrs ago
                    </td>
                  </tr>

                  {/* Row 2: Dell PowerEdge */}
                  <tr
                    onClick={() => onSelectAsset('ast-003')}
                    className="hover:bg-[#eff4ff]/60 transition-colors cursor-pointer"
                  >
                    <td className="py-3 px-3">
                      <span className="font-mono font-bold text-[#00288e]">AST-000003</span>
                    </td>
                    <td className="py-3 px-3">
                      <div className="font-semibold text-slate-900 leading-tight">
                        Dell PowerEdge R750 Rack Server
                      </div>
                      <div className="text-[11px] text-slate-500">IT Infrastructure • Tier-3 DC</div>
                    </td>
                    <td className="py-3 px-3">
                      <div className="text-slate-900 font-medium">Information Technology</div>
                      <div className="text-[11px] text-slate-500">Abuja Data Center</div>
                    </td>
                    <td className="py-3 px-3">
                      <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[11px] font-bold bg-amber-50 text-amber-800 border border-amber-200/60">
                        <span className="w-1.5 h-1.5 rounded-full bg-amber-600"></span>
                        Warranty Maintenance
                      </span>
                    </td>
                    <td className="py-3 px-3 text-right text-slate-500 font-mono text-[12px]">
                      4 hrs ago
                    </td>
                  </tr>

                  {/* Row 3: CAT 336 Excavator */}
                  <tr
                    onClick={() => onSelectAsset('ast-002')}
                    className="hover:bg-[#eff4ff]/60 transition-colors cursor-pointer"
                  >
                    <td className="py-3 px-3">
                      <span className="font-mono font-bold text-[#00288e]">AST-000002</span>
                    </td>
                    <td className="py-3 px-3">
                      <div className="font-semibold text-slate-900 leading-tight">
                        CAT 336 Hydraulic Excavator
                      </div>
                      <div className="text-[11px] text-slate-500">Heavy Equipment • Mantrac Mant.</div>
                    </td>
                    <td className="py-3 px-3">
                      <div className="text-slate-900 font-medium">Engineering</div>
                      <div className="text-[11px] text-slate-500">Warri Depot</div>
                    </td>
                    <td className="py-3 px-3">
                      <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[11px] font-bold bg-blue-50 text-[#00288e] border border-blue-200/60">
                        <span className="w-1.5 h-1.5 rounded-full bg-[#00288e]"></span>
                        Routine Overhaul Active
                      </span>
                    </td>
                    <td className="py-3 px-3 text-right text-slate-500 font-mono text-[12px]">
                      Yesterday
                    </td>
                  </tr>

                  {/* Row 4: Perkins 500kVA */}
                  <tr
                    onClick={() => onSelectAsset('ast-006')}
                    className="hover:bg-[#eff4ff]/60 transition-colors cursor-pointer"
                  >
                    <td className="py-3 px-3">
                      <span className="font-mono font-bold text-[#00288e]">AST-000006</span>
                    </td>
                    <td className="py-3 px-3">
                      <div className="font-semibold text-slate-900 leading-tight">
                        Perkins 500kVA Heavy Generator
                      </div>
                      <div className="text-[11px] text-slate-500">Power Plant • Diesel Primary</div>
                    </td>
                    <td className="py-3 px-3">
                      <div className="text-slate-900 font-medium">Facility Mgmt</div>
                      <div className="text-[11px] text-slate-500">Lagos HQ Complex</div>
                    </td>
                    <td className="py-3 px-3">
                      <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[11px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200/60">
                        <span className="w-1.5 h-1.5 rounded-full bg-emerald-600"></span>
                        Capitalized (₦54.0M)
                      </span>
                    </td>
                    <td className="py-3 px-3 text-right text-slate-500 font-mono text-[12px]">
                      2 days ago
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          <div className="pt-4 flex items-center justify-between text-[12px] text-slate-500 border-t border-slate-100">
            <span>Showing latest 4 of 38 movements in Q1 2025</span>
            <button
              onClick={() => onNavigate('transfers')}
              className="px-3 py-1 bg-[#eff4ff] text-slate-800 rounded font-semibold hover:bg-slate-200 transition-colors"
            >
              Download Movement Manifest
            </button>
          </div>
        </div>

        {/* Right Column: Operational Alert Cards (4 Cols) */}
        <div className="xl:col-span-4 space-y-4">
          {/* Upcoming & Overdue Maintenance */}
          <div className="bg-white rounded-xl p-4 md:p-5 shadow-sm border border-slate-200/80">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <span className="material-symbols-outlined text-amber-700 text-[20px]">
                  build_circle
                </span>
                <h3 className="text-[15px] font-bold text-slate-900">Upcoming & Overdue</h3>
              </div>
              <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-[#ffdad6] text-[#93000a]">
                1 Overdue
              </span>
            </div>

            <div className="space-y-2">
              {/* Overdue Item */}
              <div
                onClick={() => onSelectAsset('ast-002')}
                className="p-3 bg-red-50/70 border border-red-200/60 rounded-lg cursor-pointer hover:bg-red-50 transition-colors"
              >
                <div className="flex items-start justify-between">
                  <div>
                    <span className="font-mono text-[11px] font-bold text-red-700">AST-000002</span>
                    <div className="text-[13px] font-bold text-slate-900 leading-tight mt-0.5">
                      CAT 336 Hydraulic Excavator
                    </div>
                    <div className="text-[11px] text-slate-600">500hr Hydraulic Service • Mantrac Nig.</div>
                  </div>
                  <span className="px-2 py-0.5 rounded text-[10px] bg-red-600 text-white font-bold uppercase tracking-wider shrink-0">
                    Overdue 2d
                  </span>
                </div>
              </div>

              {/* Pending Item 1 */}
              <div
                onClick={() => onSelectAsset('ast-006')}
                className="p-3 bg-[#eff4ff]/60 border border-slate-200/60 rounded-lg cursor-pointer hover:bg-[#eff4ff] transition-colors"
              >
                <div className="flex items-start justify-between">
                  <div>
                    <span className="font-mono text-[11px] font-bold text-[#00288e]">AST-000006</span>
                    <div className="text-[13px] font-bold text-slate-900 leading-tight mt-0.5">
                      Perkins 500kVA Generator
                    </div>
                    <div className="text-[11px] text-slate-600">B-Check Oil & Filtration Replacement</div>
                  </div>
                  <span className="px-2 py-0.5 rounded text-[10px] bg-amber-100 text-amber-900 font-bold shrink-0">
                    Due in 4 days
                  </span>
                </div>
              </div>

              {/* Pending Item 2 */}
              <div className="p-3 bg-[#eff4ff]/60 border border-slate-200/60 rounded-lg">
                <div className="flex items-start justify-between">
                  <div>
                    <span className="font-mono text-[11px] font-bold text-[#00288e]">AST-000014</span>
                    <div className="text-[13px] font-bold text-slate-900 leading-tight mt-0.5">
                      Chiller Plant System (HQ)
                    </div>
                    <div className="text-[11px] text-slate-600">Quarterly HVAC & Coolant Inspection</div>
                  </div>
                  <span className="px-2 py-0.5 rounded text-[10px] bg-slate-200 text-slate-700 font-semibold shrink-0">
                    Due April 2
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* Assets Pending Disposal Approval */}
          <div className="bg-white rounded-xl p-4 md:p-5 shadow-sm border border-slate-200/80">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <span className="material-symbols-outlined text-[#00288e] text-[20px]">
                  delete_sweep
                </span>
                <h3 className="text-[15px] font-bold text-slate-900">Disposal Governance</h3>
              </div>
              <span className="px-2 py-0.5 rounded text-[10px] bg-[#eff4ff] text-[#00288e] font-bold border border-[#d3e4fe]">
                2 Pending Review
              </span>
            </div>

            <div className="space-y-2">
              {/* Disposal 1 */}
              <div
                onClick={() => onSelectAsset('ast-088')}
                className="p-3 bg-[#eff4ff]/60 border border-slate-200/60 rounded-lg cursor-pointer hover:bg-[#eff4ff] transition-colors"
              >
                <div className="flex items-start justify-between mb-1">
                  <div>
                    <span className="font-mono text-[11px] font-bold text-slate-800">AST-000088</span>
                    <div className="text-[13px] font-bold text-slate-900 leading-tight">
                      Ford Ranger Double Cabin (2017)
                    </div>
                  </div>
                  <span className="font-mono text-[12px] text-[#00288e] font-bold">NBV: ₦2.1M</span>
                </div>
                <div className="flex items-center justify-between text-[11px] text-slate-500 pt-1.5 border-t border-slate-200/60">
                  <span>Rec: <strong className="text-slate-800">Auction Sale</strong></span>
                  <span className="text-amber-800 font-bold">Approver: CFO Review</span>
                </div>
              </div>

              {/* Disposal 2 */}
              <div
                onClick={() => onSelectAsset('ast-104')}
                className="p-3 bg-[#eff4ff]/60 border border-slate-200/60 rounded-lg cursor-pointer hover:bg-[#eff4ff] transition-colors"
              >
                <div className="flex items-start justify-between mb-1">
                  <div>
                    <span className="font-mono text-[11px] font-bold text-slate-800">AST-000104</span>
                    <div className="text-[13px] font-bold text-slate-900 leading-tight">
                      HP ProLiant Gen9 Blades (x4)
                    </div>
                  </div>
                  <span className="font-mono text-[12px] text-slate-500 font-medium">
                    NBV: ₦0 (Amortized)
                  </span>
                </div>
                <div className="flex items-center justify-between text-[11px] text-slate-500 pt-1.5 border-t border-slate-200/60">
                  <span>Rec: <strong className="text-slate-800">E-Waste Scrap</strong></span>
                  <span className="text-[#00288e] font-bold">Approver: IT Director</span>
                </div>
              </div>
            </div>

            <div className="mt-3 pt-2">
              <button
                onClick={() => onNavigate('disposals')}
                className="w-full py-2 bg-[#eff4ff] text-[#00288e] hover:bg-[#dce9ff] rounded-lg text-[12px] font-bold transition-colors flex items-center justify-center gap-1"
              >
                <span>Open Executive Disposal Board</span>
                <span className="material-symbols-outlined text-[16px]">arrow_forward</span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
