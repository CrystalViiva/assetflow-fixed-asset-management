/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 * AssetFlow Repository & Data-Access Layer
 * Provides clean CRUD, filtering, pagination, and persistence abstraction.
 * Implements IAssetRepository so it can be swapped with Django REST Framework API client without UI rewrites.
 */

import {
  Asset,
  AssetCategory,
  Department,
  LocationHub,
  Transfer,
  MaintenanceRecord,
  DisposalRecord,
  AuditLogEntry,
  DashboardMetrics,
  CustodyAssignment,
  SystemSettings,
  UserProfile,
} from '../types';
import { calculateStraightLine } from './depreciationCalculator';

export interface AssetFilterParams {
  search?: string;
  category?: string;
  department?: string;
  location?: string;
  status?: string;
  acquisitionYear?: string;
  costRange?: string;
  custodian?: string;
  quickFilter?: 'all' | 'my-custody' | 'needs-audit' | 'warranty-30d';
  page?: number;
  pageSize?: number;
  sortBy?: string;
  sortOrder?: 'asc' | 'desc';
}

export interface PaginatedResult<T> {
  data: T[];
  total: number;
  page: number;
  pageSize: number;
  totalPages: number;
  totalFilteredBookValue?: number;
}

export interface IAssetRepository {
  // Assets
  getAssets(params?: AssetFilterParams): Promise<PaginatedResult<Asset>>;
  getAssetById(id: string): Promise<Asset | null>;
  getAssetByTag(tag: string): Promise<Asset | null>;
  createAsset(asset: Partial<Asset>, actorName?: string): Promise<Asset>;
  updateAsset(id: string, updates: Partial<Asset>, actorName?: string): Promise<Asset>;
  deleteAsset(id: string, actorName?: string): Promise<boolean>;

  // Lifecycle workflows
  getTransfers(): Promise<Transfer[]>;
  createTransfer(transfer: Partial<Transfer>, actorName?: string): Promise<Transfer>;
  updateTransferStatus(id: string, status: Transfer['status'], actorName?: string): Promise<Transfer>;

  getMaintenance(): Promise<MaintenanceRecord[]>;
  createMaintenance(record: Partial<MaintenanceRecord>, actorName?: string): Promise<MaintenanceRecord>;
  updateMaintenanceStatus(id: string, status: MaintenanceRecord['status'], actorName?: string): Promise<MaintenanceRecord>;

  getDisposals(): Promise<DisposalRecord[]>;
  createDisposal(disposal: Partial<DisposalRecord>, actorName?: string): Promise<DisposalRecord>;
  updateDisposalStatus(id: string, status: DisposalRecord['status'], actorName?: string): Promise<DisposalRecord>;

  // Organization Masterdata
  getCategories(): Promise<AssetCategory[]>;
  getDepartments(): Promise<Department[]>;
  getLocations(): Promise<LocationHub[]>;
  getUsers(): Promise<UserProfile[]>;
  getAssignments(): Promise<CustodyAssignment[]>;

  // Governance & Metrics
  getAuditLogs(params?: { entity?: string; search?: string }): Promise<AuditLogEntry[]>;
  getDashboardMetrics(): Promise<DashboardMetrics>;
  getSettings(): Promise<SystemSettings>;
  updateSettings(settings: Partial<SystemSettings>): Promise<SystemSettings>;
  resetToDefaultData(): Promise<void>;
}


import {
  DEFAULT_LOCATIONS,
  DEFAULT_DEPARTMENTS,
  DEFAULT_CATEGORIES,
  DEFAULT_USERS,
  DEFAULT_ASSETS,
  DEFAULT_TRANSFERS,
  DEFAULT_MAINTENANCE,
  DEFAULT_DISPOSALS,
  DEFAULT_AUDIT_LOGS,
  DEFAULT_SETTINGS,
} from "../data/mockSeedData";

const STORAGE_KEY_PREFIX = 'assetflow_storage_';

/**
 * Robust Local Storage repository implementation with immutable audit logging
 */
export class MockAssetRepository implements IAssetRepository {
  private getStorage<T>(key: string, defaultVal: T): T {
    try {
      const data = localStorage.getItem(STORAGE_KEY_PREFIX + key);
      return data ? JSON.parse(data) : defaultVal;
    } catch {
      return defaultVal;
    }
  }

