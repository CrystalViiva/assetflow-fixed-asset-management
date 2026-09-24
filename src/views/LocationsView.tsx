/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 * Nigerian Operating Hubs View
 */

import React, { useState, useEffect } from 'react';
import { LocationHub } from '../types';
import { assetRepository } from '../services/assetRepository';
import { formatNaira } from '../services/depreciationCalculator';

interface LocationsViewProps {
  onNavigate: (route: string) => void;
}

export const LocationsView: React.FC<LocationsViewProps> = ({ onNavigate }) => {
  const [locations, setLocations] = useState<LocationHub[]>([]);

  useEffect(() => {
    async function load() {
      const data = await assetRepository.getLocations();
      setLocations(data);
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
          <span className="text-slate-900 font-bold">Locations</span>
        </div>
        <h1 className="text-2xl font-bold text-slate-900">Nigerian Operating Hubs & Logistics Depots</h1>
        <p className="text-[13px] text-slate-500">
          Geographic capital distribution, GPS telematics boundaries, and depot management across Nigeria.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {locations.map(loc => (
          <div
            key={loc.id}
            className="bg-white rounded-xl shadow-sm border border-slate-200/80 p-5 space-y-3 hover:shadow-md transition-shadow"
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="w-8 h-8 rounded-lg bg-[#00288e] text-white flex items-center justify-center font-bold text-[12px]">
                  {loc.code}
                </span>
                <div>
                  <h2 className="text-[15px] font-bold text-slate-900 leading-tight">{loc.name}</h2>
                  <span className="text-[11px] text-slate-500">{loc.city}, {loc.state}</span>
                </div>
              </div>
              <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-[#eff4ff] text-[#00288e] border border-blue-200">
                {loc.percentage_of_total}% Base
              </span>
            </div>

            <div className="p-3 bg-[#eff4ff]/60 rounded-lg text-[12px] space-y-1.5 border border-slate-200/60">
              <div className="text-slate-600">
                <strong>Address:</strong> {loc.address}
              </div>
              <div className="text-slate-600 font-mono text-[11px]">
                <strong>Coordinates:</strong> {loc.coordinates}
              </div>
              <div className="text-slate-600">
                <strong>Depot Manager:</strong> {loc.hub_manager}
              </div>
            </div>

            <div className="pt-2 border-t border-slate-100 flex items-center justify-between text-[12px]">
              <div>
                <span className="text-slate-400 text-[10px] uppercase font-bold block">Asset Units</span>
                <span className="font-bold text-slate-800">{loc.asset_count} Registered</span>
              </div>
              <div className="text-right">
                <span className="text-slate-400 text-[10px] uppercase font-bold block">Capitalized Value</span>
                <span className="font-mono font-bold text-[#00288e]">{formatNaira(loc.total_cost)}</span>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
