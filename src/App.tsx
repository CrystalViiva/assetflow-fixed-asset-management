/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 * AssetFlow — Fixed Asset Management System
 * Core Application Controller & Routing Engine
 */

import React, { lazy, Suspense, useState, useEffect, useCallback } from 'react';
import { Navbar } from './components/layout/Navbar';
import { Sidebar } from './components/layout/Sidebar';
import { Breadcrumbs } from './components/layout/Breadcrumbs';

// Feature screens load only when the user opens that area.
const DashboardView = lazy(() => import('./views/DashboardView').then(m => ({ default: m.DashboardView })));
const BackendDashboardView = lazy(() => import('./views/BackendDashboardView').then(m => ({ default: m.BackendDashboardView })));
const AssetRegisterView = lazy(() => import('./views/AssetRegisterView').then(m => ({ default: m.AssetRegisterView })));
const AssetDetailView = lazy(() => import('./views/AssetDetailView').then(m => ({ default: m.AssetDetailView })));
const AssetCreateView = lazy(() => import('./views/AssetCreateView').then(m => ({ default: m.AssetCreateView })));
const CategoriesView = lazy(() => import('./views/CategoriesView').then(m => ({ default: m.CategoriesView })));
const AcquisitionsView = lazy(() => import('./views/AcquisitionsView').then(m => ({ default: m.AcquisitionsView })));
const AssignmentsView = lazy(() => import('./views/AssignmentsView').then(m => ({ default: m.AssignmentsView })));
const BackendAssignmentsView = lazy(() => import('./views/BackendAssignmentsView').then(m => ({ default: m.BackendAssignmentsView })));
const TransfersView = lazy(() => import('./views/TransfersView').then(m => ({ default: m.TransfersView })));
const BackendTransfersView = lazy(() => import('./views/BackendTransfersView').then(m => ({ default: m.BackendTransfersView })));
const DepreciationView = lazy(() => import('./views/DepreciationView').then(m => ({ default: m.DepreciationView })));
const BackendDepreciationView = lazy(() => import('./views/BackendDepreciationView').then(m => ({ default: m.BackendDepreciationView })));
const MaintenanceView = lazy(() => import('./views/MaintenanceView').then(m => ({ default: m.MaintenanceView })));
const BackendMaintenanceView = lazy(() => import('./views/BackendMaintenanceView').then(m => ({ default: m.BackendMaintenanceView })));
const DisposalsView = lazy(() => import('./views/DisposalsView').then(m => ({ default: m.DisposalsView })));
const BackendDisposalsView = lazy(() => import('./views/BackendDisposalsView').then(m => ({ default: m.BackendDisposalsView })));
const BackendVerificationView = lazy(() => import('./views/BackendVerificationView').then(m => ({ default: m.BackendVerificationView })));
const BackendAssuranceView = lazy(() => import('./views/BackendAssuranceView').then(m => ({ default: m.BackendAssuranceView })));
const MockVerificationView = lazy(() => import('./views/MockVerificationView').then(m => ({ default: m.MockVerificationView })));
const MockAssuranceView = lazy(() => import('./views/MockAssuranceView').then(m => ({ default: m.MockAssuranceView })));
const ReportsView = lazy(() => import('./views/ReportsView').then(m => ({ default: m.ReportsView })));
const BackendReportsView = lazy(() => import('./views/BackendReportsView').then(m => ({ default: m.BackendReportsView })));
const DepartmentsView = lazy(() => import('./views/DepartmentsView').then(m => ({ default: m.DepartmentsView })));
const LocationsView = lazy(() => import('./views/LocationsView').then(m => ({ default: m.LocationsView })));
const UsersRolesView = lazy(() => import('./views/UsersRolesView').then(m => ({ default: m.UsersRolesView })));
const BackendOrganizationAdminView = lazy(() => import('./views/BackendOrganizationAdminView').then(m => ({ default: m.BackendOrganizationAdminView })));
const AuditLogView = lazy(() => import('./views/AuditLogView').then(m => ({ default: m.AuditLogView })));
const BackendAuditLogView = lazy(() => import('./views/BackendAuditLogView').then(m => ({ default: m.BackendAuditLogView })));
const SettingsView = lazy(() => import('./views/SettingsView').then(m => ({ default: m.SettingsView })));

