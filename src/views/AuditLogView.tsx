/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 * Immutable Historical Audit Log View
 */

import React, { useState, useEffect } from 'react';
import { AuditLogEntry } from '../types';
import { assetRepository } from '../services/assetRepository';

interface AuditLogViewProps {
  onNavigate: (route: string) => void;
  onSelectAsset?: (assetId: string) => void;
}

export const AuditLogView: React.FC<AuditLogViewProps> = ({ onNavigate }) => {
  const [logs, setLogs] = useState<AuditLogEntry[]>([]);
  const [search, setSearch] = useState('');
  const [selectedEntity, setSelectedEntity] = useState('ALL');

  const loadLogs = async () => {
    const list = await assetRepository.getAuditLogs({
      entity: selectedEntity,
      search,
    });
    setLogs(list);
  };

  useEffect(() => {
    loadLogs();
  }, [search, selectedEntity]);

  return (
    <div className="w-full p-4 md:p-6 select-text space-y-5">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-1.5 text-[12px] text-slate-500 mb-1">
            <span onClick={() => onNavigate('dashboard')} className="hover:text-[#00288e] cursor-pointer">Home</span>
            <span className="text-slate-300">/</span>
            <span className="text-slate-500">Governance</span>
            <span className="text-slate-300">/</span>
            <span className="text-slate-900 font-bold">Audit Log</span>
          </div>
          <h1 className="text-2xl font-bold text-slate-900">Immutable Audit Ledger (IAS 16)</h1>
          <p className="text-[13px] text-slate-500">
            Cryptographically sealed and tamper-evident transaction ledger tracking every capitalization, transfer, and maintenance event.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-50 text-emerald-800 text-[12px] font-bold border border-emerald-200/80">
            <span className="w-2 h-2 rounded-full bg-emerald-600 animate-pulse"></span>
            Ledger Immutable & Signed
          </span>
        </div>
      </div>

      {/* Filter toolbar */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200/80 p-4 flex flex-wrap items-center justify-between gap-3 text-[13px]">
        <div className="relative flex-1 max-w-md">
          <span className="material-symbols-outlined absolute left-3 top-2 text-[18px] text-slate-400">search</span>
          <input
            type="text"
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Search audit trail by keyword, asset tag, or user..."
            className="w-full h-9 pl-9 pr-3 bg-[#eff4ff]/60 text-slate-900 rounded-lg border border-slate-200 focus:outline-none focus:ring-1.5 focus:ring-[#00288e]"
          />
        </div>

        <div className="flex items-center gap-2">
          <span className="text-slate-500 font-semibold text-[12px]">Filter Entity:</span>
          <select
            value={selectedEntity}
            onChange={e => setSelectedEntity(e.target.value)}
            className="h-9 px-3 bg-[#eff4ff] text-slate-900 rounded-lg border border-slate-200 font-semibold focus:outline-none"
          >
            <option value="ALL">All Entities</option>
            <option value="ASSET">ASSET</option>
            <option value="TRANSFER">TRANSFER</option>
            <option value="MAINTENANCE">MAINTENANCE</option>
            <option value="DISPOSAL">DISPOSAL</option>
            <option value="CATEGORY">CATEGORY</option>
          </select>
        </div>
      </div>

      {/* Immutable Ledger Table */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200/80 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-[13px]">
            <thead className="bg-[#eff4ff] text-slate-600 text-[11px] font-bold uppercase tracking-wider border-b border-slate-200">
              <tr>
                <th className="py-2.5 px-3">Timestamp (WAT)</th>
                <th className="py-2.5 px-3">Authorized User</th>
                <th className="py-2.5 px-3">Action</th>
                <th className="py-2.5 px-3">Entity & Tag</th>
                <th className="py-2.5 px-3 min-w-[280px]">Audit Event Description</th>
                <th className="py-2.5 px-3">Previous State</th>
                <th className="py-2.5 px-3">Committed State</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {logs.map(entry => (
                <tr key={entry.id} className="hover:bg-[#eff4ff]/40 transition-colors">
                  <td className="py-3 px-3 font-mono text-[12px] text-slate-600 whitespace-nowrap">
                    {entry.timestamp}
                  </td>
                  <td className="py-3 px-3">
                    <div className="font-bold text-slate-900">{entry.user_name}</div>
                    <div className="text-[11px] text-slate-500">{entry.user_role}</div>
                  </td>
                  <td className="py-3 px-3">
                    <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase bg-[#00288e] text-white">
                      {entry.action}
                    </span>
                  </td>
                  <td className="py-3 px-3 whitespace-nowrap">
                    <div className="font-mono font-bold text-[#00288e]">
                      {entry.entity_tag || entry.entity_id}
                    </div>
                    <div className="text-[10px] text-slate-400 uppercase font-bold">{entry.entity}</div>
                  </td>
                  <td className="py-3 px-3 text-slate-800 font-medium">
                    {entry.description}
                  </td>
                  <td className="py-3 px-3 text-slate-500 font-mono text-[11px]">
                    {entry.previous_value || '—'}
                  </td>
                  <td className="py-3 px-3 text-emerald-800 font-mono text-[11px] font-bold">
                    {entry.new_value || 'Committed'}
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
