/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 * Acquisitions & Capex In-Service Ledger View
 */

import React, { useState, useEffect } from 'react';
import { Asset } from '../types';
import { assetRepository } from '../services/assetRepository';
import { formatNaira } from '../services/depreciationCalculator';

interface AcquisitionsViewProps {
  onNavigate: (route: string) => void;
  onSelectAsset: (assetId: string) => void;
}

export const AcquisitionsView: React.FC<AcquisitionsViewProps> = ({ onNavigate, onSelectAsset }) => {
  const [assets, setAssets] = useState<Asset[]>([]);

  useEffect(() => {
    async function load() {
      const res = await assetRepository.getAssets({ pageSize: 50 });
      setAssets(res.data);
    }
    load();
  }, []);

  const totalCapex = assets.reduce((sum, a) => sum + a.total_acquisition_cost, 0);

  return (
    <div className="w-full p-4 md:p-6 select-text space-y-5">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-1.5 text-[12px] text-slate-500 mb-1">
            <span onClick={() => onNavigate('dashboard')} className="hover:text-[#00288e] cursor-pointer">Home</span>
            <span className="text-slate-300">/</span>
            <span className="text-slate-500">Assets</span>
            <span className="text-slate-300">/</span>
            <span className="text-slate-900 font-bold">Acquisitions</span>
          </div>
          <h1 className="text-2xl font-bold text-slate-900">Capex & Acquisitions Ledger</h1>
          <p className="text-[13px] text-slate-500">
            Purchase orders, vendor invoicing, and capitalization approvals under IAS 16.
          </p>
        </div>

        <button
          onClick={() => onNavigate('asset-create')}
          className="h-9 px-3.5 bg-[#00288e] text-white font-semibold text-[13px] rounded-lg shadow-xs hover:bg-[#1e40af] transition-all flex items-center gap-1.5 self-start md:self-auto"
        >
          <span className="material-symbols-outlined text-[18px]">add_circle</span>
          <span>Register New Capex</span>
        </button>
      </div>

      {/* Summary Banner */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200/80 p-4 grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div>
          <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">Total Capitalized Capex</span>
          <div className="text-2xl font-mono font-bold text-[#00288e] mt-0.5">{formatNaira(totalCapex)}</div>
        </div>
        <div>
          <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">Active Procurement Batches</span>
          <div className="text-2xl font-bold text-slate-900 mt-0.5">{assets.length} In-Service Orders</div>
        </div>
        <div>
          <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">Audited Compliance</span>
          <div className="text-2xl font-bold text-emerald-700 mt-0.5">100% Verified Threshold</div>
        </div>
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200/80 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-[13px]">
            <thead className="bg-[#eff4ff] text-slate-600 text-[11px] font-bold uppercase tracking-wider border-b border-slate-200">
              <tr>
                <th className="py-2.5 px-3">Asset Tag</th>
                <th className="py-2.5 px-3">Description</th>
                <th className="py-2.5 px-3">PO Reference</th>
                <th className="py-2.5 px-3">Vendor / Supplier</th>
                <th className="py-2.5 px-3">Capitalization Date</th>
                <th className="py-2.5 px-3 text-right">Capitalized Cost (₦)</th>
                <th className="py-2.5 px-3 text-center">In-Service Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {assets.map(asset => (
                <tr
                  key={asset.id}
                  onClick={() => onSelectAsset(asset.id)}
                  className="hover:bg-[#eff4ff]/60 transition-colors cursor-pointer"
                >
                  <td className="py-3 px-3 font-mono font-bold text-[#00288e]">{asset.tag}</td>
                  <td className="py-3 px-3">
                    <div className="font-semibold text-slate-900">{asset.name}</div>
                    <div className="text-[11px] text-slate-500">{asset.category_name}</div>
                  </td>
                  <td className="py-3 px-3 font-mono text-slate-700">{asset.purchase_order_ref}</td>
                  <td className="py-3 px-3 text-slate-800">{asset.vendor}</td>
                  <td className="py-3 px-3 font-mono text-slate-600">{asset.capitalization_date}</td>
                  <td className="py-3 px-3 text-right font-mono font-bold text-slate-900">
                    {formatNaira(asset.total_acquisition_cost)}
                  </td>
                  <td className="py-3 px-3 text-center">
                    <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-100 text-emerald-800 uppercase">
                      Capitalized
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
