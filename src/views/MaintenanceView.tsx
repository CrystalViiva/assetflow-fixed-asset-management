/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 * Maintenance & Work Order Management View
 */

import React, { useState, useEffect } from 'react';
import { MaintenanceRecord } from '../types';
import { assetRepository } from '../services/assetRepository';
import { formatNaira } from '../services/depreciationCalculator';

interface MaintenanceViewProps {
  onNavigate: (route: string) => void;
  onSelectAsset: (assetId: string) => void;
  onOpenLogMaintenance: () => void;
}

export const MaintenanceView: React.FC<MaintenanceViewProps> = ({
  onNavigate,
  onSelectAsset,
  onOpenLogMaintenance,
}) => {
  const [records, setRecords] = useState<MaintenanceRecord[]>([]);

  const loadData = async () => {
    const list = await assetRepository.getMaintenance();
    setRecords(list);
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleCompleteWorkOrder = async (id: string) => {
    await assetRepository.updateMaintenanceStatus(id, 'COMPLETED');
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
            <span className="text-slate-900 font-bold">Maintenance</span>
          </div>
          <h1 className="text-2xl font-bold text-slate-900">Maintenance & Overhaul Work Orders</h1>
          <p className="text-[13px] text-slate-500">
            Preventive, corrective, and inspection work orders with OEM contractor tracking.
          </p>
        </div>

        <button
          onClick={onOpenLogMaintenance}
          className="h-9 px-3.5 bg-[#00288e] text-white font-semibold text-[13px] rounded-lg shadow-xs hover:bg-[#1e40af] transition-all flex items-center gap-1.5 self-start md:self-auto"
        >
          <span className="material-symbols-outlined text-[18px]">add_circle</span>
          <span>Log Work Order</span>
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-white p-4 rounded-xl shadow-sm border border-slate-200/80">
          <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">Open Work Orders</span>
          <div className="text-2xl font-bold text-slate-900 mt-1">
            {records.filter(r => r.status !== 'COMPLETED').length} Active Orders
          </div>
        </div>
        <div className="bg-white p-4 rounded-xl shadow-sm border border-slate-200/80">
          <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">Overdue Service Alerts</span>
          <div className="text-2xl font-bold text-red-600 mt-1">
            {records.filter(r => r.status === 'OVERDUE').length} Overdue SLA
          </div>
        </div>
        <div className="bg-white p-4 rounded-xl shadow-sm border border-slate-200/80">
          <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">Committed Maintenance Budget</span>
          <div className="text-2xl font-mono font-bold text-[#00288e] mt-1">
            {formatNaira(records.reduce((sum, r) => sum + r.budget_cost, 0))}
          </div>
        </div>
      </div>

      <div className="space-y-3">
        {records.map(order => (
          <div
            key={order.id}
            className="bg-white rounded-xl shadow-sm border border-slate-200/80 p-5 flex flex-col md:flex-row md:items-center justify-between gap-4 hover:shadow-md transition-shadow"
          >
            <div className="space-y-1 flex-1">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-mono font-bold text-[#00288e] text-[14px]">
                  {order.work_order_no}
                </span>
                <span
                  className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase ${
                    order.status === 'OVERDUE'
                      ? 'bg-red-100 text-red-800'
                      : order.status === 'COMPLETED'
                      ? 'bg-emerald-100 text-emerald-800'
                      : 'bg-amber-100 text-amber-900'
                  }`}
                >
                  {order.status}
                </span>
                <span className="text-slate-400 text-[11px]">• {order.maintenance_type}</span>
              </div>

              <div className="flex items-center gap-2">
                <button
                  onClick={() => onSelectAsset(order.asset_id)}
                  className="font-bold text-slate-900 text-[15px] hover:text-[#00288e] transition-colors"
                >
                  {order.asset_tag} — {order.description}
                </button>
              </div>

              <div className="text-[12px] text-slate-600">
                <strong>Assigned Contractor:</strong> {order.vendor} • Scope: {order.work_scope}
              </div>
              <div className="text-[11px] text-slate-400">
                Start Date: {order.start_date} • Expected Completion: {order.expected_completion_date}
              </div>
            </div>

            <div className="flex items-center gap-3 shrink-0">
              <div className="text-right">
                <div className="font-mono font-bold text-slate-900 text-[14px]">
                  {formatNaira(order.budget_cost)}
                </div>
                <span className="text-[11px] text-slate-500">Approved Budget</span>
              </div>

              {order.status !== 'COMPLETED' && (
                <button
                  onClick={() => handleCompleteWorkOrder(order.id)}
                  className="px-3.5 py-1.5 bg-emerald-700 hover:bg-emerald-800 text-white text-[12px] font-semibold rounded-lg shadow-xs transition-colors"
                >
                  Complete Order
                </button>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
