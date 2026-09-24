/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 * Asset Disposal & Write-Off Governance Modal
 */

import React, { useState } from 'react';
import { Asset, DisposalMethod, DisposalRecord } from '../../types';
import { calculateDisposalGainLoss } from '../../services/depreciationCalculator';

interface DisposeAssetModalProps {
  isOpen: boolean;
  onClose: () => void;
  selectedAsset: Asset | null;
  assets: Asset[];
  onSubmitDisposal: (data: Partial<DisposalRecord>) => Promise<void>;
}

export const DisposeAssetModal: React.FC<DisposeAssetModalProps> = ({
  isOpen,
  onClose,
  selectedAsset,
  assets,
  onSubmitDisposal,
}) => {
  if (!isOpen) return null;

  const [assetId, setAssetId] = useState<string>(selectedAsset?.id || (assets[0]?.id ?? ''));
  const currentAsset = assets.find(a => a.id === assetId) || selectedAsset || assets[0];

  const [disposalDate, setDisposalDate] = useState<string>(new Date().toISOString().substring(0, 10));
  const [method, setMethod] = useState<DisposalMethod>('SALE');
  const [proceeds, setProceeds] = useState<number>(
    currentAsset ? Math.round(currentAsset.net_book_value * 1.1) : 0
  );
  const [reason, setReason] = useState<string>('Surplus to requirements / economic lifecycle obsolescence.');
  const [recommendation, setRecommendation] = useState<string>('Competitive executive auction to certified bidders');
  const [approvedBy, setApprovedBy] = useState<string>('Babajide Adeleke (CFO Review)');
  const [submitting, setSubmitting] = useState(false);

  const bookValue = currentAsset ? currentAsset.net_book_value : 0;
  const { gainOrLoss, isGain } = calculateDisposalGainLoss(proceeds, bookValue);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!currentAsset) return;

    setSubmitting(true);
    try {
      await onSubmitDisposal({
        asset_id: currentAsset.id,
        asset_tag: currentAsset.tag,
        asset_name: currentAsset.name,
        disposal_date: disposalDate,
        method,
        disposal_proceeds: proceeds,
        book_value: bookValue,
        gain_or_loss: gainOrLoss,
        reason,
        recommendation,
        approved_by: approvedBy,
        status: 'PENDING_REVIEW',
      });
      onClose();
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-xs animate-in fade-in">
      <div className="bg-white rounded-xl max-w-xl w-full shadow-2xl p-6 space-y-4 border border-slate-200">
        <div className="flex items-center justify-between pb-3 border-b border-slate-100">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-rose-50 text-rose-700 flex items-center justify-center">
              <span className="material-symbols-outlined text-[20px]">delete_forever</span>
            </div>
            <div>
              <h3 className="text-[16px] font-bold text-slate-900">Initiate Asset Disposal & Impairment</h3>
              <p className="text-[11px] text-slate-500">IAS 16 / IFRS 5 Derecognition and Gain/Loss Assessment</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="w-7 h-7 flex items-center justify-center rounded-full hover:bg-slate-100 text-slate-400 hover:text-slate-600 transition-colors"
          >
            <span className="material-symbols-outlined text-[18px]">close</span>
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-3.5 text-[13px]">
          {/* Asset Selection */}
          <div>
            <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-500 mb-1">
              Select Asset for Disposal <span className="text-red-500">*</span>
            </label>
            <select
              value={assetId}
              onChange={e => {
                setAssetId(e.target.value);
                const a = assets.find(item => item.id === e.target.value);
                if (a) setProceeds(Math.round(a.net_book_value * 1.1));
              }}
              className="w-full h-9 px-3 bg-[#eff4ff] text-slate-900 rounded-md border border-slate-200 focus:outline-none focus:ring-1.5 focus:ring-[#00288e] font-medium"
            >
              {assets.map(a => (
                <option key={a.id} value={a.id}>
                  {a.tag} — {a.name} (NBV: ₦{a.net_book_value.toLocaleString('en-NG')})
                </option>
              ))}
            </select>
          </div>

          {/* Real-time Accounting Impact Card */}
          <div className="p-3 bg-[#eff4ff]/70 rounded-lg border border-slate-200 grid grid-cols-3 gap-2 text-center">
            <div>
              <span className="text-slate-500 text-[10px] uppercase font-bold block">Current NBV</span>
              <span className="font-mono font-bold text-slate-800 text-[14px]">
                ₦{bookValue.toLocaleString('en-NG')}
              </span>
            </div>
            <div>
              <span className="text-slate-500 text-[10px] uppercase font-bold block">Est. Proceeds</span>
              <span className="font-mono font-bold text-[#00288e] text-[14px]">
                ₦{proceeds.toLocaleString('en-NG')}
              </span>
            </div>
            <div>
              <span className="text-slate-500 text-[10px] uppercase font-bold block">
                {isGain ? 'Recognized Gain' : 'Recognized Loss'}
              </span>
              <span
                className={`font-mono font-bold text-[14px] ${
                  isGain ? 'text-emerald-700' : 'text-rose-700'
                }`}
              >
                {gainOrLoss >= 0 ? '+' : ''}₦{gainOrLoss.toLocaleString('en-NG')}
              </span>
            </div>
          </div>

          {/* Disposal Method & Date */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-500 mb-1">
                Disposal Method <span className="text-red-500">*</span>
              </label>
              <select
                value={method}
                onChange={e => setMethod(e.target.value as DisposalMethod)}
                className="w-full h-9 px-3 bg-[#eff4ff] text-slate-900 rounded-md border border-slate-200 focus:outline-none focus:ring-1.5 focus:ring-[#00288e]"
              >
                <option value="SALE">Commercial Sale / Auction</option>
                <option value="SCRAP">Scrap / E-Waste Salvage</option>
                <option value="DONATION">Charitable Donation</option>
                <option value="WRITE_OFF">Complete Impairment Write-Off</option>
                <option value="TRANSFER_OUT">External Entity Transfer Out</option>
              </select>
            </div>

            <div>
              <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-500 mb-1">
                Disposal Date <span className="text-red-500">*</span>
              </label>
              <input
                type="date"
                value={disposalDate}
                onChange={e => setDisposalDate(e.target.value)}
                className="w-full h-9 px-3 bg-[#eff4ff] text-slate-900 font-mono rounded-md border border-slate-200 focus:outline-none focus:ring-1.5 focus:ring-[#00288e]"
                required
              />
            </div>
          </div>

          {/* Proceeds and Approver */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-500 mb-1">
                Disposal Proceeds (₦) <span className="text-red-500">*</span>
              </label>
              <input
                type="number"
                min="0"
                step="100000"
                value={proceeds}
                onChange={e => setProceeds(parseFloat(e.target.value) || 0)}
                className="w-full h-9 px-3 bg-[#eff4ff] text-slate-900 font-mono rounded-md border border-slate-200 focus:outline-none focus:ring-1.5 focus:ring-[#00288e]"
                required
              />
            </div>

            <div>
              <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-500 mb-1">
                Governance Reviewer / Approver <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                value={approvedBy}
                onChange={e => setApprovedBy(e.target.value)}
                className="w-full h-9 px-3 bg-[#eff4ff] text-slate-900 rounded-md border border-slate-200 focus:outline-none focus:ring-1.5 focus:ring-[#00288e]"
                required
              />
            </div>
          </div>

          {/* Reason */}
          <div>
            <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-500 mb-1">
              Impairment Reason / De-recognition Justification <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              value={reason}
              onChange={e => setReason(e.target.value)}
              className="w-full h-9 px-3 bg-[#eff4ff] text-slate-900 rounded-md border border-slate-200 focus:outline-none focus:ring-1.5 focus:ring-[#00288e]"
              required
            />
          </div>

          <div>
            <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-500 mb-1">
              Recommendation Details
            </label>
            <textarea
              rows={2}
              value={recommendation}
              onChange={e => setRecommendation(e.target.value)}
              className="w-full p-2 bg-[#eff4ff] text-slate-900 rounded-md border border-slate-200 focus:outline-none focus:ring-1.5 focus:ring-[#00288e] resize-none"
            />
          </div>

          <div className="flex items-center justify-end gap-2 pt-3 border-t border-slate-100">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 font-medium rounded text-[12px] transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="px-4 py-2 bg-rose-700 text-white hover:bg-rose-800 font-semibold rounded text-[12px] flex items-center gap-1.5 shadow-sm transition-colors disabled:opacity-50"
            >
              <span className="material-symbols-outlined text-[16px]">gavel</span>
              <span>{submitting ? 'Submitting...' : 'Submit to Disposal Board'}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
