/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 * Register Fixed Asset View
 * Faithfully matches the Stitch multi-section form with real-time reactive Capitalization Ledger,
 * IAS 16 calculations, amortization curve, and journal preview.
 */

import React, { useState, useMemo } from 'react';
import { Asset, AssetCategory, Department, LocationHub } from '../types';
import { assetRepository } from '../services/assetRepository';
import { formatNaira, calculateStraightLine } from '../services/depreciationCalculator';

interface AssetCreateViewProps {
  categories: AssetCategory[];
  departments: Department[];
  locations: LocationHub[];
  onNavigate: (route: string) => void;
  onAssetCreated: (asset: Asset) => void;
}

export const AssetCreateView: React.FC<AssetCreateViewProps> = ({
  categories,
  departments,
  locations,
  onNavigate,
  onAssetCreated,
}) => {
  // Form State
  const [name, setName] = useState('Mikano Perkins 250kVA Diesel Generator');
  const [customTagEnabled, setCustomTagEnabled] = useState(false);
  const [assetTag, setAssetTag] = useState('AST-001285');
  const [rfidTag, setRfidTag] = useState('RFID-8849-01285');
  const [categoryId, setCategoryId] = useState('CAT-01');
  const [subCategory, setSubCategory] = useState('Standby Power Generation & Switchgear');
  const [manufacturer, setManufacturer] = useState('Perkins / Mikano International');
  const [model, setModel] = useState('P250HE-CANOPY');
  const [serialNumber, setSerialNumber] = useState('SN-PERK-250-88319');
  const [description, setDescription] = useState(
    'Heavy duty soundproof containerized diesel generator set with automatic transfer switch (ATS), Leroy Somer alternator, and deepsea digital control module.'
  );

  // Custody
  const [departmentId, setDepartmentId] = useState('DEP-02');
  const [locationId, setLocationId] = useState('LOC-02');
  const [subLocation, setSubLocation] = useState('Power House Yard B, Trans-Amadi');
  const [costCenter, setCostCenter] = useState('CC-4020 Plant Maintenance');
  const [custodianName, setCustodianName] = useState('Engr. Ifeanyi Okeke (Senior Plant Manager) - EMP-0482');

  // Accounting / Cost Components
  const [vendor, setVendor] = useState('Mikano International Limited');
  const [vendorInvoice, setVendorInvoice] = useState('INV-MK-2025-0419');
  const [poRef, setPoRef] = useState('PO-2025-0182');
  const [acquisitionDate, setAcquisitionDate] = useState('2025-03-15');
  const [capitalizationDate, setCapitalizationDate] = useState('2025-03-20');

  // Costs
  const [costBase, setCostBase] = useState<number>(38_000_000);
  const [costFreight, setCostFreight] = useState<number>(2_500_000);
  const [costInstall, setCostInstall] = useState<number>(1_800_000);
  const [costCivil, setCostCivil] = useState<number>(1_200_000);
  const [costOther, setCostOther] = useState<number>(500_000);

  // Depreciation
  const [depMethod, setDepMethod] = useState<'SLM' | 'RBM' | 'UOP' | 'SYD'>('SLM');
  const [usefulYears, setUsefulYears] = useState<number>(8);
  const [residualRate, setResidualRate] = useState<number>(10);
  const [commencementDate, setCommencementDate] = useState('2025-04-01');
  const [prorateFirstMonth, setProrateFirstMonth] = useState<boolean>(true);

  // Submit states
  const [submitting, setSubmitting] = useState(false);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [hasAttemptedSubmit, setHasAttemptedSubmit] = useState(false);

  // Real-time calculations
  const totalCost = useMemo(() => {
    return (costBase || 0) + (costFreight || 0) + (costInstall || 0) + (costCivil || 0) + (costOther || 0);
  }, [costBase, costFreight, costInstall, costCivil, costOther]);

  const usefulMonths = useMemo(() => Math.max(0, usefulYears * 12), [usefulYears]);

  const depResult = useMemo(() => {
    return calculateStraightLine({
      cost: totalCost,
      residualRatePct: residualRate,
      usefulLifeMonths: usefulMonths || 12,
      capitalizationDate,
    });
  }, [totalCost, residualRate, usefulMonths, capitalizationDate]);

  const clearError = (key: string) => {
    setErrors(prev => {
      if (!(key in prev)) return prev;
      const copy = { ...prev };
      delete copy[key];
      return copy;
    });
  };

  const validateForm = (
    currentName = name,
    currentCat = categoryId,
    currentAcq = acquisitionDate,
    currentCap = capitalizationDate,
    currentTotal = totalCost,
    currentRes = residualRate,
    currentYears = usefulYears,
    currentMethod = depMethod,
    currentSal = depResult.salvageValue
  ): Record<string, string> => {
    const errs: Record<string, string> = {};

    // 1. Asset name is required.
    if (!currentName.trim()) {
      errs.name = 'Asset name is required.';
    }

    // 2. Asset category is required.
    if (!currentCat.trim()) {
      errs.categoryId = 'Asset category is required.';
    }

    // 3. Acquisition date is required.
    if (!currentAcq.trim()) {
      errs.acquisitionDate = 'Acquisition date is required.';
    }

    // 4. Capitalization date is required.
    if (!currentCap.trim()) {
      errs.capitalizationDate = 'Capitalization date is required.';
    }

    // 5. Capitalization date must not be earlier than acquisition date.
    if (currentAcq.trim() && currentCap.trim()) {
      const acqTime = new Date(currentAcq).getTime();
      const capTime = new Date(currentCap).getTime();
      if (!isNaN(acqTime) && !isNaN(capTime) && capTime < acqTime) {
        errs.capitalizationDate = 'Capitalization date must not be earlier than acquisition date.';
      }
    }

    // 6. Capitalizable cost must be greater than zero.
    if (currentTotal <= 0) {
      errs.cost = 'Capitalizable cost must be greater than zero.';
    }

    // 7. Residual/salvage value must not be negative.
    if (currentRes < 0 || currentSal < 0) {
      errs.residualRate = 'Residual/salvage value must not be negative.';
    }
    // 8. Residual/salvage value must not exceed the capitalizable cost.
    else if (currentRes > 100 || currentSal > currentTotal) {
      errs.residualRate = 'Residual/salvage value must not exceed the capitalizable cost.';
    }

    // 9. Useful life must be greater than zero.
    if (currentYears <= 0 || isNaN(currentYears)) {
      errs.usefulYears = 'Useful life must be greater than zero.';
    }

    // 10. Required depreciation method must be selected.
    if (!currentMethod) {
      errs.depMethod = 'Depreciation method is required.';
    }

    return errs;
  };

  const handleValidateAndCapitalize = async () => {
    setHasAttemptedSubmit(true);
    const formErrors = validateForm();
    setErrors(formErrors);

    if (Object.keys(formErrors).length > 0) {
      setSuccessMessage(null);
      window.scrollTo({ top: 0, behavior: 'smooth' });
      return;
    }

    setSubmitting(true);
    setSuccessMessage('Validating against IAS 16 thresholds and capitalization ledger...');

    setTimeout(async () => {
      try {
        const cat = categories.find(c => c.id === categoryId);
        const dept = departments.find(d => d.id === departmentId);
        const loc = locations.find(l => l.id === locationId);

        const newAsset = await assetRepository.createAsset({
          tag: assetTag,
          name,
          spec: `${subCategory} • ${model}`,
          description,
          category_id: categoryId,
          category_name: cat ? cat.name : 'Plant & Machinery',
          category_code: cat ? cat.code : 'P&M',
          manufacturer,
          model,
          serial_number: serialNumber,
          department_id: departmentId,
          department_name: dept ? dept.name : 'Operations',
          department_head: dept ? dept.head_name : 'Emeka Okafor',
          location_id: locationId,
          location_name: loc ? loc.name : 'Port Harcourt Hub',
          sub_location: subLocation,
          custodian_name: custodianName.split(' - ')[0] || custodianName,
          custodian_staff_id: custodianName.split(' - ')[1] || 'EMP-0482',
          custodian_title: 'Senior Plant Manager',
          vendor,
          commercial_invoice_ref: vendorInvoice,
          purchase_order_ref: poRef,
          acquisition_date: acquisitionDate,
          capitalization_date: capitalizationDate,
          cost_components: {
            base_purchase: costBase,
            freight: costFreight,
            installation: costInstall,
            civil_works: costCivil,
            other_costs: costOther,
          },
          total_acquisition_cost: totalCost,
          useful_life_years: usefulYears,
          useful_life_months: usefulMonths,
          residual_rate_pct: residualRate,
          rfid_tag: rfidTag,
          status: 'ACTIVE',
        });

        setSuccessMessage('Asset capitalized successfully! Redirecting to Asset Register...');
        onAssetCreated(newAsset);
        setTimeout(() => {
          onNavigate('all-assets');
        }, 1200);
      } finally {
        setSubmitting(false);
      }
    }, 800);
  };

  return (
    <div className="w-full p-4 md:p-6 select-text">
      {/* Top Context Header Section */}
      <div className="w-full mb-6">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center gap-1.5 text-[11px] font-bold text-slate-500 uppercase tracking-wider">
              <span onClick={() => onNavigate('dashboard')} className="hover:text-[#00288e] cursor-pointer">Home</span>
              <span className="text-slate-300">/</span>
              <span onClick={() => onNavigate('all-assets')} className="hover:text-[#00288e] cursor-pointer">Assets</span>
              <span className="text-slate-300">/</span>
              <span className="text-[#00288e] font-semibold">Register New Asset</span>
            </div>
            <h1 className="text-2xl md:text-[26px] font-bold text-slate-900 tracking-tight">
              Register Fixed Asset
            </h1>
            <p className="text-[13px] text-slate-500 max-w-3xl">
              Complete capitalization details, assign organizational custodian, and configure IFRS-compliant depreciation parameters.
            </p>
          </div>

          {/* Action Button Group */}
          <div className="flex items-center gap-2.5 self-start lg:self-center">
            <button
              type="button"
              onClick={() => onNavigate('all-assets')}
              className="px-3.5 py-2 rounded-lg text-[13px] font-semibold text-slate-600 hover:text-red-700 hover:bg-slate-100 transition-colors"
            >
              Discard
            </button>
            <button
              type="button"
              onClick={() => {
                setSuccessMessage('Draft details saved to local session.');
                setTimeout(() => setSuccessMessage(null), 3000);
              }}
              className="px-3.5 py-2 bg-white text-slate-800 text-[13px] font-semibold rounded-lg flex items-center gap-1.5 hover:bg-slate-50 border border-slate-200 transition-colors shadow-2xs"
            >
              <span className="material-symbols-outlined text-[18px] text-slate-500">save</span>
              <span>Save as Draft</span>
            </button>
            <button
              type="button"
              disabled={submitting}
              onClick={handleValidateAndCapitalize}
              className="px-4 py-2 bg-[#00288e] text-white text-[13px] font-bold rounded-lg flex items-center gap-1.5 hover:bg-[#1e40af] transition-all shadow-sm active:scale-[0.98] disabled:opacity-60"
            >
              <span className="material-symbols-outlined text-[18px]">
                {submitting ? 'refresh' : 'verified'}
              </span>
              <span>{submitting ? 'Validating Ledger...' : 'Validate & Capitalize Asset'}</span>
            </button>
          </div>
        </div>

        {hasAttemptedSubmit && Object.keys(errors).length > 0 && (
          <div className="mt-4 p-4 bg-rose-50 border border-rose-200 text-rose-900 rounded-xl text-[13px] flex items-start gap-3 animate-in fade-in shadow-xs">
            <span className="material-symbols-outlined text-[22px] text-rose-600 shrink-0 mt-0.5">error</span>
            <div className="space-y-1">
              <div className="font-bold text-rose-950 text-[14px]">
                Capitalization Validation Failed ({Object.keys(errors).length} issue{Object.keys(errors).length > 1 ? 's' : ''})
              </div>
              <p className="text-rose-800 text-xs leading-relaxed">
                Please correct the highlighted fields per IAS 16 statutory capitalization guidelines:
              </p>
              <ul className="list-disc pl-4 text-xs text-rose-800 space-y-0.5 pt-1">
                {Object.values(errors).map((err, idx) => (
                  <li key={idx} className="font-medium">{err}</li>
                ))}
              </ul>
            </div>
          </div>
        )}

        {successMessage && (
          <div className="mt-3 p-3 bg-emerald-50 border border-emerald-200 text-emerald-800 rounded-lg text-[13px] font-semibold flex items-center gap-2 animate-in fade-in">
            <span className="material-symbols-outlined text-[18px] text-emerald-600">check_circle</span>
            <span>{successMessage}</span>
          </div>
        )}
      </div>

      {/* Primary 2-Column Enterprise Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 w-full items-start">
        {/* Left Main Form Flow (8 Cols) */}
        <div className="lg:col-span-8 flex flex-col gap-6">
          {/* Section 1: Basic Information & Identification */}
          <div className="bg-white rounded-xl shadow-sm border border-slate-200/80 overflow-hidden">
            <div className="px-5 py-3.5 bg-[#eff4ff] flex items-center justify-between border-b border-slate-200">
              <div className="flex items-center gap-2.5">
                <span className="w-6 h-6 rounded-full bg-[#00288e] text-white flex items-center justify-center text-[12px] font-bold">
                  1
                </span>
                <h2 className="text-[15px] font-bold text-slate-900">
                  Basic Information & Identification
                </h2>
              </div>
              <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase bg-white text-[#00288e] border border-slate-200">
                Core Masterdata
              </span>
            </div>

            <div className="p-5 grid grid-cols-1 md:grid-cols-2 gap-4 text-[13px]">
              {/* Asset Name (Full Width) */}
              <div className="md:col-span-2 space-y-1">
                <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-500">
                  Asset Commercial Name <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  value={name}
                  onChange={e => {
                    setName(e.target.value);
                    clearError('name');
                  }}
                  placeholder="Enter manufacturer model or title"
                  className={`w-full h-9 px-3 bg-[#eff4ff]/60 text-slate-900 rounded-md border font-medium focus:outline-none ${
                    errors.name ? 'border-rose-500 ring-1 ring-rose-500 bg-rose-50/20' : 'border-slate-200 focus:ring-1.5 focus:ring-[#00288e]'
                  }`}
                  required
                />
                {errors.name && (
                  <p className="text-[11px] font-semibold text-rose-600 flex items-center gap-1 mt-1">
                    <span className="material-symbols-outlined text-[14px]">error</span>
                    {errors.name}
                  </p>
                )}
              </div>

              {/* System Asset Tag with Custom Toggle */}
              <div className="space-y-1">
                <div className="flex items-center justify-between">
                  <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-500">
                    System Asset Tag
                  </label>
                  <label className="flex items-center gap-1 cursor-pointer text-[11px] text-[#00288e] font-semibold">
                    <input
                      type="checkbox"
                      checked={customTagEnabled}
                      onChange={e => setCustomTagEnabled(e.target.checked)}
                      className="rounded text-[#00288e] w-3.5 h-3.5 focus:ring-0"
                    />
                    <span>Custom Tag</span>
                  </label>
                </div>
                <div className="relative flex items-center">
                  <input
                    type="text"
                    value={assetTag}
                    readOnly={!customTagEnabled}
                    onChange={e => setAssetTag(e.target.value)}
                    className={`w-full h-9 pl-3 pr-9 font-mono font-bold text-[13px] rounded-md border border-slate-200 ${
                      customTagEnabled ? 'bg-white text-slate-900 focus:ring-1.5 focus:ring-[#00288e]' : 'bg-slate-100 text-slate-600 cursor-not-allowed'
                    }`}
                  />
                  <span className="material-symbols-outlined absolute right-2.5 text-[18px] text-slate-400">
                    {customTagEnabled ? 'lock_open' : 'lock'}
                  </span>
                </div>
              </div>

              {/* Barcode / RFID Tag ID */}
              <div className="space-y-1">
                <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-500">
                  Barcode / RFID Tag ID
                </label>
                <div className="relative flex items-center">
                  <input
                    type="text"
                    value={rfidTag}
                    onChange={e => setRfidTag(e.target.value)}
                    className="w-full h-9 pl-8 pr-3 bg-[#eff4ff]/60 text-slate-900 font-mono rounded-md border border-slate-200 focus:outline-none focus:ring-1.5 focus:ring-[#00288e]"
                  />
                  <span className="material-symbols-outlined absolute left-2 text-[18px] text-slate-400">
                    qr_code_scanner
                  </span>
                </div>
              </div>

              {/* Category */}
              <div className="space-y-1">
                <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-500">
                  Asset Category <span className="text-red-500">*</span>
                </label>
                <select
                  value={categoryId}
                  onChange={e => {
                    setCategoryId(e.target.value);
                    clearError('categoryId');
                  }}
                  className={`w-full h-9 px-3 bg-[#eff4ff]/60 text-slate-900 rounded-md border focus:outline-none ${
                    errors.categoryId ? 'border-rose-500 ring-1 ring-rose-500 bg-rose-50/20' : 'border-slate-200 focus:ring-1.5 focus:ring-[#00288e]'
                  }`}
                >
                  <option value="">-- Select Asset Category --</option>
                  {categories.map(c => (
                    <option key={c.id} value={c.id}>
                      {c.name} ({c.code})
                    </option>
                  ))}
                </select>
                {errors.categoryId && (
                  <p className="text-[11px] font-semibold text-rose-600 flex items-center gap-1 mt-1">
                    <span className="material-symbols-outlined text-[14px]">error</span>
                    {errors.categoryId}
                  </p>
                )}
              </div>

              {/* Sub-Category */}
              <div className="space-y-1">
                <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-500">
                  Asset Sub-Category
                </label>
                <select
                  value={subCategory}
                  onChange={e => setSubCategory(e.target.value)}
                  className="w-full h-9 px-3 bg-[#eff4ff]/60 text-slate-900 rounded-md border border-slate-200 focus:outline-none focus:ring-1.5 focus:ring-[#00288e]"
                >
                  <option>Standby Power Generation & Switchgear</option>
                  <option>Water Treatment Plants & Pumps</option>
                  <option>Heavy Lifting & Rigging Equipment</option>
                  <option>HVAC Chiller & Environmental Units</option>
                  <option>Civil Haulage & Earthmoving</option>
                </select>
              </div>

              {/* Manufacturer */}
              <div className="space-y-1">
                <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-500">
                  Manufacturer / OEM
                </label>
                <input
                  type="text"
                  value={manufacturer}
                  onChange={e => setManufacturer(e.target.value)}
                  className="w-full h-9 px-3 bg-[#eff4ff]/60 text-slate-900 rounded-md border border-slate-200 focus:outline-none focus:ring-1.5 focus:ring-[#00288e]"
                />
              </div>

              {/* Model & Serial No Grid */}
              <div className="grid grid-cols-2 gap-2">
                <div className="space-y-1">
                  <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-500">
                    Model No.
                  </label>
                  <input
                    type="text"
                    value={model}
                    onChange={e => setModel(e.target.value)}
                    className="w-full h-9 px-3 bg-[#eff4ff]/60 text-slate-900 rounded-md border border-slate-200 focus:outline-none focus:ring-1.5 focus:ring-[#00288e]"
                  />
                </div>
                <div className="space-y-1">
                  <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-500">
                    Serial No. <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="text"
                    value={serialNumber}
                    onChange={e => setSerialNumber(e.target.value)}
                    className="w-full h-9 px-3 bg-[#eff4ff]/60 text-slate-900 font-mono rounded-md border border-slate-200 focus:outline-none focus:ring-1.5 focus:ring-[#00288e]"
                    required
                  />
                </div>
              </div>

              {/* Description */}
              <div className="md:col-span-2 space-y-1">
                <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-500">
                  Specification & Technical Description
                </label>
                <textarea
                  rows={2}
                  value={description}
                  onChange={e => setDescription(e.target.value)}
                  className="w-full p-2.5 bg-[#eff4ff]/60 text-slate-900 rounded-md border border-slate-200 focus:outline-none focus:ring-1.5 focus:ring-[#00288e] resize-none"
                />
              </div>

              {/* Asset Image Upload Slot */}
              <div className="md:col-span-2 p-3 bg-[#eff4ff]/60 rounded-lg border border-slate-200/80 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <img
                    alt="Asset Preview"
                    className="w-14 h-14 object-cover rounded shadow-xs border border-slate-200"
                    src="https://lh3.googleusercontent.com/aida-public/AB6AXuARkC1Wlvx9Ay6CnusCTKpVnMoikv2jHnwXTymqXs2qBxbMMAKFQTjdlQ1IHnNoHlbW6x2-rN60RT8qVazfUhoc2laoSuBH5TLHyMK9md4u9tBpcm5P_HMql97FKiWYTWmRpNjySGxI9bQ_-ZY3slWJoM12u7tNA2kZ-sO6juTnycIk8Z2kq5LrtlVrtXurYIFIZxHiumYNXX6dihJkhD5sh-MahSGaVdMYezsQjAkud1-_jk7EqCqhsQ"
                  />
                  <div>
                    <span className="block font-bold text-slate-900 text-[13px]">Physical Asset Image Verified</span>
                    <span className="block text-[11px] text-slate-500">
                      IMG-PERK-2025-01.jpg • 3.4 MB • Geo-tagged at Lagos Yard B
                    </span>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => alert('Photo upload portal opened: Camera/File capture.')}
                  className="px-2.5 py-1 rounded bg-white hover:bg-slate-50 text-[#00288e] text-[11px] font-bold border border-slate-200 transition-colors shadow-2xs"
                >
                  Replace Image
                </button>
              </div>
            </div>
          </div>

          {/* Section 2: Organizational Assignment & Location */}
          <div className="bg-white rounded-xl shadow-sm border border-slate-200/80 overflow-hidden">
            <div className="px-5 py-3.5 bg-[#eff4ff] flex items-center justify-between border-b border-slate-200">
              <div className="flex items-center gap-2.5">
                <span className="w-6 h-6 rounded-full bg-[#00288e] text-white flex items-center justify-center text-[12px] font-bold">
                  2
                </span>
                <h2 className="text-[15px] font-bold text-slate-900">
                  Organizational Assignment & Custody
                </h2>
              </div>
              <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase bg-white text-[#00288e] border border-slate-200">
                Custody Chain
              </span>
            </div>

            <div className="p-5 grid grid-cols-1 md:grid-cols-2 gap-4 text-[13px]">
              {/* Department */}
              <div className="space-y-1">
                <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-500">
                  Primary Department <span className="text-red-500">*</span>
                </label>
                <select
                  value={departmentId}
                  onChange={e => setDepartmentId(e.target.value)}
                  className="w-full h-9 px-3 bg-[#eff4ff]/60 text-slate-900 rounded-md border border-slate-200 focus:outline-none focus:ring-1.5 focus:ring-[#00288e]"
                >
                  {departments.map(d => (
                    <option key={d.id} value={d.id}>
                      {d.name} ({d.code})
                    </option>
                  ))}
                </select>
              </div>

              {/* Operating Hub / Location */}
              <div className="space-y-1">
                <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-500">
                  Operating Hub / Facility <span className="text-red-500">*</span>
                </label>
                <select
                  value={locationId}
                  onChange={e => setLocationId(e.target.value)}
                  className="w-full h-9 px-3 bg-[#eff4ff]/60 text-slate-900 rounded-md border border-slate-200 focus:outline-none focus:ring-1.5 focus:ring-[#00288e]"
                >
                  {locations.map(l => (
                    <option key={l.id} value={l.id}>
                      {l.name}
                    </option>
                  ))}
                </select>
              </div>

              {/* Specific Bay / Room */}
              <div className="space-y-1">
                <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-500">
                  Specific Facility Bay / Room
                </label>
                <input
                  type="text"
                  value={subLocation}
                  onChange={e => setSubLocation(e.target.value)}
                  className="w-full h-9 px-3 bg-[#eff4ff]/60 text-slate-900 rounded-md border border-slate-200 focus:outline-none focus:ring-1.5 focus:ring-[#00288e]"
                />
              </div>

              {/* Cost Center */}
              <div className="space-y-1">
                <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-500">
                  Secondary Cost Center
                </label>
                <input
                  type="text"
                  value={costCenter}
                  onChange={e => setCostCenter(e.target.value)}
                  className="w-full h-9 px-3 bg-[#eff4ff]/60 text-slate-900 font-mono rounded-md border border-slate-200 focus:outline-none focus:ring-1.5 focus:ring-[#00288e]"
                />
              </div>

              {/* Designated Asset Custodian */}
              <div className="md:col-span-2 space-y-1">
                <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-500">
                  Designated Asset Custodian <span className="text-red-500">*</span>
                </label>
                <div className="relative">
                  <select
                    value={custodianName}
                    onChange={e => setCustodianName(e.target.value)}
                    className="w-full h-10 pl-9 pr-3 bg-[#eff4ff]/60 text-slate-900 rounded-md border border-slate-200 focus:outline-none focus:ring-1.5 focus:ring-[#00288e] font-medium"
                  >
                    <option>Engr. Ifeanyi Okeke (Senior Plant Manager) - EMP-0482</option>
                    <option>Babatunde Adeleke (Senior Site Engineer) - AF-ENG-084</option>
                    <option>Amina Mohammed (Chief Maintenance Officer) - EMP-0199</option>
                    <option>Femi Balogun (Head of Facilities) - EMP-0814</option>
                  </select>
                  <span className="material-symbols-outlined absolute left-2.5 top-2.5 text-[20px] text-[#00288e]">
                    badge
                  </span>
                </div>
                <p className="text-[11px] text-slate-500 pt-0.5">
                  Custodian holds physical fiduciary duty and countersigns periodic balance sheet audit verifications.
                </p>
              </div>
            </div>
          </div>

          {/* Section 3: Acquisition & Capitalization Accounting (IAS 16) */}
          <div className="bg-white rounded-xl shadow-sm border border-slate-200/80 overflow-hidden">
            <div className="px-5 py-3.5 bg-[#eff4ff] flex items-center justify-between border-b border-slate-200">
              <div className="flex items-center gap-2.5">
                <span className="w-6 h-6 rounded-full bg-[#00288e] text-white flex items-center justify-center text-[12px] font-bold">
                  3
                </span>
                <h2 className="text-[15px] font-bold text-slate-900">
                  Acquisition & Capitalization Accounting (IAS 16)
                </h2>
              </div>
              <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase bg-white text-slate-800 border border-slate-200">
                General Ledger
              </span>
            </div>

            <div className="p-5 space-y-4 text-[13px]">
              {/* Supplier Reference Grid */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                <div className="space-y-1">
                  <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-500">
                    Vendor / Supplier
                  </label>
                  <input
                    type="text"
                    value={vendor}
                    onChange={e => setVendor(e.target.value)}
                    className="w-full h-9 px-3 bg-[#eff4ff]/60 text-slate-900 rounded-md border border-slate-200 focus:outline-none focus:ring-1.5 focus:ring-[#00288e]"
                  />
                </div>
                <div className="space-y-1">
                  <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-500">
                    Vendor Invoice No.
                  </label>
                  <input
                    type="text"
                    value={vendorInvoice}
                    onChange={e => setVendorInvoice(e.target.value)}
                    className="w-full h-9 px-3 bg-[#eff4ff]/60 text-slate-900 font-mono rounded-md border border-slate-200 focus:outline-none focus:ring-1.5 focus:ring-[#00288e]"
                  />
                </div>
                <div className="space-y-1">
                  <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-500">
                    PO Reference No.
                  </label>
                  <input
                    type="text"
                    value={poRef}
                    onChange={e => setPoRef(e.target.value)}
                    className="w-full h-9 px-3 bg-[#eff4ff]/60 text-slate-900 font-mono rounded-md border border-slate-200 focus:outline-none focus:ring-1.5 focus:ring-[#00288e]"
                  />
                </div>
              </div>

              {/* Date Pairings */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div className="space-y-1">
                  <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-500">
                    Acquisition / Delivery Date <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="date"
                    value={acquisitionDate}
                    onChange={e => {
                      setAcquisitionDate(e.target.value);
                      clearError('acquisitionDate');
                      clearError('capitalizationDate');
                    }}
                    className={`w-full h-9 px-3 bg-[#eff4ff]/60 text-slate-900 font-mono rounded-md border focus:outline-none ${
                      errors.acquisitionDate ? 'border-rose-500 ring-1 ring-rose-500 bg-rose-50/20' : 'border-slate-200 focus:ring-1.5 focus:ring-[#00288e]'
                    }`}
                    required
                  />
                  {errors.acquisitionDate && (
                    <p className="text-[11px] font-semibold text-rose-600 flex items-center gap-1 mt-1">
                      <span className="material-symbols-outlined text-[14px]">error</span>
                      {errors.acquisitionDate}
                    </p>
                  )}
                </div>
                <div className="space-y-1">
                  <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-500">
                    Capitalization (In-Service) Date <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="date"
                    value={capitalizationDate}
                    onChange={e => {
                      setCapitalizationDate(e.target.value);
                      clearError('capitalizationDate');
                    }}
                    className={`w-full h-9 px-3 bg-[#eff4ff]/60 text-slate-900 font-mono rounded-md border focus:outline-none ${
                      errors.capitalizationDate ? 'border-rose-500 ring-1 ring-rose-500 bg-rose-50/20' : 'border-slate-200 focus:ring-1.5 focus:ring-[#00288e]'
                    }`}
                    required
                  />
                  {errors.capitalizationDate && (
                    <p className="text-[11px] font-semibold text-rose-600 flex items-center gap-1 mt-1">
                      <span className="material-symbols-outlined text-[14px]">error</span>
                      {errors.capitalizationDate}
                    </p>
                  )}
                </div>
              </div>

              {/* Capitalizable Cost Elements Breakdown Table */}
              <div className="pt-2">
                <div className="flex items-center justify-between pb-2">
                  <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">
                    Capitalizable Cost Elements (Directly Attributable Costs)
                  </span>
                  <span className="text-[11px] font-bold text-[#00288e]">All figures in NGN (₦)</span>
                </div>

                <div className="bg-[#eff4ff]/60 rounded-lg p-3.5 space-y-3 border border-slate-200/80">
                  {/* Item 1: Base Purchase Price */}
                  <div className="grid grid-cols-1 md:grid-cols-12 gap-2 items-center">
                    <div className="md:col-span-7">
                      <span className="font-semibold text-slate-900 block">
                        Base Invoice Purchase Price (Excl. VAT / Recoverable Taxes)
                      </span>
                      <span className="text-[11px] text-slate-500">Core equipment unit price per vendor receipt</span>
                    </div>
                    <div className="md:col-span-5 relative flex items-center">
                      <span className="absolute left-2.5 font-mono text-slate-500 font-bold">₦</span>
                      <input
                        type="number"
                        min="0"
                        step="100000"
                        value={costBase}
                        onChange={e => {
                          const val = parseFloat(e.target.value);
                          setCostBase(isNaN(val) ? 0 : val);
                          clearError('cost');
                        }}
                        className={`w-full h-8 pl-7 pr-3 bg-white text-right font-mono font-bold text-slate-900 rounded border ${
                          errors.cost ? 'border-rose-500 ring-1 ring-rose-500' : 'border-slate-200 focus:ring-1.5 focus:ring-[#00288e]'
                        }`}
                      />
                    </div>
                  </div>

                  {/* Item 2: Freight */}
                  <div className="grid grid-cols-1 md:grid-cols-12 gap-2 items-center">
                    <div className="md:col-span-7">
                      <span className="font-semibold text-slate-900 block">
                        Shipping, Haulage & Port Freight Cost
                      </span>
                      <span className="text-[11px] text-slate-500">Direct transport from Apapa Port to Port Harcourt Hub</span>
                    </div>
                    <div className="md:col-span-5 relative flex items-center">
                      <span className="absolute left-2.5 font-mono text-slate-500 font-bold">₦</span>
                      <input
                        type="number"
                        min="0"
                        step="50000"
                        value={costFreight}
                        onChange={e => setCostFreight(parseFloat(e.target.value) || 0)}
                        className="w-full h-8 pl-7 pr-3 bg-white text-right font-mono font-bold text-slate-900 rounded border border-slate-200 focus:ring-1.5 focus:ring-[#00288e]"
                      />
                    </div>
                  </div>

                  {/* Item 3: Installation */}
                  <div className="grid grid-cols-1 md:grid-cols-12 gap-2 items-center">
                    <div className="md:col-span-7">
                      <span className="font-semibold text-slate-900 block">
                        Installation & ATS Commissioning
                      </span>
                      <span className="text-[11px] text-slate-500">Mechanical & electrical load calibration</span>
                    </div>
                    <div className="md:col-span-5 relative flex items-center">
                      <span className="absolute left-2.5 font-mono text-slate-500 font-bold">₦</span>
                      <input
                        type="number"
                        min="0"
                        step="50000"
                        value={costInstall}
                        onChange={e => setCostInstall(parseFloat(e.target.value) || 0)}
                        className="w-full h-8 pl-7 pr-3 bg-white text-right font-mono font-bold text-slate-900 rounded border border-slate-200 focus:ring-1.5 focus:ring-[#00288e]"
                      />
                    </div>
                  </div>

                  {/* Item 4: Civil Works */}
                  <div className="grid grid-cols-1 md:grid-cols-12 gap-2 items-center">
                    <div className="md:col-span-7">
                      <span className="font-semibold text-slate-900 block">
                        Foundation Civil Works & Subsurface Cabling
                      </span>
                      <span className="text-[11px] text-slate-500">Reinforced concrete generator pad construction</span>
                    </div>
                    <div className="md:col-span-5 relative flex items-center">
                      <span className="absolute left-2.5 font-mono text-slate-500 font-bold">₦</span>
                      <input
                        type="number"
                        min="0"
                        step="50000"
                        value={costCivil}
                        onChange={e => setCostCivil(parseFloat(e.target.value) || 0)}
                        className="w-full h-8 pl-7 pr-3 bg-white text-right font-mono font-bold text-slate-900 rounded border border-slate-200 focus:ring-1.5 focus:ring-[#00288e]"
                      />
                    </div>
                  </div>

                  {/* Item 5: Other Costs */}
                  <div className="grid grid-cols-1 md:grid-cols-12 gap-2 items-center">
                    <div className="md:col-span-7">
                      <span className="font-semibold text-slate-900 block">
                        Other Direct Capitalizable Costs
                      </span>
                      <span className="text-[11px] text-slate-500">Site safety earthing & initial fuel surge commissioning</span>
                    </div>
                    <div className="md:col-span-5 relative flex items-center">
                      <span className="absolute left-2.5 font-mono text-slate-500 font-bold">₦</span>
                      <input
                        type="number"
                        min="0"
                        step="50000"
                        value={costOther}
                        onChange={e => setCostOther(parseFloat(e.target.value) || 0)}
                        className="w-full h-8 pl-7 pr-3 bg-white text-right font-mono font-bold text-slate-900 rounded border border-slate-200 focus:ring-1.5 focus:ring-[#00288e]"
                      />
                    </div>
                  </div>

                  {/* Total Highlight Row */}
                  <div className={`pt-2 mt-2 rounded-lg p-3 flex items-center justify-between border ${
                    errors.cost ? 'bg-rose-50 border-rose-300' : 'bg-[#dce9ff] border-blue-200'
                  }`}>
                    <div>
                      <span className={`text-[14px] font-bold block ${errors.cost ? 'text-rose-900' : 'text-[#00288e]'}`}>
                        Total Capitalized Acquisition Cost
                      </span>
                      <span className="text-[11px] text-slate-600">
                        Recognized under IAS 16 Non-Current Asset Register
                      </span>
                      {errors.cost && (
                        <p className="text-[11px] font-semibold text-rose-700 flex items-center gap-1 mt-1">
                          <span className="material-symbols-outlined text-[14px]">error</span>
                          {errors.cost}
                        </p>
                      )}
                    </div>
                    <div className="text-right">
                      <span className={`text-[20px] font-mono font-bold ${errors.cost ? 'text-rose-700' : 'text-[#00288e]'}`}>
                        {formatNaira(totalCost)}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Section 4: Depreciation Policy & Accounting Parameters */}
          <div className="bg-white rounded-xl shadow-sm border border-slate-200/80 overflow-hidden mb-6">
            <div className="px-5 py-3.5 bg-[#eff4ff] flex items-center justify-between border-b border-slate-200">
              <div className="flex items-center gap-2.5">
                <span className="w-6 h-6 rounded-full bg-[#00288e] text-white flex items-center justify-center text-[12px] font-bold">
                  4
                </span>
                <h2 className="text-[15px] font-bold text-slate-900">
                  Depreciation Policy & Amortization Schedule
                </h2>
              </div>
              <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase bg-white text-[#00288e] border border-slate-200">
                IFRS Compliance
              </span>
            </div>

            <div className="p-5 grid grid-cols-1 md:grid-cols-2 gap-4 text-[13px]">
              {/* Depreciation Convention */}
              <div className="space-y-1">
                <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-500">
                  Depreciation Convention <span className="text-red-500">*</span>
                </label>
                <select
                  value={depMethod}
                  onChange={e => {
                    setDepMethod(e.target.value as any);
                    clearError('depMethod');
                  }}
                  className={`w-full h-9 px-3 bg-[#eff4ff]/60 text-slate-900 rounded-md border focus:outline-none ${
                    errors.depMethod ? 'border-rose-500 ring-1 ring-rose-500 bg-rose-50/20' : 'border-slate-200 focus:ring-1.5 focus:ring-[#00288e]'
                  }`}
                >
                  <option value="SLM">Straight Line Method (SLM)</option>
                  <option value="RBM">Reducing Balance Method (20% DBM)</option>
                  <option value="UOP">Units of Production (Running Hours)</option>
                  <option value="SYD">Sum of Years Digits</option>
                </select>
                {errors.depMethod && (
                  <p className="text-[11px] font-semibold text-rose-600 flex items-center gap-1 mt-1">
                    <span className="material-symbols-outlined text-[14px]">error</span>
                    {errors.depMethod}
                  </p>
                )}
              </div>

              {/* Useful Economic Life */}
              <div className="space-y-1">
                <div className="flex justify-between items-center">
                  <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-500">
                    Useful Economic Life <span className="text-red-500">*</span>
                  </label>
                  <span className="text-[11px] font-mono text-[#00288e] font-bold">{usefulMonths} Months</span>
                </div>
                <div className="relative flex items-center">
                  <input
                    type="number"
                    value={usefulYears}
                    onChange={e => {
                      const val = parseFloat(e.target.value);
                      setUsefulYears(isNaN(val) ? 0 : val);
                      clearError('usefulYears');
                    }}
                    className={`w-full h-9 px-3 pr-16 bg-[#eff4ff]/60 text-slate-900 rounded-md border font-mono font-bold focus:outline-none ${
                      errors.usefulYears ? 'border-rose-500 ring-1 ring-rose-500 bg-rose-50/20' : 'border-slate-200 focus:ring-1.5 focus:ring-[#00288e]'
                    }`}
                  />
                  <span className="absolute right-3 text-[12px] text-slate-500 pointer-events-none">Years</span>
                </div>
                {errors.usefulYears && (
                  <p className="text-[11px] font-semibold text-rose-600 flex items-center gap-1 mt-1">
                    <span className="material-symbols-outlined text-[14px]">error</span>
                    {errors.usefulYears}
                  </p>
                )}
              </div>

              {/* Salvage Rate */}
              <div className="space-y-1">
                <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-500">
                  Residual / Salvage Rate (%)
                </label>
                <div className="relative flex items-center">
                  <input
                    type="number"
                    value={residualRate}
                    onChange={e => {
                      const val = parseFloat(e.target.value);
                      setResidualRate(isNaN(val) ? 0 : val);
                      clearError('residualRate');
                    }}
                    className={`w-full h-9 px-3 pr-10 bg-[#eff4ff]/60 text-slate-900 rounded-md border font-mono font-bold focus:outline-none ${
                      errors.residualRate ? 'border-rose-500 ring-1 ring-rose-500 bg-rose-50/20' : 'border-slate-200 focus:ring-1.5 focus:ring-[#00288e]'
                    }`}
                  />
                  <span className="absolute right-3 text-[12px] text-slate-500 pointer-events-none">%</span>
                </div>
                {errors.residualRate && (
                  <p className="text-[11px] font-semibold text-rose-600 flex items-center gap-1 mt-1">
                    <span className="material-symbols-outlined text-[14px]">error</span>
                    {errors.residualRate}
                  </p>
                )}
              </div>

              {/* Calculated Salvage Value */}
              <div className="space-y-1">
                <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-500">
                  Calculated Salvage Value
                </label>
                <input
                  type="text"
                  readOnly
                  value={formatNaira(depResult.salvageValue)}
                  className="w-full h-9 px-3 bg-slate-100 text-slate-800 font-mono font-bold rounded-md border border-slate-200 cursor-not-allowed"
                />
              </div>

              {/* Depreciable Base */}
              <div className="space-y-1">
                <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-500">
                  Depreciable Cost Base (Cost - Salvage)
                </label>
                <input
                  type="text"
                  readOnly
                  value={formatNaira(depResult.depreciableBase)}
                  className="w-full h-9 px-3 bg-slate-100 text-[#00288e] font-mono font-bold rounded-md border border-slate-200 cursor-not-allowed"
                />
              </div>

              {/* Commencement Date */}
              <div className="space-y-1">
                <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-500">
                  Amortization Commencement Date
                </label>
                <input
                  type="date"
                  value={commencementDate}
                  onChange={e => setCommencementDate(e.target.value)}
                  className="w-full h-9 px-3 bg-[#eff4ff]/60 text-slate-900 font-mono rounded-md border border-slate-200 focus:outline-none focus:ring-1.5 focus:ring-[#00288e]"
                />
              </div>

              {/* Prorate Toggle */}
              <div className="md:col-span-2 p-3 bg-[#eff4ff]/60 rounded-lg border border-slate-200 flex items-center justify-between">
                <div>
                  <span className="font-semibold text-slate-900 text-[13px] block">
                    Prorate First Month Depreciation
                  </span>
                  <span className="text-[11px] text-slate-500">
                    Calculate partial statutory amortization based on operational days remaining in March 2025.
                  </span>
                </div>
                <label className="relative inline-flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    checked={prorateFirstMonth}
                    onChange={e => setProrateFirstMonth(e.target.checked)}
                    className="sr-only peer"
                  />
                  <div className="w-10 h-5 bg-slate-300 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-[#00288e]"></div>
                </label>
              </div>
            </div>
          </div>
        </div>

        {/* Right Sticky Live Financial & Depreciation Preview (4 Cols) */}
        <div className="lg:col-span-4 sticky top-16 space-y-4">
          {/* Primary Summary Card */}
          <div className="bg-white rounded-xl shadow-md border border-slate-200/80 p-5 space-y-4">
            <div className="flex items-center justify-between pb-2 border-b border-slate-100">
              <div className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full bg-emerald-600 animate-pulse"></span>
                <span className="text-[15px] font-bold text-slate-900">Capitalization Ledger</span>
              </div>
              <span className="px-2 py-0.5 rounded bg-[#eff4ff] text-[#00288e] font-mono text-[11px] font-bold border border-[#d3e4fe]">
                {assetTag || 'AST-001285'}
              </span>
            </div>

            {/* Big Highlight Metric: Total Cost */}
            <div className="p-4 bg-gradient-to-br from-[#dce9ff]/60 via-[#eff4ff] to-white rounded-xl border border-blue-200/70">
              <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
                Total Capitalized Value
              </span>
              <div className="flex items-baseline justify-between mt-1">
                <span className="text-[26px] font-mono font-extrabold text-[#00288e]">
                  {formatNaira(totalCost)}
                </span>
                <span className="text-[10px] text-emerald-800 bg-emerald-100 px-2 py-0.5 rounded font-bold">
                  Ready
                </span>
              </div>
            </div>

            {/* Metric Details List */}
            <div className="space-y-2.5 pt-1 text-[13px]">
              <div className="flex items-center justify-between">
                <span className="text-slate-500">Depreciable Base:</span>
                <span className="font-mono font-bold text-slate-900">
                  {formatNaira(depResult.depreciableBase)}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-slate-500">Monthly Depreciation:</span>
                <span className="font-mono font-bold text-[#00288e]">
                  {formatNaira(depResult.monthlyDepreciation)} <span className="text-[10px] text-slate-500 font-normal">/ mo</span>
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-slate-500">Annual Deprec. Expense:</span>
                <span className="font-mono font-bold text-slate-900">
                  {formatNaira(depResult.annualDepreciation)} <span className="text-[10px] text-slate-500 font-normal">/ yr</span>
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-slate-500">Net Book Value (Year 1 End):</span>
                <span className="font-mono font-bold text-emerald-800">
                  {formatNaira(Math.max(depResult.salvageValue, totalCost - depResult.annualDepreciation))}
                </span>
              </div>
            </div>

            {/* Visual Multi-Year Amortization Micro-Chart */}
            <div className="p-3 bg-[#eff4ff]/60 rounded-xl border border-slate-200/80 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-[10px] uppercase font-bold tracking-wider text-slate-500">
                  {usefulYears}-Year SLM Runout Curve
                </span>
                <span className="text-[10px] font-mono text-slate-600 font-bold">
                  Residual: {formatNaira(depResult.salvageValue)}
                </span>
              </div>
              <div className="w-full h-16 flex items-end">
                <svg className="w-full h-full text-[#00288e]" fill="none" preserveAspectRatio="none" viewBox="0 0 280 60">
                  <path
                    d="M0,8 L40,15 L80,22 L120,28 L160,35 L200,42 L240,48 L280,54 L280,60 L0,60 Z"
                    fill="currentColor"
                    fillOpacity="0.12"
                  />
                  <path
                    d="M0,8 L40,15 L80,22 L120,28 L160,35 L200,42 L240,48 L280,54"
                    stroke="currentColor"
                    strokeLinecap="round"
                    strokeWidth="2.5"
                  />
                  <circle cx="0" cy="8" r="3.5" className="fill-[#00288e]" />
                  <circle cx="140" cy="31" r="2.5" className="fill-[#00288e]" />
                  <circle cx="280" cy="54" r="3.5" className="fill-[#00288e]" />
                </svg>
              </div>
              <div className="flex justify-between text-[9px] font-mono text-slate-500 font-bold">
                <span>Yr 0 ({formatNaira(totalCost)})</span>
                <span>Yr {Math.round(usefulYears / 2)}</span>
                <span>Yr {usefulYears} (Residual)</span>
              </div>
            </div>

            {/* IFRS IAS 16 Standard Verification Checklist */}
            <div className="space-y-1.5 pt-1">
              <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500 block mb-1">
                IFRS IAS 16 Standard Verification
              </span>
              <div className="flex items-center gap-2 p-2 rounded bg-[#eff4ff]/60 text-[11px] border border-slate-200/60">
                <span className="material-symbols-outlined text-[16px] text-emerald-700">check_circle</span>
                <span className="text-slate-800">In-service capitalization date verified</span>
              </div>
              <div className="flex items-center gap-2 p-2 rounded bg-[#eff4ff]/60 text-[11px] border border-slate-200/60">
                <span className="material-symbols-outlined text-[16px] text-emerald-700">check_circle</span>
                <span className="text-slate-800">Conforms to capitalization threshold (&gt;₦500k)</span>
              </div>
              <div className="flex items-center gap-2 p-2 rounded bg-[#eff4ff]/60 text-[11px] border border-slate-200/60">
                <span className="material-symbols-outlined text-[16px] text-emerald-700">check_circle</span>
                <span className="text-slate-800">Designated custodian signed & assigned</span>
              </div>
              <div className="flex items-center gap-2 p-2 rounded bg-[#eff4ff]/60 text-[11px] border border-slate-200/60">
                <span className="material-symbols-outlined text-[16px] text-emerald-700">check_circle</span>
                <span className="text-slate-800">Auto-linked asset tag & RFID code registered</span>
              </div>
            </div>

            {/* Facility Location Map Snapshot */}
            <div className="pt-2">
              <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500 block mb-1">
                Target Installation Hub
              </span>
              <div
                className="w-full h-24 rounded-lg bg-cover bg-center relative overflow-hidden border border-slate-200"
                style={{
                  backgroundImage: `url('https://lh3.googleusercontent.com/aida-public/AB6AXuCnNRvGudeKdgDym3513giixGNmj2DU2YMi1a6bae5fgO7B84GU2a_FZMNz-rNIwn5OC9HUtYtqlnN9_SptEX4zhy2u1BLOURL2vKYPnSjBtawzkJcvh3_Rk_3K3FBQEl56GxN-nbxHuMDDOYPEwLz_wtjx0qMf_edR_O0M5-DX7j4IeYzrUOAFdHUKTA8i4pSXomvu9J0oZliBWRJRmaFXhwd3r-4iwfAlId3p85A7aCrranlwPMGxtg')`,
                }}
              >
                <div className="absolute inset-0 bg-[#00288e]/15"></div>
                <div className="absolute bottom-2 left-2 px-2 py-0.5 bg-white/95 rounded text-[10px] font-bold text-slate-900 flex items-center gap-1 shadow-xs">
                  <span className="material-symbols-outlined text-[13px] text-red-600">location_on</span>
                  <span>Trans-Amadi Hub, Rivers</span>
                </div>
              </div>
            </div>
          </div>

          {/* Quick Action Assist Box: Ledger Journal Preview */}
          <div className="bg-[#eff4ff] p-4 rounded-xl space-y-2 border border-blue-200/70">
            <div className="flex items-center gap-2 text-[#00288e]">
              <span className="material-symbols-outlined text-[18px]">account_balance</span>
              <span className="text-[13px] font-bold">Ledger Journal Preview</span>
            </div>
            <div className="text-[11px] font-mono text-slate-700 space-y-1 bg-white p-2.5 rounded-lg border border-slate-200 shadow-2xs">
              <div className="flex justify-between">
                <span>DR: 1500-01 Plant & Machinery</span>
                <span className="font-bold text-slate-900">{formatNaira(totalCost)}</span>
              </div>
              <div className="flex justify-between text-slate-500">
                <span>CR: 2010-00 Mikano Acc. Payable</span>
                <span className="font-bold">{formatNaira(costBase)}</span>
              </div>
              <div className="flex justify-between text-slate-500">
                <span>CR: 1010-00 Treasury Cash / Outlay</span>
                <span className="font-bold">{formatNaira(totalCost - costBase)}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
