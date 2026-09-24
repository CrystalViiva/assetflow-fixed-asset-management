/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 * Asset Detail View
 * Faithfully matches the Stitch Asset Detail prototype with 7 tabs, machinery visuals,
 * live telematics, cost buildup, active work order, and documents.
 */

import React, { useState, useEffect } from 'react';
import { Asset, MaintenanceRecord, Transfer, AuditLogEntry, DepreciationScheduleItem } from '../types';
import { assetRepository } from '../services/assetRepository';
import { formatNaira, generateDepreciationSchedule } from '../services/depreciationCalculator';

interface AssetDetailViewProps {
  assetId: string;
  onNavigate: (route: string) => void;
  onTriggerPrintBarcode: (asset: Asset) => void;
  onTriggerTransfer: (asset: Asset) => void;
  onTriggerMaintenance: (asset: Asset) => void;
  onTriggerDisposal: (asset: Asset) => void;
}

export const AssetDetailView: React.FC<AssetDetailViewProps> = ({
  assetId,
  onNavigate,
  onTriggerPrintBarcode,
  onTriggerTransfer,
  onTriggerMaintenance,
  onTriggerDisposal,
}) => {
  const [asset, setAsset] = useState<Asset | null>(null);
  const [activeTab, setActiveTab] = useState<
    'overview' | 'depreciation' | 'assignments' | 'transfers' | 'maintenance' | 'documents' | 'audit'
  >('overview');
  const [transfers, setTransfers] = useState<Transfer[]>([]);
  const [maintenanceRecords, setMaintenanceRecords] = useState<MaintenanceRecord[]>([]);
  const [auditLogs, setAuditLogs] = useState<AuditLogEntry[]>([]);
  const [depSchedule, setDepSchedule] = useState<DepreciationScheduleItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    async function load() {
      setLoading(true);
      try {
        const found = await assetRepository.getAssetById(assetId);
        if (found) {
          setAsset(found);
          const allTransfers = await assetRepository.getTransfers();
          setTransfers(allTransfers.filter(t => t.asset_id === found.id || t.asset_tag === found.tag));

          const allMnt = await assetRepository.getMaintenance();
          setMaintenanceRecords(allMnt.filter(m => m.asset_id === found.id || m.asset_tag === found.tag));

          const allLogs = await assetRepository.getAuditLogs();
          setAuditLogs(allLogs.filter(l => l.entity_id === found.id || l.entity_tag === found.tag));

          const schedule = generateDepreciationSchedule(
            found.total_acquisition_cost,
            found.salvage_value,
            found.useful_life_months,
            found.capitalization_date
          );
          setDepSchedule(schedule);
        }
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [assetId]);

  if (loading || !asset) {
    return (
      <div className="p-12 flex items-center justify-center">
        <div className="flex items-center gap-3 text-slate-500 font-medium">
          <span className="material-symbols-outlined text-[24px] animate-spin text-[#00288e]">
            refresh
          </span>
          <span>Loading asset details for {assetId}...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="w-full p-4 md:p-6 select-text">
      {/* Top Context & Action Bar */}
      <div className="bg-white p-4 md:p-5 rounded-xl shadow-sm border border-slate-200/80 mb-4">
        <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
          <div className="flex items-center gap-1.5 text-[12px] text-slate-500 font-medium">
            <button
              onClick={() => onNavigate('all-assets')}
              className="hover:text-[#00288e] transition-colors flex items-center gap-1 text-slate-700 font-semibold"
            >
              <span className="material-symbols-outlined text-[16px]">arrow_back</span>
              <span>Back to Asset Register</span>
            </button>
            <span className="text-slate-300">/</span>
            <span>Assets</span>
            <span className="text-slate-300">/</span>
            <span>All Assets</span>
            <span className="text-slate-300">/</span>
            <span className="text-[#00288e] font-mono font-bold">{asset.tag}</span>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-[12px] text-slate-600 flex items-center gap-1 mr-2">
              <span className="material-symbols-outlined text-[15px] text-[#00288e]">verified</span>
              IAS 16 Capital Asset Verified
            </span>
            <span className="px-2 py-0.5 rounded bg-[#eff4ff] text-slate-700 font-mono text-[11px] uppercase tracking-wider font-bold border border-slate-200">
              Ledger Code: {asset.ledger_code}
            </span>
          </div>
        </div>

        {/* Title & Primary Control Bar */}
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 pt-1">
          <div className="space-y-1">
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="text-xl md:text-[24px] text-slate-900 font-bold tracking-tight">
                {asset.tag} — {asset.name}
              </h1>

              {/* Status Badge */}
              {asset.status === 'IN_MAINTENANCE' && (
                <div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-amber-50 text-amber-900 border border-amber-200">
                  <span className="w-2 h-2 rounded-full bg-amber-500 animate-pulse"></span>
                  <span className="text-[11px] font-bold tracking-wider uppercase">IN_MAINTENANCE</span>
                </div>
              )}
              {asset.status === 'ACTIVE' && (
                <div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-emerald-50 text-emerald-800 border border-emerald-200">
                  <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
                  <span className="text-[11px] font-bold tracking-wider uppercase">ACTIVE</span>
                </div>
              )}
              {asset.status === 'TRANSFERRED' && (
                <div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-blue-50 text-blue-900 border border-blue-200">
                  <span className="w-2 h-2 rounded-full bg-blue-500"></span>
                  <span className="text-[11px] font-bold tracking-wider uppercase">TRANSFERRED</span>
                </div>
              )}
              {asset.status === 'IMPAIRED' && (
                <div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-rose-50 text-rose-900 border border-rose-200">
                  <span className="w-2 h-2 rounded-full bg-rose-500"></span>
                  <span className="text-[11px] font-bold tracking-wider uppercase">IMPAIRED</span>
                </div>
              )}

              {/* Category Pill */}
              <div className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-[#e5eeff] text-[#00288e] text-[11px] font-semibold">
                <span className="material-symbols-outlined text-[14px]">precision_manufacturing</span>
                <span>{asset.category_name}</span>
              </div>
            </div>

            <p className="text-[12px] text-slate-500 flex flex-wrap items-center gap-2">
              <span>Asset Custody: <strong className="text-slate-700">{asset.location_name}</strong></span>
              <span className="text-slate-300">•</span>
              <span>Asset Tag ID: <span className="font-mono text-slate-700">{asset.tag}</span></span>
              <span className="text-slate-300">•</span>
              <span className="text-emerald-700 font-semibold">
                Insured by {asset.insurance_carrier || 'Leadway Assurance'} (Active)
              </span>
            </p>
          </div>

          {/* Quick Action Buttons */}
          <div className="flex flex-wrap items-center gap-1.5">
            <button
              onClick={() => onTriggerPrintBarcode(asset)}
              className="h-9 px-3 bg-[#eff4ff] hover:bg-slate-200 text-slate-800 text-[12px] font-semibold rounded-lg shadow-2xs flex items-center gap-1.5 transition-colors border border-slate-200/80"
              title="Print physical thermal asset tag"
            >
              <span className="material-symbols-outlined text-[17px] text-slate-600">qr_code_2</span>
              <span>Print QR/Barcode</span>
            </button>

            <button
              onClick={() => onNavigate('asset-create')}
              className="h-9 px-3 bg-[#eff4ff] hover:bg-slate-200 text-slate-800 text-[12px] font-semibold rounded-lg shadow-2xs flex items-center gap-1.5 transition-colors border border-slate-200/80"
            >
              <span className="material-symbols-outlined text-[17px] text-slate-600">edit</span>
              <span>Edit Asset Details</span>
            </button>

            <button
              onClick={() => onTriggerTransfer(asset)}
              className="h-9 px-3 bg-[#eff4ff] hover:bg-slate-200 text-slate-800 text-[12px] font-semibold rounded-lg shadow-2xs flex items-center gap-1.5 transition-colors border border-slate-200/80"
            >
              <span className="material-symbols-outlined text-[17px] text-slate-600">swap_horiz</span>
              <span>Initiate Transfer</span>
            </button>

            <button
              onClick={() => onTriggerMaintenance(asset)}
              className="h-9 px-3.5 bg-[#00288e] text-white text-[12px] font-semibold rounded-lg shadow-xs hover:bg-[#1e40af] flex items-center gap-1.5 transition-colors"
            >
              <span className="material-symbols-outlined text-[17px]">build</span>
              <span>Log Maintenance</span>
            </button>

            <button
              onClick={() => onTriggerDisposal(asset)}
              className="h-9 px-3 bg-rose-50 text-rose-800 hover:bg-rose-100 text-[12px] font-semibold rounded-lg border border-rose-200 flex items-center gap-1.5 transition-colors"
            >
              <span className="material-symbols-outlined text-[17px]">delete_forever</span>
              <span>Dispose / Write-Off</span>
            </button>
          </div>
        </div>
      </div>

      {/* Top Financial & Lifecycle KPI Summary Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-4">
        {/* Card 1: Acquisition Cost */}
        <div className="bg-white p-4 rounded-xl shadow-sm border border-slate-200/80 relative overflow-hidden flex flex-col justify-between">
          <div className="flex items-center justify-between mb-1">
            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">
              Acquisition Cost
            </span>
            <div className="w-7 h-7 rounded bg-[#eff4ff] flex items-center justify-center text-[#00288e]">
              <span className="material-symbols-outlined text-[18px]">payments</span>
            </div>
          </div>
          <div>
            <div className="text-[22px] font-bold text-slate-900 tracking-tight font-mono">
              {formatNaira(asset.total_acquisition_cost)}
            </div>
            <div className="mt-1 flex items-center justify-between text-[11px] text-slate-500">
              <span>Capitalized: {asset.capitalization_date}</span>
              <span className="px-1.5 py-0.5 rounded bg-[#eff4ff] text-[#00288e] font-bold">Historical</span>
            </div>
          </div>
          <div className="mt-2.5 h-1.5 w-full bg-slate-100 rounded-full overflow-hidden">
            <div className="h-full bg-[#00288e] rounded-full w-full"></div>
          </div>
        </div>

        {/* Card 2: Current Net Book Value */}
        <div className="bg-white p-4 rounded-xl shadow-sm border border-slate-200/80 relative overflow-hidden flex flex-col justify-between">
          <div className="flex items-center justify-between mb-1">
            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">
              Current Net Book Value
            </span>
            <div className="w-7 h-7 rounded bg-emerald-50 text-emerald-700 flex items-center justify-center">
              <span className="material-symbols-outlined text-[18px]">account_balance_wallet</span>
            </div>
          </div>
          <div>
            <div className="text-[22px] font-bold text-emerald-800 tracking-tight font-mono">
              {formatNaira(asset.net_book_value)}
            </div>
            <div className="mt-1 flex items-center justify-between text-[11px] text-slate-500">
              <span>Carrying Rate: <strong className="text-slate-900">{asset.carrying_rate_pct}%</strong></span>
              <span className="text-emerald-700 font-bold">
                {formatNaira(asset.accumulated_depreciation)} Written Down
              </span>
            </div>
          </div>
          <div className="mt-2.5 h-1.5 w-full bg-slate-100 rounded-full overflow-hidden">
            <div
              className="h-full bg-emerald-600 rounded-full transition-all duration-500"
              style={{ width: `${asset.carrying_rate_pct}%` }}
            ></div>
          </div>
        </div>

        {/* Card 3: Accumulated Depreciation */}
        <div className="bg-white p-4 rounded-xl shadow-sm border border-slate-200/80 relative overflow-hidden flex flex-col justify-between">
          <div className="flex items-center justify-between mb-1">
            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">
              Accumulated Depreciation
            </span>
            <div className="w-7 h-7 rounded bg-amber-50 text-amber-800 flex items-center justify-center">
              <span className="material-symbols-outlined text-[18px]">trending_down</span>
            </div>
          </div>
          <div>
            <div className="text-[22px] font-bold text-slate-900 tracking-tight font-mono">
              {formatNaira(asset.accumulated_depreciation)}
            </div>
            <div className="mt-1 flex items-center justify-between text-[11px] text-slate-500">
              <span>Straight-Line • {asset.useful_life_years} Yrs</span>
              <span className="font-semibold text-slate-700">
                {(asset.accumulated_depreciation / (asset.annual_depreciation || 1)).toFixed(2)} Yrs Expired
              </span>
            </div>
          </div>
          <div className="mt-2.5 h-1.5 w-full bg-slate-100 rounded-full overflow-hidden">
            <div
              className="h-full bg-amber-500 rounded-full transition-all duration-500"
              style={{ width: `${100 - asset.carrying_rate_pct}%` }}
            ></div>
          </div>
        </div>

        {/* Card 4: Salvage / Residual Value */}
        <div className="bg-white p-4 rounded-xl shadow-sm border border-slate-200/80 relative overflow-hidden flex flex-col justify-between">
          <div className="flex items-center justify-between mb-1">
            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">
              Salvage / Residual Value
            </span>
            <div className="w-7 h-7 rounded bg-[#eff4ff] text-slate-700 flex items-center justify-center">
              <span className="material-symbols-outlined text-[18px]">price_check</span>
            </div>
          </div>
          <div>
            <div className="text-[22px] font-bold text-slate-900 tracking-tight font-mono">
              {formatNaira(asset.salvage_value)}
            </div>
            <div className="mt-1 flex items-center justify-between text-[11px] text-slate-500">
              <span>Floor Limit: {asset.residual_rate_pct}% Residual</span>
              <span className="text-slate-800 font-bold">IAS 16 Bound</span>
            </div>
          </div>
          <div className="mt-2.5 h-1.5 w-full bg-slate-100 rounded-full overflow-hidden">
            <div
              className="h-full bg-slate-600 rounded-full"
              style={{ width: `${asset.residual_rate_pct}%` }}
            ></div>
          </div>
        </div>
      </div>

      {/* Navigation Tabs Bar */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200/80 px-4 pt-1 mb-4 overflow-x-auto">
        <nav className="flex items-center space-x-2 min-w-max text-[13px]">
          <button
            onClick={() => setActiveTab('overview')}
            className={`flex items-center gap-2 px-3.5 py-2.5 font-bold border-b-2 transition-colors ${
              activeTab === 'overview'
                ? 'text-[#00288e] border-[#00288e]'
                : 'text-slate-500 border-transparent hover:text-slate-800'
            }`}
          >
            <span className="material-symbols-outlined text-[18px]">dashboard</span>
            <span>Overview</span>
          </button>

          <button
            onClick={() => setActiveTab('depreciation')}
            className={`flex items-center gap-2 px-3.5 py-2.5 font-bold border-b-2 transition-colors ${
              activeTab === 'depreciation'
                ? 'text-[#00288e] border-[#00288e]'
                : 'text-slate-500 border-transparent hover:text-slate-800'
            }`}
          >
            <span className="material-symbols-outlined text-[18px]">calendar_month</span>
            <span>Depreciation Schedule</span>
            <span className="px-1.5 py-0.2 rounded text-[10px] bg-[#eff4ff] text-[#00288e] font-bold">
              {asset.useful_life_months} mos
            </span>
          </button>

          <button
            onClick={() => setActiveTab('assignments')}
            className={`flex items-center gap-2 px-3.5 py-2.5 font-bold border-b-2 transition-colors ${
              activeTab === 'assignments'
                ? 'text-[#00288e] border-[#00288e]'
                : 'text-slate-500 border-transparent hover:text-slate-800'
            }`}
          >
            <span className="material-symbols-outlined text-[18px]">badge</span>
            <span>Assignments & Custody</span>
          </button>

          <button
            onClick={() => setActiveTab('transfers')}
            className={`flex items-center gap-2 px-3.5 py-2.5 font-bold border-b-2 transition-colors ${
              activeTab === 'transfers'
                ? 'text-[#00288e] border-[#00288e]'
                : 'text-slate-500 border-transparent hover:text-slate-800'
            }`}
          >
            <span className="material-symbols-outlined text-[18px]">local_shipping</span>
            <span>Transfers History</span>
            <span className="px-1.5 py-0.2 rounded text-[10px] bg-[#eff4ff] text-[#00288e] font-bold">
              {transfers.length}
            </span>
          </button>

          <button
            onClick={() => setActiveTab('maintenance')}
            className={`flex items-center gap-2 px-3.5 py-2.5 font-bold border-b-2 transition-colors ${
              activeTab === 'maintenance'
                ? 'text-[#00288e] border-[#00288e]'
                : 'text-slate-500 border-transparent hover:text-slate-800'
            }`}
          >
            <span className="material-symbols-outlined text-[18px]">construction</span>
            <span>Maintenance Log</span>
            <span className="px-1.5 py-0.2 rounded text-[10px] bg-amber-100 text-amber-900 font-bold">
              {maintenanceRecords.length}
            </span>
          </button>

          <button
            onClick={() => setActiveTab('documents')}
            className={`flex items-center gap-2 px-3.5 py-2.5 font-bold border-b-2 transition-colors ${
              activeTab === 'documents'
                ? 'text-[#00288e] border-[#00288e]'
                : 'text-slate-500 border-transparent hover:text-slate-800'
            }`}
          >
            <span className="material-symbols-outlined text-[18px]">folder</span>
            <span>Documents & Warranties</span>
            <span className="px-1.5 py-0.2 rounded text-[10px] bg-[#eff4ff] text-[#00288e] font-bold">
              {asset.documents?.length || 4}
            </span>
          </button>

          <button
            onClick={() => setActiveTab('audit')}
            className={`flex items-center gap-2 px-3.5 py-2.5 font-bold border-b-2 transition-colors ${
              activeTab === 'audit'
                ? 'text-[#00288e] border-[#00288e]'
                : 'text-slate-500 border-transparent hover:text-slate-800'
            }`}
          >
            <span className="material-symbols-outlined text-[18px]">history</span>
            <span>Audit Trail</span>
            <span className="w-2 h-2 rounded-full bg-emerald-600"></span>
          </button>
        </nav>
      </div>

      {/* TAB CONTENT: Overview Tab */}
      {activeTab === 'overview' && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 items-start">
          {/* LEFT COLUMN: 7 Cols */}
          <div className="lg:col-span-7 space-y-4">
            {/* Machinery Showcase with Telematics */}
            <div className="bg-white rounded-xl shadow-sm border border-slate-200/80 overflow-hidden">
              <div className="relative h-60 w-full overflow-hidden bg-slate-900">
                <img
                  className="w-full h-full object-cover"
                  src={asset.image_url}
                  alt={asset.name}
                />
                <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-transparent to-black/30"></div>

                <div className="absolute top-3 left-3 flex flex-wrap items-center gap-2">
                  <span className="px-2.5 py-1 rounded bg-black/70 backdrop-blur-sm text-white text-[11px] font-bold uppercase tracking-wider flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
                    GPS Telematics Online
                  </span>
                  <span className="px-2.5 py-1 rounded bg-black/60 backdrop-blur-sm text-white text-[11px]">
                    {asset.location_name} Geo-Fence: Locked
                  </span>
                </div>

                <div className="absolute bottom-3 right-3 bg-white/95 backdrop-blur-sm px-3.5 py-1.5 rounded-lg shadow-lg flex items-center gap-3">
                  <div className="flex items-center gap-1.5 text-slate-900">
                    <span className="material-symbols-outlined text-[18px] text-[#00288e]">speed</span>
                    <span className="text-[16px] font-bold font-mono">
                      {(asset.operating_hours || 3420).toLocaleString('en-NG')}
                    </span>
                    <span className="text-[12px] text-slate-500">Hours</span>
                  </div>
                  <div className="h-4 w-px bg-slate-300"></div>
                  <div className="flex items-center gap-1 text-emerald-800">
                    <span className="material-symbols-outlined text-[18px]">battery_full</span>
                    <span className="text-[13px] font-bold">{asset.voltage || '24.2V'}</span>
                  </div>
                </div>
              </div>

              <div className="p-3.5 bg-[#eff4ff] flex flex-wrap items-center justify-between gap-2 text-[12px]">
                <div className="flex items-center gap-2">
                  <span className="text-slate-600 font-medium">Asset Health Index:</span>
                  <div className="flex items-center gap-1">
                    <div className="w-3 h-3 rounded-sm bg-emerald-600"></div>
                    <div className="w-3 h-3 rounded-sm bg-emerald-600"></div>
                    <div className="w-3 h-3 rounded-sm bg-emerald-600"></div>
                    <div className="w-3 h-3 rounded-sm bg-amber-500"></div>
                    <div className="w-3 h-3 rounded-sm bg-slate-300"></div>
                  </div>
                  <span className="font-bold text-slate-900">
                    {asset.health_score || 78}/100 ({asset.status === 'IN_MAINTENANCE' ? 'Service Required' : 'Optimal'})
                  </span>
                </div>
                <div className="text-slate-600">
                  Next Inspection: <strong className="text-slate-900 font-bold">{asset.next_inspection_hours || 3500} Hrs (in 80h)</strong>
                </div>
              </div>
            </div>

            {/* Specifications & Identifiers Card */}
            <div className="bg-white rounded-xl shadow-sm border border-slate-200/80 p-5">
              <div className="flex items-center justify-between pb-3 mb-3 border-b border-slate-100">
                <div className="flex items-center gap-2">
                  <div className="w-8 h-8 rounded-lg bg-[#eff4ff] flex items-center justify-center text-[#00288e]">
                    <span className="material-symbols-outlined text-[20px]">engineering</span>
                  </div>
                  <h2 className="text-[16px] font-bold text-slate-900">
                    Asset Specifications & Identifiers
                  </h2>
                </div>
                <span className="font-mono text-[11px] text-slate-500 font-bold">
                  TAG #{asset.tag}
                </span>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-y-3 gap-x-6 text-[13px]">
                <div className="flex justify-between items-baseline py-1 border-b border-slate-100">
                  <span className="text-slate-500">Manufacturer</span>
                  <span className="font-semibold text-slate-900">{asset.manufacturer}</span>
                </div>
                <div className="flex justify-between items-baseline py-1 border-b border-slate-100">
                  <span className="text-slate-500">Model</span>
                  <span className="font-semibold text-slate-900">{asset.model}</span>
                </div>
                <div className="flex justify-between items-baseline py-1 border-b border-slate-100">
                  <span className="text-slate-500">Serial Number</span>
                  <span className="font-mono font-bold text-[#00288e] select-all">
                    {asset.serial_number}
                  </span>
                </div>
                <div className="flex justify-between items-baseline py-1 border-b border-slate-100">
                  <span className="text-slate-500">Engine / Power Model</span>
                  <span className="text-slate-900 font-medium">{asset.engine_model || 'Standard Engine'}</span>
                </div>
                <div className="flex justify-between items-baseline py-1 border-b border-slate-100">
                  <span className="text-slate-500">Year of Manufacture</span>
                  <span className="text-slate-900 font-medium">{asset.year_of_manufacture || 2022}</span>
                </div>
                <div className="flex justify-between items-baseline py-1 border-b border-slate-100">
                  <span className="text-slate-500">Net Power / Output</span>
                  <span className="text-slate-900 font-medium">{asset.net_power || 'N/A'}</span>
                </div>
                <div className="flex justify-between items-baseline py-1 border-b border-slate-100">
                  <span className="text-slate-500">Operating Weight</span>
                  <span className="text-slate-900 font-medium">{asset.operating_weight || '37,200 kg'}</span>
                </div>
                <div className="flex justify-between items-baseline py-1 border-b border-slate-100">
                  <span className="text-slate-500">Operating Meter / Hours</span>
                  <span className="font-bold text-amber-800">
                    {(asset.operating_hours || 3420).toLocaleString('en-NG')} Service Hours
                  </span>
                </div>
              </div>

              {/* Barcode & Thermal Tag Integration Preview */}
              <div className="mt-4 p-3.5 bg-[#eff4ff] rounded-lg border border-slate-200/80 flex flex-col sm:flex-row items-center justify-between gap-4">
                <div className="flex items-center gap-3">
                  <div className="bg-white p-2 rounded shadow-2xs flex flex-col items-center border border-slate-200">
                    {/* Simulated SVG Barcode */}
                    <svg className="h-8 w-40" viewBox="0 0 200 40" fill="currentColor">
                      <rect x="0" y="0" width="3" height="35" />
                      <rect x="5" y="0" width="1" height="35" />
                      <rect x="8" y="0" width="4" height="35" />
                      <rect x="15" y="0" width="2" height="35" />
                      <rect x="20" y="0" width="3" height="35" />
                      <rect x="26" y="0" width="1" height="35" />
                      <rect x="30" y="0" width="5" height="35" />
                      <rect x="38" y="0" width="2" height="35" />
                      <rect x="43" y="0" width="3" height="35" />
                      <rect x="48" y="0" width="1" height="35" />
                      <rect x="52" y="0" width="4" height="35" />
                      <rect x="58" y="0" width="2" height="35" />
                      <rect x="63" y="0" width="3" height="35" />
                      <rect x="68" y="0" width="2" height="35" />
                      <rect x="73" y="0" width="4" height="35" />
                      <rect x="80" y="0" width="1" height="35" />
                      <rect x="84" y="0" width="3" height="35" />
                      <rect x="90" y="0" width="2" height="35" />
                      <rect x="95" y="0" width="4" height="35" />
                      <rect x="102" y="0" width="2" height="35" />
                      <rect x="108" y="0" width="3" height="35" />
                      <rect x="114" y="0" width="1" height="35" />
                      <rect x="118" y="0" width="4" height="35" />
                      <rect x="125" y="0" width="2" height="35" />
                      <rect x="130" y="0" width="3" height="35" />
                      <rect x="136" y="0" width="1" height="35" />
                      <rect x="140" y="0" width="5" height="35" />
                      <rect x="148" y="0" width="2" height="35" />
                      <rect x="153" y="0" width="3" height="35" />
                      <rect x="158" y="0" width="1" height="35" />
                      <rect x="162" y="0" width="4" height="35" />
                      <rect x="170" y="0" width="2" height="35" />
                      <rect x="175" y="0" width="3" height="35" />
                      <rect x="180" y="0" width="2" height="35" />
                      <rect x="185" y="0" width="4" height="35" />
                      <rect x="192" y="0" width="2" height="35" />
                      <rect x="197" y="0" width="3" height="35" />
                    </svg>
                    <span className="text-[10px] font-mono tracking-widest text-slate-800 font-bold mt-1">
                      {asset.tag}-NG
                    </span>
                  </div>

                  <div className="w-12 h-12 bg-white p-1 rounded shadow-2xs flex items-center justify-center border border-slate-200">
                    <span className="material-symbols-outlined text-[36px] text-slate-900">qr_code_2</span>
                  </div>
                </div>

                <div className="text-left sm:text-right">
                  <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500 block">
                    Thermal Tag Status
                  </span>
                  <span className="text-[12px] font-bold text-emerald-700 flex items-center sm:justify-end gap-1 mt-0.5">
                    <span className="material-symbols-outlined text-[16px]">check_circle</span>
                    Physical RFID Tag Active
                  </span>
                  <span className="text-[11px] text-slate-500 block mt-0.5">
                    Scanned during Q4 Fixed Asset Audit
                  </span>
                </div>
              </div>
            </div>

            {/* Acquisition & Financial Metadata Card */}
            <div className="bg-white rounded-xl shadow-sm border border-slate-200/80 p-5">
              <div className="flex items-center justify-between pb-3 mb-3 border-b border-slate-100">
                <div className="flex items-center gap-2">
                  <div className="w-8 h-8 rounded-lg bg-[#eff4ff] flex items-center justify-center text-[#00288e]">
                    <span className="material-symbols-outlined text-[20px]">account_balance</span>
                  </div>
                  <h2 className="text-[16px] font-bold text-slate-900">
                    Acquisition & Financial Metadata
                  </h2>
                </div>
                <span className="text-[11px] px-2 py-0.5 rounded bg-[#eff4ff] text-[#00288e] font-bold">
                  CAPEX Ledger
                </span>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-y-3 gap-x-6 text-[13px]">
                <div className="flex justify-between items-baseline py-1 border-b border-slate-100">
                  <span className="text-slate-500">Vendor / Authorized Dealer</span>
                  <span className="font-semibold text-slate-900">{asset.vendor}</span>
                </div>
                <div className="flex justify-between items-baseline py-1 border-b border-slate-100">
                  <span className="text-slate-500">Purchase Order Ref</span>
                  <span className="font-mono text-[#00288e] font-semibold">{asset.purchase_order_ref}</span>
                </div>
                <div className="flex justify-between items-baseline py-1 border-b border-slate-100">
                  <span className="text-slate-500">Commercial Invoice Ref</span>
                  <span className="font-mono text-slate-800">{asset.commercial_invoice_ref}</span>
                </div>
                <div className="flex justify-between items-baseline py-1 border-b border-slate-100">
                  <span className="text-slate-500">Acquisition Date</span>
                  <span className="text-slate-900">{asset.acquisition_date}</span>
                </div>
                <div className="flex justify-between items-baseline py-1 border-b border-slate-100">
                  <span className="text-slate-500">Capitalization Date</span>
                  <span className="text-slate-900 font-semibold">{asset.capitalization_date}</span>
                </div>
                <div className="flex justify-between items-baseline py-1 border-b border-slate-100">
                  <span className="text-slate-500">Depreciation Method</span>
                  <span className="text-slate-900">Straight Line Method (IAS 16)</span>
                </div>
                <div className="flex justify-between items-baseline py-1 border-b border-slate-100">
                  <span className="text-slate-500">Useful Lifespan</span>
                  <span className="text-slate-900">{asset.useful_life_years} Years ({asset.useful_life_months} Periods)</span>
                </div>
                <div className="flex justify-between items-baseline py-1 border-b border-slate-100">
                  <span className="text-slate-500">Annual Depreciation</span>
                  <span className="font-mono font-bold text-slate-900">
                    {formatNaira(asset.annual_depreciation)} / yr
                  </span>
                </div>
              </div>

              {/* Capitalized Cost Breakdown Table */}
              <div className="mt-4">
                <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400 mb-2">
                  Capitalized Cost Buildup Breakdown
                </div>
                <div className="overflow-x-auto rounded-lg border border-slate-200">
                  <table className="w-full text-left text-[12px]">
                    <thead>
                      <tr className="bg-[#eff4ff] text-slate-600 font-bold uppercase text-[10px] tracking-wider border-b border-slate-200">
                        <th className="py-2 px-3">Cost Component</th>
                        <th className="py-2 px-3">Source Reference</th>
                        <th className="py-2 px-3 text-right">Amount (NGN)</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      <tr>
                        <td className="py-2 px-3 font-semibold text-slate-800">Base Purchase Price</td>
                        <td className="py-2 px-3 text-slate-500 font-mono text-[11px]">{asset.commercial_invoice_ref}</td>
                        <td className="py-2 px-3 text-right font-mono font-semibold text-slate-900">
                          {formatNaira(asset.cost_components?.base_purchase || asset.total_acquisition_cost * 0.9)}
                        </td>
                      </tr>
                      <tr>
                        <td className="py-2 px-3 font-semibold text-slate-800">Freight & Inland Heavy Haulage</td>
                        <td className="py-2 px-3 text-slate-500 font-mono text-[11px]">WAYBILL-HAUL-902</td>
                        <td className="py-2 px-3 text-right font-mono font-semibold text-slate-900">
                          {formatNaira(asset.cost_components?.freight || asset.total_acquisition_cost * 0.06)}
                        </td>
                      </tr>
                      <tr>
                        <td className="py-2 px-3 font-semibold text-slate-800">Pre-commissioning, Assembly & Testing</td>
                        <td className="py-2 px-3 text-slate-500 font-mono text-[11px]">COMM-MANT-441</td>
                        <td className="py-2 px-3 text-right font-mono font-semibold text-slate-900">
                          {formatNaira(asset.cost_components?.installation || asset.total_acquisition_cost * 0.04)}
                        </td>
                      </tr>
                      <tr className="bg-[#eff4ff] font-bold text-slate-900 border-t border-slate-200">
                        <td className="py-2.5 px-3" colSpan={2}>Total Capitalized Asset Cost (Gross Balance)</td>
                        <td className="py-2.5 px-3 text-right font-mono font-bold text-[#00288e] text-[14px]">
                          {formatNaira(asset.total_acquisition_cost)}
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          </div>

          {/* RIGHT COLUMN: 5 Cols */}
          <div className="lg:col-span-5 space-y-4">
            {/* Custody Card */}
            <div className="bg-white rounded-xl shadow-sm border border-slate-200/80 p-5">
              <div className="flex items-center justify-between pb-3 mb-3 border-b border-slate-100">
                <div className="flex items-center gap-2">
                  <div className="w-8 h-8 rounded-lg bg-[#eff4ff] flex items-center justify-center text-[#00288e]">
                    <span className="material-symbols-outlined text-[20px]">person_pin_circle</span>
                  </div>
                  <h2 className="text-[16px] font-bold text-slate-900">Current Custody & Assignment</h2>
                </div>
                <span className="material-symbols-outlined text-[18px] text-emerald-600">verified_user</span>
              </div>

              <div className="space-y-3 text-[13px]">
                <div className="p-3 rounded-lg bg-[#eff4ff] border border-slate-200/80 flex items-start gap-3">
                  <img
                    alt={asset.custodian_name}
                    className="w-11 h-11 rounded-full object-cover mt-0.5 ring-1 ring-slate-300"
                    src="https://lh3.googleusercontent.com/aida-public/AB6AXuAQjfBsnhUaJsODwEIF9c0JR_abXkekvgOcDVi5SDEn9XwB2QLLVFL0I1mqW9ENZWMpBgmArkeKu5892aDBQ0yigfitDIhl9sqzrnljzIYp_0HXvxK7VK6ASuCN_XIy6kJYGz9kr8GcG810_r_gs-X88MTihb5Xc-ZVfmZ07aEHzm7G1sewQIAapXSeztpsj10RgiJMkHqoR5_q8ysDR0QiTJRFPX9t9WrYg57P33GZz-83I6HU8x-cTw"
                  />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] uppercase font-bold text-slate-500">Current Custodian</span>
                      <span className="text-[10px] px-1.5 py-0.2 rounded bg-emerald-100 text-emerald-800 font-bold">
                        Signed Ack
                      </span>
                    </div>
                    <p className="text-[14px] font-bold text-slate-900 truncate mt-0.5">
                      {asset.custodian_name}
                    </p>
                    <p className="text-[11px] text-slate-500 truncate">
                      {asset.custodian_title} • Staff ID: {asset.custodian_staff_id}
                    </p>
                  </div>
                </div>

                <div className="space-y-2 pt-1 text-[13px]">
                  <div className="flex justify-between items-center py-1 border-b border-slate-100">
                    <span className="text-slate-500">Department</span>
                    <span className="font-semibold text-slate-900">{asset.department_name}</span>
                  </div>
                  <div className="flex justify-between items-center py-1 border-b border-slate-100">
                    <span className="text-slate-500">Department Head</span>
                    <span className="font-semibold text-slate-900">{asset.department_head}</span>
                  </div>
                  <div className="flex justify-between items-center py-1 border-b border-slate-100">
                    <span className="text-slate-500">Physical Location</span>
                    <span className="font-semibold text-slate-900">{asset.location_name}</span>
                  </div>
                  <div className="flex justify-between items-center py-1 border-b border-slate-100">
                    <span className="text-slate-500">Exact Sub-Location</span>
                    <span className="font-bold text-[#00288e]">{asset.sub_location}</span>
                  </div>
                  <div className="flex justify-between items-center py-1">
                    <span className="text-slate-500">Custody Handover Date</span>
                    <span className="text-slate-900">{asset.custody_handover_date}</span>
                  </div>
                </div>

                {/* Staging Map Snapshot */}
                <div className="mt-2 rounded-lg overflow-hidden border border-slate-200 relative">
                  <div
                    className="w-full h-28 bg-cover bg-center"
                    style={{
                      backgroundImage: `url('https://lh3.googleusercontent.com/aida-public/AB6AXuCnNRvGudeKdgDym3513giixGNmj2DU2YMi1a6bae5fgO7B84GU2a_FZMNz-rNIwn5OC9HUtYtqlnN9_SptEX4zhy2u1BLOURL2vKYPnSjBtawzkJcvh3_Rk_3K3FBQEl56GxN-nbxHuMDDOYPEwLz_wtjx0qMf_edR_O0M5-DX7j4IeYzrUOAFdHUKTA8i4pSXomvu9J0oZliBWRJRmaFXhwd3r-4iwfAlId3p85A7aCrranlwPMGxtg')`,
                    }}
                  ></div>
                  <div className="absolute bottom-2 left-2 right-2 bg-white/95 backdrop-blur-xs p-1.5 px-2.5 rounded text-[11px] flex items-center justify-between shadow-xs">
                    <span className="font-semibold text-slate-800">
                      Depot GPS: {asset.coordinates || '5.5160° N, 5.7500° E'}
                    </span>
                    <span className="text-[#00288e] font-bold hover:underline cursor-pointer">
                      View Coordinates
                    </span>
                  </div>
                </div>
              </div>
            </div>

            {/* Active Work Order Card */}
            <div className="bg-white rounded-xl shadow-sm border border-slate-200/80 p-5">
              <div className="flex items-center justify-between pb-3 mb-3 border-b border-slate-100">
                <div className="flex items-center gap-2">
                  <div className="w-8 h-8 rounded-lg bg-amber-50 text-amber-800 flex items-center justify-center">
                    <span className="material-symbols-outlined text-[20px]">build_circle</span>
                  </div>
                  <div>
                    <h2 className="text-[16px] font-bold text-slate-900">Active Work Order</h2>
                    <span className="font-mono text-[11px] text-[#00288e] font-bold">#WO-2025-089</span>
                  </div>
                </div>
                <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-amber-100 text-amber-900 uppercase">
                  In Progress
                </span>
              </div>

              {/* Overdue Alert Ribbon */}
              <div className="p-3 rounded-lg bg-red-50 border border-red-200/80 text-red-900 flex items-center gap-2.5 mb-3">
                <span className="material-symbols-outlined text-[22px] text-red-600 shrink-0">warning</span>
                <div className="text-[12px] leading-tight">
                  <strong className="font-bold">Attention: Service Overdue by 2 Days</strong>
                  <div className="text-[11px] text-red-700 mt-0.5">
                    Planned target was March 28, 2025. Pending OEM hydraulic seal clearance.
                  </div>
                </div>
              </div>

              <div className="space-y-2 text-[13px]">
                <div className="flex justify-between items-center py-1 border-b border-slate-100">
                  <span className="text-slate-500">Maintenance Scope</span>
                  <span className="font-semibold text-slate-900">Preventive & Hydraulic Overhaul</span>
                </div>
                <div className="flex justify-between items-center py-1 border-b border-slate-100">
                  <span className="text-slate-500">Assigned Contractor</span>
                  <span className="font-semibold text-slate-900">Mantrac Certified Field Services</span>
                </div>
                <div className="flex justify-between items-center py-1 border-b border-slate-100">
                  <span className="text-slate-500">Revised Est. Completion</span>
                  <span className="font-bold text-amber-900">March 30, 2025 (Expected)</span>
                </div>
                <div className="flex justify-between items-center py-1 border-b border-slate-100">
                  <span className="text-slate-500">Approved Budget</span>
                  <span className="font-mono font-bold text-slate-900">₦4,850,000</span>
                </div>
                <div className="pt-1">
                  <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 block mb-1">
                    Detailed Work Scope
                  </span>
                  <p className="text-[12px] text-slate-700 bg-[#eff4ff] p-2.5 rounded-lg leading-relaxed border border-slate-200/60">
                    High-pressure hydraulic seal replacement on main boom cylinders, complete hydraulic system oil flush (Cat HYDO Advanced 10), and electronic track tensioner recalibration.
                  </p>
                </div>
              </div>

              <div className="mt-3 pt-2 flex items-center justify-end gap-2">
                <button
                  onClick={() => onTriggerMaintenance(asset)}
                  className="px-3 py-1.5 rounded-lg bg-[#eff4ff] hover:bg-slate-200 text-slate-800 text-[12px] font-semibold transition-colors"
                >
                  View Job Sheet
                </button>
                <button
                  onClick={() => onTriggerMaintenance(asset)}
                  className="px-3 py-1.5 rounded-lg bg-[#00288e] text-white text-[12px] font-semibold hover:bg-[#1e40af] transition-colors"
                >
                  Update Progress
                </button>
              </div>
            </div>

            {/* Attached Documents & Warranties Card */}
            <div className="bg-white rounded-xl shadow-sm border border-slate-200/80 p-5">
              <div className="flex items-center justify-between pb-3 mb-3 border-b border-slate-100">
                <div className="flex items-center gap-2">
                  <div className="w-8 h-8 rounded-lg bg-[#eff4ff] flex items-center justify-center text-[#00288e]">
                    <span className="material-symbols-outlined text-[20px]">attachment</span>
                  </div>
                  <h2 className="text-[16px] font-bold text-slate-900">Documents & Warranties</h2>
                </div>
                <span className="text-[11px] text-slate-500 font-bold">4 Critical Files</span>
              </div>

              <div className="space-y-2">
                {[
                  { name: 'OEM Warranty Certificate (Cat Standard)', sub: 'Valid through Jun 2025 • 2.4 MB' },
                  { name: 'Mantrac Purchase Invoice & Bill of Lading', sub: 'Signed & Stamped • 5.1 MB' },
                  { name: 'Physical Verification & Tagging Signoff', sub: 'Internal Audit Lagos HQ • 1.8 MB' },
                  { name: 'Comprehensive Insurance Policy Certificate', sub: 'Policy #PLA-882910 • Active' },
                ].map((doc, idx) => (
                  <div
                    key={idx}
                    className="p-2.5 rounded-lg bg-[#eff4ff]/60 hover:bg-[#eff4ff] border border-slate-200/60 flex items-center justify-between transition-colors"
                  >
                    <div className="flex items-center gap-2.5 min-w-0">
                      <div className="w-8 h-8 rounded bg-red-100 text-red-700 flex items-center justify-center font-bold text-[10px] shrink-0">
                        PDF
                      </div>
                      <div className="min-w-0">
                        <p className="text-[12px] font-bold text-slate-900 truncate">{doc.name}</p>
                        <p className="text-[10px] text-slate-500">{doc.sub}</p>
                      </div>
                    </div>
                    <button
                      onClick={() => alert(`Downloading ${doc.name}`)}
                      className="p-1.5 text-slate-500 hover:text-[#00288e] transition-colors"
                      title="Download File"
                    >
                      <span className="material-symbols-outlined text-[18px]">download</span>
                    </button>
                  </div>
                ))}
              </div>

              <button
                onClick={() => alert('File uploader opened: Select PDF or Certificate to attach to this asset.')}
                className="w-full mt-3 py-2 rounded-lg bg-[#eff4ff] hover:bg-[#dce9ff] text-[#00288e] text-[12px] font-bold transition-colors flex items-center justify-center gap-1.5"
              >
                <span className="material-symbols-outlined text-[16px]">upload_file</span>
                <span>Attach New Governance Document</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* TAB CONTENT: Depreciation Schedule Tab */}
      {activeTab === 'depreciation' && (
        <div className="bg-white rounded-xl shadow-sm border border-slate-200/80 p-5 space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-slate-100">
            <div>
              <h2 className="text-[16px] font-bold text-slate-900">
                Straight-Line Amortization Schedule (IAS 16)
              </h2>
              <p className="text-[12px] text-slate-500">
                Useful life: {asset.useful_life_years} years ({asset.useful_life_months} periods) • Monthly Amortization: {formatNaira(asset.monthly_depreciation)}
              </p>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-[12px] font-semibold text-slate-600">Residual Value Floor:</span>
              <span className="font-mono font-bold text-[#00288e]">{formatNaira(asset.salvage_value)}</span>
            </div>
          </div>

          <div className="overflow-x-auto max-h-[520px]">
            <table className="w-full text-left text-[12px]">
              <thead className="sticky top-0 bg-[#eff4ff] text-slate-700 font-bold uppercase text-[10px] tracking-wider border-b border-slate-200">
                <tr>
                  <th className="py-2.5 px-3">Period #</th>
                  <th className="py-2.5 px-3">Posting Month</th>
                  <th className="py-2.5 px-3 text-right">Opening Book Value (₦)</th>
                  <th className="py-2.5 px-3 text-right">Monthly Expense (₦)</th>
                  <th className="py-2.5 px-3 text-right">Accumulated Deprec (₦)</th>
                  <th className="py-2.5 px-3 text-right">Closing Book Value (₦)</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 font-mono">
                {depSchedule.slice(0, 48).map(item => (
                  <tr key={item.period_index} className="hover:bg-slate-50">
                    <td className="py-2 px-3 font-semibold text-slate-500">{item.period_index}</td>
                    <td className="py-2 px-3 font-sans font-medium text-slate-800">{item.period_label}</td>
                    <td className="py-2 px-3 text-right text-slate-600">{formatNaira(item.opening_book_value)}</td>
                    <td className="py-2 px-3 text-right text-amber-700 font-semibold">{formatNaira(item.depreciation_expense)}</td>
                    <td className="py-2 px-3 text-right text-slate-600">{formatNaira(item.accumulated_depreciation)}</td>
                    <td className="py-2 px-3 text-right font-bold text-[#00288e]">{formatNaira(item.closing_book_value)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="text-[11px] text-slate-500 italic">
            Showing first 48 of {asset.useful_life_months} amortization periods. Schedule dynamically recalculates upon capitalization updates.
          </div>
        </div>
      )}

      {/* TAB CONTENT: Transfers History Tab */}
      {activeTab === 'transfers' && (
        <div className="bg-white rounded-xl shadow-sm border border-slate-200/80 p-5 space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-slate-100">
            <div>
              <h2 className="text-[16px] font-bold text-slate-900">Inter-Facility Movement History</h2>
              <p className="text-[12px] text-slate-500">Immutable audit log of all physical relocations and waybill manifests</p>
            </div>
            <button
              onClick={() => onTriggerTransfer(asset)}
              className="h-8 px-3 bg-[#00288e] text-white rounded text-[12px] font-semibold hover:bg-[#1e40af] flex items-center gap-1"
            >
              <span className="material-symbols-outlined text-[16px]">add</span>
              <span>New Transfer</span>
            </button>
          </div>

          {transfers.length === 0 ? (
            <div className="p-8 text-center text-slate-500 text-[13px]">
              No relocation transfers recorded for this asset yet.
            </div>
          ) : (
            <div className="space-y-3">
              {transfers.map(t => (
                <div key={t.id} className="p-3.5 bg-[#eff4ff]/60 rounded-lg border border-slate-200 flex flex-col md:flex-row md:items-center justify-between gap-3 text-[13px]">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-mono font-bold text-[#00288e]">{t.transfer_no}</span>
                      <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-blue-100 text-blue-900">
                        {t.status}
                      </span>
                      <span className="text-slate-400 text-[11px]">• Waybill: {t.waybill_no}</span>
                    </div>
                    <div className="mt-1 font-semibold text-slate-800">
                      From: {t.from_location_name} ({t.from_department_name}) → To: {t.to_location_name} ({t.to_department_name})
                    </div>
                    <div className="text-[11px] text-slate-500 mt-0.5">
                      Reason: {t.reason} • Approved by: {t.approved_by}
                    </div>
                  </div>
                  <div className="text-right">
                    <span className="font-mono text-[11px] text-slate-500 block">{t.transfer_date}</span>
                    <span className="text-[11px] text-emerald-700 font-bold">Verified Signoff</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* TAB CONTENT: Maintenance Log Tab */}
      {activeTab === 'maintenance' && (
        <div className="bg-white rounded-xl shadow-sm border border-slate-200/80 p-5 space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-slate-100">
            <div>
              <h2 className="text-[16px] font-bold text-slate-900">Maintenance & Work Order Ledger</h2>
              <p className="text-[12px] text-slate-500">Preventive schedules, corrective servicing, and vendor SLA records</p>
            </div>
            <button
              onClick={() => onTriggerMaintenance(asset)}
              className="h-8 px-3 bg-[#00288e] text-white rounded text-[12px] font-semibold hover:bg-[#1e40af] flex items-center gap-1"
            >
              <span className="material-symbols-outlined text-[16px]">add</span>
              <span>Log Work Order</span>
            </button>
          </div>

          <div className="space-y-3">
            {maintenanceRecords.map(m => (
              <div key={m.id} className="p-3.5 bg-[#eff4ff]/60 rounded-lg border border-slate-200 flex flex-col md:flex-row md:items-center justify-between gap-3 text-[13px]">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-mono font-bold text-[#00288e]">{m.work_order_no}</span>
                    <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${m.status === 'OVERDUE' ? 'bg-red-100 text-red-800' : 'bg-amber-100 text-amber-900'}`}>
                      {m.status}
                    </span>
                    <span className="text-slate-500 text-[11px]">• {m.maintenance_type}</span>
                  </div>
                  <div className="font-bold text-slate-900 mt-1">{m.description}</div>
                  <div className="text-[11px] text-slate-500">
                    Vendor: {m.vendor} • Scope: {m.work_scope || 'Standard service'}
                  </div>
                </div>
                <div className="text-right">
                  <div className="font-mono font-bold text-slate-900">{formatNaira(m.budget_cost)}</div>
                  <div className="text-[11px] text-slate-500">Due: {m.expected_completion_date}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* TAB CONTENT: Audit Trail Tab */}
      {activeTab === 'audit' && (
        <div className="bg-white rounded-xl shadow-sm border border-slate-200/80 p-5 space-y-4">
          <div className="pb-3 border-b border-slate-100">
            <h2 className="text-[16px] font-bold text-slate-900">Immutable Audit Trail (IAS 16 Compliance)</h2>
            <p className="text-[12px] text-slate-500">Cryptographically sequenced audit trail for asset {asset.tag}</p>
          </div>

          <div className="space-y-3">
            {auditLogs.map(log => (
              <div key={log.id} className="p-3 bg-[#eff4ff]/50 rounded-lg border border-slate-200/80 text-[13px]">
                <div className="flex items-center justify-between">
                  <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase bg-[#00288e] text-white">
                    {log.action}
                  </span>
                  <span className="font-mono text-[11px] text-slate-500">{log.timestamp}</span>
                </div>
                <div className="font-semibold text-slate-900 mt-1">{log.description}</div>
                <div className="text-[11px] text-slate-500 mt-1 flex flex-wrap items-center gap-3">
                  <span>Authorized by: <strong>{log.user_name}</strong></span>
                  <span>IP: {log.ip_address}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* TAB CONTENT: Custody Assignments Tab */}
      {activeTab === 'assignments' && (
        <div className="bg-white rounded-xl shadow-sm border border-slate-200/80 p-5 space-y-4">
          <div className="pb-3 border-b border-slate-100">
            <h2 className="text-[16px] font-bold text-slate-900">Custody & Fiduciary History</h2>
            <p className="text-[12px] text-slate-500">Signed acknowledgments and employee custody obligations</p>
          </div>
          <div className="p-4 bg-[#eff4ff]/60 rounded-lg border border-slate-200 space-y-2 text-[13px]">
            <div className="flex items-center justify-between">
              <span className="text-[11px] uppercase font-bold text-slate-500">Current Custody Record</span>
              <span className="px-2 py-0.5 rounded bg-emerald-100 text-emerald-800 text-[11px] font-bold">
                Active & Verified
              </span>
            </div>
            <div className="text-[14px] font-bold text-slate-900">{asset.custodian_name} ({asset.custodian_staff_id})</div>
            <div className="text-slate-600">{asset.custodian_title} — {asset.department_name}</div>
            <div className="text-[11px] text-slate-500 pt-2 border-t border-slate-200">
              Countersigned physical inspection during Q4 Audit. Location: {asset.location_name} ({asset.sub_location}).
            </div>
          </div>
        </div>
      )}

      {/* TAB CONTENT: Documents Tab */}
      {activeTab === 'documents' && (
        <div className="bg-white rounded-xl shadow-sm border border-slate-200/80 p-5 space-y-4">
          <div className="pb-3 border-b border-slate-100 flex items-center justify-between">
            <div>
              <h2 className="text-[16px] font-bold text-slate-900">Governance & Warranty Archive</h2>
              <p className="text-[12px] text-slate-500">All scanned invoices, OEM warranties, and insurance certificates</p>
            </div>
            <button
              onClick={() => alert('Opening document upload portal...')}
              className="h-8 px-3 bg-[#00288e] text-white rounded text-[12px] font-semibold hover:bg-[#1e40af] flex items-center gap-1"
            >
              <span className="material-symbols-outlined text-[16px]">upload</span>
              <span>Upload Document</span>
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {(asset.documents || []).map(d => (
              <div key={d.id} className="p-3 bg-[#eff4ff]/60 rounded-lg border border-slate-200 flex items-start justify-between gap-2 text-[13px]">
                <div>
                  <div className="font-bold text-slate-900">{d.name}</div>
                  <div className="text-[11px] text-slate-500">{d.description}</div>
                  <div className="text-[10px] text-slate-400 mt-1">{d.date} • {d.size}</div>
                </div>
                <button
                  onClick={() => alert(`Downloading ${d.name}`)}
                  className="p-1.5 text-[#00288e] hover:bg-white rounded"
                  title="Download"
                >
                  <span className="material-symbols-outlined text-[18px]">download</span>
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
