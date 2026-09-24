/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 * Asset Categories Management View
 */

import React, { useState, useEffect } from 'react';
import { AssetCategory } from '../types';
import { assetRepository } from '../services/assetRepository';
import { formatNaira } from '../services/depreciationCalculator';

interface CategoriesViewProps {
  onNavigate: (route: string) => void;
}

export const CategoriesView: React.FC<CategoriesViewProps> = ({ onNavigate }) => {
  const [categories, setCategories] = useState<AssetCategory[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      const cats = await assetRepository.getCategories();
      setCategories(cats);
      setLoading(false);
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
            <span className="text-slate-900 font-bold">Categories</span>
          </div>
          <h1 className="text-2xl font-bold text-slate-900">Asset Categories & Classification</h1>
          <p className="text-[13px] text-slate-500">
            IAS 16 statutory useful life standards, residual value minimums, and balance sheet classifications.
          </p>
        </div>

        <button
          onClick={() => alert('Add Category modal')}
          className="h-9 px-3.5 bg-[#00288e] text-white font-semibold text-[13px] rounded-lg shadow-xs hover:bg-[#1e40af] transition-all flex items-center gap-1.5 self-start md:self-auto"
        >
          <span className="material-symbols-outlined text-[18px]">add</span>
          <span>New Category</span>
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {categories.map(cat => (
          <div
            key={cat.id}
            className="bg-white rounded-xl shadow-sm border border-slate-200/80 p-5 flex flex-col justify-between hover:shadow-md transition-shadow"
          >
            <div>
              <div className="flex items-center justify-between">
                <span className="px-2 py-0.5 rounded text-[11px] font-mono font-bold bg-[#eff4ff] text-[#00288e] border border-blue-200">
                  {cat.code}
                </span>
                <span className="text-[12px] text-slate-500 font-bold">{cat.asset_count} Assets</span>
              </div>

              <h2 className="text-[16px] font-bold text-slate-900 mt-2">{cat.name}</h2>
              <p className="text-[12px] text-slate-500 mt-1 leading-relaxed">{cat.description}</p>
            </div>

            <div className="mt-4 pt-3 border-t border-slate-100 space-y-2 text-[12px]">
              <div className="flex justify-between">
                <span className="text-slate-500">Useful Life Standard:</span>
                <span className="font-semibold text-slate-800">
                  {Math.round(cat.standard_useful_life_months / 12)} Yrs ({cat.standard_useful_life_months} mos)
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Default Residual Rate:</span>
                <span className="font-semibold text-slate-800">{cat.default_residual_rate_pct}%</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Total Capitalized Value:</span>
                <span className="font-mono font-bold text-[#00288e]">{formatNaira(cat.total_cost)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Current Net Carrying Value:</span>
                <span className="font-mono font-bold text-emerald-800">{formatNaira(cat.total_nbv)}</span>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