  private setStorage<T>(key: string, value: T): void {
    try {
      localStorage.setItem(STORAGE_KEY_PREFIX + key, JSON.stringify(value));
    } catch (e) {
      console.warn('LocalStorage write failed', e);
    }
  }

  // Getters for in-memory / persistent collections
  private get assets(): Asset[] {
    return this.getStorage<Asset[]>('assets', DEFAULT_ASSETS);
  }
  private set assets(items: Asset[]) {
    this.setStorage('assets', items);
  }

  private get transfers(): Transfer[] {
    return this.getStorage<Transfer[]>('transfers', DEFAULT_TRANSFERS);
  }
  private set transfers(items: Transfer[]) {
    this.setStorage('transfers', items);
  }

  private get maintenance(): MaintenanceRecord[] {
    return this.getStorage<MaintenanceRecord[]>('maintenance', DEFAULT_MAINTENANCE);
  }
  private set maintenance(items: MaintenanceRecord[]) {
    this.setStorage('maintenance', items);
  }

  private get disposals(): DisposalRecord[] {
    return this.getStorage<DisposalRecord[]>('disposals', DEFAULT_DISPOSALS);
  }
  private set disposals(items: DisposalRecord[]) {
    this.setStorage('disposals', items);
  }

  private get auditLogs(): AuditLogEntry[] {
    return this.getStorage<AuditLogEntry[]>('audit_logs', DEFAULT_AUDIT_LOGS);
  }
  private set auditLogs(items: AuditLogEntry[]) {
    this.setStorage('audit_logs', items);
  }

  private logAudit(
    action: AuditLogEntry['action'],
    entity: AuditLogEntry['entity'],
    entityId: string,
    entityTag: string | undefined,
    description: string,
    previousValue?: string,
    newValue?: string,
    actorName: string = 'Babajide Adeleke'
  ): void {
    const newEntry: AuditLogEntry = {
      id: 'aud-' + Date.now(),
      timestamp: new Date().toISOString().replace('T', ' ').substring(0, 19) + ' WAT',
      user_name: actorName,
      user_role: 'Head of Asset Accounting & Treasury',
      action,
      entity,
      entity_id: entityId,
      entity_tag: entityTag,
      description,
      previous_value: previousValue,
      new_value: newValue,
      ip_address: '105.112.48.91 (Lagos HQ)',
    };
    this.auditLogs = [newEntry, ...this.auditLogs];
  }

  async getAssets(params?: AssetFilterParams): Promise<PaginatedResult<Asset>> {
    let result = [...this.assets];

    if (params) {
      if (params.search) {
        const query = params.search.toLowerCase().trim();
        result = result.filter(
          a =>
            a.tag.toLowerCase().includes(query) ||
            a.name.toLowerCase().includes(query) ||
            a.serial_number.toLowerCase().includes(query) ||
            a.custodian_name.toLowerCase().includes(query) ||
            a.department_name.toLowerCase().includes(query) ||
            a.location_name.toLowerCase().includes(query) ||
            a.purchase_order_ref.toLowerCase().includes(query)
        );
      }

      if (params.category && params.category !== 'All Categories') {
        result = result.filter(a => a.category_name.toLowerCase().includes(params.category!.toLowerCase()));
      }

      if (params.department && params.department !== 'All Departments') {
        result = result.filter(a => a.department_name.toLowerCase().includes(params.department!.toLowerCase()));
      }

      if (params.location && params.location !== 'All Locations') {
        result = result.filter(a => a.location_name.toLowerCase().includes(params.location!.toLowerCase()));
      }

      if (params.status && params.status !== 'All Statuses') {
        result = result.filter(a => a.status.toLowerCase() === params.status!.toLowerCase());
      }

      if (params.quickFilter === 'my-custody') {
        result = result.filter(a => a.custodian_name.includes('Adeleke'));
      } else if (params.quickFilter === 'needs-audit') {
        result = result.filter(a => !a.custody_signed_ack || a.health_score < 80);
      } else if (params.quickFilter === 'warranty-30d') {
        result = result.filter(a => a.status === 'IN_MAINTENANCE' || a.health_score < 75);
      }

      if (params.costRange && params.costRange !== '₦0 - ₦100M+') {
        if (params.costRange.includes('0 - ₦10M')) {
          result = result.filter(a => a.total_acquisition_cost <= 10_000_000);
        } else if (params.costRange.includes('10M - ₦50M')) {
          result = result.filter(a => a.total_acquisition_cost > 10_000_000 && a.total_acquisition_cost <= 50_000_000);
        } else if (params.costRange.includes('50M - ₦150M')) {
          result = result.filter(a => a.total_acquisition_cost > 50_000_000 && a.total_acquisition_cost <= 150_000_000);
        } else if (params.costRange.includes('> ₦150M')) {
          result = result.filter(a => a.total_acquisition_cost > 150_000_000);
        }
      }
    }

    const totalFilteredBookValue = result.reduce((sum, a) => sum + a.net_book_value, 0);

    const page = params?.page || 1;
    const pageSize = params?.pageSize || 10;
    const total = result.length;
    const totalPages = Math.ceil(total / pageSize) || 1;
    const startIndex = (page - 1) * pageSize;
    const paginatedData = result.slice(startIndex, startIndex + pageSize);

    return {
      data: paginatedData,
      total,
      page,
      pageSize,
      totalPages,
      totalFilteredBookValue,
    };
  }

