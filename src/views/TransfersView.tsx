/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 * Inter-Facility Transfers Workflow View
 */

import React, { useState, useEffect } from 'react';
import { Transfer } from '../types';
import { assetRepository } from '../services/assetRepository';

interface TransfersViewProps {
  onNavigate: (route: string) => void;
  onSelectAsset: (assetId: string) => void;
  onOpenInitiateTransfer: () => void;
}

export const TransfersView: React.FC<TransfersViewProps> = ({
  onNavigate,
  onSelectAsset,
  onOpenInitiateTransfer,
}) => {
  const [transfers, setTransfers] = useState<Transfer[]>([]);
  const [filterStatus, setFilterStatus] = useState<string>('ALL');

  const loadData = async () => {
    const list = await assetRepository.getTransfers();
    setTransfers(list);
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleApprove = async (id: string) => {
    await assetRepository.updateTransferStatus(id, 'IN_TRANSIT');
    await loadData();
  };

  const handleComplete = async (id: string) => {
    await assetRepository.updateTransferStatus(id, 'COMPLETED');
    await loadData();
  };

  const filtered = transfers.filter(t => (filterStatus === 'ALL' ? true : t.status === filterStatus));

  const getStatusBadge = (status: Transfer['status']) => {
    switch (status) {
      case 'PENDING':
        return (
          <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-amber-100 text-amber-900 uppercase">
            Pending Approval
          </span>
        );
      case 'IN_TRANSIT':
        return (
          <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-blue-100 text-blue-900 uppercase">
            In-Transit (Waybill)
          </span>
        );
      case 'COMPLETED':
        return (
          <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-emerald-100 text-emerald-800 uppercase">
            Completed
          </span>
        );
      case 'REJECTED':
        return (
          <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-rose-100 text-rose-800 uppercase">
            Rejected
          </span>
        );
      default:
        return null;
    }
  };

  return (
    <div className="w-full p-4 md:p-6 select-text space-y-5">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-1.5 text-[12px] text-slate-500 mb-1">
            <span onClick={() => onNavigate('dashboard')} className="hover:text-[#00288e] cursor-pointer">Home</span>
            <span className="text-slate-300">/</span>
            <span className="text-slate-500">Assets</span>
            <span className="text-slate-300">/</span>
            <span className="text-slate-900 font-bold">Transfers</span>
          </div>
          <h1 className="text-2xl font-bold text-slate-900">Asset Transfers & Inter-Facility Movements</h1>
          <p className="text-[13px] text-slate-500">
            Track asset relocation workflows, waybills, and department change custody handovers.
          </p>
        </div>

        <button
          onClick={onOpenInitiateTransfer}
          className="h-9 px-3.5 bg-[#00288e] text-white font-semibold text-[13px] rounded-lg shadow-xs hover:bg-[#1e40af] transition-all flex items-center gap-1.5 self-start md:self-auto"
        >
          <span className="material-symbols-outlined text-[18px]">add_circle</span>
          <span>Initiate Transfer</span>
        </button>
      </div>

      {/* Filter Tabs */}
      <div className="flex items-center gap-2 border-b border-slate-200 pb-2 text-[13px]">
        {['ALL', 'PENDING', 'IN_TRANSIT', 'COMPLETED'].map(st => (
          <button
            key={st}
            onClick={() => setFilterStatus(st)}
            className={`px-3 py-1 rounded-md font-semibold transition-colors ${
              filterStatus === st ? 'bg-[#00288e] text-white shadow-xs' : 'text-slate-600 hover:bg-slate-100'
            }`}
          >
            {st.replace('_', ' ')}
          </button>
        ))}
      </div>

      {/* Transfer Cards / List */}
      <div className="space-y-3">
        {filtered.map(transfer => (
          <div
            key={transfer.id}
            className="bg-white rounded-xl shadow-sm border border-slate-200/80 p-5 flex flex-col lg:flex-row lg:items-center justify-between gap-4 hover:shadow-md transition-shadow"
          >
            <div className="space-y-1.5 flex-1">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-mono font-bold text-[#00288e] text-[14px]">
                  {transfer.transfer_no}
                </span>
                {getStatusBadge(transfer.status)}
                <span className="text-[12px] font-mono text-slate-500">
                  Waybill: {transfer.waybill_no}
                </span>
                <span className="text-[12px] text-slate-400">• Scheduled: {transfer.transfer_date}</span>
              </div>

              <div className="flex items-center gap-2">
                <button
                  onClick={() => onSelectAsset(transfer.asset_id)}
                  className="font-bold text-slate-900 text-[15px] hover:text-[#00288e] transition-colors"
                >
                  {transfer.asset_tag} — {transfer.asset_name}
                </button>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-[12px] pt-1">
                <div className="p-2 rounded bg-slate-50 border border-slate-100">
                  <span className="text-slate-400 text-[10px] uppercase font-bold block">From</span>
                  <span className="font-semibold text-slate-800">
                    {transfer.from_location_name} ({transfer.from_department_name})
                  </span>
                </div>
                <div className="p-2 rounded bg-[#eff4ff] border border-blue-100">
                  <span className="text-[#00288e] text-[10px] uppercase font-bold block">To Destination</span>
                  <span className="font-bold text-[#00288e]">
                    {transfer.to_location_name} ({transfer.to_department_name})
                  </span>
                </div>
              </div>

              <div className="text-[12px] text-slate-600 pt-1">
                <strong>Justification:</strong> {transfer.reason}
              </div>
              <div className="text-[11px] text-slate-400">
                Requested by: {transfer.requested_by} • Approved by: {transfer.approved_by}
              </div>
            </div>

            <div className="flex lg:flex-col items-center lg:items-end justify-between gap-2 shrink-0 border-t lg:border-t-0 pt-3 lg:pt-0 border-slate-100">
              {transfer.status === 'PENDING' && (
                <button
                  onClick={() => handleApprove(transfer.id)}
                  className="px-3.5 py-1.5 bg-[#00288e] text-white hover:bg-[#1e40af] text-[12px] font-semibold rounded-lg shadow-xs transition-colors"
                >
                  Authorize Waybill
                </button>
              )}
              {transfer.status === 'IN_TRANSIT' && (
                <button
                  onClick={() => handleComplete(transfer.id)}
                  className="px-3.5 py-1.5 bg-emerald-700 text-white hover:bg-emerald-800 text-[12px] font-semibold rounded-lg shadow-xs transition-colors"
                >
                  Acknowledge Receipt
                </button>
              )}
              <button
                onClick={() => onSelectAsset(transfer.asset_id)}
                className="px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 text-[12px] font-semibold rounded-lg transition-colors"
              >
                Inspect Asset
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
