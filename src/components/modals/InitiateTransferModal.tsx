/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 * Initiate Inter-Facility Asset Transfer Modal
 */

import React, { useState } from 'react';
import { Asset, Department, LocationHub, Transfer } from '../../types';

interface InitiateTransferModalProps {
  isOpen: boolean;
  onClose: () => void;
  selectedAsset: Asset | null;
  assets: Asset[];
  departments: Department[];
  locations: LocationHub[];
  onSubmitTransfer: (transferData: Partial<Transfer>) => Promise<void>;
}

export const InitiateTransferModal: React.FC<InitiateTransferModalProps> = ({
  isOpen,
  onClose,
  selectedAsset,
  assets,
  departments,
  locations,
  onSubmitTransfer,
}) => {
  if (!isOpen) return null;

  const [assetId, setAssetId] = useState<string>(selectedAsset?.id || (assets[0]?.id ?? ''));
  const currentAsset = assets.find(a => a.id === assetId) || selectedAsset || assets[0];

  const [newDepartmentName, setNewDepartmentName] = useState<string>(
    departments.find(d => d.name !== currentAsset?.department_name)?.name || departments[0]?.name || ''
  );
  const [newLocationName, setNewLocationName] = useState<string>(
    locations.find(l => l.name !== currentAsset?.location_name)?.name || locations[0]?.name || ''
  );
  const [transferDate, setTransferDate] = useState<string>(
    new Date().toISOString().substring(0, 10)
  );
  const [reason, setReason] = useState<string>('Operational redeployment to support site project requirements.');
  const [notes, setNotes] = useState<string>('Heavy transport escort required with gate manifest authorization.');
  const [requestedBy, setRequestedBy] = useState<string>('Babajide Adeleke (Treasury & Accounting)');
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!currentAsset) return;

    setSubmitting(true);
    try {
      await onSubmitTransfer({
        asset_id: currentAsset.id,
        asset_tag: currentAsset.tag,
        asset_name: currentAsset.name,
        from_department_id: currentAsset.department_id,
        from_department_name: currentAsset.department_name,
        from_location_id: currentAsset.location_id,
        from_location_name: currentAsset.location_name,
        to_department_name: newDepartmentName,
        to_location_name: newLocationName,
        transfer_date: transferDate,
        reason,
        notes,
        requested_by: requestedBy,
        approved_by: 'Babajide Adeleke (CFO)',
        status: 'PENDING',
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
            <div className="w-8 h-8 rounded-lg bg-[#e5eeff] text-[#00288e] flex items-center justify-center">
              <span className="material-symbols-outlined text-[20px]">swap_horiz</span>
            </div>
            <div>
              <h3 className="text-[16px] font-bold text-slate-900">Initiate Asset Transfer</h3>
              <p className="text-[11px] text-slate-500">Create inter-facility redeployment and logistics manifest</p>
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
              Select Asset to Transfer <span className="text-red-500">*</span>
            </label>
            <select
              value={assetId}
              onChange={e => setAssetId(e.target.value)}
              className="w-full h-9 px-3 bg-[#eff4ff] text-slate-900 rounded-md border border-slate-200 focus:outline-none focus:ring-1.5 focus:ring-[#00288e] font-medium"
            >
              {assets.map(a => (
                <option key={a.id} value={a.id}>
                  {a.tag} — {a.name} ({a.location_name})
                </option>
              ))}
            </select>
          </div>

          {/* Current Custody & Stationing Read-Only Box */}
          {currentAsset && (
            <div className="p-3 bg-[#eff4ff]/60 rounded-lg border border-slate-200/80 grid grid-cols-2 gap-2 text-[12px]">
              <div>
                <span className="text-slate-400 block text-[10px] uppercase font-semibold">Current Department</span>
                <span className="font-semibold text-slate-800">{currentAsset.department_name}</span>
              </div>
              <div>
                <span className="text-slate-400 block text-[10px] uppercase font-semibold">Current Location</span>
                <span className="font-semibold text-slate-800">{currentAsset.location_name}</span>
              </div>
              <div>
                <span className="text-slate-400 block text-[10px] uppercase font-semibold">Active Custodian</span>
                <span className="text-slate-700">{currentAsset.custodian_name}</span>
              </div>
              <div>
                <span className="text-slate-400 block text-[10px] uppercase font-semibold">Carrying Net Book Value</span>
                <span className="font-mono font-bold text-[#00288e]">
                  ₦{currentAsset.net_book_value.toLocaleString('en-NG')}
                </span>
              </div>
            </div>
          )}

          {/* Target Department and Target Location */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-500 mb-1">
                New Target Department <span className="text-red-500">*</span>
              </label>
              <select
                value={newDepartmentName}
                onChange={e => setNewDepartmentName(e.target.value)}
                className="w-full h-9 px-3 bg-[#eff4ff] text-slate-900 rounded-md border border-slate-200 focus:outline-none focus:ring-1.5 focus:ring-[#00288e]"
                required
              >
                {departments.map(d => (
                  <option key={d.id} value={d.name}>
                    {d.name}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-500 mb-1">
                New Target Operating Hub <span className="text-red-500">*</span>
              </label>
              <select
                value={newLocationName}
                onChange={e => setNewLocationName(e.target.value)}
                className="w-full h-9 px-3 bg-[#eff4ff] text-slate-900 rounded-md border border-slate-200 focus:outline-none focus:ring-1.5 focus:ring-[#00288e]"
                required
              >
                {locations.map(l => (
                  <option key={l.id} value={l.name}>
                    {l.name}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Transfer Date & Requested By */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-500 mb-1">
                Scheduled Transfer Date <span className="text-red-500">*</span>
              </label>
              <input
                type="date"
                value={transferDate}
                onChange={e => setTransferDate(e.target.value)}
                className="w-full h-9 px-3 bg-[#eff4ff] text-slate-900 font-mono rounded-md border border-slate-200 focus:outline-none focus:ring-1.5 focus:ring-[#00288e]"
                required
              />
            </div>
            <div>
              <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-500 mb-1">
                Requested By <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                value={requestedBy}
                onChange={e => setRequestedBy(e.target.value)}
                className="w-full h-9 px-3 bg-[#eff4ff] text-slate-900 rounded-md border border-slate-200 focus:outline-none focus:ring-1.5 focus:ring-[#00288e]"
                required
              />
            </div>
          </div>

          {/* Reason & Logistics Notes */}
          <div>
            <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-500 mb-1">
              Business Justification / Reason <span className="text-red-500">*</span>
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
              Logistics Notes & Gate Clearance Details
            </label>
            <textarea
              rows={2}
              value={notes}
              onChange={e => setNotes(e.target.value)}
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
              className="px-4 py-2 bg-[#00288e] text-white hover:bg-[#1e40af] font-semibold rounded text-[12px] flex items-center gap-1.5 shadow-sm transition-colors disabled:opacity-50"
            >
              <span className="material-symbols-outlined text-[16px]">send</span>
              <span>{submitting ? 'Submitting...' : 'Submit Transfer for Approval'}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