  async getAssetById(id: string): Promise<Asset | null> {
    return this.assets.find(a => a.id === id || a.tag.toLowerCase() === id.toLowerCase()) || null;
  }

  async getAssetByTag(tag: string): Promise<Asset | null> {
    return this.assets.find(a => a.tag.toLowerCase() === tag.toLowerCase()) || null;
  }

  async createAsset(newAssetData: Partial<Asset>, actorName: string = 'Babajide Adeleke'): Promise<Asset> {
    // Generate next tag if not provided
    const nextNum = this.assets.length + 1285;
    const tag = newAssetData.tag || `AST-${String(nextNum).padStart(6, '0')}`;
    const id = 'ast-' + Date.now();

    // Run IAS 16 straight-line calculation
    const cost = newAssetData.total_acquisition_cost || 0;
    const usefulLifeYears = newAssetData.useful_life_years || 8;
    const usefulLifeMonths = newAssetData.useful_life_months || usefulLifeYears * 12;
    const residualRatePct = newAssetData.residual_rate_pct ?? 10;

    const depResult = calculateStraightLine({
      cost,
      usefulLifeMonths,
      residualRatePct,
      capitalizationDate: newAssetData.capitalization_date,
    });

    const fullAsset: Asset = {
      id,
      tag,
      name: newAssetData.name || 'New Enterprise Fixed Asset',
      spec: newAssetData.spec || '',
      description: newAssetData.description || '',
      category_id: newAssetData.category_id || 'CAT-01',
      category_name: newAssetData.category_name || 'Plant & Machinery',
      category_code: newAssetData.category_code || 'P&M',
      manufacturer: newAssetData.manufacturer || '',
      model: newAssetData.model || '',
      serial_number: newAssetData.serial_number || `SN-${Date.now()}`,
      department_id: newAssetData.department_id || 'DEP-02',
      department_name: newAssetData.department_name || 'Operations',
      department_head: newAssetData.department_head || 'Emeka Okafor',
      location_id: newAssetData.location_id || 'LOC-01',
      location_name: newAssetData.location_name || 'Lagos HQ',
      sub_location: newAssetData.sub_location || '',
      custodian_id: newAssetData.custodian_id || 'USR-01',
      custodian_name: newAssetData.custodian_name || 'Designated Custodian',
      custodian_staff_id: newAssetData.custodian_staff_id || 'AF-GEN-001',
      custodian_title: newAssetData.custodian_title || 'Asset Custodian',
      custody_handover_date: newAssetData.custody_handover_date || new Date().toISOString().substring(0, 10),
      custody_signed_ack: true,
      vendor: newAssetData.vendor || 'Authorized Vendor',
      purchase_order_ref: newAssetData.purchase_order_ref || `PO-${new Date().getFullYear()}-${Math.floor(1000 + Math.random() * 9000)}`,
      commercial_invoice_ref: newAssetData.commercial_invoice_ref || `INV-${Math.floor(10000 + Math.random() * 90000)}`,
      acquisition_date: newAssetData.acquisition_date || new Date().toISOString().substring(0, 10),
      capitalization_date: newAssetData.capitalization_date || new Date().toISOString().substring(0, 10),
      currency: 'NGN',
      cost_components: newAssetData.cost_components || {
        base_purchase: cost,
        freight: 0,
        installation: 0,
        civil_works: 0,
        other_costs: 0,
      },
      total_acquisition_cost: cost,
      depreciation_method: newAssetData.depreciation_method || 'SLM',
      useful_life_years: usefulLifeYears,
      useful_life_months: usefulLifeMonths,
      residual_rate_pct: residualRatePct,
      salvage_value: depResult.salvageValue,
      depreciable_base: depResult.depreciableBase,
      monthly_depreciation: depResult.monthlyDepreciation,
      annual_depreciation: depResult.annualDepreciation,
      accumulated_depreciation: depResult.accumulatedDepreciation,
      net_book_value: depResult.netBookValue,
      carrying_rate_pct: depResult.carryingRatePct,
      status: newAssetData.status || 'ACTIVE',
      is_capitalized: true,
      ledger_code: newAssetData.ledger_code || '1500-01',
      insurance_policy: newAssetData.insurance_policy || 'PLA-ACTIVE',
      insurance_carrier: 'Leadway Assurance',
      rfid_tag: newAssetData.rfid_tag || `RFID-${Math.floor(1000 + Math.random() * 9000)}-${tag}`,
      image_url: newAssetData.image_url || 'https://lh3.googleusercontent.com/aida-public/AB6AXuARkC1Wlvx9Ay6CnusCTKpVnMoikv2jHnwXTymqXs2qBxbMMAKFQTjdlQ1IHnNoHlbW6x2-rN60RT8qVazfUhoc2laoSuBH5TLHyMK9md4u9tBpcm5P_HMql97FKiWYTWmRpNjySGxI9bQ_-ZY3slWJoM12u7tNA2kZ-sO6juTnycIk8Z2kq5LrtlVrtXurYIFIZxHiumYNXX6dihJkhD5sh-MahSGaVdMYezsQjAkud1-_jk7EqCqhsQ',
      health_score: 100,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };

    this.assets = [fullAsset, ...this.assets];
    this.logAudit(
      'CAPITALIZE',
      'ASSET',
      id,
      tag,
      `Capitalized new fixed asset ${tag} (${fullAsset.name}) recognized at ₦${cost.toLocaleString('en-NG')}.`,
      'Draft Creation',
      `Capitalized (NBV: ₦${fullAsset.net_book_value.toLocaleString('en-NG')})`,
      actorName
    );

    return fullAsset;
  }

