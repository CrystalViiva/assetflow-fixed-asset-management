/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 * Custody & Assignments Register View
 */

import React, { useState, useEffect } from 'react';
import { CustodyAssignment } from '../types';
import { assetRepository } from '../services/assetRepository';

interface AssignmentsViewProps {
  onNavigate: (route: string) => void;
  onSelectAsset: (assetId: string) => void;
}

export const AssignmentsView: React.FC<AssignmentsViewProps> = ({ onNavigate, onSelectAsset }) => {
  const [assignments, setAssignments] = useState<CustodyAssignment[]>([]);

  useEffect(() => {
    async function load() {
      const data = await assetRepository.getAssignments();
      setAssignments(data);
    }
    load();
  }, []);

  return (
    <div className="w-full p-4 md:p-6 select-text space-y-5">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-1.5 text-[12px] text-slate-500 mb-1">
            <span onClick={() => onNavigate('dashboard')} className="hover:text-[#00288e] cursor-pointer">Home</span>
            <span className="text-slate-300">/</span>
            <span className="text-slate-500">Assets</span>
            <span className="text-slate-300">/</span>
            <span className="text-slate-900 font-bold">Assignments</span>
          </div>
          <h1 className="text-2xl font-bold text-slate-900">Custody & Fiduciary Register</h1>
          <p className="text-[13px] text-slate-500">
            Designated asset custodians, signed custody acknowledgments, and physical verifications.
          </p>
        </div>

        <button
          onClick={() => alert('Custody Assignment reassignment wizard')}
          className="h-9 px-3.5 bg-[#00288e] text-white font-semibold text-[13px] rounded-lg shadow-xs hover:bg-[#1e40af] transition-all flex items-center gap-1.5 self-start md:self-auto"
        >
          <span className="material-symbols-outlined text-[18px]">person_add</span>
          <span>Assign Custodian</span>
        </button>
      </div>

      <div className="bg-white rounded-xl shadow-sm border border-slate-200/80 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-[13px]">
            <thead className="bg-[#eff4ff] text-slate-600 text-[11px] font-bold uppercase tracking-wider border-b border-slate-200">
              <tr>
                <th className="py-2.5 px-3">Asset Tag</th>
                <th className="py-2.5 px-3">Asset Name</th>
                <th className="py-2.5 px-3">Custodian Name</th>
                <th className="py-2.5 px-3">Staff ID</th>
                <th className="py-2.5 px-3">Department & Location</th>
                <th className="py-2.5 px-3">Handover Date</th>
                <th className="py-2.5 px-3 text-center">Fiduciary Acknowledgment</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {assignments.map(a => (
                <tr
                  key={a.id}
                  onClick={() => onSelectAsset(a.asset_id)}
                  className="hover:bg-[#eff4ff]/60 transition-colors cursor-pointer"
                >
                  <td className="py-3 px-3 font-mono font-bold text-[#00288e]">{a.asset_tag}</td>
                  <td className="py-3 px-3 font-semibold text-slate-900">{a.asset_name}</td>
                  <td className="py-3 px-3">
                    <div className="font-bold text-slate-900">{a.custodian_name}</div>
                    <div className="text-[11px] text-slate-500">{a.custodian_title}</div>
                  </td>
                  <td className="py-3 px-3 font-mono text-slate-600">{a.custodian_staff_id}</td>
                  <td className="py-3 px-3">
                    <div className="text-slate-900 font-medium">{a.department_name}</div>
                    <div className="text-[11px] text-slate-500">{a.location_name}</div>
                  </td>
                  <td className="py-3 px-3 font-mono text-slate-600">{a.assigned_date}</td>
                  <td className="py-3 px-3 text-center">
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-bold bg-emerald-100 text-emerald-800">
                      <span className="material-symbols-outlined text-[14px]">verified</span>
                      Signed Acknowledgment
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
