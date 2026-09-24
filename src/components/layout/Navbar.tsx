/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 * AssetFlow Top Navigation Bar
 * Conforms to the Stitch enterprise prototype specifications.
 */

import React, { useState, useRef, useEffect } from 'react';
import { AssetFlowLogo } from '../common/AssetFlowLogo';

interface NavbarProps {
  onNavigate: (route: string) => void;
  onOpenQuickAction: (action: string) => void;
  globalSearch: string;
  setGlobalSearch: (s: string) => void;
}

export const Navbar: React.FC<NavbarProps> = ({
  onNavigate,
  onOpenQuickAction,
  globalSearch,
  setGlobalSearch,
}) => {
  const [actionsOpen, setActionsOpen] = useState(false);
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const actionsRef = useRef<HTMLDivElement>(null);
  const notifRef = useRef<HTMLDivElement>(null);
  const profileRef = useRef<HTMLDivElement>(null);

  // Close dropdowns on outside click
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (actionsRef.current && !actionsRef.current.contains(event.target as Node)) {
        setActionsOpen(false);
      }
      if (notifRef.current && !notifRef.current.contains(event.target as Node)) {
        setNotificationsOpen(false);
      }
      if (profileRef.current && !profileRef.current.contains(event.target as Node)) {
        setProfileOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Keyboard shortcut cmd+k
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        const searchInput = document.getElementById('global-search-input');
        if (searchInput) searchInput.focus();
      }
    }
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  return (
    <header className="fixed top-0 left-0 right-0 h-12 bg-white z-50 flex items-center justify-between px-3 md:px-4 border-b border-slate-200/80 shadow-[0_1px_4px_rgba(0,0,0,0.03)] select-none">
      {/* Brand Zone */}
      <div className="flex items-center gap-3 min-w-[280px]">
        <button
          onClick={() => onNavigate('dashboard')}
          className="flex items-center gap-2 text-left focus:outline-none group"
        >
          <AssetFlowLogo className="h-7 w-7 transition-transform group-hover:scale-105" />
          <span className="text-[17px] font-bold tracking-tight text-[#00288e]">
            AssetFlow
          </span>
        </button>

        <span className="hidden sm:inline-block px-1.5 py-0.5 rounded text-[10px] font-semibold uppercase bg-[#e5eeff] text-[#00288e] tracking-wider border border-[#d3e4fe]">
          Enterprise Edition
        </span>

        <div className="hidden xl:flex items-center gap-1.5 pl-2 border-l border-slate-200">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-600 animate-pulse"></span>
          <span className="text-[11px] text-[#444653] font-medium">Production (Lagos HQ)</span>
        </div>
      </div>

      {/* Global Search Center Input */}
      <div className="flex-1 max-w-xl px-2 md:px-4">
        <div className="relative flex items-center w-full">
          <span className="material-symbols-outlined absolute left-2.5 text-[18px] text-[#757684] pointer-events-none">
            search
          </span>
          <input
            id="global-search-input"
            value={globalSearch}
            onChange={(e) => setGlobalSearch(e.target.value)}
            onFocus={() => {
              if (window.location.hash !== '#all-assets') {
                // optionally switch to assets view if searching
              }
            }}
            className="w-full h-8 pl-8 pr-14 bg-[#eff4ff]/80 text-[13px] text-[#0b1c30] rounded-md placeholder:text-[#757684] focus:outline-none focus:bg-white focus:ring-1.5 focus:ring-[#00288e] border border-transparent focus:border-[#00288e] transition-all"
            placeholder="Search assets (tag, serial, model), custodians, PO numbers..."
            type="text"
          />
          <div className="absolute right-2 flex items-center gap-0.5">
            <kbd className="px-1.5 py-0.5 text-[10px] font-medium bg-[#d3e4fe]/60 text-[#444653] rounded border border-slate-300/50 shadow-2xs">
              ⌘K
            </kbd>
          </div>
        </div>
      </div>

      {/* Actions & Utilities Right Zone */}
      <div className="flex items-center gap-2 sm:gap-2.5">
        {/* Quick Actions Dropdown */}
        <div className="relative" ref={actionsRef}>
          <button
            onClick={() => setActionsOpen(!actionsOpen)}
            className="h-8 px-2.5 bg-[#00288e] text-white text-[12px] font-semibold rounded flex items-center gap-1 hover:bg-[#1e40af] transition-colors shadow-xs active:scale-[0.98]"
          >
            <span className="material-symbols-outlined text-[16px]">add</span>
            <span>Actions</span>
            <span className="material-symbols-outlined text-[16px]">
              {actionsOpen ? 'expand_less' : 'expand_more'}
            </span>
          </button>

          {actionsOpen && (
            <div className="absolute right-0 mt-1.5 w-56 bg-white rounded-lg shadow-xl border border-slate-200 py-1.5 z-50 text-[13px]">
              <div className="px-3 py-1 text-[10px] font-bold uppercase tracking-wider text-slate-400 border-b border-slate-100">
                Quick Lifecycle Workflows
              </div>
              <button
                onClick={() => {
                  setActionsOpen(false);
                  onNavigate('asset-create');
                }}
                className="w-full text-left px-3 py-2 flex items-center gap-2.5 text-slate-700 hover:bg-[#eff4ff] hover:text-[#00288e] transition-colors"
              >
                <span className="material-symbols-outlined text-[18px] text-[#00288e]">
                  add_circle
                </span>
                <div>
                  <div className="font-semibold text-slate-900 leading-tight">Register Fixed Asset</div>
                  <div className="text-[11px] text-slate-500">IAS 16 Capitalization Form</div>
                </div>
              </button>

              <button
                onClick={() => {
                  setActionsOpen(false);
                  onOpenQuickAction('transfer');
                }}
                className="w-full text-left px-3 py-2 flex items-center gap-2.5 text-slate-700 hover:bg-[#eff4ff] hover:text-[#00288e] transition-colors"
              >
                <span className="material-symbols-outlined text-[18px] text-blue-600">
                  swap_horiz
                </span>
                <div>
                  <div className="font-semibold text-slate-900 leading-tight">Initiate Transfer</div>
                  <div className="text-[11px] text-slate-500">Inter-Facility Redeployment</div>
                </div>
              </button>

              <button
                onClick={() => {
                  setActionsOpen(false);
                  onOpenQuickAction('maintenance');
                }}
                className="w-full text-left px-3 py-2 flex items-center gap-2.5 text-slate-700 hover:bg-[#eff4ff] hover:text-[#00288e] transition-colors"
              >
                <span className="material-symbols-outlined text-[18px] text-amber-600">
                  build
                </span>
                <div>
                  <div className="font-semibold text-slate-900 leading-tight">Log Maintenance</div>
                  <div className="text-[11px] text-slate-500">Preventive / Work Order</div>
                </div>
              </button>

              <button
                onClick={() => {
                  setActionsOpen(false);
                  onOpenQuickAction('disposal');
                }}
                className="w-full text-left px-3 py-2 flex items-center gap-2.5 text-slate-700 hover:bg-[#eff4ff] hover:text-[#00288e] transition-colors"
              >
                <span className="material-symbols-outlined text-[18px] text-rose-600">
                  archive
                </span>
                <div>
                  <div className="font-semibold text-slate-900 leading-tight">Disposal / Write-off</div>
                  <div className="text-[11px] text-slate-500">Impairment & Auction Board</div>
                </div>
              </button>
            </div>
          )}
        </div>

        <div className="h-4 w-px bg-slate-200 mx-0.5"></div>

        {/* Notifications Icon & Popover */}
        <div className="relative" ref={notifRef}>
          <button
            onClick={() => setNotificationsOpen(!notificationsOpen)}
            className="relative w-8 h-8 flex items-center justify-center rounded text-slate-600 hover:bg-[#eff4ff] hover:text-[#00288e] transition-colors"
            title="Notifications"
          >
            <span className="material-symbols-outlined text-[20px]">notifications</span>
            <span className="absolute top-1 right-1 w-4 h-4 bg-[#ba1a1a] text-white rounded-full text-[10px] font-bold flex items-center justify-center leading-none">
              3
            </span>
          </button>

          {notificationsOpen && (
            <div className="absolute right-0 mt-1.5 w-80 bg-white rounded-lg shadow-xl border border-slate-200 py-2 z-50 text-[13px]">
              <div className="px-3 pb-2 border-b border-slate-100 flex items-center justify-between">
                <span className="font-bold text-slate-900">Governance Alerts</span>
                <span className="px-1.5 py-0.2 bg-red-100 text-red-800 text-[10px] font-bold rounded">
                  3 Critical
                </span>
              </div>
              <div className="divide-y divide-slate-100 max-h-72 overflow-y-auto">
                <div
                  onClick={() => {
                    setNotificationsOpen(false);
                    onNavigate('asset-detail');
                  }}
                  className="p-3 hover:bg-slate-50 cursor-pointer transition-colors"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-[11px] font-bold text-red-600">AST-000002</span>
                    <span className="text-[10px] text-red-700 font-bold bg-red-50 px-1 rounded">
                      Overdue 2d
                    </span>
                  </div>
                  <div className="font-semibold text-slate-800 mt-0.5 text-[12px]">
                    CAT 336 Hydraulic Excavator Service
                  </div>
                  <div className="text-[11px] text-slate-500">Mantrac certified seal replacement delayed.</div>
                </div>

                <div
                  onClick={() => {
                    setNotificationsOpen(false);
                    onNavigate('transfers');
                  }}
                  className="p-3 hover:bg-slate-50 cursor-pointer transition-colors"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-[11px] font-bold text-blue-600">TRF-2025-0042</span>
                    <span className="text-[10px] text-blue-700 font-bold bg-blue-50 px-1 rounded">
                      In-Transit
                    </span>
                  </div>
                  <div className="font-semibold text-slate-800 mt-0.5 text-[12px]">
                    Komatsu WA380 Transfer to Port Harcourt
                  </div>
                  <div className="text-[11px] text-slate-500">Waybill #WB-WAR-2025-084 pending receipt.</div>
                </div>

                <div
                  onClick={() => {
                    setNotificationsOpen(false);
                    onNavigate('disposals');
                  }}
                  className="p-3 hover:bg-slate-50 cursor-pointer transition-colors"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-[11px] font-bold text-amber-600">AST-000088</span>
                    <span className="text-[10px] text-amber-800 font-bold bg-amber-50 px-1 rounded">
                      Approval Needed
                    </span>
                  </div>
                  <div className="font-semibold text-slate-800 mt-0.5 text-[12px]">
                    Ford Ranger Double Cabin (2017)
                  </div>
                  <div className="text-[11px] text-slate-500">NBV ₦2.1M submitted for auction signoff.</div>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Documentation / Help */}
        <button
          onClick={() => onNavigate('settings')}
          className="w-8 h-8 flex items-center justify-center rounded text-slate-600 hover:bg-[#eff4ff] hover:text-[#00288e] transition-colors"
          title="Documentation & Settings"
        >
          <span className="material-symbols-outlined text-[20px]">help</span>
        </button>

        <div className="h-4 w-px bg-slate-200 mx-0.5"></div>

        {/* User Profile Menu */}
        <div className="relative" ref={profileRef}>
          <button
            onClick={() => setProfileOpen(!profileOpen)}
            className="flex items-center gap-2 pl-1 pr-1.5 py-1 rounded hover:bg-[#eff4ff] transition-colors text-left"
          >
            <img
              alt="Babajide Adeleke"
              className="w-7 h-7 rounded-full object-cover ring-1 ring-slate-300"
              src="https://lh3.googleusercontent.com/aida-public/AB6AXuAQjfBsnhUaJsODwEIF9c0JR_abXkekvgOcDVi5SDEn9XwB2QLLVFL0I1mqW9ENZWMpBgmArkeKu5892aDBQ0yigfitDIhl9sqzrnljzIYp_0HXvxK7VK6ASuCN_XIy6kJYGz9kr8GcG810_r_gs-X88MTihb5Xc-ZVfmZ07aEHzm7G1sewQIAapXSeztpsj10RgiJMkHqoR5_q8ysDR0QiTJRFPX9t9WrYg57P33GZz-83I6HU8x-cTw"
            />
            <div className="hidden lg:flex flex-col text-left">
              <span className="text-[12px] font-bold text-slate-900 leading-tight">
                Babajide Adeleke
              </span>
              <span className="text-[10px] text-slate-500 leading-tight truncate max-w-[150px]">
                Head of Asset Accounting & Treasury
              </span>
            </div>
            <span className="material-symbols-outlined text-[16px] text-slate-500">
              expand_more
            </span>
          </button>

          {profileOpen && (
            <div className="absolute right-0 mt-1.5 w-64 bg-white rounded-lg shadow-xl border border-slate-200 py-2 z-50 text-[13px]">
              <div className="px-3 pb-2 border-b border-slate-100">
                <div className="font-bold text-slate-900">Babajide Adeleke</div>
                <div className="text-[11px] text-slate-500">b.adeleke@assetflow.ng</div>
                <div className="mt-1 flex items-center gap-1.5">
                  <span className="px-1.5 py-0.5 rounded text-[10px] font-bold uppercase bg-emerald-100 text-emerald-800">
                    Lead Administrator
                  </span>
                  <span className="text-[11px] text-slate-400">• Staff AF-FIN-001</span>
                </div>
              </div>

              <div className="py-1">
                <button
                  onClick={() => {
                    setProfileOpen(false);
                    onNavigate('users-and-roles');
                  }}
                  className="w-full text-left px-3 py-1.5 hover:bg-slate-50 flex items-center gap-2 text-slate-700"
                >
                  <span className="material-symbols-outlined text-[16px] text-slate-500">manage_accounts</span>
                  <span>Manage Users & Roles</span>
                </button>

                <button
                  onClick={() => {
                    setProfileOpen(false);
                    onNavigate('settings');
                  }}
                  className="w-full text-left px-3 py-1.5 hover:bg-slate-50 flex items-center gap-2 text-slate-700"
                >
                  <span className="material-symbols-outlined text-[16px] text-slate-500">settings</span>
                  <span>System Settings</span>
                </button>
              </div>

              <div className="pt-1 border-t border-slate-100">
                <div className="px-3 py-1 text-[11px] text-slate-400">
                  Active Facility: <strong className="text-slate-700">Lagos HQ (VI)</strong>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </header>
  );
};