  async updateAsset(id: string, updates: Partial<Asset>, actorName: string = 'Babajide Adeleke'): Promise<Asset> {
    const list = [...this.assets];
    const index = list.findIndex(a => a.id === id);
    if (index === -1) throw new Error(`Asset not found: ${id}`);

    const existing = list[index];
    const updated: Asset = {
      ...existing,
      ...updates,
      updated_at: new Date().toISOString(),
    };

    list[index] = updated;
    this.assets = list;

    this.logAudit(
      'UPDATE',
      'ASSET',
      id,
      existing.tag,
      `Updated asset details for ${existing.tag} (${updated.name}).`,
      `Status: ${existing.status}, Custodian: ${existing.custodian_name}`,
      `Status: ${updated.status}, Custodian: ${updated.custodian_name}`,
      actorName
    );

    return updated;
  }

  async deleteAsset(id: string, actorName: string = 'Babajide Adeleke'): Promise<boolean> {
    const existing = this.assets.find(a => a.id === id);
    if (!existing) return false;

    this.assets = this.assets.filter(a => a.id !== id);
    this.logAudit(
      'DISPOSE',
      'ASSET',
      id,
      existing.tag,
      `Removed/De-registered asset ${existing.tag} from primary ledger.`,
      `Active (Cost: ₦${existing.total_acquisition_cost.toLocaleString('en-NG')})`,
      'De-registered',
      actorName
    );
    return true;
  }

  async getTransfers(): Promise<Transfer[]> {
    return this.transfers;
  }

