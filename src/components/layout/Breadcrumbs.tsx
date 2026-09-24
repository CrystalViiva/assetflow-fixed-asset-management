/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 * Context Breadcrumbs Sub-Header with Live Time
 */

import React, { useState, useEffect } from 'react';

interface BreadcrumbsProps {
  currentRoute: string;
  subTitle?: string;
  onNavigate: (route: string) => void;
}

export const Breadcrumbs: React.FC<BreadcrumbsProps> = ({ currentRoute, subTitle, onNavigate }) => {
  const [timeStr, setTimeStr] = useState('');

  useEffect(() => {
    function updateClock() {
      const now = new Date();
      // Format as "Oct 24, 2025 14:32:08 WAT"
      const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
      const month = months[now.getMonth()];
      const day = String(now.getDate()).padStart(2, '0');
      const year = now.getFullYear();
      const hours = String(now.getHours()).padStart(2, '0');
      const mins = String(now.getMinutes()).padStart(2, '0');
      const secs = String(now.getSeconds()).padStart(2, '0');
      setTimeStr(`${month} ${day}, ${year} ${hours}:${mins}:${secs} WAT`);
    }
    updateClock();
    const timer = setInterval(updateClock, 1000);
    return () => clearInterval(timer);
  }, []);

  const getRouteLabel = () => {
    switch (currentRoute) {
      case 'dashboard':
        return 'Executive Asset Dashboard';
      case 'all-assets':
        return 'Asset Register';
      case 'asset-detail':
        return subTitle || 'Asset Detail View';
      case 'asset-create':
        return 'Register New Asset';
      case 'asset-categories':
        return 'Asset Classification & Master Categories';
      case 'acquisitions':
        return 'Capex & Acquisitions Ledger';
      case 'transfers':
        return 'Inter-Facility Transfers & Movements';
      case 'assignments':
        return 'Asset Custody & Assignment Register';
      case 'depreciation':
        return 'Statutory Depreciation Engine (IAS 16)';
      case 'maintenance':
        return 'Maintenance & Overhaul Work Orders';
      case 'disposals':
        return 'Disposal Governance & Impairment Board';
      case 'reports':
        return 'Institutional Financial Reports Center';
      case 'departments':
        return 'Organizational Departments';
      case 'locations':
        return 'Nigerian Operational Hubs';
      case 'users-and-roles':
        return 'Users, Roles & RBAC Matrix';
      case 'audit-log':
        return 'Immutable Audit Ledger';
      case 'settings':
        return 'System & Accounting Configuration';
      default:
        return 'Active Ledger View';
    }
  };

  return (
    <div className="w-full px-4 md:px-6 py-2 bg-white flex flex-wrap items-center justify-between border-b border-slate-200/80 shadow-[0_1px_2px_rgba(0,0,0,0.02)] text-[12px] select-none">
      <div className="flex items-center gap-1.5 text-slate-500 font-medium">
        <span className="material-symbols-outlined text-[16px] text-[#00288e]">domain</span>
        <span
          onClick={() => onNavigate('locations')}
          className="hover:text-slate-800 cursor-pointer transition-colors"
        >
          Lagos Corporate Facility
        </span>
        <span className="text-slate-300">/</span>
        <span
          onClick={() => onNavigate('dashboard')}
          className="hover:text-slate-800 cursor-pointer transition-colors"
        >
          Treasury & Asset Accounting
        </span>
        <span className="text-slate-300">/</span>
        <span className="text-slate-900 font-semibold">{getRouteLabel()}</span>
      </div>

      <div className="flex items-center gap-1.5 text-slate-500">
        <span className="material-symbols-outlined text-[14px] text-slate-400">schedule</span>
        <span>
          As of:{' '}
          <span className="font-mono font-medium text-slate-800">
            {timeStr || 'Oct 24, 2025 14:32:08 WAT'}
          </span>
        </span>
      </div>
    </div>
  );
};
