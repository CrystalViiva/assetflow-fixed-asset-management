/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 * AssetFlow — Fixed Asset Management System
 * Core Application Controller & Routing Engine
 */

import React, { useState, useEffect, useCallback } from 'react';
import { Navbar } from './components/layout/Navbar';
import { Sidebar } from './components/layout/Sidebar';
import { Breadcrumbs } from './components/layout/Breadcrumbs';

// Views
import { DashboardView } from './views/DashboardView';
import { AssetRegisterView } from './views/AssetRegisterView';
import { AssetDetailView } from './views/AssetDetailView';
import { AssetCreateView } from './views/AssetCreateView';
import { CategoriesView } from './views/CategoriesView';
import { AcquisitionsView } from './views/AcquisitionsView';
import { AssignmentsView } from './views/AssignmentsView';
import { TransfersView } from './views/TransfersView';
import { DepreciationView } from './views/DepreciationView';
import { MaintenanceView } from './views/MaintenanceView';
import { DisposalsView } from './views/DisposalsView';
import { ReportsView } from './views/ReportsView';
import { DepartmentsView } from './views/DepartmentsView';
import { LocationsView } from './views/LocationsView';
import { UsersRolesView } from './views/UsersRolesView';
import { AuditLogView } from './views/AuditLogView';
import { SettingsView } from './views/SettingsView';

// Modals
import { PrintBarcodeModal } from './components/modals/PrintBarcodeModal';
import { InitiateTransferModal } from './components/modals/InitiateTransferModal';
import { LogMaintenanceModal } from './components/modals/LogMaintenanceModal';
import { DisposeAssetModal } from './components/modals/DisposeAssetModal';

// Types & Services
import { Asset, AssetCategory, Department, LocationHub, Transfer, MaintenanceRecord, DisposalRecord } from './types';
import { assetRepository } from './services/assetRepository';

interface ToastNotification {
  id: string;
  type: 'success' | 'info' | 'warning' | 'error';
  title: string;
  message: string;
}

