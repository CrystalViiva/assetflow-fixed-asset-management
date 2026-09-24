/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 * Users & Roles RBAC Matrix View
 */

import React, { useState, useEffect } from 'react';
import { UserProfile } from '../types';
import { assetRepository } from '../services/assetRepository';

interface UsersRolesViewProps {
  onNavigate: (route: string) => void;
}

export const UsersRolesView: React.FC<UsersRolesViewProps> = ({ onNavigate }) => {
  const [users, setUsers] = useState<UserProfile[]>([]);

  useEffect(() => {
    async function load() {
      const u = await assetRepository.getUsers();
      setUsers(u);
    }
    load();
  }, []);

  const rolesMatrix = [
    { role: 'Administrator', desc: 'Full control over capitalization, accounting parameters, user roles, and system configuration.', users: '1 User' },
    { role: 'Asset Manager', desc: 'Can create assets, authorize inter-facility transfers, schedule maintenance, and update telematics.', users: '3 Users' },
    { role: 'Accountant', desc: 'Can view ledgers, trigger depreciation posting schedules, verify journal entries, and run financial audits.', users: '2 Users' },
    { role: 'Department Manager', desc: 'Departmental custodian management, initiates asset transfers, and signs off verification checklists.', users: '6 Users' },
    { role: 'Employee', desc: 'View assigned assets, counter-sign physical handover acknowledgments, and report maintenance issues.', users: '42 Users' },
  ];

  return (
    <div className="w-full p-4 md:p-6 select-text space-y-6">
      <div>
        <div className="flex items-center gap-1.5 text-[12px] text-slate-500 mb-1">
          <span onClick={() => onNavigate('dashboard')} className="hover:text-[#00288e] cursor-pointer">Home</span>
          <span className="text-slate-300">/</span>
          <span className="text-slate-500">Administration</span>
          <span className="text-slate-300">/</span>
          <span className="text-slate-900 font-bold">Users & Roles</span>
        </div>
        <h1 className="text-2xl font-bold text-slate-900">Users & Role-Based Access Control (RBAC)</h1>
        <p className="text-[13px] text-slate-500">
          Enforces separation of duties across asset acquisition, custody, accounting, and write-off authorizations.
        </p>
      </div>

      {/* Role Definitions */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200/80 p-5 space-y-3">
        <h2 className="text-[16px] font-bold text-slate-900">Governance Role Hierarchy</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3 text-[13px]">
          {rolesMatrix.map(r => (
            <div key={r.role} className="p-3 bg-[#eff4ff]/60 rounded-lg border border-slate-200/80 space-y-1">
              <div className="flex items-center justify-between">
                <span className="font-bold text-[#00288e]">{r.role}</span>
                <span className="text-[11px] font-bold text-slate-500">{r.users}</span>
              </div>
              <p className="text-[11px] text-slate-600 leading-relaxed">{r.desc}</p>
            </div>
          ))}
        </div>
      </div>

      {/* User Accounts Table */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200/80 overflow-hidden">
        <div className="px-5 py-3.5 bg-[#eff4ff] border-b border-slate-200 flex items-center justify-between">
          <h2 className="text-[15px] font-bold text-slate-900">Active Authorized Personnel</h2>
          <button
            onClick={() => alert('Invite user modal')}
            className="h-8 px-3 bg-[#00288e] text-white text-[12px] font-semibold rounded-md hover:bg-[#1e40af] flex items-center gap-1"
          >
            <span className="material-symbols-outlined text-[16px]">person_add</span>
            <span>Invite User</span>
          </button>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-[13px]">
            <thead className="bg-[#eff4ff]/60 text-slate-600 text-[11px] font-bold uppercase tracking-wider border-b border-slate-200">
              <tr>
                <th className="py-2.5 px-4">User</th>
                <th className="py-2.5 px-4">Staff ID</th>
                <th className="py-2.5 px-4">Role</th>
                <th className="py-2.5 px-4">Department</th>
                <th className="py-2.5 px-4">Operating Base</th>
                <th className="py-2.5 px-4 text-center">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {users.map(u => (
                <tr key={u.id} className="hover:bg-slate-50">
                  <td className="py-3 px-4 flex items-center gap-2.5">
                    <img
                      src={u.avatar_url || 'https://lh3.googleusercontent.com/aida-public/AB6AXuAQjfBsnhUaJsODwEIF9c0JR_abXkekvgOcDVi5SDEn9XwB2QLLVFL0I1mqW9ENZWMpBgmArkeKu5892aDBQ0yigfitDIhl9sqzrnljzIYp_0HXvxK7VK6ASuCN_XIy6kJYGz9kr8GcG810_r_gs-X88MTihb5Xc-ZVfmZ07aEHzm7G1sewQIAapXSeztpsj10RgiJMkHqoR5_q8ysDR0QiTJRFPX9t9WrYg57P33GZz-83I6HU8x-cTw'}
                      alt={u.name}
                      className="w-8 h-8 rounded-full object-cover ring-1 ring-slate-200"
                    />
                    <div>
                      <div className="font-bold text-slate-900">{u.name}</div>
                      <div className="text-[11px] text-slate-500">{u.email}</div>
                    </div>
                  </td>
                  <td className="py-3 px-4 font-mono font-semibold text-slate-700">{u.staff_id}</td>
                  <td className="py-3 px-4">
                    <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-[#eff4ff] text-[#00288e] border border-blue-200">
                      {u.role.replace('_', ' ')}
                    </span>
                  </td>
                  <td className="py-3 px-4 text-slate-700">{u.department_name}</td>
                  <td className="py-3 px-4 text-slate-700">{u.location_name}</td>
                  <td className="py-3 px-4 text-center">
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-bold bg-emerald-100 text-emerald-800">
                      Active
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
