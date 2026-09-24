/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 * AssetFlow Enterprise Navigation Sidebar
 * Conforms to the Stitch visual hierarchy and design.
 */

import React, { useState } from 'react';

interface SidebarProps {
  currentRoute: string;
  onNavigate: (route: string) => void;
  isCollapsed: boolean;
  onToggleCollapse: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  currentRoute,
  onNavigate,
  isCollapsed,
  onToggleCollapse,
}) => {
  const [assetsOpen, setAssetsOpen] = useState(true);
  const [orgOpen, setOrgOpen] = useState(false);

  const isActive = (route: string) => currentRoute === route;

  return (
    <aside
      className={`fixed left-0 top-12 bottom-0 bg-white z-40 flex flex-col justify-between border-r border-slate-200/80 shadow-[0_1px_4px_rgba(0,0,0,0.02)] select-none transition-all duration-200 ${
        isCollapsed ? 'w-16' : 'w-64'
      }`}
    >
      {/* Scrollable Navigation Items */}
      <div className="flex-1 overflow-y-auto py-2 px-1.5 space-y-3">
        {/* MAIN SECTION */}
        <div>
          {!isCollapsed && (
            <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400 px-2.5 mb-1">
              MAIN
            </div>
          )}
          <button
            onClick={() => onNavigate('dashboard')}
            title="Dashboard"
            className={`w-full flex items-center gap-2.5 px-2.5 py-1.5 rounded transition-colors text-[13px] ${
              isActive('dashboard')
                ? 'bg-[#00288e] text-white font-semibold shadow-xs'
                : 'text-slate-600 hover:bg-[#eff4ff] hover:text-[#00288e]'
            }`}
          >
            <span className="material-symbols-outlined text-[18px]">grid_view</span>
            {!isCollapsed && <span>Dashboard</span>}
          </button>
        </div>

        {/* ASSET LIFECYCLE SECTION */}
        <div>
          {!isCollapsed && (
            <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400 px-2.5 mb-1">
              ASSET LIFECYCLE
            </div>
          )}
          <div className="space-y-0.5">
            {/* Assets Accordion Header */}
            {!isCollapsed ? (
              <div>
                <button
                  onClick={() => setAssetsOpen(!assetsOpen)}
                  className="w-full flex items-center justify-between px-2.5 py-1.5 text-[13px] text-slate-600 hover:bg-[#eff4ff] hover:text-[#00288e] rounded transition-colors"
                >
                  <div className="flex items-center gap-2.5">
                    <span className="material-symbols-outlined text-[18px]">inventory_2</span>
                    <span>Assets</span>
                  </div>
                  <span className="material-symbols-outlined text-[16px] text-slate-400">
                    {assetsOpen ? 'expand_less' : 'expand_more'}
                  </span>
                </button>

                {/* Submenu items */}
                {assetsOpen && (
                  <div className="pl-6 pr-1 space-y-0.5 mt-0.5">
                    <button
                      onClick={() => onNavigate('all-assets')}
                      className={`w-full flex items-center justify-between px-2.5 py-1 rounded text-[13px] transition-colors ${
                        isActive('all-assets') || isActive('asset-detail')
                          ? 'bg-[#00288e] text-white font-semibold'
                          : 'text-slate-600 hover:bg-[#eff4ff] hover:text-[#00288e]'
                      }`}
                    >
                      <span>All Assets</span>
                      <span
                        className={`px-1.5 py-0.2 rounded text-[10px] font-bold ${
                          isActive('all-assets')
                            ? 'bg-blue-800 text-white'
                            : 'bg-[#dce9ff] text-[#00288e]'
                        }`}
                      >
                        1,284
                      </span>
                    </button>

                    <button
                      onClick={() => onNavigate('asset-categories')}
                      className={`w-full flex items-center px-2.5 py-1 rounded text-[13px] transition-colors ${
                        isActive('asset-categories')
                          ? 'bg-[#00288e] text-white font-semibold'
                          : 'text-slate-600 hover:bg-[#eff4ff] hover:text-[#00288e]'
                      }`}
                    >
                      <span>Asset Categories</span>
                    </button>

                    <button
                      onClick={() => onNavigate('acquisitions')}
                      className={`w-full flex items-center px-2.5 py-1 rounded text-[13px] transition-colors ${
                        isActive('acquisitions') || isActive('asset-create')
                          ? 'bg-[#00288e] text-white font-semibold'
                          : 'text-slate-600 hover:bg-[#eff4ff] hover:text-[#00288e]'
                      }`}
                    >
                      <span>Acquisitions</span>
                    </button>

                    <button
                      onClick={() => onNavigate('transfers')}
                      className={`w-full flex items-center justify-between px-2.5 py-1 rounded text-[13px] transition-colors ${
                        isActive('transfers')
                          ? 'bg-[#00288e] text-white font-semibold'
                          : 'text-slate-600 hover:bg-[#eff4ff] hover:text-[#00288e]'
                      }`}
                    >
                      <span>Transfers</span>
                      <span className="px-1.5 py-0.2 rounded text-[10px] font-bold bg-[#ffdad6] text-[#93000a]">
                        4 pending
                      </span>
                    </button>

                    <button
                      onClick={() => onNavigate('assignments')}
                      className={`w-full flex items-center px-2.5 py-1 rounded text-[13px] transition-colors ${
                        isActive('assignments')
                          ? 'bg-[#00288e] text-white font-semibold'
                          : 'text-slate-600 hover:bg-[#eff4ff] hover:text-[#00288e]'
                      }`}
                    >
                      <span>Assignments</span>
                    </button>
                  </div>
                )}
              </div>
            ) : (
              <button
                onClick={() => onNavigate('all-assets')}
                title="All Assets"
                className={`w-full flex items-center justify-center p-2 rounded text-[13px] ${
                  isActive('all-assets') ? 'bg-[#00288e] text-white' : 'text-slate-600 hover:bg-[#eff4ff]'
                }`}
              >
                <span className="material-symbols-outlined text-[18px]">inventory_2</span>
              </button>
            )}

            {/* Depreciation */}
            <button
              onClick={() => onNavigate('depreciation')}
              title="Depreciation"
              className={`w-full flex items-center gap-2.5 px-2.5 py-1.5 rounded transition-colors text-[13px] ${
                isActive('depreciation')
                  ? 'bg-[#00288e] text-white font-semibold'
                  : 'text-slate-600 hover:bg-[#eff4ff] hover:text-[#00288e]'
              }`}
            >
              <span className="material-symbols-outlined text-[18px]">calculate</span>
              {!isCollapsed && <span>Depreciation</span>}
            </button>

            {/* Maintenance */}
            <button
              onClick={() => onNavigate('maintenance')}
              title="Maintenance"
              className={`w-full flex items-center justify-between px-2.5 py-1.5 rounded transition-colors text-[13px] ${
                isActive('maintenance')
                  ? 'bg-[#00288e] text-white font-semibold'
                  : 'text-slate-600 hover:bg-[#eff4ff] hover:text-[#00288e]'
              }`}
            >
              <div className="flex items-center gap-2.5">
                <span className="material-symbols-outlined text-[18px]">build</span>
                {!isCollapsed && <span>Maintenance</span>}
              </div>
              {!isCollapsed && (
                <span className="px-1.5 py-0.2 rounded text-[10px] font-bold bg-[#ffdad6] text-[#93000a]">
                  2 overdue
                </span>
              )}
            </button>

            {/* Disposals */}
            <button
              onClick={() => onNavigate('disposals')}
              title="Disposals"
              className={`w-full flex items-center gap-2.5 px-2.5 py-1.5 rounded transition-colors text-[13px] ${
                isActive('disposals')
                  ? 'bg-[#00288e] text-white font-semibold'
                  : 'text-slate-600 hover:bg-[#eff4ff] hover:text-[#00288e]'
              }`}
            >
              <span className="material-symbols-outlined text-[18px]">archive</span>
              {!isCollapsed && <span>Disposals</span>}
            </button>
          </div>
        </div>

        {/* INSIGHTS & GOVERNANCE */}
        <div>
          {!isCollapsed && (
            <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400 px-2.5 mb-1">
              INSIGHTS & GOVERNANCE
            </div>
          )}
          <div className="space-y-0.5">
            <button
              onClick={() => onNavigate('reports')}
              title="Reports"
              className={`w-full flex items-center gap-2.5 px-2.5 py-1.5 rounded transition-colors text-[13px] ${
                isActive('reports')
                  ? 'bg-[#00288e] text-white font-semibold'
                  : 'text-slate-600 hover:bg-[#eff4ff] hover:text-[#00288e]'
              }`}
            >
              <span className="material-symbols-outlined text-[18px]">bar_chart</span>
              {!isCollapsed && <span>Reports</span>}
            </button>

            <button
              onClick={() => onNavigate('audit-log')}
              title="Audit Log"
              className={`w-full flex items-center gap-2.5 px-2.5 py-1.5 rounded transition-colors text-[13px] ${
                isActive('audit-log')
                  ? 'bg-[#00288e] text-white font-semibold'
                  : 'text-slate-600 hover:bg-[#eff4ff] hover:text-[#00288e]'
              }`}
            >
              <span className="material-symbols-outlined text-[18px]">verified_user</span>
              {!isCollapsed && <span>Audit Log</span>}
            </button>
          </div>
        </div>

        {/* ADMINISTRATION */}
        <div>
          {!isCollapsed && (
            <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400 px-2.5 mb-1">
              ADMINISTRATION
            </div>
          )}
          <div className="space-y-0.5">
            {!isCollapsed ? (
              <div>
                <button
                  onClick={() => setOrgOpen(!orgOpen)}
                  className="w-full flex items-center justify-between px-2.5 py-1.5 text-[13px] text-slate-600 hover:bg-[#eff4ff] hover:text-[#00288e] rounded transition-colors"
                >
                  <div className="flex items-center gap-2.5">
                    <span className="material-symbols-outlined text-[18px]">apartment</span>
                    <span>Organization</span>
                  </div>
                  <span className="material-symbols-outlined text-[16px] text-slate-400">
                    {orgOpen ? 'expand_less' : 'expand_more'}
                  </span>
                </button>

                {orgOpen && (
                  <div className="pl-6 pr-1 space-y-0.5 mt-0.5">
                    <button
                      onClick={() => onNavigate('departments')}
                      className={`w-full flex items-center px-2.5 py-1 rounded text-[13px] transition-colors ${
                        isActive('departments')
                          ? 'bg-[#00288e] text-white font-semibold'
                          : 'text-slate-600 hover:bg-[#eff4ff] hover:text-[#00288e]'
                      }`}
                    >
                      <span>Departments</span>
                    </button>

                    <button
                      onClick={() => onNavigate('locations')}
                      className={`w-full flex items-center px-2.5 py-1 rounded text-[13px] transition-colors ${
                        isActive('locations')
                          ? 'bg-[#00288e] text-white font-semibold'
                          : 'text-slate-600 hover:bg-[#eff4ff] hover:text-[#00288e]'
                      }`}
                    >
                      <span>Locations</span>
                    </button>

                    <button
                      onClick={() => onNavigate('users-and-roles')}
                      className={`w-full flex items-center px-2.5 py-1 rounded text-[13px] transition-colors ${
                        isActive('users-and-roles')
                          ? 'bg-[#00288e] text-white font-semibold'
                          : 'text-slate-600 hover:bg-[#eff4ff] hover:text-[#00288e]'
                      }`}
                    >
                      <span>Users & Roles</span>
                    </button>
                  </div>
                )}
              </div>
            ) : (
              <button
                onClick={() => onNavigate('departments')}
                title="Organization"
                className="w-full flex items-center justify-center p-2 rounded text-slate-600 hover:bg-[#eff4ff]"
              >
                <span className="material-symbols-outlined text-[18px]">apartment</span>
              </button>
            )}

            <button
              onClick={() => onNavigate('settings')}
              title="Settings"
              className={`w-full flex items-center gap-2.5 px-2.5 py-1.5 rounded transition-colors text-[13px] ${
                isActive('settings')
                  ? 'bg-[#00288e] text-white font-semibold'
                  : 'text-slate-600 hover:bg-[#eff4ff] hover:text-[#00288e]'
              }`}
            >
              <span className="material-symbols-outlined text-[18px]">tune</span>
              {!isCollapsed && <span>Settings</span>}
            </button>
          </div>
        </div>
      </div>

      {/* Bottom Period & Base Currency Panel */}
      {!isCollapsed ? (
        <div className="p-2 bg-[#eff4ff]/80 border-t border-slate-200">
          <div className="flex items-center justify-between px-2 py-1 rounded bg-white text-[11px] mb-1 border border-slate-200/60 shadow-2xs">
            <span className="text-slate-500 font-medium">Period:</span>
            <span className="text-emerald-700 font-bold">FY 2025 - Q1 Active</span>
          </div>

          <div className="flex items-center justify-between px-2 py-1 rounded bg-white text-[11px] mb-2 border border-slate-200/60 shadow-2xs">
            <span className="text-slate-500 font-medium">Base Currency:</span>
            <span className="font-mono font-bold text-slate-900">NGN (₦)</span>
          </div>

          <button
            onClick={onToggleCollapse}
            className="w-full flex items-center justify-center gap-1.5 py-1 text-[11px] text-slate-600 hover:bg-slate-200/60 rounded transition-colors"
            title="Collapse navigation panel"
          >
            <span className="material-symbols-outlined text-[16px]">keyboard_double_arrow_left</span>
            <span className="font-semibold">Collapse Sidebar</span>
          </button>
        </div>
      ) : (
        <div className="p-2 border-t border-slate-200 flex justify-center">
          <button
            onClick={onToggleCollapse}
            className="p-1.5 text-slate-500 hover:bg-slate-100 rounded"
            title="Expand Sidebar"
          >
            <span className="material-symbols-outlined text-[18px]">keyboard_double_arrow_right</span>
          </button>
        </div>
      )}
    </aside>
  );
};