  async createTransfer(transferData: Partial<Transfer>, actorName: string = 'Babajide Adeleke'): Promise<Transfer> {
    const id = 'trf-' + Date.now();
    const transfer_no = `TRF-${new Date().getFullYear()}-${String(this.transfers.length + 45).padStart(4, '0')}`;

    const newTransfer: Transfer = {
      id,
      transfer_no,
      asset_id: transferData.asset_id || '',
      asset_tag: transferData.asset_tag || '',
      asset_name: transferData.asset_name || '',
      from_department_id: transferData.from_department_id || '',
      from_department_name: transferData.from_department_name || '',
      from_location_id: transferData.from_location_id || '',
      from_location_name: transferData.from_location_name || '',
      to_department_id: transferData.to_department_id || '',
      to_department_name: transferData.to_department_name || '',
      to_location_id: transferData.to_location_id || '',
      to_location_name: transferData.to_location_name || '',
      requested_by: transferData.requested_by || actorName,
      approved_by: transferData.approved_by || 'Babajide Adeleke (CFO)',
      transfer_date: transferData.transfer_date || new Date().toISOString().substring(0, 10),
      reason: transferData.reason || 'Operational redeployment',
      notes: transferData.notes || '',
      status: transferData.status || 'PENDING',
      waybill_no: transferData.waybill_no || `WB-${Math.floor(1000 + Math.random() * 9000)}`,
      created_at: new Date().toISOString(),
    };

    this.transfers = [newTransfer, ...this.transfers];

    // If asset exists, update its status
    if (transferData.asset_id) {
      const asset = this.assets.find(a => a.id === transferData.asset_id);
      if (asset) {
        await this.updateAsset(asset.id, { status: 'TRANSFERRED' }, actorName);
      }
    }

    this.logAudit(
      'TRANSFER',
      'TRANSFER',
      id,
      newTransfer.asset_tag,
      `Created transfer request ${transfer_no} for ${newTransfer.asset_tag} from ${newTransfer.from_location_name} to ${newTransfer.to_location_name}.`,
      'Stationary',
      `Pending Transfer (${newTransfer.to_location_name})`,
      actorName
    );

    return newTransfer;
  }

  async updateTransferStatus(id: string, status: Transfer['status'], actorName: string = 'Babajide Adeleke'): Promise<Transfer> {
    const list = [...this.transfers];
    const index = list.findIndex(t => t.id === id);
    if (index === -1) throw new Error('Transfer not found');

    const prevStatus = list[index].status;
    list[index].status = status;
    this.transfers = list;

    // If completed, update asset location
    if (status === 'COMPLETED' && list[index].asset_id) {
      const asset = this.assets.find(a => a.id === list[index].asset_id);
      if (asset) {
        await this.updateAsset(
          asset.id,
          {
            location_name: list[index].to_location_name,
            department_name: list[index].to_department_name,
            status: 'ACTIVE',
          },
          actorName
        );
      }
    }

    this.logAudit(
      'TRANSFER',
      'TRANSFER',
      id,
      list[index].asset_tag,
      `Updated transfer ${list[index].transfer_no} status from ${prevStatus} to ${status}.`,
      prevStatus,
      status,
      actorName
    );

    return list[index];
  }

  async getMaintenance(): Promise<MaintenanceRecord[]> {
    return this.maintenance;
  }

  async createMaintenance(data: Partial<MaintenanceRecord>, actorName: string = 'Babajide Adeleke'): Promise<MaintenanceRecord> {
    const id = 'mnt-' + Date.now();
    const work_order_no = `WO-${new Date().getFullYear()}-${String(this.maintenance.length + 96).padStart(3, '0')}`;

    const newRecord: MaintenanceRecord = {
      id,
      work_order_no,
      asset_id: data.asset_id || '',
      asset_tag: data.asset_tag || '',
      asset_name: data.asset_name || '',
      maintenance_type: data.maintenance_type || 'PREVENTIVE',
      description: data.description || 'Scheduled inspection & overhaul',
      vendor: data.vendor || 'Mantrac Certified Services',
      start_date: data.start_date || new Date().toISOString().substring(0, 10),
      expected_completion_date: data.expected_completion_date || new Date(Date.now() + 7 * 86400000).toISOString().substring(0, 10),
      budget_cost: data.budget_cost || 500_000,
      status: data.status || 'IN_PROGRESS',
      work_scope: data.work_scope || '',
      created_at: new Date().toISOString(),
    };

    this.maintenance = [newRecord, ...this.maintenance];

    if (data.asset_id) {
      const asset = this.assets.find(a => a.id === data.asset_id);
      if (asset) {
        await this.updateAsset(asset.id, { status: 'IN_MAINTENANCE' }, actorName);
      }
    }

    this.logAudit(
      'MAINTENANCE',
      'MAINTENANCE',
      id,
      newRecord.asset_tag,
      `Logged maintenance work order ${work_order_no} for ${newRecord.asset_tag} (${newRecord.description}).`,
      'Active Operation',
      `In Maintenance (${work_order_no})`,
      actorName
    );

    return newRecord;
  }

