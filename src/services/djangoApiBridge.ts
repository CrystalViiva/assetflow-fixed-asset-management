/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 * Django REST Framework Integration Bridge & Architecture Specification
 * 
 * ARCHITECTURE SPECIFICATION:
 * This frontend is architected with a decoupled Data Access Object (DAO) / Repository pattern.
 * React UI components ONLY depend on the `IAssetRepository` interface and domain models defined
 * in `src/types/index.ts`.
 * 
 * When migrating from the local `MockAssetRepository` to production Django REST Framework:
 * 1. Deploy the Django REST Framework backend with PostgreSQL.
 * 2. Configure `VITE_BACKEND_API_URL` in `.env` (e.g. `https://api.assetflow.ng/api/v1`).
 * 3. Swap the active singleton export in `src/services/assetRepository.ts` from
 *    `new MockAssetRepository()` to `new DjangoAssetRepository(apiUrl)`.
 * 4. Zero React component modifications required!
 */

import {
  Asset,
  AssetCategory,
  AuditLogEntry,
  CustodyAssignment,
  DashboardMetrics,
  Department,
  DisposalRecord,
  LocationHub,
  MaintenanceRecord,
  SystemSettings,
  Transfer,
  UserProfile,
} from '../types';
import { AssetFilterParams, IAssetRepository, PaginatedResult } from './assetRepository';

/**
 * Django REST Framework Endpoint Contract Map
 * ============================================
 * 
 * MODEL & SERIALIZER MAPPING:
 * 
 * 1. Asset Model: `apps.assets.models.FixedAsset`
 *    Endpoint: `/api/v1/assets/` [GET, POST]
 *    Endpoint: `/api/v1/assets/<uuid:pk>/` [GET, PUT, PATCH, DELETE]
 *    Endpoint: `/api/v1/assets/<uuid:pk>/depreciation-schedule/` [GET]
 *    Endpoint: `/api/v1/assets/<uuid:pk>/thermal-tag/` [GET]
 * 
 * 2. Transfer Model: `apps.lifecycle.models.AssetTransfer`
 *    Endpoint: `/api/v1/transfers/` [GET, POST]
 *    Endpoint: `/api/v1/transfers/<uuid:pk>/approve/` [POST]
 * 
 * 3. Maintenance Model: `apps.lifecycle.models.MaintenanceWorkOrder`
 *    Endpoint: `/api/v1/maintenance/` [GET, POST]
 *    Endpoint: `/api/v1/maintenance/<uuid:pk>/complete/` [POST]
 * 
 * 4. Disposal Model: `apps.lifecycle.models.AssetDisposal`
 *    Endpoint: `/api/v1/disposals/` [GET, POST]
 *    Endpoint: `/api/v1/disposals/<uuid:pk>/approve/` [POST]
 * 
 * 5. Audit Trail: `apps.governance.models.AuditLog`
 *    Endpoint: `/api/v1/audit-logs/` [GET] (Immutable, read-only)
 * 
 * 6. Executive Dashboard:
 *    Endpoint: `/api/v1/dashboard/executive-metrics/` [GET]
 */

export class DjangoAssetRepository implements IAssetRepository {
  private baseUrl: string;
  private authToken: string | null = null;

  constructor(baseUrl: string = '/api/v1') {
    this.baseUrl = baseUrl.replace(/\/$/, '');
  }

  public setAuthToken(token: string) {
    this.authToken = token;
  }

  private async request<T>(path: string, options: RequestInit = {}): Promise<T> {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      Accept: 'application/json',
    };

    if (this.authToken) {
      headers['Authorization'] = `Bearer ${this.authToken}`;
    }

    const response = await fetch(`${this.baseUrl}${path}`, {
      ...options,
      headers: {
        ...headers,
        ...options.headers,
      },
    });

    if (!response.ok) {
      const errorBody = await response.text();
      throw new Error(`Django API Error (${response.status}): ${errorBody}`);
    }

