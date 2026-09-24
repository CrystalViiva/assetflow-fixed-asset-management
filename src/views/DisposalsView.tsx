/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 * Disposal Governance & Impairment Board View
 */

import React, { useState, useEffect } from 'react';
import { DisposalRecord } from '../types';
import { assetRepository } from '../services/assetRepository';
import { formatNaira } from '../services/depreciationCalculator';

interface DisposalsViewProps {
  onNavigate: (route: string) => void;
  onSelectAsset: (assetId: string) => void;
  onOpenDisposeAsset: () => void;
}

export const DisposalsView: React.FC<DisposalsViewProps> = ({
  onNavigate,
  onSelectAsset,
  onOpenDisposeAsset,
}) => {
  const [disposals, setDisposals] = useState<DisposalRecord[]>([]);

  const loadData = async () => {
    const list = await assetRepository.getDisposals();
    setDisposals(list);
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleApproveDisposal = async (id: string) => {
    await assetRepository.updateDisposalStatus(id, 'COMPLETED');
    await loadData();
  };

  return (
    <div className="w-full p-4 md:p-6 select-text space-y-5">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-1.5 text-[12px] text-slate-500 mb-1">
            <span onClick={() => onNavigate('dashboard')} className="hover:text-[#00288e] cursor-pointer">Home</span>
            <span className="text-slate-300">/</span>
            <span className="text-slate-500">Lifecycle</span>
            <span className="text-slate-300">/</span>
            <span className="text-slate-900 font-bold">Disposals</span>
          </div>
          <h1 className="text-2xl font-bold text-slate-900">
            Executive Disposal & Derecognition Board
          </h1>
          <p className="text-[13px] text-slate-500">
            IAS 16 / IFRS 5 derecognition governance, gain/loss accounting, and asset write-off authorizations.
          </p>
        </div>

        <button
          onClick={onOpenDisposeAsset}
          className="h-9 px-3.5 bg-rose-700 text-white font-semibold text-[13px] rounded-lg shadow-xs hover:bg-rose-800 transition-all flex items-center gap-1.5 self-start md:self-auto"
        >
          <span className="material-symbols-outlined text-[18px]">delete_sweep</span>
          <span>Record Asset Disposal</span>
        </button>
      </div>

      <div className="space-y-3">
        {disposals.map(disp => {
          const isGain = disp.gain_or_loss >= 0;
          return (
            <div
              key={disp.id}
              className="bg-white rounded-xl shadow-sm border border-slate-200/80 p-5 flex flex-col md:flex-row md:items-center justify-between gap-4 hover:shadow-md transition-shadow"
            >
              <div className="space-y-1 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-mono font-bold text-slate-900 text-[14px]">
                    {disp.disposal_no}
                  </span>
                  <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-[#eff4ff] text-[#00288e]">
                    Method: {disp.method}
                  </span>
                  <span
                    className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                      disp.status === 'COMPLETED' ? 'bg-emerald-100 text-emerald-800' : 'bg-amber-100 text-amber-900'
                    }`}
                  >
                    {disp.status.replace('_', ' ')}
                  </span>
                  <span className="text-[11px] text-slate-400 font-mono">• Date: {disp.disposal_date}</span>
                </div>

                <div className="flex items-center gap-2">
                  <button
                    onClick={() => onSelectAsset(disp.asset_id)}
                    className="font-bold text-slate-900 text-[15px] hover:text-[#00288e] transition-colors"
                  >
                    {disp.asset_tag} — {disp.asset_name}
                  </button>
                </div>

                <div className="text-[12px] text-slate-600">
                  <strong>Reason:</strong> {disp.reason}
                </div>
                <div className="text-[11px] text-slate-500">
                  Recommendation: {disp.recommendation} • Approver: {disp.approved_by}
                </div>
              </div>

              {/* Financial Gain/Loss Card */}
              <div className="flex items-center gap-4 shrink-0 p-3 bg-[#eff4ff]/60 rounded-lg border border-slate-200 text-center">
                <div>
                  <span className="text-[10px] text-slate-500 uppercase font-bold block">Carrying Book Value</span>
                  <span className="font-mono font-bold text-slate-800 text-[13px]">
                    {formatNaira(disp.book_value)}
                  </span>
                </div>

                <div className="h-6 w-px bg-slate-300"></div>

                <div>
                  <span className="text-[10px] text-slate-500 uppercase font-bold block">Proceeds</span>
                  <span className="font-mono font-bold text-[#00288e] text-[13px]">
                    {formatNaira(disp.disposal_proceeds)}
                  </span>
                </div>

                <div className="h-6 w-px bg-slate-300"></div>

                <div>
                  <span className="text-[10px] text-slate-500 uppercase font-bold block">Gain / (Loss)</span>
                  <span
                    className={`font-mono font-bold text-[13px] ${
                      isGain ? 'text-emerald-700' : 'text-rose-700'
                    }`}
                  >
                    {isGain ? '+' : ''}{formatNaira(disp.gain_or_loss)}
                  </span>
                </div>

                {disp.status === 'PENDING_REVIEW' && (
                  <button
                    onClick={() => handleApproveDisposal(disp.id)}
                    className="ml-2 px-3 py-1.5 bg-[#00288e] hover:bg-[#1e40af] text-white text-[11px] font-bold rounded shadow-xs"
                  >
                    Sign Off
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