  async updateMaintenanceStatus(id: string, status: MaintenanceRecord['status'], actorName: string = 'Babajide Adeleke'): Promise<MaintenanceRecord> {
    const list = [...this.maintenance];
    const index = list.findIndex(m => m.id === id);
    if (index === -1) throw new Error('Maintenance record not found');

    const prev = list[index].status;
    list[index].status = status;
    if (status === 'COMPLETED') {
      list[index].completion_date = new Date().toISOString().substring(0, 10);
      // Restore asset to active
      if (list[index].asset_id) {
        const asset = this.assets.find(a => a.id === list[index].asset_id);
        if (asset) {
          await this.updateAsset(asset.id, { status: 'ACTIVE' }, actorName);
        }
      }
    }
    this.maintenance = list;

    this.logAudit(
      'MAINTENANCE',
      'MAINTENANCE',
      id,
      list[index].asset_tag,
      `Updated work order ${list[index].work_order_no} status to ${status}.`,
      prev,
      status,
      actorName
    );

    return list[index];
  }

  async getDisposals(): Promise<DisposalRecord[]> {
    return this.disposals;
  }

  async createDisposal(data: Partial<DisposalRecord>, actorName: string = 'Babajide Adeleke'): Promise<DisposalRecord> {
    const id = 'dsp-' + Date.now();
    const disposal_no = `DSP-${new Date().getFullYear()}-${String(this.disposals.length + 14).padStart(4, '0')}`;

    const proceeds = data.disposal_proceeds || 0;
    const bookVal = data.book_value || 0;
    const gainOrLoss = proceeds - bookVal;

    const newRecord: DisposalRecord = {
      id,
      disposal_no,
      asset_id: data.asset_id || '',
      asset_tag: data.asset_tag || '',
      asset_name: data.asset_name || '',
      disposal_date: data.disposal_date || new Date().toISOString().substring(0, 10),
      method: data.method || 'SALE',
      disposal_proceeds: proceeds,
      book_value: bookVal,
      gain_or_loss: gainOrLoss,
      reason: data.reason || 'End of economic lifespan',
      approved_by: data.approved_by || 'CFO Review Pending',
      status: data.status || 'PENDING_REVIEW',
      recommendation: data.recommendation || 'Auction Sale',
      buyer_or_beneficiary: data.buyer_or_beneficiary || '',
      notes: data.notes || '',
      created_at: new Date().toISOString(),
    };

    this.disposals = [newRecord, ...this.disposals];

    if (data.asset_id) {
      const asset = this.assets.find(a => a.id === data.asset_id);
      if (asset) {
        await this.updateAsset(asset.id, { status: 'IMPAIRED' }, actorName);
      }
    }

    this.logAudit(
      'DISPOSE',
      'DISPOSAL',
      id,
      newRecord.asset_tag,
      `Initiated formal disposal / write-off workflow ${disposal_no} for ${newRecord.asset_tag}. Method: ${newRecord.method}, Book Value: ₦${bookVal.toLocaleString('en-NG')}.`,
      'Active Carrying Asset',
      `Pending Disposal Board Review (${disposal_no})`,
      actorName
    );

    return newRecord;
  }

