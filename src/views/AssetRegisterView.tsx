/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 * All Assets / Asset Register Table View
 * Matches the Stitch Asset Register design with sorting, filtering, bulk selection, and column controls.
 */

import React, { useState, useEffect, useMemo } from 'react';
import { Asset, AssetCategory, Department, LocationHub } from '../types';
import { assetRepository, AssetFilterParams } from '../services/assetRepository';
import { formatNaira } from '../services/depreciationCalculator';

interface AssetRegisterViewProps {
  onNavigate: (route: string) => void;
  onSelectAsset: (assetId: string) => void;
  onOpenQuickAction: (action: string) => void;
  onTriggerPrintBarcode: (asset: Asset) => void;
  globalSearch: string;
}

export const AssetRegisterView: React.FC<AssetRegisterViewProps> = ({
  onNavigate,
  onSelectAsset,
  onOpenQuickAction,
  onTriggerPrintBarcode,
  globalSearch,
}) => {
  const [assets, setAssets] = useState<Asset[]>([]);
  const [categories, setCategories] = useState<AssetCategory[]>([]);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [locations, setLocations] = useState<LocationHub[]>([]);
  const [totalCount, setTotalCount] = useState<number>(1284);
  const [totalFilteredBookValue, setTotalFilteredBookValue] = useState<number>(2_434_850_000);
  const [loading, setLoading] = useState<boolean>(true);

  // Filters
  const [search, setSearch] = useState<string>(globalSearch || '');
  const [selectedCategory, setSelectedCategory] = useState<string>('All Categories');
  const [selectedDepartment, setSelectedDepartment] = useState<string>('All Departments');
  const [selectedLocation, setSelectedLocation] = useState<string>('All Locations');
  const [selectedStatus, setSelectedStatus] = useState<string>('All Statuses');
  const [selectedAcquisition, setSelectedAcquisition] = useState<string>('All Years');
  const [selectedCostRange, setSelectedCostRange] = useState<string>('₦0 - ₦100M+');
  const [quickFilter, setQuickFilter] = useState<'all' | 'my-custody' | 'needs-audit' | 'warranty-30d'>('all');

  // Pagination
  const [currentPage, setCurrentPage] = useState<number>(1);
  const [pageSize, setPageSize] = useState<number>(10);
  const [viewMode, setViewMode] = useState<'table' | 'card'>('table');

  // Multi-Selection
  const [selectedAssetIds, setSelectedAssetIds] = useState<Set<string>>(new Set(['ast-001', 'ast-002', 'ast-003']));
  const [exportMenuOpen, setExportMenuOpen] = useState<boolean>(false);
  const [columnMenuOpen, setColumnMenuOpen] = useState<boolean>(false);

  // Columns visibility state
  const [visibleColumns, setVisibleColumns] = useState({
    tag: true,
    name: true,
    category: true,
    serial: true,
    deptCustodian: true,
    location: true,
    acquired: true,
    cost: true,
    bookValue: true,
    status: true,
  });

  // Sync with globalSearch if changed from navbar
  useEffect(() => {
    if (globalSearch !== search) {
      setSearch(globalSearch);
    }
  }, [globalSearch]);

  const loadData = async () => {
    setLoading(true);
    try {
      const cats = await assetRepository.getCategories();
      const depts = await assetRepository.getDepartments();
      const locs = await assetRepository.getLocations();
      setCategories(cats);
      setDepartments(depts);
      setLocations(locs);

      const params: AssetFilterParams = {
        search,
        category: selectedCategory,
        department: selectedDepartment,
        location: selectedLocation,
        status: selectedStatus,
        costRange: selectedCostRange,
        quickFilter,
        page: currentPage,
        pageSize,
      };

      const result = await assetRepository.getAssets(params);
      setAssets(result.data);
      setTotalCount(result.total);
      if (result.totalFilteredBookValue !== undefined) {
        setTotalFilteredBookValue(result.totalFilteredBookValue);
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [search, selectedCategory, selectedDepartment, selectedLocation, selectedStatus, selectedCostRange, quickFilter, currentPage, pageSize]);

  // Selection helpers
  const isAllSelected = assets.length > 0 && assets.every(a => selectedAssetIds.has(a.id));
  const toggleSelectAll = () => {
    if (isAllSelected) {
      setSelectedAssetIds(new Set());
    } else {
      const newSet = new Set(selectedAssetIds);
      assets.forEach(a => newSet.add(a.id));
      setSelectedAssetIds(newSet);
    }
  };

  const toggleSelectRow = (id: string) => {
    const newSet = new Set(selectedAssetIds);
    if (newSet.has(id)) {
      newSet.delete(id);
    } else {
      newSet.add(id);
    }
    setSelectedAssetIds(newSet);
  };

  // Export handlers
  const handleExport = (format: 'xlsx' | 'csv' | 'pdf') => {
    setExportMenuOpen(false);
    const content = assets.map(a => `${a.tag},"${a.name}",${a.category_name},${a.serial_number},${a.department_name},${a.location_name},${a.total_acquisition_cost},${a.net_book_value},${a.status}`).join('\n');
    const blob = new Blob([`Asset Tag,Name,Category,Serial,Department,Location,Cost,Book Value,Status\n` + content], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `AssetFlow_Register_${new Date().toISOString().substring(0, 10)}.${format === 'xlsx' ? 'csv' : format}`;
    link.click();
  };

  const getStatusBadge = (status: Asset['status']) => {
    switch (status) {
      case 'ACTIVE':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200/60">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-600"></span>
            ACTIVE
          </span>
        );
      case 'IN_MAINTENANCE':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-bold bg-amber-50 text-amber-800 border border-amber-200/60">
            <span className="w-1.5 h-1.5 rounded-full bg-amber-500"></span>
            IN_MAINTENANCE
          </span>
        );
      case 'TRANSFERRED':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-bold bg-blue-50 text-[#00288e] border border-blue-200/60">
            <span className="w-1.5 h-1.5 rounded-full bg-[#00288e]"></span>
            TRANSFERRED
          </span>
        );
      case 'IMPAIRED':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-bold bg-rose-50 text-rose-700 border border-rose-200/60">
            <span className="w-1.5 h-1.5 rounded-full bg-rose-600"></span>
            IMPAIRED
          </span>
        );
      case 'DISPOSED':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-bold bg-slate-100 text-slate-600 border border-slate-200">
            <span className="w-1.5 h-1.5 rounded-full bg-slate-400"></span>
            DISPOSED
          </span>
        );
      default:
        return null;
    }
  };

  const getCategoryIcon = (categoryName: string) => {
    if (categoryName.includes('Motor') || categoryName.includes('Vehicle')) return 'directions_car';
    if (categoryName.includes('Heavy') || categoryName.includes('Machinery')) return 'precision_manufacturing';
    if (categoryName.includes('IT') || categoryName.includes('Server')) return 'dns';
    if (categoryName.includes('Furniture')) return 'chair';
    if (categoryName.includes('Plant') || categoryName.includes('Generator')) return 'bolt';
    return 'inventory_2';
  };

  return (
    <div className="w-full p-4 md:p-6 select-text">
      {/* Top Context Header Area */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-5">
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-1.5 text-slate-500 text-[12px]">
            <span onClick={() => onNavigate('dashboard')} className="hover:text-[#00288e] cursor-pointer">Home</span>
            <span className="text-slate-300">/</span>
            <span className="text-slate-500">Assets</span>
            <span className="text-slate-300">/</span>
            <span className="text-slate-900 font-bold">All Assets</span>
          </div>
          <div className="flex items-center gap-2.5 mt-0.5">
            <h1 className="text-2xl md:text-[26px] font-bold text-slate-900 tracking-tight">
              Asset Register
            </h1>
            <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-bold bg-[#dce9ff] text-[#00288e]">
              {totalCount.toLocaleString('en-NG')} Total Assets Listed
            </span>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex flex-wrap items-center gap-2">
          {/* Column Visibility Toggle */}
          <div className="relative">
            <button
              onClick={() => setColumnMenuOpen(!columnMenuOpen)}
              className="h-9 px-3 bg-white text-slate-700 font-semibold text-[13px] rounded-lg shadow-2xs hover:bg-slate-50 border border-slate-200 transition-colors flex items-center gap-1.5"
              title="Manage visible table columns"
            >
              <span className="material-symbols-outlined text-[18px] text-slate-500">view_column</span>
              <span>Columns</span>
            </button>

            {columnMenuOpen && (
              <div className="absolute right-0 mt-1 w-52 bg-white rounded-lg shadow-xl border border-slate-200 py-2 z-40 text-[12px]">
                <div className="px-3 pb-1.5 border-b border-slate-100 font-bold text-slate-700">
                  Toggle Columns
                </div>
                <div className="p-2 space-y-1.5 max-h-56 overflow-y-auto">
                  {Object.entries(visibleColumns).map(([key, isVis]) => (
                    <label key={key} className="flex items-center gap-2 px-1 cursor-pointer hover:bg-slate-50 py-0.5 rounded">
                      <input
                        type="checkbox"
                        checked={isVis}
                        onChange={() => setVisibleColumns(prev => ({ ...prev, [key]: !isVis }))}
                        className="rounded text-[#00288e] focus:ring-0 w-3.5 h-3.5"
                      />
                      <span className="capitalize text-slate-700">{key.replace(/([A-Z])/g, ' $1')}</span>
                    </label>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Import Assets */}
          <button
            onClick={() => onNavigate('asset-create')}
            className="h-9 px-3 bg-white text-slate-700 font-semibold text-[13px] rounded-lg shadow-2xs hover:bg-slate-50 border border-slate-200 transition-colors flex items-center gap-1.5"
          >
            <span className="material-symbols-outlined text-[18px] text-slate-500">upload_file</span>
            <span>Import Assets</span>
          </button>

          {/* Export Dropdown */}
          <div className="relative">
            <button
              onClick={() => setExportMenuOpen(!exportMenuOpen)}
              className="h-9 px-3 bg-white text-slate-700 font-semibold text-[13px] rounded-lg shadow-2xs hover:bg-slate-50 border border-slate-200 transition-colors flex items-center gap-1.5"
            >
              <span className="material-symbols-outlined text-[18px] text-slate-500">file_download</span>
              <span>Export</span>
              <span className="material-symbols-outlined text-[16px] text-slate-400">expand_more</span>
            </button>

            {exportMenuOpen && (
              <div className="absolute right-0 mt-1 w-48 bg-white rounded-lg shadow-xl border border-slate-200 py-1 z-40 text-[13px]">
                <button
                  onClick={() => handleExport('xlsx')}
                  className="w-full text-left flex items-center gap-2 px-3 py-2 hover:bg-[#eff4ff] text-slate-700 transition-colors"
                >
                  <span className="material-symbols-outlined text-[16px] text-emerald-700">table_view</span>
                  <span>Excel (.xlsx)</span>
                </button>
                <button
                  onClick={() => handleExport('csv')}
                  className="w-full text-left flex items-center gap-2 px-3 py-2 hover:bg-[#eff4ff] text-slate-700 transition-colors"
                >
                  <span className="material-symbols-outlined text-[16px] text-[#00288e]">description</span>
                  <span>CSV Delimited</span>
                </button>
                <button
                  onClick={() => handleExport('pdf')}
                  className="w-full text-left flex items-center gap-2 px-3 py-2 hover:bg-[#eff4ff] text-slate-700 transition-colors"
                >
                  <span className="material-symbols-outlined text-[16px] text-rose-600">picture_as_pdf</span>
                  <span>PDF Asset Schedule</span>
                </button>
              </div>
            )}
          </div>

          {/* Add Asset CTA */}
          <button
            onClick={() => onNavigate('asset-create')}
            className="h-9 px-3.5 bg-[#00288e] text-white font-semibold text-[13px] rounded-lg shadow-xs hover:bg-[#1e40af] transition-all flex items-center gap-1.5 active:scale-[0.98]"
          >
            <span className="material-symbols-outlined text-[18px]">add_circle</span>
            <span>Add Asset</span>
          </button>
        </div>
      </div>

      {/* Filter & Search Toolbar Container */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200/80 p-4 mb-4 space-y-3">
        {/* Top Search and View Switcher */}
        <div className="flex flex-col lg:flex-row items-stretch lg:items-center justify-between gap-3">
          {/* Search Input */}
          <div className="relative flex-1 max-w-2xl">
            <span className="material-symbols-outlined absolute left-3 top-2 text-[18px] text-slate-400 pointer-events-none">
              search
            </span>
            <input
              value={search}
              onChange={e => setSearch(e.target.value)}
              className="w-full h-9 pl-9 pr-10 bg-[#eff4ff]/80 text-[13px] text-slate-900 rounded-lg placeholder:text-slate-400 focus:outline-none focus:bg-white focus:ring-1.5 focus:ring-[#00288e] border border-slate-200/80 transition-all"
              placeholder="Search by tag (AST-...), serial number, asset name, or custodian..."
              type="text"
            />
            {search && (
              <button
                onClick={() => setSearch('')}
                className="absolute right-3 top-2 text-slate-400 hover:text-slate-600"
              >
                <span className="material-symbols-outlined text-[16px]">close</span>
              </button>
            )}
          </div>

          {/* Quick Toggle Pills & View Mode */}
          <div className="flex flex-wrap items-center justify-between lg:justify-end gap-2">
            <div className="flex items-center gap-1.5 overflow-x-auto py-0.5">
              <button
                onClick={() => setQuickFilter(quickFilter === 'my-custody' ? 'all' : 'my-custody')}
                className={`px-2.5 py-1 rounded text-[11px] font-semibold transition-colors whitespace-nowrap ${
                  quickFilter === 'my-custody'
                    ? 'bg-[#00288e] text-white shadow-xs'
                    : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
                }`}
              >
                My Custody
              </button>

              <button
                onClick={() => setQuickFilter(quickFilter === 'needs-audit' ? 'all' : 'needs-audit')}
                className={`px-2.5 py-1 rounded text-[11px] font-semibold transition-colors flex items-center gap-1 whitespace-nowrap ${
                  quickFilter === 'needs-audit'
                    ? 'bg-rose-700 text-white shadow-xs'
                    : 'bg-red-50 text-red-700 hover:bg-red-100 border border-red-200/60'
                }`}
              >
                <span className={`w-1.5 h-1.5 rounded-full ${quickFilter === 'needs-audit' ? 'bg-white' : 'bg-red-600'}`}></span>
                Needs Audit
              </button>

              <button
                onClick={() => setQuickFilter(quickFilter === 'warranty-30d' ? 'all' : 'warranty-30d')}
                className={`px-2.5 py-1 rounded text-[11px] font-semibold transition-colors whitespace-nowrap ${
                  quickFilter === 'warranty-30d'
                    ? 'bg-amber-700 text-white shadow-xs'
                    : 'bg-amber-50 text-amber-800 hover:bg-amber-100 border border-amber-200/60'
                }`}
              >
                Warranty &lt; 30d
              </button>

              {quickFilter !== 'all' && (
                <button
                  onClick={() => setQuickFilter('all')}
                  className="text-[11px] text-slate-400 hover:text-slate-600 underline px-1"
                >
                  Clear
                </button>
              )}
            </div>

            <div className="flex items-center bg-slate-100 p-0.5 rounded-md border border-slate-200">
              <button
                onClick={() => setViewMode('table')}
                className={`p-1 rounded ${viewMode === 'table' ? 'bg-white text-[#00288e] shadow-2xs' : 'text-slate-500 hover:text-slate-800'}`}
                title="Table View"
              >
                <span className="material-symbols-outlined text-[18px]">table_rows</span>
              </button>
              <button
                onClick={() => setViewMode('card')}
                className={`p-1 rounded ${viewMode === 'card' ? 'bg-white text-[#00288e] shadow-2xs' : 'text-slate-500 hover:text-slate-800'}`}
                title="Card View"
              >
                <span className="material-symbols-outlined text-[18px]">grid_view</span>
              </button>
            </div>
          </div>
        </div>

        {/* Filter Multi-Select Row */}
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-2 pt-1">
          {/* Category Filter */}
          <div className="flex flex-col gap-1">
            <label className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Category</label>
            <select
              value={selectedCategory}
              onChange={e => setSelectedCategory(e.target.value)}
              className="h-8 px-2 bg-[#eff4ff]/60 text-[12px] text-slate-800 rounded border border-slate-200 focus:outline-none focus:ring-1 focus:ring-[#00288e]"
            >
              <option>All Categories</option>
              {categories.map(c => (
                <option key={c.id} value={c.name}>{c.name}</option>
              ))}
            </select>
          </div>

          {/* Department Filter */}
          <div className="flex flex-col gap-1">
            <label className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Department</label>
            <select
              value={selectedDepartment}
              onChange={e => setSelectedDepartment(e.target.value)}
              className="h-8 px-2 bg-[#eff4ff]/60 text-[12px] text-slate-800 rounded border border-slate-200 focus:outline-none focus:ring-1 focus:ring-[#00288e]"
            >
              <option>All Departments</option>
              {departments.map(d => (
                <option key={d.id} value={d.name}>{d.name}</option>
              ))}
            </select>
          </div>

          {/* Location Hub Filter */}
          <div className="flex flex-col gap-1">
            <label className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Location</label>
            <select
              value={selectedLocation}
              onChange={e => setSelectedLocation(e.target.value)}
              className="h-8 px-2 bg-[#eff4ff]/60 text-[12px] text-slate-800 rounded border border-slate-200 focus:outline-none focus:ring-1 focus:ring-[#00288e]"
            >
              <option>All Locations</option>
              {locations.map(l => (
                <option key={l.id} value={l.name}>{l.name}</option>
              ))}
            </select>
          </div>

          {/* Status Filter */}
          <div className="flex flex-col gap-1">
            <label className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Status</label>
            <select
              value={selectedStatus}
              onChange={e => setSelectedStatus(e.target.value)}
              className="h-8 px-2 bg-[#eff4ff]/60 text-[12px] text-slate-800 rounded border border-slate-200 focus:outline-none focus:ring-1 focus:ring-[#00288e]"
            >
              <option>All Statuses</option>
              <option value="ACTIVE">ACTIVE</option>
              <option value="IN_MAINTENANCE">IN_MAINTENANCE</option>
              <option value="TRANSFERRED">TRANSFERRED</option>
              <option value="IMPAIRED">IMPAIRED</option>
              <option value="DISPOSED">DISPOSED</option>
            </select>
          </div>

          {/* Acquisition Year Filter */}
          <div className="flex flex-col gap-1">
            <label className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Acquisition</label>
            <select
              value={selectedAcquisition}
              onChange={e => setSelectedAcquisition(e.target.value)}
              className="h-8 px-2 bg-[#eff4ff]/60 text-[12px] text-slate-800 rounded border border-slate-200 focus:outline-none focus:ring-1 focus:ring-[#00288e]"
            >
              <option>All Years</option>
              <option>FY 2025</option>
              <option>FY 2024</option>
              <option>FY 2023</option>
              <option>FY 2022</option>
              <option>Prior Years</option>
            </select>
          </div>

          {/* Cost Range Filter */}
          <div className="flex flex-col gap-1">
            <label className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Cost Range</label>
            <select
              value={selectedCostRange}
              onChange={e => setSelectedCostRange(e.target.value)}
              className="h-8 px-2 bg-[#eff4ff]/60 text-[12px] text-slate-800 rounded border border-slate-200 focus:outline-none focus:ring-1 focus:ring-[#00288e]"
            >
              <option>₦0 - ₦100M+</option>
              <option>₦0 - ₦10M</option>
              <option>₦10M - ₦50M</option>
              <option>₦50M - ₦150M</option>
              <option>&gt; ₦150M</option>
            </select>
          </div>
        </div>
      </div>

      {/* Bulk Context Action Bar (Active when rows selected) */}
      {selectedAssetIds.size > 0 && (
        <div className="bg-[#dde1ff] text-[#001453] px-4 py-2 rounded-lg shadow-xs mb-3 flex flex-wrap items-center justify-between gap-3 border border-blue-200 transition-all duration-200">
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={selectedAssetIds.size > 0}
                onChange={toggleSelectAll}
                className="w-4 h-4 rounded text-[#00288e] focus:ring-0 cursor-pointer"
              />
              <span className="text-[13px] font-bold">
                {selectedAssetIds.size} assets selected
              </span>
            </div>
            <div className="h-4 w-px bg-blue-300 hidden sm:block"></div>
            <span className="text-[12px] text-blue-900 hidden sm:inline">
              Bulk batch ID: <span className="font-mono font-bold">BCH-2025-0914</span>
            </span>
          </div>

          {/* Action buttons on selection */}
          <div className="flex flex-wrap items-center gap-2">
            <button
              onClick={() => {
                const first = assets.find(a => selectedAssetIds.has(a.id));
                if (first) onTriggerPrintBarcode(first);
              }}
              className="h-7 px-2.5 bg-white text-slate-800 rounded text-[11px] font-semibold hover:bg-slate-50 shadow-2xs flex items-center gap-1 transition-colors"
            >
              <span className="material-symbols-outlined text-[15px] text-[#00288e]">qr_code_2</span>
              <span>Print Labels</span>
            </button>

            <button
              onClick={() => onOpenQuickAction('transfer')}
              className="h-7 px-2.5 bg-white text-slate-800 rounded text-[11px] font-semibold hover:bg-slate-50 shadow-2xs flex items-center gap-1 transition-colors"
            >
              <span className="material-symbols-outlined text-[15px] text-blue-700">swap_horiz</span>
              <span>Bulk Transfer</span>
            </button>

            <button
              onClick={() => onOpenQuickAction('maintenance')}
              className="h-7 px-2.5 bg-white text-slate-800 rounded text-[11px] font-semibold hover:bg-slate-50 shadow-2xs flex items-center gap-1 transition-colors"
            >
              <span className="material-symbols-outlined text-[15px] text-amber-700">handyman</span>
              <span>Schedule Maintenance</span>
            </button>

            <button
              onClick={() => handleExport('csv')}
              className="h-7 px-2.5 bg-white text-slate-800 rounded text-[11px] font-semibold hover:bg-slate-50 shadow-2xs flex items-center gap-1 transition-colors"
            >
              <span className="material-symbols-outlined text-[15px] text-slate-600">download</span>
              <span>Export Selected</span>
            </button>

            <button
              onClick={() => setSelectedAssetIds(new Set())}
              className="h-7 w-7 flex items-center justify-center rounded hover:bg-blue-200 text-blue-900 transition-colors"
              title="Deselect all"
            >
              <span className="material-symbols-outlined text-[18px]">close</span>
            </button>
          </div>
        </div>
      )}

      {/* Enterprise Data Table / Card View Container */}
      {viewMode === 'table' ? (
        <div className="w-full bg-white rounded-xl shadow-sm border border-slate-200/80 overflow-hidden">
          <div className="w-full overflow-x-auto">
            <table className="w-full text-left border-collapse select-text text-[13px]">
              <thead>
                <tr className="bg-[#eff4ff] text-slate-600 text-[11px] font-bold uppercase tracking-wider h-10 select-none border-b border-slate-200">
                  <th className="w-10 px-3 text-center">
                    <input
                      type="checkbox"
                      checked={isAllSelected}
                      onChange={toggleSelectAll}
                      className="w-4 h-4 rounded text-[#00288e] focus:ring-0 cursor-pointer"
                    />
                  </th>
                  {visibleColumns.tag && <th className="px-3 py-2 font-bold">Asset Tag</th>}
                  {visibleColumns.name && <th className="px-3 py-2 font-bold min-w-[220px]">Asset Name & Spec</th>}
                  {visibleColumns.category && <th className="px-3 py-2 font-bold">Category</th>}
                  {visibleColumns.serial && <th className="px-3 py-2 font-bold">Serial Number</th>}
                  {visibleColumns.deptCustodian && (
                    <th className="px-3 py-2 font-bold min-w-[180px]">Department & Custodian</th>
                  )}
                  {visibleColumns.location && <th className="px-3 py-2 font-bold">Location</th>}
                  {visibleColumns.acquired && <th className="px-3 py-2 font-bold">Acquired</th>}
                  {visibleColumns.cost && <th className="px-3 py-2 font-bold text-right">Cost (₦)</th>}
                  {visibleColumns.bookValue && (
                    <th className="px-3 py-2 font-bold text-right">Book Value (₦)</th>
                  )}
                  {visibleColumns.status && <th className="px-3 py-2 font-bold text-center">Status</th>}
                  <th className="w-20 px-3 py-2 text-center font-bold">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {assets.length === 0 ? (
                  <tr>
                    <td colSpan={12} className="py-12 text-center text-slate-500">
                      <span className="material-symbols-outlined text-[36px] text-slate-300 block mb-1">
                        search_off
                      </span>
                      No fixed assets found matching the selected filter criteria.
                    </td>
                  </tr>
                ) : (
                  assets.map(asset => {
                    const isSelected = selectedAssetIds.has(asset.id);
                    return (
                      <tr
                        key={asset.id}
                        className={`transition-colors h-11 ${
                          isSelected ? 'bg-[#eff4ff]/60 hover:bg-[#eff4ff]' : 'hover:bg-slate-50/80'
                        }`}
                      >
                        <td className="px-3 text-center">
                          <input
                            type="checkbox"
                            checked={isSelected}
                            onChange={() => toggleSelectRow(asset.id)}
                            className="w-4 h-4 rounded text-[#00288e] focus:ring-0 cursor-pointer"
                          />
                        </td>

                        {visibleColumns.tag && (
                          <td className="px-3 py-2 whitespace-nowrap">
                            <div className="flex items-center gap-1.5">
                              <span
                                onClick={() => onTriggerPrintBarcode(asset)}
                                className="material-symbols-outlined text-[16px] text-slate-400 hover:text-[#00288e] cursor-pointer"
                                title="Print Zebra Thermal Tag"
                              >
                                qr_code
                              </span>
                              <button
                                onClick={() => onSelectAsset(asset.id)}
                                className="font-mono font-bold text-[#00288e] hover:underline text-left"
                              >
                                {asset.tag}
                              </button>
                            </div>
                          </td>
                        )}

                        {visibleColumns.name && (
                          <td className="px-3 py-2">
                            <div
                              onClick={() => onSelectAsset(asset.id)}
                              className="flex items-center gap-2 cursor-pointer group"
                            >
                              <span className="material-symbols-outlined text-[18px] text-slate-500 bg-slate-100 p-1 rounded group-hover:bg-[#dce9ff] group-hover:text-[#00288e] transition-colors">
                                {getCategoryIcon(asset.category_name)}
                              </span>
                              <div>
                                <div className="font-semibold text-slate-900 leading-tight group-hover:text-[#00288e] transition-colors">
                                  {asset.name}
                                </div>
                                <div className="text-[11px] text-slate-500 leading-tight">
                                  {asset.spec || asset.model}
                                </div>
                              </div>
                            </div>
                          </td>
                        )}

                        {visibleColumns.category && (
                          <td className="px-3 py-2 whitespace-nowrap text-slate-600">
                            {asset.category_name}
                          </td>
                        )}

                        {visibleColumns.serial && (
                          <td className="px-3 py-2 font-mono text-slate-500 whitespace-nowrap text-[12px]">
                            {asset.serial_number}
                          </td>
                        )}

                        {visibleColumns.deptCustodian && (
                          <td className="px-3 py-2 whitespace-nowrap">
                            <div className="leading-tight font-semibold text-slate-900">
                              {asset.custodian_name}
                            </div>
                            <div className="text-[11px] text-slate-500">
                              {asset.department_name}
                            </div>
                          </td>
                        )}

                        {visibleColumns.location && (
                          <td className="px-3 py-2 whitespace-nowrap text-slate-600">
                            {asset.location_name}
                          </td>
                        )}

                        {visibleColumns.acquired && (
                          <td className="px-3 py-2 whitespace-nowrap text-slate-500 text-[12px]">
                            {asset.acquisition_date}
                          </td>
                        )}

                        {visibleColumns.cost && (
                          <td className="px-3 py-2 text-right font-mono font-medium text-slate-700 whitespace-nowrap">
                            {asset.total_acquisition_cost.toLocaleString('en-NG', { minimumFractionDigits: 2 })}
                          </td>
                        )}

                        {visibleColumns.bookValue && (
                          <td className="px-3 py-2 text-right font-mono font-bold text-slate-900 whitespace-nowrap">
                            {asset.net_book_value.toLocaleString('en-NG', { minimumFractionDigits: 2 })}
                          </td>
                        )}

                        {visibleColumns.status && (
                          <td className="px-3 py-2 text-center whitespace-nowrap">
                            {getStatusBadge(asset.status)}
                          </td>
                        )}

                        <td className="px-3 py-2 text-center whitespace-nowrap">
                          <div className="flex items-center justify-center gap-1">
                            <button
                              onClick={() => onSelectAsset(asset.id)}
                              className="w-7 h-7 flex items-center justify-center rounded hover:bg-[#eff4ff] text-slate-500 hover:text-[#00288e] transition-colors"
                              title="View Asset Details"
                            >
                              <span className="material-symbols-outlined text-[16px]">visibility</span>
                            </button>
                            <button
                              onClick={() => onTriggerPrintBarcode(asset)}
                              className="w-7 h-7 flex items-center justify-center rounded hover:bg-[#eff4ff] text-slate-500 hover:text-[#00288e] transition-colors"
                              title="Print Tag"
                            >
                              <span className="material-symbols-outlined text-[16px]">print</span>
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>

          {/* Table Pagination & Aggregate Footer */}
          <div className="p-3.5 bg-[#eff4ff]/60 border-t border-slate-200 flex flex-col md:flex-row items-center justify-between gap-3 text-[12px] select-none">
            {/* Left Statistics */}
            <div className="flex flex-wrap items-center gap-2 text-slate-600">
              <span>
                Showing <strong className="text-slate-900 font-bold">{Math.min(1, assets.length)}</strong> to{' '}
                <strong className="text-slate-900 font-bold">{assets.length}</strong> of{' '}
                <strong className="text-slate-900 font-bold">{totalCount.toLocaleString('en-NG')}</strong> entries
              </span>
              <span className="text-slate-300">|</span>
              <span className="inline-flex items-center gap-1">
                Total Filtered Book Value:{' '}
                <span className="font-mono font-bold text-[#00288e]">
                  {formatNaira(totalFilteredBookValue, true)}
                </span>
              </span>
            </div>

            {/* Rows Per Page */}
            <div className="flex items-center gap-2 text-slate-600">
              <span>Rows per page:</span>
              <select
                value={pageSize}
                onChange={e => setPageSize(parseInt(e.target.value))}
                className="h-7 px-2 bg-white text-slate-800 rounded font-semibold border border-slate-200 shadow-2xs focus:outline-none focus:ring-1 focus:ring-[#00288e]"
              >
                <option value={10}>10</option>
                <option value={25}>25</option>
                <option value={50}>50</option>
                <option value={100}>100</option>
              </select>
            </div>

            {/* Pagination Controls */}
            <div className="flex items-center gap-1 font-medium">
              <button
                onClick={() => setCurrentPage(1)}
                disabled={currentPage === 1}
                className="w-7 h-7 flex items-center justify-center rounded bg-white border border-slate-200 text-slate-600 hover:bg-slate-50 disabled:opacity-40"
                title="First Page"
              >
                <span className="material-symbols-outlined text-[16px]">first_page</span>
              </button>
              <button
                onClick={() => setCurrentPage(prev => Math.max(1, prev - 1))}
                disabled={currentPage === 1}
                className="w-7 h-7 flex items-center justify-center rounded bg-white border border-slate-200 text-slate-600 hover:bg-slate-50 disabled:opacity-40"
                title="Previous Page"
              >
                <span className="material-symbols-outlined text-[16px]">chevron_left</span>
              </button>

              <button className="w-7 h-7 flex items-center justify-center rounded bg-[#00288e] text-white font-bold shadow-2xs">
                {currentPage}
              </button>
              <button
                onClick={() => setCurrentPage(prev => prev + 1)}
                className="w-7 h-7 flex items-center justify-center rounded bg-white border border-slate-200 text-slate-700 hover:bg-slate-50"
              >
                {currentPage + 1}
              </button>
              <button
                onClick={() => setCurrentPage(prev => prev + 2)}
                className="w-7 h-7 flex items-center justify-center rounded bg-white border border-slate-200 text-slate-700 hover:bg-slate-50"
              >
                {currentPage + 2}
              </button>
              <span className="px-1 text-slate-400">...</span>
              <button
                onClick={() => setCurrentPage(129)}
                className="w-7 h-7 flex items-center justify-center rounded bg-white border border-slate-200 text-slate-700 hover:bg-slate-50"
              >
                129
              </button>

              <button
                onClick={() => setCurrentPage(prev => prev + 1)}
                className="w-7 h-7 flex items-center justify-center rounded bg-white border border-slate-200 text-slate-600 hover:bg-slate-50"
                title="Next Page"
              >
                <span className="material-symbols-outlined text-[16px]">chevron_right</span>
              </button>
              <button
                onClick={() => setCurrentPage(129)}
                className="w-7 h-7 flex items-center justify-center rounded bg-white border border-slate-200 text-slate-600 hover:bg-slate-50"
                title="Last Page"
              >
                <span className="material-symbols-outlined text-[16px]">last_page</span>
              </button>
            </div>
          </div>
        </div>
      ) : (
        /* Card Grid View */
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {assets.map(asset => (
            <div
              key={asset.id}
              onClick={() => onSelectAsset(asset.id)}
              className="bg-white rounded-xl shadow-sm border border-slate-200/80 p-4 cursor-pointer hover:shadow-md transition-all flex flex-col justify-between"
            >
              <div>
                <div className="flex items-start justify-between">
                  <span className="font-mono text-[12px] font-bold text-[#00288e]">{asset.tag}</span>
                  {getStatusBadge(asset.status)}
                </div>
                <h3 className="font-bold text-slate-900 mt-1 text-[14px] leading-tight">
                  {asset.name}
                </h3>
                <p className="text-[11px] text-slate-500 mt-0.5">{asset.category_name}</p>

                <div className="mt-3 p-2 bg-[#eff4ff] rounded text-[11px] space-y-1">
                  <div className="flex justify-between">
                    <span className="text-slate-500">Location:</span>
                    <span className="font-medium text-slate-800">{asset.location_name}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">Custodian:</span>
                    <span className="font-medium text-slate-800">{asset.custodian_name}</span>
                  </div>
                </div>
              </div>

              <div className="mt-4 pt-2 border-t border-slate-100 flex items-center justify-between">
                <div>
                  <span className="text-[10px] text-slate-400 uppercase font-bold block">Current NBV</span>
                  <span className="font-mono font-bold text-[#00288e] text-[14px]">
                    ₦{asset.net_book_value.toLocaleString('en-NG')}
                  </span>
                </div>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    onTriggerPrintBarcode(asset);
                  }}
                  className="p-1.5 rounded-lg bg-slate-100 hover:bg-[#eff4ff] text-slate-600 hover:text-[#00288e]"
                  title="Print Tag"
                >
                  <span className="material-symbols-outlined text-[18px]">qr_code</span>
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Operational Lifecycle Analytics Strip */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mt-5">
        <div className="bg-white rounded-xl p-4 shadow-sm border border-slate-200/80 flex items-center justify-between">
          <div className="flex flex-col">
            <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
              Active Assets
            </span>
            <span className="text-2xl font-bold text-slate-900 mt-0.5">1,192</span>
            <span className="text-[11px] text-emerald-700 font-semibold mt-0.5">
              92.8% Operational Availability
            </span>
          </div>
          <div className="w-10 h-10 rounded-full bg-emerald-50 flex items-center justify-center text-emerald-700">
            <span className="material-symbols-outlined text-[20px]">check_circle</span>
          </div>
        </div>

        <div className="bg-white rounded-xl p-4 shadow-sm border border-slate-200/80 flex items-center justify-between">
          <div className="flex flex-col">
            <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
              Maintenance In-Progress
            </span>
            <span className="text-2xl font-bold text-slate-900 mt-0.5">48</span>
            <span className="text-[11px] text-amber-700 font-semibold mt-0.5">
              6 Overdue Service SLAs
            </span>
          </div>
          <div className="w-10 h-10 rounded-full bg-amber-50 flex items-center justify-center text-amber-700">
            <span className="material-symbols-outlined text-[20px]">build_circle</span>
          </div>
        </div>

        <div className="bg-white rounded-xl p-4 shadow-sm border border-slate-200/80 flex items-center justify-between">
          <div className="flex flex-col">
            <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
              Inter-Facility Transit
            </span>
            <span className="text-2xl font-bold text-slate-900 mt-0.5">29</span>
            <span className="text-[11px] text-[#00288e] font-semibold mt-0.5">
              4 Waybills Pending Receipt
            </span>
          </div>
          <div className="w-10 h-10 rounded-full bg-blue-50 flex items-center justify-center text-[#00288e]">
            <span className="material-symbols-outlined text-[20px]">local_shipping</span>
          </div>
        </div>

        <div className="bg-white rounded-xl p-4 shadow-sm border border-slate-200/80 flex items-center justify-between">
          <div className="flex flex-col">
            <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
              Impaired & Staged
            </span>
            <span className="text-2xl font-bold text-slate-900 mt-0.5">15</span>
            <span className="text-[11px] text-rose-700 font-semibold mt-0.5">
              ₦81.6M Salvage Target
            </span>
          </div>
          <div className="w-10 h-10 rounded-full bg-rose-50 flex items-center justify-center text-rose-700">
            <span className="material-symbols-outlined text-[20px]">report_problem</span>
          </div>
        </div>
      </div>
    </div>
  );
};