// Modals
const PrintBarcodeModal = lazy(() => import('./components/modals/PrintBarcodeModal').then(m => ({ default: m.PrintBarcodeModal })));
const InitiateTransferModal = lazy(() => import('./components/modals/InitiateTransferModal').then(m => ({ default: m.InitiateTransferModal })));
const LogMaintenanceModal = lazy(() => import('./components/modals/LogMaintenanceModal').then(m => ({ default: m.LogMaintenanceModal })));
const DisposeAssetModal = lazy(() => import('./components/modals/DisposeAssetModal').then(m => ({ default: m.DisposeAssetModal })));

// Types & Services
import { Asset, AssetCategory, Department, LocationHub, Transfer, MaintenanceRecord, DisposalRecord } from './types';
import { assetRepository } from './services/assetRepository';
import { dataSource } from './services/config';
import { IntegrationPending } from './components/common/AsyncState';
import { ChunkLoadBoundary } from './components/common/ChunkLoadBoundary';

interface ToastNotification {
  id: string;
  type: 'success' | 'info' | 'warning' | 'error';
  title: string;
  message: string;
}

export default function App() {
  // Navigation State (hash-supported)
  const [currentRoute, setCurrentRoute] = useState<string>(dataSource === 'django' ? 'all-assets' : 'dashboard');
  const [selectedAssetId, setSelectedAssetId] = useState<string>(dataSource === 'django' ? '' : 'AST-000002');
  const [creationAssetId, setCreationAssetId] = useState<string | undefined>();
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState<boolean>(false);
  const [isMobileNavOpen, setIsMobileNavOpen] = useState(false);
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
    if (dataSource === 'django') return;
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
        } else if (hash.startsWith('asset-create/')) {
          setCreationAssetId(hash.slice('asset-create/'.length));
          setCurrentRoute('asset-create');
        } else {
          if (hash === 'asset-create') setCreationAssetId(undefined);
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
    if (route.startsWith('asset-detail/')) {
      setSelectedAssetId(route.slice('asset-detail/'.length)); setCurrentRoute('asset-detail');
    } else if (route.startsWith('asset-create/')) {
      setCreationAssetId(route.slice('asset-create/'.length)); setCurrentRoute('asset-create');
    } else { if (route === 'asset-create') setCreationAssetId(undefined); setCurrentRoute(route); }
    window.location.hash = route;
    setIsMobileNavOpen(false);
    window.scrollTo({ top: 0, behavior: window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' });
  };

  const handleSelectAsset = (assetId: string) => {
    setSelectedAssetId(assetId);
    setCurrentRoute('asset-detail');
    window.location.hash = `asset-detail/${assetId}`;
    setIsMobileNavOpen(false);
    window.scrollTo({ top: 0, behavior: window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' });
  };

  // Quick Action Handler (from Navbar or Views)
  const handleOpenQuickAction = (action: string) => {
    if (dataSource === 'django') { if (action === 'maintenance') navigateTo('maintenance'); if (action === 'disposal') navigateTo('disposals'); return; }
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
    if (dataSource === 'django' && !['dashboard', 'all-assets', 'asset-detail', 'asset-create', 'asset-categories', 'acquisitions', 'depreciation', 'assignments', 'transfers', 'maintenance', 'disposals', 'verification', 'assurance', 'reports', 'audit-log', 'departments', 'locations', 'users-and-roles'].includes(currentRoute)) return <IntegrationPending />;
    switch (currentRoute) {
      case 'dashboard':
        if (dataSource === 'django') return <BackendDashboardView onNavigate={navigateTo} />;
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
            resumeAssetId={creationAssetId}
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
        if (dataSource === 'django') return <BackendTransfersView onNavigate={navigateTo} onSelectAsset={handleSelectAsset} />;
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
        if (dataSource === 'django') return <BackendAssignmentsView onNavigate={navigateTo} onSelectAsset={handleSelectAsset} />;
        return (
          <AssignmentsView
            onNavigate={navigateTo}
            onSelectAsset={handleSelectAsset}
          />
        );
      case 'depreciation':
        if (dataSource === 'django') return <BackendDepreciationView onNavigate={navigateTo} onSelectAsset={handleSelectAsset} />;
        return (
          <DepreciationView
            onNavigate={navigateTo}
            onSelectAsset={handleSelectAsset}
          />
        );
      case 'maintenance':
        if (dataSource === 'django') return <BackendMaintenanceView onNavigate={navigateTo} onSelectAsset={handleSelectAsset} />;
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
        if (dataSource === 'django') return <BackendDisposalsView onNavigate={navigateTo} onSelectAsset={handleSelectAsset} initialAssetId={selectedAssetId} />;
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
      case 'verification':
        return dataSource === 'django' ? <BackendVerificationView /> : <MockVerificationView />;
      case 'assurance':
        return dataSource === 'django' ? <BackendAssuranceView onSelectAsset={handleSelectAsset} /> : <MockAssuranceView />;
      case 'reports':
        if (dataSource === 'django') return <BackendReportsView />;
        return (
          <ReportsView
            onNavigate={navigateTo}
            onSelectAsset={handleSelectAsset}
          />
        );
      case 'departments':
        if (dataSource === 'django') return <BackendOrganizationAdminView section="departments" />;
        return <DepartmentsView onNavigate={navigateTo} />;
      case 'locations':
        if (dataSource === 'django') return <BackendOrganizationAdminView section="locations" />;
        return <LocationsView onNavigate={navigateTo} />;
      case 'users-and-roles':
        if (dataSource === 'django') return <BackendOrganizationAdminView section="users" />;
        return <UsersRolesView onNavigate={navigateTo} />;
      case 'audit-log':
        if (dataSource === 'django') return <BackendAuditLogView onSelectAsset={handleSelectAsset} />;
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
      <a href="#app-main" onClick={event => { event.preventDefault(); document.getElementById('app-main')?.focus(); }} className="sr-only z-[60] rounded bg-white px-4 py-2 text-[#00288e] focus:not-sr-only focus:fixed focus:left-3 focus:top-14 focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-700">Skip to main content</a>
      {/* Top Navbar */}
      <Navbar
        onNavigate={navigateTo}
        onOpenQuickAction={handleOpenQuickAction}
        globalSearch={globalSearch}
        setGlobalSearch={setGlobalSearch}
        onToggleMobileNav={() => setIsMobileNavOpen(value => !value)}
        isMobileNavOpen={isMobileNavOpen}
      />

      {/* Main Layout Container */}
      <div className="flex flex-1 pt-12">
        {/* Left Sidebar */}
        <Sidebar
          currentRoute={currentRoute}
          onNavigate={navigateTo}
          isCollapsed={isSidebarCollapsed}
          onToggleCollapse={() => setIsSidebarCollapsed(!isSidebarCollapsed)}
          isMobileOpen={isMobileNavOpen}
          onCloseMobile={() => setIsMobileNavOpen(false)}
        />

        {/* Content Region */}
        <main
          id="app-main"
          tabIndex={-1}
          className={`flex-1 flex flex-col transition-all duration-200 min-w-0 ${
            isSidebarCollapsed ? 'md:ml-16' : 'md:ml-64'
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
            <ChunkLoadBoundary>
              <Suspense fallback={<div role="status" className="m-5 rounded-xl border border-slate-200 bg-white p-8 text-center text-sm text-slate-600">Opening this workspace…</div>}>
                {renderCurrentView()}
              </Suspense>
            </ChunkLoadBoundary>
          </div>
        </main>
      </div>

      {/* Reusable Action Modals */}
      {barcodeModalOpen && <Suspense fallback={null}><PrintBarcodeModal
        isOpen={barcodeModalOpen}
        onClose={() => setBarcodeModalOpen(false)}
        asset={selectedBarcodeAsset}
      /></Suspense>}

      {transferModalOpen && <Suspense fallback={null}><InitiateTransferModal
        isOpen={transferModalOpen}
        onClose={() => setTransferModalOpen(false)}
        selectedAsset={selectedTransferAsset}
        assets={assets}
        departments={departments}
        locations={locations}
        onSubmitTransfer={handleSubmitTransfer}
      /></Suspense>}

      {maintenanceModalOpen && <Suspense fallback={null}><LogMaintenanceModal
        isOpen={maintenanceModalOpen}
        onClose={() => setMaintenanceModalOpen(false)}
        selectedAsset={selectedMaintenanceAsset}
        assets={assets}
        onSubmitMaintenance={handleSubmitMaintenance}
      /></Suspense>}

      {disposalModalOpen && <Suspense fallback={null}><DisposeAssetModal
        isOpen={disposalModalOpen}
        onClose={() => setDisposalModalOpen(false)}
        selectedAsset={selectedDisposalAsset}
        assets={assets}
        onSubmitDisposal={handleSubmitDisposal}
      /></Suspense>}

      {/* Floating Enterprise Toast Notifications */}
      <div aria-live="polite" aria-relevant="additions" className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 max-w-sm pointer-events-none">
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
              type="button"
              aria-label={`Dismiss notification: ${toast.title}`}
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