  async updateDisposalStatus(id: string, status: DisposalRecord['status'], actorName: string = 'Babajide Adeleke'): Promise<DisposalRecord> {
    const list = [...this.disposals];
    const index = list.findIndex(d => d.id === id);
    if (index === -1) throw new Error('Disposal not found');

    const prev = list[index].status;
    list[index].status = status;
    this.disposals = list;

    if (status === 'COMPLETED' && list[index].asset_id) {
      const asset = this.assets.find(a => a.id === list[index].asset_id);
      if (asset) {
        await this.updateAsset(asset.id, { status: 'DISPOSED', net_book_value: 0 }, actorName);
      }
    }

    this.logAudit(
      'DISPOSE',
      'DISPOSAL',
      id,
      list[index].asset_tag,
      `Disposal board updated ${list[index].disposal_no} status to ${status}.`,
      prev,
      status,
      actorName
    );

    return list[index];
  }

  async getCategories(): Promise<AssetCategory[]> {
    // Dynamic recalculation of totals
    const currentAssets = this.assets;
    return DEFAULT_CATEGORIES.map(cat => {
      const catAssets = currentAssets.filter(a => a.category_name.toLowerCase().includes(cat.name.toLowerCase()) || a.category_id === cat.id);
      const totalCost = catAssets.reduce((sum, a) => sum + a.total_acquisition_cost, 0) || cat.total_cost;
      const totalNbv = catAssets.reduce((sum, a) => sum + a.net_book_value, 0) || cat.total_nbv;
      return {
        ...cat,
        asset_count: catAssets.length > 0 ? catAssets.length : cat.asset_count,
        total_cost: totalCost,
        total_nbv: totalNbv,
      };
    });
  }

  async getDepartments(): Promise<Department[]> {
    const currentAssets = this.assets;
    return DEFAULT_DEPARTMENTS.map(dept => {
      const deptAssets = currentAssets.filter(a => a.department_name.toLowerCase().includes(dept.name.toLowerCase()) || a.department_id === dept.id);
      const totalCost = deptAssets.reduce((sum, a) => sum + a.total_acquisition_cost, 0) || dept.total_cost;
      const totalNbv = deptAssets.reduce((sum, a) => sum + a.net_book_value, 0) || dept.total_nbv;
      return {
        ...dept,
        asset_count: deptAssets.length > 0 ? deptAssets.length : dept.asset_count,
        total_cost: totalCost,
        total_nbv: totalNbv,
      };
    });
  }

  async getLocations(): Promise<LocationHub[]> {
    const currentAssets = this.assets;
    return DEFAULT_LOCATIONS.map(loc => {
      const locAssets = currentAssets.filter(a => a.location_name.toLowerCase().includes(loc.name.toLowerCase()) || a.location_id === loc.id);
      const totalCost = locAssets.reduce((sum, a) => sum + a.total_acquisition_cost, 0) || loc.total_cost;
      const totalNbv = locAssets.reduce((sum, a) => sum + a.net_book_value, 0) || loc.total_nbv;
      return {
        ...loc,
        asset_count: locAssets.length > 0 ? locAssets.length : loc.asset_count,
        total_cost: totalCost,
        total_nbv: totalNbv,
      };
    });
  }

  async getUsers(): Promise<UserProfile[]> {
    return DEFAULT_USERS;
  }

  async getAssignments(): Promise<CustodyAssignment[]> {
    return this.assets.map(a => ({
      id: 'asg-' + a.id,
      asset_id: a.id,
      asset_tag: a.tag,
      asset_name: a.name,
      custodian_id: a.custodian_id,
      custodian_name: a.custodian_name,
      custodian_staff_id: a.custodian_staff_id,
      custodian_title: a.custodian_title,
      department_name: a.department_name,
      location_name: a.location_name,
      assigned_date: a.custody_handover_date,
      signed_ack: a.custody_signed_ack,
      notes: a.sub_location,
    }));
  }

  async getAuditLogs(params?: { entity?: string; search?: string }): Promise<AuditLogEntry[]> {
    let logs = [...this.auditLogs];
    if (params?.entity && params.entity !== 'ALL') {
      logs = logs.filter(l => l.entity === params.entity);
    }
    if (params?.search) {
      const q = params.search.toLowerCase();
      logs = logs.filter(
        l =>
          l.description.toLowerCase().includes(q) ||
          l.user_name.toLowerCase().includes(q) ||
          (l.entity_tag && l.entity_tag.toLowerCase().includes(q))
      );
    }
    return logs;
  }

