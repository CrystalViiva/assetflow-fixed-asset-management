/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 * Departments Registry View
 */

import React, { useState, useEffect } from 'react';
import { Department } from '../types';
import { assetRepository } from '../services/assetRepository';
import { formatNaira } from '../services/depreciationCalculator';

interface DepartmentsViewProps {
  onNavigate: (route: string) => void;
}

export const DepartmentsView: React.FC<DepartmentsViewProps> = ({ onNavigate }) => {
  const [departments, setDepartments] = useState<Department[]>([]);

  useEffect(() => {
    async function load() {
      const data = await assetRepository.getDepartments();
      setDepartments(data);
    }
    load();
  }, []);

  return (
    <div className="w-full p-4 md:p-6 select-text space-y-5">
      <div>
        <div className="flex items-center gap-1.5 text-[12px] text-slate-500 mb-1">
          <span onClick={() => onNavigate('dashboard')} className="hover:text-[#00288e] cursor-pointer">Home</span>
          <span className="text-slate-300">/</span>
          <span className="text-slate-500">Organization</span>
          <span className="text-slate-300">/</span>
          <span className="text-slate-900 font-bold">Departments</span>
        </div>
        <h1 className="text-2xl font-bold text-slate-900">Organizational Departments</h1>
        <p className="text-[13px] text-slate-500">
          Fixed asset allocation, cost centers, and departmental responsibility matrices.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {departments.map(dept => (
          <div
            key={dept.id}
            className="bg-white rounded-xl shadow-sm border border-slate-200/80 p-5 space-y-3 hover:shadow-md transition-shadow"
          >
            <div className="flex items-center justify-between">
              <span className="px-2 py-0.5 rounded text-[11px] font-mono font-bold bg-[#eff4ff] text-[#00288e] border border-blue-200">
                {dept.code}
              </span>
              <span className="text-[12px] font-bold text-slate-500">{dept.asset_count} Assets</span>
            </div>

            <h2 className="text-[16px] font-bold text-slate-900">{dept.name}</h2>

            <div className="p-3 bg-[#eff4ff]/60 rounded-lg text-[12px] space-y-1 border border-slate-200/60">
              <div className="text-slate-500 text-[10px] uppercase font-bold">Department Head</div>
              <div className="font-bold text-slate-900">{dept.head_name}</div>
              <div className="text-slate-500">{dept.email} • Staff ID: {dept.head_staff_id}</div>
            </div>

            <div className="pt-2 border-t border-slate-100 flex items-center justify-between text-[12px]">
              <div>
                <span className="text-slate-400 text-[10px] uppercase block font-bold">Capitalized Base</span>
                <span className="font-mono font-bold text-slate-800">{formatNaira(dept.total_cost)}</span>
              </div>
              <div className="text-right">
                <span className="text-slate-400 text-[10px] uppercase block font-bold">Net Carrying Value</span>
                <span className="font-mono font-bold text-emerald-800">{formatNaira(dept.total_nbv)}</span>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
