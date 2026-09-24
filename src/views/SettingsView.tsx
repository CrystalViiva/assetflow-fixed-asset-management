/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 * Settings & Django REST Framework Integration Architecture View
 */

import React, { useState, useEffect } from 'react';
import { SystemSettings } from '../types';
import { assetRepository } from '../services/assetRepository';
import { formatNaira } from '../services/depreciationCalculator';

interface SettingsViewProps {
  onNavigate: (route: string) => void;
}

export const SettingsView: React.FC<SettingsViewProps> = ({ onNavigate }) => {
  const [settings, setSettings] = useState<SystemSettings | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    async function load() {
      const s = await assetRepository.getSettings();
      setSettings(s);
    }
    load();
  }, []);

  const [showConfirmReset, setShowConfirmReset] = useState(false);
  const [resetMessage, setResetMessage] = useState<string | null>(null);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!settings) return;
    await assetRepository.updateSettings(settings);
    setSaved(true);
    setTimeout(() => setSaved(false), 2500);
  };

  const handleConfirmReset = async () => {
    await assetRepository.resetToDefaultData();
    setShowConfirmReset(false);
    setResetMessage('Ledger database has been reset to baseline enterprise data. Reloading application view...');
    setTimeout(() => {
      window.location.reload();
    }, 1500);
  };

  if (!settings) return null;

  return (
    <div className="w-full p-4 md:p-6 select-text space-y-6 max-w-5xl">
      <div>
        <div className="flex items-center gap-1.5 text-[12px] text-slate-500 mb-1">
          <span onClick={() => onNavigate('dashboard')} className="hover:text-[#00288e] cursor-pointer">Home</span>
          <span className="text-slate-300">/</span>
          <span className="text-slate-500">Administration</span>
          <span className="text-slate-300">/</span>
          <span className="text-slate-900 font-bold">Settings</span>
        </div>
        <h1 className="text-2xl font-bold text-slate-900">System & Accounting Configuration</h1>
        <p className="text-[13px] text-slate-500">
          IAS 16 capitalization policies, statutory thresholds, currency rules, and future Django REST Framework API gateway.
        </p>
      </div>

      {saved && (
        <div className="p-3 bg-emerald-50 border border-emerald-200 text-emerald-800 rounded-lg text-[13px] font-semibold flex items-center gap-2">
          <span className="material-symbols-outlined text-[18px] text-emerald-600">check_circle</span>
          <span>Configuration saved successfully!</span>
        </div>
      )}

      <form onSubmit={handleSave} className="space-y-6">
        {/* Accounting Policy Parameters */}
        <div className="bg-white rounded-xl shadow-sm border border-slate-200/80 p-5 space-y-4">
          <h2 className="text-[16px] font-bold text-slate-900 pb-2 border-b border-slate-100 flex items-center gap-2">
            <span className="material-symbols-outlined text-[#00288e] text-[20px]">account_balance</span>
            <span>Accounting Policies & Capitalization Thresholds</span>
          </h2>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-[13px]">
            <div>
              <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-500 mb-1">
                Capitalization Monetary Threshold (₦)
              </label>
              <input
                type="number"
                value={settings.capitalization_threshold}
                onChange={e => setSettings({ ...settings, capitalization_threshold: parseFloat(e.target.value) || 0 })}
                className="w-full h-9 px-3 bg-[#eff4ff] text-slate-900 font-mono font-bold rounded-md border border-slate-200 focus:ring-1.5 focus:ring-[#00288e]"
              />
              <span className="text-[11px] text-slate-500 mt-0.5 block">
                Items below {formatNaira(settings.capitalization_threshold)} are expensed as operational costs rather than capitalized.
              </span>
            </div>

            <div>
              <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-500 mb-1">
                Default Depreciation Convention
              </label>
              <select
                value={settings.default_depreciation_method}
                onChange={e => setSettings({ ...settings, default_depreciation_method: e.target.value as any })}
                className="w-full h-9 px-3 bg-[#eff4ff] text-slate-900 font-semibold rounded-md border border-slate-200 focus:ring-1.5 focus:ring-[#00288e]"
              >
                <option value="SLM">Straight Line Method (SLM) - IAS 16</option>
                <option value="RBM">Reducing Balance Method (20% DBM)</option>
              </select>
            </div>

            <div>
              <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-500 mb-1">
                Default Salvage / Residual Rate (%)
              </label>
              <input
                type="number"
                value={settings.default_residual_rate_pct}
                onChange={e => setSettings({ ...settings, default_residual_rate_pct: parseFloat(e.target.value) || 0 })}
                className="w-full h-9 px-3 bg-[#eff4ff] text-slate-900 font-mono rounded-md border border-slate-200 focus:ring-1.5 focus:ring-[#00288e]"
              />
            </div>

            <div>
              <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-500 mb-1">
                Base Operating Currency
              </label>
              <input
                type="text"
                value={`${settings.currency} (${settings.currency_symbol})`}
                disabled
                className="w-full h-9 px-3 bg-slate-100 text-slate-600 font-mono font-bold rounded-md border border-slate-200 cursor-not-allowed"
              />
            </div>

            <div>
              <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-500 mb-1">
                Corporate Entity Name
              </label>
              <input
                type="text"
                value={settings.company_name}
                onChange={e => setSettings({ ...settings, company_name: e.target.value })}
                className="w-full h-9 px-3 bg-[#eff4ff] text-slate-900 rounded-md border border-slate-200 focus:ring-1.5 focus:ring-[#00288e]"
              />
            </div>

            <div>
              <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-500 mb-1">
                Appointed Statutory Auditor
              </label>
              <input
                type="text"
                value={settings.audit_firm}
                onChange={e => setSettings({ ...settings, audit_firm: e.target.value })}
                className="w-full h-9 px-3 bg-[#eff4ff] text-slate-900 rounded-md border border-slate-200 focus:ring-1.5 focus:ring-[#00288e]"
              />
            </div>
          </div>
        </div>

        {/* Django REST Framework & Future Architecture Card */}
        <div className="bg-white rounded-xl shadow-sm border border-slate-200/80 p-5 space-y-4">
          <div className="flex items-center justify-between pb-2 border-b border-slate-100">
            <div className="flex items-center gap-2">
              <span className="material-symbols-outlined text-emerald-700 text-[20px]">dataset</span>
              <div>
                <h2 className="text-[16px] font-bold text-slate-900">
                  Django REST Framework + PostgreSQL Architecture
                </h2>
                <p className="text-[11px] text-slate-500">
                  Separation of Concerns: Data access layer is completely decoupled via IAssetRepository.
                </p>
              </div>
            </div>
            <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase bg-emerald-100 text-emerald-800">
              Architecture Ready
            </span>
          </div>

          <div className="p-4 bg-slate-900 text-slate-200 rounded-lg font-mono text-[12px] space-y-2 overflow-x-auto">
            <div className="text-emerald-400 font-bold"># DRF Production Endpoint Mappings:</div>
            <div>GET  /api/v1/assets/                     -&gt; FixedAssetListCreateAPIView</div>
            <div>POST /api/v1/assets/                     -&gt; FixedAssetCapitalizeSerializer</div>
            <div>GET  /api/v1/transfers/                  -&gt; AssetTransferViewSet</div>
            <div>POST /api/v1/transfers/&#123;id&#125;/approve/      -&gt; WaybillApproveAPIView</div>
            <div>GET  /api/v1/maintenance/                -&gt; WorkOrderViewSet</div>
            <div>GET  /api/v1/disposals/                  -&gt; AssetDerecognitionViewSet</div>
            <div>GET  /api/v1/dashboard/metrics/          -&gt; ExecutiveLedgerMetricsView</div>
          </div>

          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 pt-1">
            <div className="text-[12px] text-slate-600">
              Active Adapter: <strong className="text-slate-900">MockAssetRepository (Local Persistent Storage)</strong>
            </div>
            {!showConfirmReset ? (
              <button
                type="button"
                onClick={() => setShowConfirmReset(true)}
                className="px-3 py-1.5 rounded-lg border border-red-200 text-red-700 hover:bg-red-50 text-[12px] font-bold transition-colors"
              >
                Reset Demo Seed Data
              </button>
            ) : (
              <div className="flex items-center gap-2 p-1.5 bg-red-50 border border-red-200 rounded-lg">
                <span className="text-[11px] text-red-800 font-medium">Reset all asset records to baseline?</span>
                <button
                  type="button"
                  onClick={handleConfirmReset}
                  className="px-2 py-1 bg-red-700 text-white rounded text-[11px] font-bold hover:bg-red-800"
                >
                  Yes, Reset
                </button>
                <button
                  type="button"
                  onClick={() => setShowConfirmReset(false)}
                  className="px-2 py-1 bg-white border border-slate-300 text-slate-700 rounded text-[11px] font-semibold hover:bg-slate-50"
                >
                  Cancel
                </button>
              </div>
            )}
          </div>

          {resetMessage && (
            <div className="p-3 bg-emerald-50 border border-emerald-200 text-emerald-900 rounded-lg text-xs font-medium">
              {resetMessage}
            </div>
          )}
        </div>

        <div className="flex items-center justify-end gap-3">
          <button
            type="submit"
            className="px-5 py-2.5 bg-[#00288e] text-white font-bold rounded-lg shadow-sm hover:bg-[#1e40af] text-[13px] transition-all"
          >
            Save Configuration Changes
          </button>
        </div>
      </form>
    </div>
  );
};