  async getDashboardMetrics(): Promise<DashboardMetrics> {
    const assets = this.assets;
    const totalAssets = 1284; // Canonical institutional figure
    const activeAssets = 1192;
    const maintenanceAssets = 64;
    const transferredAssets = 18;
    const impairedAssets = 10;
    const totalAcqCost = 2_431_850_000;
    const currentBookVal = 1_711_850_000;
    const accumulatedDeprec = 720_000_000;

    return {
      total_assets: totalAssets,
      active_assets: activeAssets,
      maintenance_assets: maintenanceAssets,
      transferred_assets: transferredAssets,
      impaired_assets: impairedAssets,
      disposed_assets: 14,
      total_acquisition_cost: totalAcqCost,
      current_book_value: currentBookVal,
      accumulated_depreciation: accumulatedDeprec,
      carrying_retention_pct: 70.4,
      monthly_run_rate: 32_400_000,
      scheduled_posting_date: 'March 31, 2025',
      category_breakdown: [
        { category_id: 'CAT-01', category_name: 'Heavy Machinery & Equipment', total_value: 920_000_000, unit_count: 142, percentage: 38.0, color: '#00288e' },
        { category_id: 'CAT-02', category_name: 'IT Infrastructure & Servers', total_value: 540_000_000, unit_count: 480, percentage: 22.0, color: '#1e40af' },
        { category_id: 'CAT-03', category_name: 'Motor Vehicles & Fleet', total_value: 480_000_000, unit_count: 185, percentage: 20.0, color: '#3755c3' },
        { category_id: 'CAT-04', category_name: 'Buildings & Leasehold Improvements', total_value: 320_000_000, unit_count: 48, percentage: 13.0, color: '#565e74' },
        { category_id: 'CAT-05', category_name: 'Office Furniture & Fixtures', total_value: 171_850_000, unit_count: 429, percentage: 7.0, color: '#757684' },
      ],
      hub_breakdown: [
        { code: 'LOS', name: 'Lagos HQ & Tech Hub', asset_count: 580, total_value: 1_120_000_000, percentage: 46.1 },
        { code: 'PHC', name: 'Port Harcourt Industrial Base', asset_count: 310, total_value: 680_000_000, percentage: 28.0 },
        { code: 'ABJ', name: 'Abuja Liaison & Data Center', asset_count: 220, total_value: 390_000_000, percentage: 16.0 },
        { code: 'WAR', name: 'Warri Logistics Depot', asset_count: 114, total_value: 160_000_000, percentage: 6.6 },
        { code: 'IBD', name: 'Ibadan Operations', asset_count: 60, total_value: 81_850_000, percentage: 3.3 },
      ],
      monthly_trend: [
        { month: 'Oct 2024', capitalization: 38_000_000, depreciation: 31_200_000 },
        { month: 'Nov 2024', capitalization: 25_000_000, depreciation: 31_500_000 },
        { month: 'Dec 2024', capitalization: 88_500_000, depreciation: 32_000_000, notes: 'Machinery & Heavy Generators' },
        { month: 'Jan 2025', capitalization: 48_500_000, depreciation: 32_200_000 },
        { month: 'Feb 2025', capitalization: 42_000_000, depreciation: 32_400_000 },
        { month: 'Mar 2025', capitalization: 52_000_000, depreciation: 32_800_000, is_projected: true, notes: 'Fleet Acquisition' },
      ],
    };
  }

  async getSettings(): Promise<SystemSettings> {
    return this.getStorage<SystemSettings>('settings', DEFAULT_SETTINGS);
  }

  async updateSettings(updates: Partial<SystemSettings>): Promise<SystemSettings> {
    const current = await this.getSettings();
    const updated = { ...current, ...updates };
    this.setStorage('settings', updated);
    return updated;
  }

  async resetToDefaultData(): Promise<void> {
    localStorage.removeItem(STORAGE_KEY_PREFIX + 'assets');
    localStorage.removeItem(STORAGE_KEY_PREFIX + 'transfers');
    localStorage.removeItem(STORAGE_KEY_PREFIX + 'maintenance');
    localStorage.removeItem(STORAGE_KEY_PREFIX + 'disposals');
    localStorage.removeItem(STORAGE_KEY_PREFIX + 'audit_logs');
    localStorage.removeItem(STORAGE_KEY_PREFIX + 'settings');
  }
}

// Global repository singleton
export const assetRepository: IAssetRepository = new MockAssetRepository();
