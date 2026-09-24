/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 * Log Maintenance Work Order Modal
 */

import React, { useState } from 'react';
import { Asset, MaintenanceRecord, MaintenanceType } from '../../types';

interface LogMaintenanceModalProps {
  isOpen: boolean;
  onClose: () => void;
  selectedAsset: Asset | null;
  assets: Asset[];
  onSubmitMaintenance: (data: Partial<MaintenanceRecord>) => Promise<void>;
}

export const LogMaintenanceModal: React.FC<LogMaintenanceModalProps> = ({
  isOpen,
  onClose,
  selectedAsset,
  assets,
  onSubmitMaintenance,
}) => {
  if (!isOpen) return null;

  const [assetId, setAssetId] = useState<string>(selectedAsset?.id || (assets[0]?.id ?? ''));
  const currentAsset = assets.find(a => a.id === assetId) || selectedAsset || assets[0];

  const [type, setType] = useState<MaintenanceType>('PREVENTIVE');
  const [description, setDescription] = useState<string>('Scheduled OEM preventive servicing & mechanical overhaul');
  const [vendor, setVendor] = useState<string>('Mantrac Certified Field Services');
  const [startDate, setStartDate] = useState<string>(new Date().toISOString().substring(0, 10));
  const [expectedCompletionDate, setExpectedCompletionDate] = useState<string>(
    new Date(Date.now() + 7 * 86400000).toISOString().substring(0, 10)
  );
  const [budgetCost, setBudgetCost] = useState<number>(1_850_000);
  const [workScope, setWorkScope] = useState<string>(
    'Complete system diagnostic, fluid and filter replacements, OEM calibrated testing and signoff.'
  );
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!currentAsset) return;

    setSubmitting(true);
    try {
      await onSubmitMaintenance({
        asset_id: currentAsset.id,
        asset_tag: currentAsset.tag,
        asset_name: currentAsset.name,
        maintenance_type: type,
        description,
        vendor,
        start_date: startDate,
        expected_completion_date: expectedCompletionDate,
        budget_cost: budgetCost,
        status: 'IN_PROGRESS',
        work_scope: workScope,
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
            <div className="w-8 h-8 rounded-lg bg-amber-50 text-amber-800 flex items-center justify-center">
              <span className="material-symbols-outlined text-[20px]">build</span>
            </div>
            <div>
              <h3 className="text-[16px] font-bold text-slate-900">Log Maintenance Work Order</h3>
              <p className="text-[11px] text-slate-500">Open preventive overhaul or corrective repair schedule</p>
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
              Select Asset for Maintenance <span className="text-red-500">*</span>
            </label>
            <select
              value={assetId}
              onChange={e => setAssetId(e.target.value)}
              className="w-full h-9 px-3 bg-[#eff4ff] text-slate-900 rounded-md border border-slate-200 focus:outline-none focus:ring-1.5 focus:ring-[#00288e] font-medium"
            >
              {assets.map(a => (
                <option key={a.id} value={a.id}>
                  {a.tag} — {a.name} ({a.status})
                </option>
              ))}
            </select>
          </div>

          {/* Maintenance Type & Budget Cost */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-500 mb-1">
                Maintenance Classification <span className="text-red-500">*</span>
              </label>
              <select
                value={type}
                onChange={e => setType(e.target.value as MaintenanceType)}
                className="w-full h-9 px-3 bg-[#eff4ff] text-slate-900 rounded-md border border-slate-200 focus:outline-none focus:ring-1.5 focus:ring-[#00288e]"
              >
                <option value="PREVENTIVE">Preventive Maintenance</option>
                <option value="CORRECTIVE">Corrective Repair</option>
                <option value="INSPECTION">Routine Inspection</option>
                <option value="EMERGENCY">Emergency Breakdown</option>
              </select>
            </div>

            <div>
              <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-500 mb-1">
                Approved Budget Cost (₦) <span className="text-red-500">*</span>
              </label>
              <input
                type="number"
                min="0"
                step="10000"
                value={budgetCost}
                onChange={e => setBudgetCost(parseFloat(e.target.value) || 0)}
                className="w-full h-9 px-3 bg-[#eff4ff] text-slate-900 font-mono rounded-md border border-slate-200 focus:outline-none focus:ring-1.5 focus:ring-[#00288e]"
                required
              />
            </div>
          </div>

          {/* Description & Vendor */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-500 mb-1">
                Work Order Title / Description <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                value={description}
                onChange={e => setDescription(e.target.value)}
                className="w-full h-9 px-3 bg-[#eff4ff] text-slate-900 rounded-md border border-slate-200 focus:outline-none focus:ring-1.5 focus:ring-[#00288e]"
                required
              />
            </div>

            <div>
              <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-500 mb-1">
                Assigned Vendor / Service Partner <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                value={vendor}
                onChange={e => setVendor(e.target.value)}
                className="w-full h-9 px-3 bg-[#eff4ff] text-slate-900 rounded-md border border-slate-200 focus:outline-none focus:ring-1.5 focus:ring-[#00288e]"
                required
              />
            </div>
          </div>

          {/* Dates */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-500 mb-1">
                Start Date <span className="text-red-500">*</span>
              </label>
              <input
                type="date"
                value={startDate}
                onChange={e => setStartDate(e.target.value)}
                className="w-full h-9 px-3 bg-[#eff4ff] text-slate-900 font-mono rounded-md border border-slate-200 focus:outline-none focus:ring-1.5 focus:ring-[#00288e]"
                required
              />
            </div>

            <div>
              <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-500 mb-1">
                Target Completion Date <span className="text-red-500">*</span>
              </label>
              <input
                type="date"
                value={expectedCompletionDate}
                onChange={e => setExpectedCompletionDate(e.target.value)}
                className="w-full h-9 px-3 bg-[#eff4ff] text-slate-900 font-mono rounded-md border border-slate-200 focus:outline-none focus:ring-1.5 focus:ring-[#00288e]"
                required
              />
            </div>
          </div>

          {/* Detailed Work Scope */}
          <div>
            <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-500 mb-1">
              Detailed Work Scope & Parts Needed
            </label>
            <textarea
              rows={2}
              value={workScope}
              onChange={e => setWorkScope(e.target.value)}
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
              <span className="material-symbols-outlined text-[16px]">check_circle</span>
              <span>{submitting ? 'Registering...' : 'Register Maintenance Order'}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