    return response.json();
  }

  async getAssets(params?: AssetFilterParams): Promise<PaginatedResult<Asset>> {
    const query = new URLSearchParams();
    if (params?.search) query.set('search', params.search);
    if (params?.category && params.category !== 'All Categories') query.set('category__name', params.category);
    if (params?.department && params.department !== 'All Departments') query.set('department__name', params.department);
    if (params?.location && params.location !== 'All Locations') query.set('location__name', params.location);
    if (params?.status && params.status !== 'All Statuses') query.set('status', params.status);
    if (params?.page) query.set('page', String(params.page));
    if (params?.pageSize) query.set('page_size', String(params.pageSize));

    return this.request<PaginatedResult<Asset>>(`/assets/?${query.toString()}`);
  }

  async getAssetById(id: string): Promise<Asset | null> {
    return this.request<Asset>(`/assets/${id}/`);
  }

  async getAssetByTag(tag: string): Promise<Asset | null> {
    return this.request<Asset>(`/assets/by-tag/${tag}/`);
  }

  async createAsset(asset: Partial<Asset>): Promise<Asset> {
    return this.request<Asset>('/assets/', {
      method: 'POST',
      body: JSON.stringify(asset),
    });
  }

  async updateAsset(id: string, updates: Partial<Asset>): Promise<Asset> {
    return this.request<Asset>(`/assets/${id}/`, {
      method: 'PATCH',
      body: JSON.stringify(updates),
    });
  }

  async deleteAsset(id: string): Promise<boolean> {
    await this.request(`/assets/${id}/`, { method: 'DELETE' });
    return true;
  }

  async getTransfers(): Promise<Transfer[]> {
    return this.request<Transfer[]>('/transfers/');
  }

  async createTransfer(transfer: Partial<Transfer>): Promise<Transfer> {
    return this.request<Transfer>('/transfers/', {
      method: 'POST',
      body: JSON.stringify(transfer),
    });
  }

  async updateTransferStatus(id: string, status: Transfer['status']): Promise<Transfer> {
    return this.request<Transfer>(`/transfers/${id}/status/`, {
      method: 'POST',
      body: JSON.stringify({ status }),
    });
  }

  async getMaintenance(): Promise<MaintenanceRecord[]> {
    return this.request<MaintenanceRecord[]>('/maintenance/');
  }

  async createMaintenance(record: Partial<MaintenanceRecord>): Promise<MaintenanceRecord> {
    return this.request<MaintenanceRecord>('/maintenance/', {
      method: 'POST',
      body: JSON.stringify(record),
    });
  }

  async updateMaintenanceStatus(id: string, status: MaintenanceRecord['status']): Promise<MaintenanceRecord> {
    return this.request<MaintenanceRecord>(`/maintenance/${id}/`, {
      method: 'PATCH',
      body: JSON.stringify({ status }),
    });
  }

  async getDisposals(): Promise<DisposalRecord[]> {
    return this.request<DisposalRecord[]>('/disposals/');
  }

  async createDisposal(disposal: Partial<DisposalRecord>): Promise<DisposalRecord> {
    return this.request<DisposalRecord>('/disposals/', {
      method: 'POST',
      body: JSON.stringify(disposal),
    });
  }

  async updateDisposalStatus(id: string, status: DisposalRecord['status']): Promise<DisposalRecord> {
    return this.request<DisposalRecord>(`/disposals/${id}/`, {
      method: 'PATCH',
      body: JSON.stringify({ status }),
    });
  }

  async getCategories(): Promise<AssetCategory[]> {
    return this.request<AssetCategory[]>('/categories/');
  }

  async getDepartments(): Promise<Department[]> {
    return this.request<Department[]>('/departments/');
  }

  async getLocations(): Promise<LocationHub[]> {
    return this.request<LocationHub[]>('/locations/');
  }

  async getUsers(): Promise<UserProfile[]> {
    return this.request<UserProfile[]>('/users/');
  }

  async getAssignments(): Promise<CustodyAssignment[]> {
    return this.request<CustodyAssignment[]>('/assignments/');
  }

  async getAuditLogs(params?: { entity?: string; search?: string }): Promise<AuditLogEntry[]> {
    const query = new URLSearchParams();
    if (params?.entity) query.set('entity', params.entity);
    if (params?.search) query.set('search', params.search);
    return this.request<AuditLogEntry[]>(`/audit-logs/?${query.toString()}`);
  }

  async getDashboardMetrics(): Promise<DashboardMetrics> {
    return this.request<DashboardMetrics>('/dashboard/executive-metrics/');
  }

  async getSettings(): Promise<SystemSettings> {
    return this.request<SystemSettings>('/settings/');
  }

  async updateSettings(settings: Partial<SystemSettings>): Promise<SystemSettings> {
    return this.request<SystemSettings>('/settings/', {
      method: 'PATCH',
      body: JSON.stringify(settings),
    });
  }

  async resetToDefaultData(): Promise<void> {
    await this.request('/admin/reset-demo-seed/', { method: 'POST' });
  }
}
