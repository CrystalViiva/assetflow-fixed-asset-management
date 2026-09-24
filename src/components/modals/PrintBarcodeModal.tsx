/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 * Print Asset QR & Barcode Thermal Label Modal
 */

import React from 'react';
import { Asset } from '../../types';

interface PrintBarcodeModalProps {
  isOpen: boolean;
  onClose: () => void;
  asset: Asset | null;
}

export const PrintBarcodeModal: React.FC<PrintBarcodeModalProps> = ({ isOpen, onClose, asset }) => {
  if (!isOpen || !asset) return null;

  const handlePrint = () => {
    window.print();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-xs animate-in fade-in">
      <div className="bg-white rounded-xl max-w-sm w-full shadow-2xl p-5 space-y-4 text-center border border-slate-200">
        <div className="flex items-center justify-between pb-2 border-b border-slate-100">
          <div className="flex items-center gap-2 text-left">
            <span className="material-symbols-outlined text-[#00288e] text-[20px]">qr_code_scanner</span>
            <div>
              <h3 className="text-[15px] font-bold text-slate-900">Zebra Thermal Label</h3>
              <p className="text-[11px] text-slate-500">Standard 50mm x 30mm RFID Asset Tag</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="w-7 h-7 flex items-center justify-center rounded-full hover:bg-slate-100 text-slate-400 hover:text-slate-600 transition-colors"
          >
            <span className="material-symbols-outlined text-[18px]">close</span>
          </button>
        </div>

        {/* Printable Label Preview Box */}
        <div id="printable-tag" className="p-4 bg-white rounded-lg border-2 border-dashed border-slate-300 flex flex-col items-center justify-center text-center shadow-inner">
          <div className="text-[10px] font-bold uppercase tracking-widest text-[#00288e] mb-0.5">
            AssetFlow Verified Asset
          </div>
          <div className="font-mono text-sm font-bold text-slate-900">{asset.tag}</div>

          {/* Large SVG QR Representation */}
          <div className="my-2 p-2 bg-white rounded border border-slate-200 shadow-2xs">
            <svg className="w-28 h-28" viewBox="0 0 100 100" fill="currentColor">
              {/* Corner 1 */}
              <rect x="10" y="10" width="28" height="28" fill="#0b1c30" />
              <rect x="14" y="14" width="20" height="20" fill="white" />
              <rect x="18" y="18" width="12" height="12" fill="#0b1c30" />
              {/* Corner 2 */}
              <rect x="62" y="10" width="28" height="28" fill="#0b1c30" />
              <rect x="66" y="14" width="20" height="20" fill="white" />
              <rect x="70" y="18" width="12" height="12" fill="#0b1c30" />
              {/* Corner 3 */}
              <rect x="10" y="62" width="28" height="28" fill="#0b1c30" />
              <rect x="14" y="66" width="20" height="20" fill="white" />
              <rect x="18" y="70" width="12" height="12" fill="#0b1c30" />
              {/* Data Pattern */}
              <rect x="42" y="14" width="6" height="12" fill="#0b1c30" />
              <rect x="52" y="20" width="6" height="6" fill="#0b1c30" />
              <rect x="42" y="32" width="16" height="6" fill="#0b1c30" />
              <rect x="20" y="44" width="8" height="8" fill="#0b1c30" />
              <rect x="36" y="44" width="14" height="14" fill="#00288e" />
              <rect x="56" y="44" width="8" height="12" fill="#0b1c30" />
              <rect x="70" y="44" width="16" height="6" fill="#0b1c30" />
              <rect x="42" y="66" width="8" height="12" fill="#0b1c30" />
              <rect x="56" y="62" width="12" height="8" fill="#0b1c30" />
              <rect x="74" y="74" width="14" height="14" fill="#0b1c30" />
              <rect x="56" y="78" width="10" height="10" fill="#00288e" />
            </svg>
          </div>

          <div className="text-[12px] font-bold text-slate-900 truncate max-w-[220px]">
            {asset.name}
          </div>
          <div className="font-mono text-[10px] text-slate-500 mt-0.5">
            SN: {asset.serial_number}
          </div>
          <div className="text-[9px] text-slate-400 mt-1 uppercase tracking-wider">
            {asset.location_name} • {asset.department_name}
          </div>
        </div>

        <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-100">
          <button
            type="button"
            onClick={onClose}
            className="px-3 py-1.5 bg-slate-100 hover:bg-slate-200 rounded text-[12px] font-medium text-slate-700 transition-colors"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handlePrint}
            className="px-4 py-1.5 bg-[#00288e] text-white hover:bg-[#1e40af] rounded text-[12px] font-semibold flex items-center gap-1.5 shadow-sm transition-colors"
          >
            <span className="material-symbols-outlined text-[16px]">print</span>
            <span>Send to Zebra Thermal</span>
          </button>
        </div>
      </div>
    </div>
  );
};