export default function App() {
  // Navigation State (hash-supported)
  const [currentRoute, setCurrentRoute] = useState<string>('dashboard');
  const [selectedAssetId, setSelectedAssetId] = useState<string>('AST-000002');
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState<boolean>(false);
  const [globalSearch, setGlobalSearch] = useState<string>('');

  // Domain Master Data
  const [assets, setAssets] = useState<Asset[]>([]);
  const [categories, setCategories] = useState<AssetCategory[]>([]);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [locations, setLocations] = useState<LocationHub[]>([]);

  // Modal State
  const [barcodeModalOpen, setBarcodeModalOpen] = useState(false);
  const [selectedBarcodeAsset, setSelectedBarcodeAsset] = useState<Asset | null>(null);

  const [transferModalOpen, setTransferModalOpen] = useState(false);
  const [selectedTransferAsset, setSelectedTransferAsset] = useState<Asset | null>(null);

  const [maintenanceModalOpen, setMaintenanceModalOpen] = useState(false);
  const [selectedMaintenanceAsset, setSelectedMaintenanceAsset] = useState<Asset | null>(null);

  const [disposalModalOpen, setDisposalModalOpen] = useState(false);
  const [selectedDisposalAsset, setSelectedDisposalAsset] = useState<Asset | null>(null);

  // Toast Notifications
  const [toasts, setToasts] = useState<ToastNotification[]>([]);

  const addToast = (type: 'success' | 'info' | 'warning' | 'error', title: string, message: string) => {
    const id = Math.random().toString(36).substring(2, 9);
    setToasts((prev) => [...prev, { id, type, title, message }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 4500);
  };

  const removeToast = (id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  };

  // Load initial data
  const loadMasterData = useCallback(async () => {
    try {
      const [assetListRes, catList, deptList, locList] = await Promise.all([
        assetRepository.getAssets({ pageSize: 100 }),
        assetRepository.getCategories(),
        assetRepository.getDepartments(),
        assetRepository.getLocations(),
      ]);
      setAssets(assetListRes.data);
      setCategories(catList);
      setDepartments(deptList);
      setLocations(locList);
    } catch (err) {
      console.error('Failed loading master data', err);
    }
  }, []);

  useEffect(() => {
    loadMasterData();
  }, [loadMasterData]);

  // Sync hash routing
  useEffect(() => {
    const handleHashChange = () => {
      const hash = window.location.hash.replace('#', '').trim();
      if (hash) {
        if (hash.startsWith('asset-detail/')) {
          const id = hash.replace('asset-detail/', '');
          setSelectedAssetId(id);
          setCurrentRoute('asset-detail');
        } else {
          setCurrentRoute(hash);
        }
      }
    };

    if (window.location.hash) {
      handleHashChange();
    }
    window.addEventListener('hashchange', handleHashChange);
    return () => window.removeEventListener('hashchange', handleHashChange);
  }, []);

  const navigateTo = (route: string) => {
    setCurrentRoute(route);
    window.location.hash = route;
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const handleSelectAsset = (assetId: string) => {
    setSelectedAssetId(assetId);
    setCurrentRoute('asset-detail');
    window.location.hash = `asset-detail/${assetId}`;
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  // Quick Action Handler (from Navbar or Views)
  const handleOpenQuickAction = (action: string) => {
    const targetAsset = assets.find((a) => a.id === selectedAssetId) || assets[0] || null;
    if (action === 'transfer') {
      setSelectedTransferAsset(targetAsset);
      setTransferModalOpen(true);
    } else if (action === 'maintenance') {
      setSelectedMaintenanceAsset(targetAsset);
      setMaintenanceModalOpen(true);
    } else if (action === 'disposal') {
      setSelectedDisposalAsset(targetAsset);
      setDisposalModalOpen(true);
    } else if (action === 'register' || action === 'asset-create') {
      navigateTo('asset-create');
    }
  };

  // Barcode Printing trigger
  const handleTriggerPrintBarcode = (asset: Asset) => {
    setSelectedBarcodeAsset(asset);
    setBarcodeModalOpen(true);
  };

  // Workflow Handlers
  const handleSubmitTransfer = async (transferData: Partial<Transfer>) => {
    try {
      await assetRepository.createTransfer(transferData);
      setTransferModalOpen(false);
      addToast(
        'success',
        'Transfer Initiated',
        `Asset movement workflow logged. Sent for Head of Operations sign-off.`
      );
      await loadMasterData();
    } catch (err) {
      addToast('error', 'Transfer Failed', 'Unable to record transfer at this time.');
    }
  };

  const handleSubmitMaintenance = async (data: Partial<MaintenanceRecord>) => {
    try {
      await assetRepository.createMaintenance(data);
      setMaintenanceModalOpen(false);
      addToast(
        'success',
        'Work Order Created',
        `Maintenance order ${data.work_order_no || ''} recorded successfully.`
      );
      await loadMasterData();
    } catch (err) {
      addToast('error', 'Work Order Failed', 'Unable to create work order.');
    }
  };

  const handleSubmitDisposal = async (data: Partial<DisposalRecord>) => {
    try {
      await assetRepository.createDisposal(data);
      setDisposalModalOpen(false);
      addToast(
        'warning',
        'Disposal Registered',
        `Asset de-capitalization and journal entry submitted for Audit review.`
      );
      await loadMasterData();
    } catch (err) {
      addToast('error', 'Disposal Failed', 'Unable to record asset disposal.');
    }
  };

  const handleAssetCreated = (newAsset: Asset) => {
    addToast(
      'success',
      'Asset Capitalized & Registered',
      `${newAsset.tag} — ${newAsset.name} has been added to the Active Asset Ledger.`
    );
    loadMasterData();
    setSelectedAssetId(newAsset.id);
    navigateTo('asset-detail');
  };

  // Render current view
  const renderCurrentView = () => {
    switch (currentRoute) {
      case 'dashboard':
        return (
          <DashboardView
            onNavigate={navigateTo}
            onSelectAsset={handleSelectAsset}
            onOpenQuickAction={handleOpenQuickAction}
          />
        );
      case 'all-assets':
        return (
          <AssetRegisterView
            onNavigate={navigateTo}
            onSelectAsset={handleSelectAsset}
            onOpenQuickAction={handleOpenQuickAction}
            onTriggerPrintBarcode={handleTriggerPrintBarcode}
            globalSearch={globalSearch}
          />
        );
      case 'asset-detail':
        return (
          <AssetDetailView
            assetId={selectedAssetId}
            onNavigate={navigateTo}
            onTriggerPrintBarcode={handleTriggerPrintBarcode}
            onTriggerTransfer={(asset) => {
              setSelectedTransferAsset(asset);
              setTransferModalOpen(true);
            }}
            onTriggerMaintenance={(asset) => {
              setSelectedMaintenanceAsset(asset);
              setMaintenanceModalOpen(true);
            }}
            onTriggerDisposal={(asset) => {
              setSelectedDisposalAsset(asset);
              setDisposalModalOpen(true);
            }}
          />
        );
      case 'asset-create':
        return (
          <AssetCreateView
            categories={categories}
            departments={departments}
            locations={locations}
            onNavigate={navigateTo}
            onAssetCreated={handleAssetCreated}
          />
        );
      case 'asset-categories':
        return <CategoriesView onNavigate={navigateTo} />;
      case 'acquisitions':
        return (
          <AcquisitionsView
            onNavigate={navigateTo}
            onSelectAsset={handleSelectAsset}
          />
        );
      case 'transfers':
        return (
          <TransfersView
            onNavigate={navigateTo}
            onSelectAsset={handleSelectAsset}
            onOpenInitiateTransfer={() => {
              setSelectedTransferAsset(assets[0] || null);
              setTransferModalOpen(true);
            }}
          />
        );
      case 'assignments':
        return (
          <AssignmentsView
            onNavigate={navigateTo}
            onSelectAsset={handleSelectAsset}
          />
        );
      case 'depreciation':
        return (
          <DepreciationView
            onNavigate={navigateTo}
            onSelectAsset={handleSelectAsset}
          />
        );
      case 'maintenance':
        return (
          <MaintenanceView
            onNavigate={navigateTo}
            onSelectAsset={handleSelectAsset}
            onOpenLogMaintenance={() => {
              setSelectedMaintenanceAsset(assets[0] || null);
              setMaintenanceModalOpen(true);
            }}
          />
        );
      case 'disposals':
        return (
          <DisposalsView
            onNavigate={navigateTo}
            onSelectAsset={handleSelectAsset}
            onOpenDisposeAsset={() => {
              setSelectedDisposalAsset(assets[0] || null);
              setDisposalModalOpen(true);
            }}
          />
        );
      case 'reports':
        return (
          <ReportsView
            onNavigate={navigateTo}
            onSelectAsset={handleSelectAsset}
          />
        );
      case 'departments':
        return <DepartmentsView onNavigate={navigateTo} />;
      case 'locations':
        return <LocationsView onNavigate={navigateTo} />;
      case 'users-and-roles':
        return <UsersRolesView onNavigate={navigateTo} />;
      case 'audit-log':
        return (
          <AuditLogView
            onNavigate={navigateTo}
            onSelectAsset={handleSelectAsset}
          />
        );
      case 'settings':
        return <SettingsView onNavigate={navigateTo} />;
      default:
        return (
          <DashboardView
            onNavigate={navigateTo}
            onSelectAsset={handleSelectAsset}
            onOpenQuickAction={handleOpenQuickAction}
          />
        );
    }
  };

  return (
    <div className="min-h-screen bg-[#f8f9ff] text-[#0b1c30] flex flex-col font-sans antialiased">
      {/* Top Navbar */}
      <Navbar
        onNavigate={navigateTo}
        onOpenQuickAction={handleOpenQuickAction}
        globalSearch={globalSearch}
        setGlobalSearch={setGlobalSearch}
      />

      {/* Main Layout Container */}
      <div className="flex flex-1 pt-12">
        {/* Left Sidebar */}
        <Sidebar
          currentRoute={currentRoute}
          onNavigate={navigateTo}
          isCollapsed={isSidebarCollapsed}
          onToggleCollapse={() => setIsSidebarCollapsed(!isSidebarCollapsed)}
        />

        {/* Content Region */}
        <main
          className={`flex-1 flex flex-col transition-all duration-200 min-w-0 ${
            isSidebarCollapsed ? 'ml-16' : 'ml-64'
          }`}
        >
          {/* Subheader Breadcrumbs with Real-time Clock */}
          <Breadcrumbs
            currentRoute={currentRoute}
            subTitle={currentRoute === 'asset-detail' ? `Asset Detail: ${selectedAssetId}` : undefined}
            onNavigate={navigateTo}
          />

          {/* Active View Container */}
          <div className="flex-1 w-full max-w-[1680px] mx-auto">
            {renderCurrentView()}
          </div>
        </main>
      </div>

      {/* Reusable Action Modals */}
      <PrintBarcodeModal
        isOpen={barcodeModalOpen}
        onClose={() => setBarcodeModalOpen(false)}
        asset={selectedBarcodeAsset}
      />

      <InitiateTransferModal
        isOpen={transferModalOpen}
        onClose={() => setTransferModalOpen(false)}
        selectedAsset={selectedTransferAsset}
        assets={assets}
        departments={departments}
        locations={locations}
        onSubmitTransfer={handleSubmitTransfer}
      />

      <LogMaintenanceModal
        isOpen={maintenanceModalOpen}
        onClose={() => setMaintenanceModalOpen(false)}
        selectedAsset={selectedMaintenanceAsset}
        assets={assets}
        onSubmitMaintenance={handleSubmitMaintenance}
      />

      <DisposeAssetModal
        isOpen={disposalModalOpen}
        onClose={() => setDisposalModalOpen(false)}
        selectedAsset={selectedDisposalAsset}
        assets={assets}
        onSubmitDisposal={handleSubmitDisposal}
      />

      {/* Floating Enterprise Toast Notifications */}
      <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 max-w-sm pointer-events-none">
        {toasts.map((toast) => (
          <div
            key={toast.id}
            className={`pointer-events-auto p-3.5 rounded-lg shadow-lg border text-[13px] flex items-start gap-3 bg-white transition-all transform animate-in slide-in-from-bottom-3 ${
              toast.type === 'success'
                ? 'border-emerald-200 text-emerald-950 shadow-emerald-900/5'
                : toast.type === 'warning'
                ? 'border-amber-200 text-amber-950 shadow-amber-900/5'
                : toast.type === 'error'
                ? 'border-rose-200 text-rose-950 shadow-rose-900/5'
                : 'border-blue-200 text-blue-950 shadow-blue-900/5'
            }`}
          >
            <span
              className={`material-symbols-outlined text-[20px] shrink-0 mt-0.5 ${
                toast.type === 'success'
                  ? 'text-emerald-600'
                  : toast.type === 'warning'
                  ? 'text-amber-600'
                  : toast.type === 'error'
                  ? 'text-rose-600'
                  : 'text-blue-600'
              }`}
            >
              {toast.type === 'success'
                ? 'check_circle'
                : toast.type === 'warning'
                ? 'warning'
                : toast.type === 'error'
                ? 'error'
                : 'info'}
            </span>
            <div className="flex-1 min-w-0">
              <div className="font-bold text-[13px] text-slate-900 leading-snug">
                {toast.title}
              </div>
              <div className="text-[12px] text-slate-600 leading-normal mt-0.5">
                {toast.message}
              </div>
            </div>
            <button
              onClick={() => removeToast(toast.id)}
              className="text-slate-400 hover:text-slate-600 p-0.5 transition-colors"
            >
              <span className="material-symbols-outlined text-[16px]">close</span>
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
