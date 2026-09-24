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

// Default Seed Data
const DEFAULT_LOCATIONS: LocationHub[] = [
  {
    id: 'LOC-01',
    code: 'LOS',
    name: 'Lagos HQ & Tech Hub',
    city: 'Victoria Island',
    state: 'Lagos State',
    address: 'Plot 12B, Adeola Odeku Street, Victoria Island, Lagos',
    coordinates: '6.4281° N, 3.4219° E',
    hub_manager: 'Femi Lawson',
    asset_count: 580,
    total_cost: 1_120_000_000,
    total_nbv: 820_000_000,
    percentage_of_total: 46.1,
  },
  {
    id: 'LOC-02',
    code: 'PHC',
    name: 'Port Harcourt Industrial Base',
    city: 'Trans-Amadi',
    state: 'Rivers State',
    address: 'KM 14, Trans-Amadi Industrial Layout, Port Harcourt',
    coordinates: '4.8156° N, 7.0498° E',
    hub_manager: 'Engr. Ifeanyi Okeke',
    asset_count: 310,
    total_cost: 680_000_000,
    total_nbv: 490_000_000,
    percentage_of_total: 28.0,
  },
  {
    id: 'LOC-03',
    code: 'ABJ',
    name: 'Abuja Liaison & Data Center',
    city: 'Central Business District',
    state: 'Federal Capital Territory',
    address: 'Plot 742, Constitution Avenue, CBD, Abuja',
    coordinates: '9.0579° N, 7.4951° E',
    hub_manager: 'Funke Akindele',
    asset_count: 220,
    total_cost: 390_000_000,
    total_nbv: 260_000_000,
    percentage_of_total: 16.0,
  },
  {
    id: 'LOC-04',
    code: 'WAR',
    name: 'Warri Logistics Depot',
    city: 'Warri',
    state: 'Delta State',
    address: 'Heavy Staging Yard Bay 4B, Jetty Road, Warri',
    coordinates: '5.5160° N, 5.7500° E',
    hub_manager: 'Musa Danjuma',
    asset_count: 114,
    total_cost: 160_000_000,
    total_nbv: 98_000_000,
    percentage_of_total: 6.6,
  },
  {
    id: 'LOC-05',
    code: 'IBD',
    name: 'Ibadan Operations',
    city: 'Ring Road',
    state: 'Oyo State',
    address: 'Industrial Estate, Ring Road, Ibadan',
    coordinates: '7.3775° N, 3.9470° E',
    hub_manager: 'Samuel Okon',
    asset_count: 60,
    total_cost: 81_850_000,
    total_nbv: 43_850_000,
    percentage_of_total: 3.3,
  },
];

const DEFAULT_DEPARTMENTS: Department[] = [
  {
    id: 'DEP-01',
    code: 'FIN',
    name: 'Finance & Treasury',
    head_name: 'Babajide Adeleke',
    head_staff_id: 'AF-FIN-001',
    email: 'b.adeleke@assetflow.ng',
    asset_count: 85,
    total_cost: 95_000_000,
    total_nbv: 72_000_000,
  },
  {
    id: 'DEP-02',
    code: 'OPS',
    name: 'Operations & Logistics',
    head_name: 'Emeka Okafor',
    head_staff_id: 'AF-OPS-012',
    email: 'e.okafor@assetflow.ng',
    asset_count: 420,
    total_cost: 840_000_000,
    total_nbv: 590_000_000,
  },
  {
    id: 'DEP-03',
    code: 'IT',
    name: 'Information Technology',
    head_name: 'Funke Akindele',
    head_staff_id: 'AF-IT-004',
    email: 'f.akindele@assetflow.ng',
    asset_count: 360,
    total_cost: 540_000_000,
    total_nbv: 380_000_000,
  },
  {
    id: 'DEP-04',
    code: 'ENG',
    name: 'Engineering & Infrastructure',
    head_name: 'Engr. Musa Danjuma, FNSE',
    head_staff_id: 'AF-ENG-002',
    email: 'm.danjuma@assetflow.ng',
    asset_count: 240,
    total_cost: 650_000_000,
    total_nbv: 440_000_000,
  },
  {
    id: 'DEP-05',
    code: 'PRC',
    name: 'Procurement',
    head_name: 'Chinedu Eze',
    head_staff_id: 'AF-PRC-019',
    email: 'c.eze@assetflow.ng',
    asset_count: 55,
    total_cost: 68_000_000,
    total_nbv: 52_000_000,
  },
  {
    id: 'DEP-06',
    code: 'HR',
    name: 'Human Resources & Admin',
    head_name: 'Samuel Okon',
    head_staff_id: 'AF-HR-007',
    email: 's.okon@assetflow.ng',
    asset_count: 64,
    total_cost: 114_000_000,
    total_nbv: 78_000_000,
  },
  {
    id: 'DEP-07',
    code: 'ADM',
    name: 'Administration & Facilities',
    head_name: 'Aisha Bello',
    head_staff_id: 'AF-ADM-015',
    email: 'a.bello@assetflow.ng',
    asset_count: 60,
    total_cost: 124_850_000,
    total_nbv: 99_850_000,
  },
];

const DEFAULT_CATEGORIES: AssetCategory[] = [
  {
    id: 'CAT-01',
    code: 'HME',
    name: 'Heavy Machinery & Equipment',
    description: 'Earthmoving crawlers, excavators, loaders, and quarry machines',
    standard_useful_life_months: 120,
    default_depreciation_method: 'SLM',
    default_residual_rate_pct: 10,
    asset_count: 142,
    total_cost: 920_000_000,
    total_nbv: 644_000_000,
  },
  {
    id: 'CAT-02',
    code: 'ITE',
    name: 'IT Infrastructure & Servers',
    description: 'Tier-3 data center blade racks, routers, high-capacity core switches, SAN storage',
    standard_useful_life_months: 60,
    default_depreciation_method: 'SLM',
    default_residual_rate_pct: 5,
    asset_count: 480,
    total_cost: 540_000_000,
    total_nbv: 378_000_000,
  },
  {
    id: 'CAT-03',
    code: 'MVF',
    name: 'Motor Vehicles & Fleet',
    description: 'Executive haulage, 4x4 operations pickups, staff buses, transport trucks',
    standard_useful_life_months: 60,
    default_depreciation_method: 'SLM',
    default_residual_rate_pct: 15,
    asset_count: 185,
    total_cost: 480_000_000,
    total_nbv: 336_000_000,
  },
  {
    id: 'CAT-04',
    code: 'BLI',
    name: 'Buildings & Leasehold Improvements',
    description: 'Corporate facilities, civil structures, warehouse extensions, security perimeters',
    standard_useful_life_months: 300,
    default_depreciation_method: 'SLM',
    default_residual_rate_pct: 10,
    asset_count: 48,
    total_cost: 320_000_000,
    total_nbv: 240_000_000,
  },
  {
    id: 'CAT-05',
    code: 'OFF',
    name: 'Office Furniture & Fixtures',
    description: 'Executive workstations, boardroom acoustic suites, ergonomic chairs, safes',
    standard_useful_life_months: 96,
    default_depreciation_method: 'SLM',
    default_residual_rate_pct: 5,
    asset_count: 429,
    total_cost: 171_850_000,
    total_nbv: 113_850_000,
  },
];

const DEFAULT_USERS: UserProfile[] = [
  {
    id: 'USR-01',
    staff_id: 'AF-FIN-001',
    name: 'Babajide Adeleke',
    email: 'b.adeleke@assetflow.ng',
    role: 'ADMIN',
    department_name: 'Finance & Treasury',
    location_name: 'Lagos HQ & Tech Hub',
    avatar_url: 'https://lh3.googleusercontent.com/aida-public/AB6AXuAQjfBsnhUaJsODwEIF9c0JR_abXkekvgOcDVi5SDEn9XwB2QLLVFL0I1mqW9ENZWMpBgmArkeKu5892aDBQ0yigfitDIhl9sqzrnljzIYp_0HXvxK7VK6ASuCN_XIy6kJYGz9kr8GcG810_r_gs-X88MTihb5Xc-ZVfmZ07aEHzm7G1sewQIAapXSeztpsj10RgiJMkHqoR5_q8ysDR0QiTJRFPX9t9WrYg57P33GZz-83I6HU8x-cTw',
    is_active: true,
  },
  {
    id: 'USR-02',
    staff_id: 'AF-ENG-084',
    name: 'Babatunde Adeleke',
    email: 'babatunde.a@assetflow.ng',
    role: 'ASSET_MANAGER',
    department_name: 'Engineering & Infrastructure',
    location_name: 'Warri Logistics Depot',
    avatar_url: 'https://lh3.googleusercontent.com/aida-public/AB6AXuAQjfBsnhUaJsODwEIF9c0JR_abXkekvgOcDVi5SDEn9XwB2QLLVFL0I1mqW9ENZWMpBgmArkeKu5892aDBQ0yigfitDIhl9sqzrnljzIYp_0HXvxK7VK6ASuCN_XIy6kJYGz9kr8GcG810_r_gs-X88MTihb5Xc-ZVfmZ07aEHzm7G1sewQIAapXSeztpsj10RgiJMkHqoR5_q8ysDR0QiTJRFPX9t9WrYg57P33GZz-83I6HU8x-cTw',
    is_active: true,
  },
  {
    id: 'USR-03',
    staff_id: 'AF-OPS-012',
    name: 'Emeka Okafor',
    email: 'e.okafor@assetflow.ng',
    role: 'DEPT_MANAGER',
    department_name: 'Operations & Logistics',
    location_name: 'Port Harcourt Industrial Base',
    avatar_url: '',
    is_active: true,
  },
  {
    id: 'USR-04',
    staff_id: 'AF-IT-004',
    name: 'Funke Akindele',
    email: 'f.akindele@assetflow.ng',
    role: 'DEPT_MANAGER',
    department_name: 'Information Technology',
    location_name: 'Abuja Liaison & Data Center',
    avatar_url: '',
    is_active: true,
  },
  {
    id: 'USR-05',
    staff_id: 'AF-ENG-002',
    name: 'Engr. Musa Danjuma, FNSE',
    email: 'm.danjuma@assetflow.ng',
    role: 'DEPT_MANAGER',
    department_name: 'Engineering & Infrastructure',
    location_name: 'Warri Logistics Depot',
    avatar_url: '',
    is_active: true,
  },
];

const DEFAULT_ASSETS: Asset[] = [
  {
    id: 'ast-001',
    tag: 'AST-000001',
    name: 'Toyota Hilux 2.8 GD-6 4x4',
    spec: 'Fleet Ref: PH-V-01 • Automatic 4WD Diesel',
    description: 'Double cabin heavy-duty field support vehicle with winch and roll bar.',
    category_id: 'CAT-03',
    category_name: 'Motor Vehicles & Fleet',
    category_code: 'MVF',
    manufacturer: 'Toyota Motor Corp',
    model: 'Hilux 2.8 GD-6 Double Cabin',
    serial_number: 'SN-THLX-8839201',
    engine_model: '1GD-FTV 2.8L Turbo Diesel',
    year_of_manufacture: 2023,
    net_power: '150 kW (201 hp)',
    operating_hours: 1450,
    department_id: 'DEP-02',
    department_name: 'Operations',
    department_head: 'Emeka Okafor',
    location_id: 'LOC-02',
    location_name: 'Port Harcourt Hub',
    sub_location: 'Bay 2 Field Operations Yard',
    coordinates: '4.8156° N, 7.0498° E',
    custodian_id: 'USR-03',
    custodian_name: 'Emeka Okafor',
    custodian_staff_id: 'AF-OPS-012',
    custodian_title: 'Head of Operations',
    custody_handover_date: '2023-01-20',
    custody_signed_ack: true,
    vendor: 'Elizade Nigeria Limited',
    vendor_branch: 'Port Harcourt Branch',
    purchase_order_ref: 'PO-2023-0091',
    commercial_invoice_ref: 'INV-ELZ-84920',
    acquisition_date: '2023-01-14',
    capitalization_date: '2023-01-15',
    currency: 'NGN',
    cost_components: {
      base_purchase: 39_000_000,
      freight: 1_800_000,
      installation: 1_200_000,
      civil_works: 0,
      other_costs: 500_000,
    },
    total_acquisition_cost: 42_500_000,
    depreciation_method: 'SLM',
    useful_life_years: 5,
    useful_life_months: 60,
    residual_rate_pct: 15,
    salvage_value: 6_375_000,
    depreciable_base: 36_125_000,
    monthly_depreciation: 602_083,
    annual_depreciation: 7_225_000,
    accumulated_depreciation: 10_625_000,
    net_book_value: 31_875_000,
    carrying_rate_pct: 75.0,
    status: 'ACTIVE',
    is_capitalized: true,
    ledger_code: '1210-OPS',
    insurance_policy: 'PLA-991204',
    insurance_carrier: 'Leadway Assurance',
    rfid_tag: 'RFID-THLX-000001',
    image_url: 'https://images.unsplash.com/photo-1559297434-fae8a1916a79?auto=format&fit=crop&w=600&q=80',
    health_score: 94,
    next_inspection_hours: 2000,
    created_at: '2023-01-15T08:00:00Z',
    updated_at: '2025-02-10T14:20:00Z',
    documents: [
      { id: 'doc-01', name: 'Elizade Original Bill of Sale', type: 'PDF', size: '2.1 MB', date: 'Jan 14, 2023', description: 'Certified purchase invoice and customs receipt', verified: true },
      { id: 'doc-02', name: 'Comprehensive Fleet Insurance', type: 'PDF', size: '1.4 MB', date: 'Jan 15, 2024', description: 'Leadway Assurance active policy endorsement', verified: true },
    ],
  },
  {
    id: 'ast-002',
    tag: 'AST-000002',
    name: 'Caterpillar 336 Hydraulic Excavator',
    spec: 'Tier 4 Final • Heavy Crawler • 3,420 Hours',
    description: 'Heavy duty earthmoving crawler excavator for site remediation and infrastructural ground engineering.',
    category_id: 'CAT-01',
    category_name: 'Heavy Machinery & Equipment',
    category_code: 'HME',
    manufacturer: 'Caterpillar Inc. (USA)',
    model: '336 Heavy Duty HEX',
    serial_number: 'CAT-0336-HEX-994821',
    engine_model: 'Cat C9.3B ACERT Tier 4 Final',
    year_of_manufacture: 2022,
    net_power: '234 kW (314 hp)',
    operating_weight: '37,200 kg (81,900 lb)',
    operating_hours: 3420,
    voltage: '24.2V',
    department_id: 'DEP-04',
    department_name: 'Engineering & Infrastructure',
    department_head: 'Engr. Musa Danjuma, FNSE',
    location_id: 'LOC-04',
    location_name: 'Warri Logistics Depot',
    sub_location: 'Heavy Yard Bay 4B, Jetty Road',
    coordinates: '5.5160° N, 5.7500° E',
    custodian_id: 'USR-02',
    custodian_name: 'Babatunde Adeleke',
    custodian_staff_id: 'AF-ENG-084',
    custodian_title: 'Senior Site Engineer',
    custodian_avatar: 'https://lh3.googleusercontent.com/aida-public/AB6AXuAQjfBsnhUaJsODwEIF9c0JR_abXkekvgOcDVi5SDEn9XwB2QLLVFL0I1mqW9ENZWMpBgmArkeKu5892aDBQ0yigfitDIhl9sqzrnljzIYp_0HXvxK7VK6ASuCN_XIy6kJYGz9kr8GcG810_r_gs-X88MTihb5Xc-ZVfmZ07aEHzm7G1sewQIAapXSeztpsj10RgiJMkHqoR5_q8ysDR0QiTJRFPX9t9WrYg57P33GZz-83I6HU8x-cTw',
    custody_handover_date: 'August 12, 2023 (via Port Harcourt)',
    custody_signed_ack: true,
    vendor: 'Mantrac Nigeria Ltd',
    vendor_branch: 'Lagos Branch',
    purchase_order_ref: 'PO-2022-0418',
    commercial_invoice_ref: 'INV-MAN-88392',
    acquisition_date: '2022-06-05',
    capitalization_date: '2022-06-15',
    currency: 'NGN',
    cost_components: {
      base_purchase: 260_000_000,
      freight: 18_000_000,
      installation: 7_000_000,
      civil_works: 0,
      other_costs: 0,
    },
    total_acquisition_cost: 285_000_000,
    depreciation_method: 'SLM',
    useful_life_years: 10,
    useful_life_months: 120,
    residual_rate_pct: 10,
    salvage_value: 28_500_000,
    depreciable_base: 256_500_000,
    monthly_depreciation: 2_137_500,
    annual_depreciation: 25_650_000,
    accumulated_depreciation: 85_500_000,
    net_book_value: 199_500_000,
    carrying_rate_pct: 70.0,
    status: 'IN_MAINTENANCE',
    is_capitalized: true,
    ledger_code: '1410-ENG',
    insurance_policy: 'PLA-882910',
    insurance_carrier: 'Leadway Assurance',
    rfid_tag: 'AST-000002-NG',
    image_url: 'https://lh3.googleusercontent.com/aida-public/AB6AXuCJANM-meqI8f_wd1w65c5rU2bLWTVHSmsYlW1NmBhpENPBpHm-jMnAx8H6Rwv9aVI85CsGhLLmfd-9oeZW65EcavmS9Gs2zPyGkgJ18c_EGynwJproWt-H01BenxM0mzLg0nR3wVxuVap0aqk3s7_z4EaoIF1NG8ZIIi9_wkEjCoeimyb5aFFtTB9UiH6vTgk3Lw1cQ6HzmIZR6oVpKSMDtcqROO8e5Ah-TSfIEFDj8xXgGSoUDuQcVw',
    health_score: 78,
    next_inspection_hours: 3500,
    created_at: '2022-06-15T10:00:00Z',
    updated_at: '2025-03-24T09:15:00Z',
    documents: [
      { id: 'doc-cat-1', name: 'OEM Warranty Certificate (Cat Standard)', type: 'PDF', size: '2.4 MB', date: 'Jun 15, 2022', description: 'Valid through Jun 2025 certified warranty', verified: true },
      { id: 'doc-cat-2', name: 'Mantrac Purchase Invoice & Bill of Lading', type: 'PDF', size: '5.1 MB', date: 'Jun 05, 2022', description: 'Signed and stamped shipping manifest', verified: true },
      { id: 'doc-cat-3', name: 'Physical Verification & Tagging Signoff', type: 'PDF', size: '1.8 MB', date: 'Oct 24, 2024', description: 'Internal Audit Lagos HQ signoff', verified: true },
      { id: 'doc-cat-4', name: 'Comprehensive Insurance Policy Certificate', type: 'PDF', size: '3.2 MB', date: 'Jan 10, 2025', description: 'Policy #PLA-882910 active policy schedule', verified: true },
    ],
  },
  {
    id: 'ast-003',
    tag: 'AST-000003',
    name: 'Dell PowerEdge R750 Rack Server',
    spec: 'Dual Intel Xeon Gold • 256GB RAM • 16TB NVMe SSD',
    description: 'Enterprise production rack server powering financial core banking replication and ERP ledgers.',
    category_id: 'CAT-02',
    category_name: 'IT Infrastructure & Servers',
    category_code: 'ITE',
    manufacturer: 'Dell Technologies',
    model: 'PowerEdge R750 2U',
    serial_number: 'SRV-DELL-R750-019',
    year_of_manufacture: 2023,
    department_id: 'DEP-03',
    department_name: 'Information Technology',
    department_head: 'Funke Akindele',
    location_id: 'LOC-03',
    location_name: 'Abuja Data Center',
    sub_location: 'Tier-3 Vault Rack Bay 08',
    coordinates: '9.0579° N, 7.4951° E',
    custodian_id: 'USR-04',
    custodian_name: 'Funke Akindele',
    custodian_staff_id: 'AF-IT-004',
    custodian_title: 'Director of Technology',
    custody_handover_date: '2023-11-22',
    custody_signed_ack: true,
    vendor: 'Resourcery Plc',
    purchase_order_ref: 'PO-2023-0841',
    commercial_invoice_ref: 'INV-RES-9931',
    acquisition_date: '2023-11-20',
    capitalization_date: '2023-11-22',
    currency: 'NGN',
    cost_components: {
      base_purchase: 16_500_000,
      freight: 900_000,
      installation: 1_200_000,
      civil_works: 0,
      other_costs: 300_000,
    },
    total_acquisition_cost: 18_900_000,
    depreciation_method: 'SLM',
    useful_life_years: 5,
    useful_life_months: 60,
    residual_rate_pct: 5,
    salvage_value: 945_000,
    depreciable_base: 17_955_000,
    monthly_depreciation: 299_250,
    annual_depreciation: 3_591_000,
    accumulated_depreciation: 4_725_000,
    net_book_value: 14_175_000,
    carrying_rate_pct: 75.0,
    status: 'ACTIVE',
    is_capitalized: true,
    ledger_code: '1310-IT',
    insurance_policy: 'PLA-391821',
    insurance_carrier: 'AIICO Insurance',
    rfid_tag: 'RFID-R750-000003',
    image_url: 'https://images.unsplash.com/photo-1558494949-ef010cbdcc31?auto=format&fit=crop&w=600&q=80',
    health_score: 96,
    created_at: '2023-11-22T11:00:00Z',
    updated_at: '2025-01-18T10:00:00Z',
  },
  {
    id: 'ast-004',
    tag: 'AST-000004',
    name: 'HP ProBook 450 G9 (Batch of 25)',
    spec: 'Intel Core i7-1255U • 16GB RAM • 512GB PCIe SSD',
    description: 'Standard engineering and operational field laptops deployed across procurement and logistics.',
    category_id: 'CAT-02',
    category_name: 'IT Infrastructure & Servers',
    category_code: 'ITE',
    manufacturer: 'HP Inc',
    model: 'ProBook 450 G9',
    serial_number: 'HP-PB450-ENG-LOT2',
    year_of_manufacture: 2024,
    department_id: 'DEP-05',
    department_name: 'Procurement',
    department_head: 'Chinedu Eze',
    location_id: 'LOC-01',
    location_name: 'Lagos HQ & Tech Hub',
    sub_location: 'Procurement Wing, 3rd Floor',
    custodian_id: 'USR-01',
    custodian_name: 'Chinedu Eze',
    custodian_staff_id: 'AF-PRC-019',
    custodian_title: 'Procurement Specialist',
    custody_handover_date: '2024-03-12',
    custody_signed_ack: true,
    vendor: 'TD Africa Distribution',
    purchase_order_ref: 'PO-2024-0192',
    commercial_invoice_ref: 'INV-TDA-2024-81',
    acquisition_date: '2024-03-10',
    capitalization_date: '2024-03-12',
    currency: 'NGN',
    cost_components: {
      base_purchase: 15_500_000,
      freight: 450_000,
      installation: 200_000,
      civil_works: 0,
      other_costs: 100_000,
    },
    total_acquisition_cost: 16_250_000,
    depreciation_method: 'SLM',
    useful_life_years: 4,
    useful_life_months: 48,
    residual_rate_pct: 5,
    salvage_value: 812_500,
    depreciable_base: 15_437_500,
    monthly_depreciation: 321_615,
    annual_depreciation: 3_859_375,
    accumulated_depreciation: 1_625_000,
    net_book_value: 14_625_000,
    carrying_rate_pct: 90.0,
    status: 'ACTIVE',
    is_capitalized: true,
    ledger_code: '1320-IT',
    insurance_policy: 'PLA-771829',
    insurance_carrier: 'AXA Mansard',
    rfid_tag: 'RFID-HP-000004',
    image_url: 'https://images.unsplash.com/photo-1593642632823-8f785ba67e45?auto=format&fit=crop&w=600&q=80',
    health_score: 98,
    created_at: '2024-03-12T09:00:00Z',
    updated_at: '2025-01-05T12:00:00Z',
  },
  {
    id: 'ast-005',
    tag: 'AST-000005',
    name: 'Boardroom Ergonomic Suite (16x Herman Miller Aeron)',
    spec: 'Herman Miller Aeron Graphite Fully Adjustable Set',
    description: 'Executive conference boardroom ergonomic task chairs and solid mahogany table setup.',
    category_id: 'CAT-05',
    category_name: 'Office Furniture & Fixtures',
    category_code: 'OFF',
    manufacturer: 'Herman Miller',
    model: 'Aeron Ergonomic B-Size',
    serial_number: 'FF-HM-AERON-2023',
    year_of_manufacture: 2023,
    department_id: 'DEP-07',
    department_name: 'Administration',
    department_head: 'Aisha Bello',
    location_id: 'LOC-01',
    location_name: 'Lagos HQ & Tech Hub',
    sub_location: 'Executive Boardroom 5th Floor',
    custodian_id: 'USR-01',
    custodian_name: 'Aisha Bello',
    custodian_staff_id: 'AF-ADM-015',
    custodian_title: 'Facilities Administrator',
    custody_handover_date: '2023-08-20',
    custody_signed_ack: true,
    vendor: 'Vantage Interiors Lagos',
    purchase_order_ref: 'PO-2023-0612',
    commercial_invoice_ref: 'INV-VAN-552',
    acquisition_date: '2023-08-18',
    capitalization_date: '2023-08-20',
    currency: 'NGN',
    cost_components: {
      base_purchase: 23_000_000,
      freight: 1_000_000,
      installation: 600_000,
      civil_works: 0,
      other_costs: 200_000,
    },
    total_acquisition_cost: 24_800_000,
    depreciation_method: 'SLM',
    useful_life_years: 8,
    useful_life_months: 96,
    residual_rate_pct: 5,
    salvage_value: 1_240_000,
    depreciable_base: 23_560_000,
    monthly_depreciation: 245_417,
    annual_depreciation: 2_945_000,
    accumulated_depreciation: 3_720_000,
    net_book_value: 21_080_000,
    carrying_rate_pct: 85.0,
    status: 'ACTIVE',
    is_capitalized: true,
    ledger_code: '1510-ADM',
    insurance_policy: 'PLA-901844',
    insurance_carrier: 'Leadway Assurance',
    rfid_tag: 'RFID-HM-000005',
    image_url: 'https://images.unsplash.com/photo-1580481077197-25e2e49c6d54?auto=format&fit=crop&w=600&q=80',
    health_score: 95,
    created_at: '2023-08-20T14:00:00Z',
    updated_at: '2024-12-01T10:00:00Z',
  },
  {
    id: 'ast-006',
    tag: 'AST-000006',
    name: 'Mikano Perkins 500kVA Heavy Generator',
    spec: 'Soundproof Enclosure • Auto-ATS • Deepsea Digital Control',
    description: 'Primary continuous standby power plant for Lagos HQ operational continuity.',
    category_id: 'CAT-01',
    category_name: 'Heavy Machinery & Equipment',
    category_code: 'HME',
    manufacturer: 'Mikano International / Perkins',
    model: 'P500HE Containerized',
    serial_number: 'PK-500KVA-NG-401',
    year_of_manufacture: 2021,
    operating_hours: 4890,
    department_id: 'DEP-07',
    department_name: 'Facility Mgmt',
    department_head: 'Tunde Bakare',
    location_id: 'LOC-01',
    location_name: 'Lagos HQ & Tech Hub',
    sub_location: 'Central Power Substation Pad A',
    custodian_id: 'USR-01',
    custodian_name: 'Tunde Bakare',
    custodian_staff_id: 'AF-FAC-031',
    custodian_title: 'Facilities Chief Engineer',
    custody_handover_date: '2021-02-10',
    custody_signed_ack: true,
    vendor: 'Mikano International Ltd',
    purchase_order_ref: 'PO-2021-0104',
    commercial_invoice_ref: 'INV-MK-2021-049',
    acquisition_date: '2021-02-02',
    capitalization_date: '2021-02-10',
    currency: 'NGN',
    cost_components: {
      base_purchase: 48_000_000,
      freight: 2_500_000,
      installation: 2_000_000,
      civil_works: 1_200_000,
      other_costs: 300_000,
    },
    total_acquisition_cost: 54_000_000,
    depreciation_method: 'SLM',
    useful_life_years: 8,
    useful_life_months: 96,
    residual_rate_pct: 10,
    salvage_value: 5_400_000,
    depreciable_base: 48_600_000,
    monthly_depreciation: 506_250,
    annual_depreciation: 6_075_000,
    accumulated_depreciation: 27_000_000,
    net_book_value: 27_000_000,
    carrying_rate_pct: 50.0,
    status: 'ACTIVE',
    is_capitalized: true,
    ledger_code: '1420-ENG',
    insurance_policy: 'PLA-331092',
    insurance_carrier: 'Leadway Assurance',
    rfid_tag: 'RFID-PK-000006',
    image_url: 'https://lh3.googleusercontent.com/aida-public/AB6AXuARkC1Wlvx9Ay6CnusCTKpVnMoikv2jHnwXTymqXs2qBxbMMAKFQTjdlQ1IHnNoHlbW6x2-rN60RT8qVazfUhoc2laoSuBH5TLHyMK9md4u9tBpcm5P_HMql97FKiWYTWmRpNjySGxI9bQ_-ZY3slWJoM12u7tNA2kZ-sO6juTnycIk8Z2kq5LrtlVrtXurYIFIZxHiumYNXX6dihJkhD5sh-MahSGaVdMYezsQjAkud1-_jk7EqCqhsQ',
    health_score: 82,
    created_at: '2021-02-10T08:00:00Z',
    updated_at: '2025-02-28T16:00:00Z',
  },
  {
    id: 'ast-007',
    tag: 'AST-000007',
    name: 'Komatsu WA380 Wheel Loader',
    spec: 'Bucket Capacity: 3.4 m³ • 142 kW Tier-4 Heavy Duty',
    description: 'Heavy pneumatic wheel loader used for aggregates and logistical materials transfer.',
    category_id: 'CAT-01',
    category_name: 'Heavy Machinery & Equipment',
    category_code: 'HME',
    manufacturer: 'Komatsu Ltd',
    model: 'WA380-8',
    serial_number: 'KM-WA380-0082',
    year_of_manufacture: 2021,
    department_id: 'DEP-02',
    department_name: 'Operations',
    department_head: 'Emeka Okafor',
    location_id: 'LOC-02',
    location_name: 'Port Harcourt Hub',
    sub_location: 'Yard Sector 3, Trans-Amadi',
    custodian_id: 'USR-03',
    custodian_name: 'Ibrahim Yusuf',
    custodian_staff_id: 'AF-OPS-039',
    custodian_title: 'Heavy Fleet Supervisor',
    custody_handover_date: '2021-07-15',
    custody_signed_ack: true,
    vendor: 'Komatsu West Africa',
    purchase_order_ref: 'PO-2021-0391',
    commercial_invoice_ref: 'INV-KM-7729',
    acquisition_date: '2021-07-12',
    capitalization_date: '2021-07-15',
    currency: 'NGN',
    cost_components: {
      base_purchase: 178_000_000,
      freight: 11_000_000,
      installation: 4_500_000,
      civil_works: 0,
      other_costs: 1_500_000,
    },
    total_acquisition_cost: 195_000_000,
    depreciation_method: 'SLM',
    useful_life_years: 10,
    useful_life_months: 120,
    residual_rate_pct: 10,
    salvage_value: 19_500_000,
    depreciable_base: 175_500_000,
    monthly_depreciation: 1_462_500,
    annual_depreciation: 17_550_000,
    accumulated_depreciation: 78_000_000,
    net_book_value: 117_000_000,
    carrying_rate_pct: 60.0,
    status: 'TRANSFERRED',
    is_capitalized: true,
    ledger_code: '1410-ENG',
    insurance_policy: 'PLA-661920',
    insurance_carrier: 'Leadway Assurance',
    rfid_tag: 'RFID-KM-000007',
    image_url: 'https://images.unsplash.com/photo-1581092160607-ee22621dd758?auto=format&fit=crop&w=600&q=80',
    health_score: 86,
    created_at: '2021-07-15T10:00:00Z',
    updated_at: '2025-03-01T11:00:00Z',
  },
  {
    id: 'ast-008',
    tag: 'AST-000008',
    name: 'Cisco Catalyst 9500 Core Switch',
    spec: '40-Port 100G Modular Enterprise Backbone Switch',
    description: 'Central campus core networking switch connecting corporate HQ to cloud regional data centers.',
    category_id: 'CAT-02',
    category_name: 'IT Infrastructure & Servers',
    category_code: 'ITE',
    manufacturer: 'Cisco Systems',
    model: 'Catalyst C9500-40X',
    serial_number: 'CS-CAT9500-NG-88',
    year_of_manufacture: 2023,
    department_id: 'DEP-03',
    department_name: 'Information Technology',
    department_head: 'Funke Akindele',
    location_id: 'LOC-01',
    location_name: 'Lagos HQ & Tech Hub',
    sub_location: 'Server Room 2B, Lagos HQ',
    custodian_id: 'USR-04',
    custodian_name: 'Kayode Fashola',
    custodian_staff_id: 'AF-IT-018',
    custodian_title: 'Network Systems Architect',
    custody_handover_date: '2023-05-20',
    custody_signed_ack: true,
    vendor: 'Dimension Data Nigeria',
    purchase_order_ref: 'PO-2023-0382',
    commercial_invoice_ref: 'INV-DD-4410',
    acquisition_date: '2023-05-19',
    capitalization_date: '2023-05-20',
    currency: 'NGN',
    cost_components: {
      base_purchase: 11_000_000,
      freight: 600_000,
      installation: 600_000,
      civil_works: 0,
      other_costs: 200_000,
    },
    total_acquisition_cost: 12_400_000,
    depreciation_method: 'SLM',
    useful_life_years: 5,
    useful_life_months: 60,
    residual_rate_pct: 5,
    salvage_value: 620_000,
    depreciable_base: 11_780_000,
    monthly_depreciation: 196_333,
    annual_depreciation: 2_356_000,
    accumulated_depreciation: 2_480_000,
    net_book_value: 9_920_000,
    carrying_rate_pct: 80.0,
    status: 'ACTIVE',
    is_capitalized: true,
    ledger_code: '1310-IT',
    insurance_policy: 'PLA-119283',
    insurance_carrier: 'AIICO Insurance',
    rfid_tag: 'RFID-CS-000008',
    image_url: 'https://images.unsplash.com/photo-1544197150-b99a580bb7a8?auto=format&fit=crop&w=600&q=80',
    health_score: 99,
    created_at: '2023-05-20T08:00:00Z',
    updated_at: '2025-01-15T14:00:00Z',
  },
  {
    id: 'ast-009',
    tag: 'AST-000009',
    name: 'Toyota Coaster Staff Bus (30-Seater)',
    spec: '30-Seater Diesel Manual • Inter-city Logistics',
    description: 'Staff transport shuttle bus servicing Ibadan regional operations and logistics routes.',
    category_id: 'CAT-03',
    category_name: 'Motor Vehicles & Fleet',
    category_code: 'MVF',
    manufacturer: 'Toyota Motor Corp',
    model: 'Coaster Standard HZB50',
    serial_number: 'TY-CST-30S-2020',
    year_of_manufacture: 2020,
    operating_hours: 112000,
    department_id: 'DEP-06',
    department_name: 'HR & Admin',
    department_head: 'Samuel Okon',
    location_id: 'LOC-05',
    location_name: 'Ibadan Operations',
    sub_location: 'Ring Road Depot Bay 1',
    custodian_id: 'USR-01',
    custodian_name: 'Samuel Okon',
    custodian_staff_id: 'AF-HR-007',
    custodian_title: 'Regional HR Manager',
    custody_handover_date: '2020-01-18',
    custody_signed_ack: true,
    vendor: 'Globe Motors Limited',
    purchase_order_ref: 'PO-2020-0012',
    commercial_invoice_ref: 'INV-GLB-291',
    acquisition_date: '2020-01-15',
    capitalization_date: '2020-01-18',
    currency: 'NGN',
    cost_components: {
      base_purchase: 62_000_000,
      freight: 3_500_000,
      installation: 1_500_000,
      civil_works: 0,
      other_costs: 1_000_000,
    },
    total_acquisition_cost: 68_000_000,
    depreciation_method: 'SLM',
    useful_life_years: 5,
    useful_life_months: 60,
    residual_rate_pct: 10,
    salvage_value: 6_800_000,
    depreciable_base: 61_200_000,
    monthly_depreciation: 1_020_000,
    annual_depreciation: 12_240_000,
    accumulated_depreciation: 54_400_000,
    net_book_value: 13_600_000,
    carrying_rate_pct: 20.0,
    status: 'IMPAIRED',
    is_capitalized: true,
    ledger_code: '1210-HR',
    insurance_policy: 'PLA-482910',
    insurance_carrier: 'Leadway Assurance',
    rfid_tag: 'RFID-TY-000009',
    image_url: 'https://images.unsplash.com/photo-1570125909232-eb263c188f7e?auto=format&fit=crop&w=600&q=80',
    health_score: 45,
    created_at: '2020-01-18T09:00:00Z',
    updated_at: '2025-02-12T15:00:00Z',
  },
  {
    id: 'ast-010',
    tag: 'AST-000010',
    name: 'Atlas Copco Air Compressor (Industrial Rotary)',
    spec: 'GA 75 VSD Industrial Rotary Screw • Variable Speed',
    description: 'High-pressure pneumatic air supply compressor for engineering fabrication workshops.',
    category_id: 'CAT-01',
    category_name: 'Plant & Machinery',
    category_code: 'P&M',
    manufacturer: 'Atlas Copco',
    model: 'GA 75 VSD+',
    serial_number: 'AC-GA75VSD-012',
    year_of_manufacture: 2022,
    department_id: 'DEP-04',
    department_name: 'Engineering',
    department_head: 'Engr. Musa Danjuma, FNSE',
    location_id: 'LOC-04',
    location_name: 'Warri Depot',
    sub_location: 'Fabrication Workshop 2',
    custodian_id: 'USR-05',
    custodian_name: 'Aliyu Mohammed',
    custodian_staff_id: 'AF-ENG-051',
    custodian_title: 'Lead Plant Mechanic',
    custody_handover_date: '2022-10-06',
    custody_signed_ack: true,
    vendor: 'Atlas Copco Nigeria',
    purchase_order_ref: 'PO-2022-0711',
    commercial_invoice_ref: 'INV-AC-9018',
    acquisition_date: '2022-10-04',
    capitalization_date: '2022-10-06',
    currency: 'NGN',
    cost_components: {
      base_purchase: 34_000_000,
      freight: 2_000_000,
      installation: 1_800_000,
      civil_works: 500_000,
      other_costs: 200_000,
    },
    total_acquisition_cost: 38_500_000,
    depreciation_method: 'SLM',
    useful_life_years: 8,
    useful_life_months: 96,
    residual_rate_pct: 10,
    salvage_value: 3_850_000,
    depreciable_base: 34_650_000,
    monthly_depreciation: 360_938,
    annual_depreciation: 4_331_250,
    accumulated_depreciation: 9_625_000,
    net_book_value: 28_875_000,
    carrying_rate_pct: 75.0,
    status: 'IN_MAINTENANCE',
    is_capitalized: true,
    ledger_code: '1420-ENG',
    insurance_policy: 'PLA-892102',
    insurance_carrier: 'Leadway Assurance',
    rfid_tag: 'RFID-AC-000010',
    image_url: 'https://images.unsplash.com/photo-1504917599217-d4dc5ebe6122?auto=format&fit=crop&w=600&q=80',
    health_score: 72,
    created_at: '2022-10-06T10:00:00Z',
    updated_at: '2025-03-14T08:00:00Z',
  },
  {
    id: 'ast-088',
    tag: 'AST-000088',
    name: 'Ford Ranger Double Cabin (2017)',
    spec: '2.2L TDCi 4x4 • 240,000 km Mileage',
    description: 'Retired operational support truck currently recommended for executive disposal auction.',
    category_id: 'CAT-03',
    category_name: 'Motor Vehicles & Fleet',
    category_code: 'MVF',
    manufacturer: 'Ford Motor Company',
    model: 'Ranger 2.2 XL',
    serial_number: 'FR-RNG-2017-009',
    year_of_manufacture: 2017,
    department_id: 'DEP-02',
    department_name: 'Operations',
    department_head: 'Emeka Okafor',
    location_id: 'LOC-01',
    location_name: 'Lagos HQ & Tech Hub',
    sub_location: 'Holding Staging Lot C',
    custodian_id: 'USR-01',
    custodian_name: 'Femi Lawson',
    custodian_staff_id: 'AF-LOG-014',
    custodian_title: 'Logistics Supervisor',
    custody_handover_date: '2017-04-10',
    custody_signed_ack: true,
    vendor: 'Coscharis Motors',
    purchase_order_ref: 'PO-2017-0044',
    commercial_invoice_ref: 'INV-COS-291',
    acquisition_date: '2017-04-02',
    capitalization_date: '2017-04-10',
    currency: 'NGN',
    cost_components: {
      base_purchase: 25_000_000,
      freight: 1_800_000,
      installation: 700_000,
      civil_works: 0,
      other_costs: 500_000,
    },
    total_acquisition_cost: 28_000_000,
    depreciation_method: 'SLM',
    useful_life_years: 5,
    useful_life_months: 60,
    residual_rate_pct: 7.5,
    salvage_value: 2_100_000,
    depreciable_base: 25_900_000,
    monthly_depreciation: 431_667,
    annual_depreciation: 5_180_000,
    accumulated_depreciation: 25_900_000,
    net_book_value: 2_100_000,
    carrying_rate_pct: 7.5,
    status: 'IMPAIRED',
    is_capitalized: true,
    ledger_code: '1210-OPS',
    insurance_policy: 'PLA-Expired',
    insurance_carrier: 'Leadway Assurance',
    rfid_tag: 'RFID-FR-000088',
    image_url: 'https://images.unsplash.com/photo-1533473359331-0135ef1b58bf?auto=format&fit=crop&w=600&q=80',
    health_score: 38,
    created_at: '2017-04-10T10:00:00Z',
    updated_at: '2025-03-20T11:00:00Z',
  },
  {
    id: 'ast-104',
    tag: 'AST-000104',
    name: 'HP ProLiant Gen9 Blades (x4 Server Pack)',
    spec: 'Legacy Virtualization Cluster • Retired',
    description: 'Fully amortized server cluster flagged for environmental e-waste scrap disposal under WEEE guidelines.',
    category_id: 'CAT-02',
    category_name: 'IT Infrastructure & Servers',
    category_code: 'ITE',
    manufacturer: 'Hewlett Packard Enterprise',
    model: 'ProLiant BL460c Gen9',
    serial_number: 'HPE-BL460-GEN9-PACK',
    year_of_manufacture: 2016,
    department_id: 'DEP-03',
    department_name: 'Information Technology',
    department_head: 'Funke Akindele',
    location_id: 'LOC-03',
    location_name: 'Abuja Data Center',
    sub_location: 'Decommissioned Storage Room 1',
    custodian_id: 'USR-04',
    custodian_name: 'Funke Akindele',
    custodian_staff_id: 'AF-IT-004',
    custodian_title: 'Director of Technology',
    custody_handover_date: '2016-09-12',
    custody_signed_ack: true,
    vendor: 'Resourcery Plc',
    purchase_order_ref: 'PO-2016-0312',
    commercial_invoice_ref: 'INV-RES-2016-44',
    acquisition_date: '2016-09-05',
    capitalization_date: '2016-09-12',
    currency: 'NGN',
    cost_components: {
      base_purchase: 12_500_000,
      freight: 700_000,
      installation: 500_000,
      civil_works: 0,
      other_costs: 300_000,
    },
    total_acquisition_cost: 14_000_000,
    depreciation_method: 'SLM',
    useful_life_years: 5,
    useful_life_months: 60,
    residual_rate_pct: 0,
    salvage_value: 0,
    depreciable_base: 14_000_000,
    monthly_depreciation: 233_333,
    annual_depreciation: 2_800_000,
    accumulated_depreciation: 14_000_000,
    net_book_value: 0,
    carrying_rate_pct: 0,
    status: 'DISPOSED',
    is_capitalized: true,
    ledger_code: '1310-IT',
    insurance_policy: 'De-listed',
    insurance_carrier: 'None',
    rfid_tag: 'RFID-HPE-000104',
    image_url: 'https://images.unsplash.com/photo-1544197150-b99a580bb7a8?auto=format&fit=crop&w=600&q=80',
    health_score: 15,
    created_at: '2016-09-12T10:00:00Z',
    updated_at: '2025-03-10T16:00:00Z',
  },
  {
    id: 'ast-1285',
    tag: 'AST-001285',
    name: 'Mikano Perkins 250kVA Diesel Generator',
    spec: 'Standby Power Generation • P250HE-CANOPY • Soundproof',
    description: 'Heavy duty soundproof containerized diesel generator set with automatic transfer switch (ATS), Leroy Somer alternator, and deepsea digital control module.',
    category_id: 'CAT-01',
    category_name: 'Plant & Machinery',
    category_code: 'P&M-01',
    manufacturer: 'Perkins / Mikano International',
    model: 'P250HE-CANOPY',
    serial_number: 'SN-PERK-250-88319',
    year_of_manufacture: 2025,
    operating_hours: 48,
    voltage: '415V / 50Hz',
    department_id: 'DEP-02',
    department_name: 'Operations & Infrastructure',
    department_head: 'Emeka Okafor',
    location_id: 'LOC-02',
    location_name: 'Port Harcourt Hub, Rivers State',
    sub_location: 'Power House Yard B, Trans-Amadi',
    coordinates: '4.8156° N, 7.0498° E',
    custodian_id: 'USR-03',
    custodian_name: 'Engr. Ifeanyi Okeke',
    custodian_staff_id: 'EMP-0482',
    custodian_title: 'Senior Plant Manager',
    custody_handover_date: '2025-03-20',
    custody_signed_ack: true,
    vendor: 'Mikano International Limited',
    purchase_order_ref: 'PO-2025-0182',
    commercial_invoice_ref: 'INV-MK-2025-0419',
    acquisition_date: '2025-03-15',
    capitalization_date: '2025-03-20',
    currency: 'NGN',
    cost_components: {
      base_purchase: 38_000_000,
      freight: 2_500_000,
      installation: 1_800_000,
      civil_works: 1_200_000,
      other_costs: 500_000,
    },
    total_acquisition_cost: 44_000_000,
    depreciation_method: 'SLM',
    useful_life_years: 8,
    useful_life_months: 96,
    residual_rate_pct: 10,
    salvage_value: 4_400_000,
    depreciable_base: 39_600_000,
    monthly_depreciation: 412_500,
    annual_depreciation: 4_950_000,
    accumulated_depreciation: 0,
    net_book_value: 44_000_000,
    carrying_rate_pct: 100.0,
    status: 'ACTIVE',
    is_capitalized: true,
    ledger_code: '1500-01',
    insurance_policy: 'PLA-2025-9912',
    insurance_carrier: 'Leadway Assurance',
    rfid_tag: 'RFID-8849-01285',
    image_url: 'https://lh3.googleusercontent.com/aida-public/AB6AXuARkC1Wlvx9Ay6CnusCTKpVnMoikv2jHnwXTymqXs2qBxbMMAKFQTjdlQ1IHnNoHlbW6x2-rN60RT8qVazfUhoc2laoSuBH5TLHyMK9md4u9tBpcm5P_HMql97FKiWYTWmRpNjySGxI9bQ_-ZY3slWJoM12u7tNA2kZ-sO6juTnycIk8Z2kq5LrtlVrtXurYIFIZxHiumYNXX6dihJkhD5sh-MahSGaVdMYezsQjAkud1-_jk7EqCqhsQ',
    health_score: 100,
    created_at: '2025-03-20T12:00:00Z',
    updated_at: '2025-03-20T12:00:00Z',
  },
];

const DEFAULT_TRANSFERS: Transfer[] = [
  {
    id: 'trf-01',
    transfer_no: 'TRF-2025-0041',
    asset_id: 'ast-001',
    asset_tag: 'AST-000001',
    asset_name: 'Toyota Hilux 2.8 GD-6 4x4',
    from_department_id: 'DEP-01',
    from_department_name: 'Finance & Admin',
    from_location_id: 'LOC-01',
    from_location_name: 'Lagos HQ & Tech Hub',
    to_department_id: 'DEP-02',
    to_department_name: 'Operations',
    to_location_id: 'LOC-02',
    to_location_name: 'Port Harcourt Hub',
    requested_by: 'Emeka Okafor',
    approved_by: 'Babajide Adeleke (CFO)',
    transfer_date: '2025-03-22',
    reason: 'Operational redeployment for deepwater terminal support logistics.',
    notes: 'Waybill signed and counter-inspected by Port Harcourt depot gatekeeper.',
    status: 'COMPLETED',
    waybill_no: 'WB-PHC-2025-019',
    created_at: '2025-03-20T10:00:00Z',
  },
  {
    id: 'trf-02',
    transfer_no: 'TRF-2025-0042',
    asset_id: 'ast-007',
    asset_tag: 'AST-000007',
    asset_name: 'Komatsu WA380 Wheel Loader',
    from_department_id: 'DEP-04',
    from_department_name: 'Engineering',
    from_location_id: 'LOC-04',
    from_location_name: 'Warri Depot',
    to_department_id: 'DEP-02',
    to_department_name: 'Operations',
    to_location_id: 'LOC-02',
    to_location_name: 'Port Harcourt Hub',
    requested_by: 'Ibrahim Yusuf',
    approved_by: 'Babajide Adeleke',
    transfer_date: '2025-03-24',
    reason: 'Port Harcourt wharf expansion civil earthworks requirements.',
    notes: 'In-transit via heavy lowbed trailer. GPS telematics monitored.',
    status: 'IN_TRANSIT',
    waybill_no: 'WB-WAR-2025-084',
    created_at: '2025-03-24T08:00:00Z',
  },
  {
    id: 'trf-03',
    transfer_no: 'TRF-2025-0043',
    asset_id: 'ast-003',
    asset_tag: 'AST-000003',
    asset_name: 'Dell PowerEdge R750 Server',
    from_department_id: 'DEP-03',
    from_department_name: 'Information Technology',
    from_location_id: 'LOC-01',
    from_location_name: 'Lagos HQ & Tech Hub',
    to_department_id: 'DEP-03',
    to_department_name: 'Information Technology',
    to_location_id: 'LOC-03',
    to_location_name: 'Abuja Data Center',
    requested_by: 'Funke Akindele',
    approved_by: 'Babajide Adeleke',
    transfer_date: '2025-03-25',
    reason: 'Disaster recovery failover cluster provisioning in Abuja CBD.',
    notes: 'Requires temperature controlled air-conditioned transport escort.',
    status: 'PENDING',
    waybill_no: 'WB-ABJ-2025-002',
    created_at: '2025-03-24T11:00:00Z',
  },
  {
    id: 'trf-04',
    transfer_no: 'TRF-2025-0044',
    asset_id: 'ast-010',
    asset_tag: 'AST-000010',
    asset_name: 'Atlas Copco Air Compressor',
    from_department_id: 'DEP-04',
    from_department_name: 'Engineering',
    from_location_id: 'LOC-02',
    from_location_name: 'Port Harcourt Hub',
    to_department_id: 'DEP-04',
    to_department_name: 'Engineering',
    to_location_id: 'LOC-04',
    to_location_name: 'Warri Depot',
    requested_by: 'Engr. Musa Danjuma, FNSE',
    approved_by: 'Babajide Adeleke',
    transfer_date: '2025-03-26',
    reason: 'Workshop heavy pneumatic support overhaul.',
    notes: 'Awaiting transport logistics quotation clearance.',
    status: 'PENDING',
    waybill_no: 'WB-WAR-2025-091',
    created_at: '2025-03-24T14:30:00Z',
  },
];

const DEFAULT_MAINTENANCE: MaintenanceRecord[] = [
  {
    id: 'mnt-01',
    work_order_no: 'WO-2025-089',
    asset_id: 'ast-002',
    asset_tag: 'AST-000002',
    asset_name: 'Caterpillar 336 Hydraulic Excavator',
    maintenance_type: 'PREVENTIVE',
    description: '500hr Hydraulic Service & Boom Cylinder Seal Replacement',
    vendor: 'Mantrac Certified Field Services',
    start_date: '2025-03-20',
    expected_completion_date: '2025-03-30',
    budget_cost: 4_850_000,
    status: 'OVERDUE',
    overdue_days: 2,
    work_scope: 'High-pressure hydraulic seal replacement on main boom cylinders, complete hydraulic system oil flush (Cat HYDO Advanced 10), and electronic track tensioner recalibration.',
    created_at: '2025-03-18T09:00:00Z',
  },
  {
    id: 'mnt-02',
    work_order_no: 'WO-2025-092',
    asset_id: 'ast-006',
    asset_tag: 'AST-000006',
    asset_name: 'Mikano Perkins 500kVA Heavy Generator',
    maintenance_type: 'PREVENTIVE',
    description: 'B-Check Oil, Filtration & Fuel Water Separator Replacement',
    vendor: 'Mikano Energy Field Team',
    start_date: '2025-03-28',
    expected_completion_date: '2025-03-29',
    budget_cost: 1_250_000,
    status: 'SCHEDULED',
    work_scope: 'Oil filter replacement, 15W-40 lube flush, radiator coolant test, injector calibration.',
    created_at: '2025-03-22T10:00:00Z',
  },
  {
    id: 'mnt-03',
    work_order_no: 'WO-2025-095',
    asset_id: 'ast-010',
    asset_tag: 'AST-000010',
    asset_name: 'Atlas Copco Air Compressor',
    maintenance_type: 'CORRECTIVE',
    description: 'Rotary screw air-end bearing vibration inspection and oil separator swap',
    vendor: 'Atlas Copco Technical Services',
    start_date: '2025-03-21',
    expected_completion_date: '2025-03-27',
    budget_cost: 2_100_000,
    status: 'IN_PROGRESS',
    work_scope: 'Bearing replacement and thermal acoustic sensor inspection.',
    created_at: '2025-03-20T15:00:00Z',
  },
  {
    id: 'mnt-04',
    work_order_no: 'WO-2025-078',
    asset_id: 'ast-003',
    asset_tag: 'AST-000003',
    asset_name: 'Dell PowerEdge R750 Rack Server',
    maintenance_type: 'INSPECTION',
    description: 'Firmware BIOS upgrade and redundant power supply failover stress test',
    vendor: 'Dell ProSupport Plus Nigeria',
    start_date: '2025-03-10',
    completion_date: '2025-03-11',
    expected_completion_date: '2025-03-11',
    budget_cost: 450_000,
    actual_cost: 450_000,
    status: 'COMPLETED',
    work_scope: 'iDRAC9 7.00 firmware upgrade and RAID 10 battery check.',
    created_at: '2025-03-08T10:00:00Z',
  },
];

const DEFAULT_DISPOSALS: DisposalRecord[] = [
  {
    id: 'dsp-01',
    disposal_no: 'DSP-2025-0012',
    asset_id: 'ast-088',
    asset_tag: 'AST-000088',
    asset_name: 'Ford Ranger Double Cabin (2017)',
    disposal_date: '2025-04-15',
    method: 'SALE',
    disposal_proceeds: 3_500_000,
    book_value: 2_100_000,
    gain_or_loss: 1_400_000,
    reason: 'Exceeded economical maintenance threshold. Reached 240,000 km.',
    approved_by: 'CFO Review Pending',
    status: 'PENDING_REVIEW',
    recommendation: 'Public corporate sealed-bid auction sale',
    created_at: '2025-03-15T12:00:00Z',
  },
  {
    id: 'dsp-02',
    disposal_no: 'DSP-2025-0013',
    asset_id: 'ast-104',
    asset_tag: 'AST-000104',
    asset_name: 'HP ProLiant Gen9 Blades (x4 Server Pack)',
    disposal_date: '2025-04-10',
    method: 'SCRAP',
    disposal_proceeds: 150_000,
    book_value: 0,
    gain_or_loss: 150_000,
    reason: 'Completely written-down legacy blade hardware. Incompatible with modern hypervisors.',
    approved_by: 'IT Director (Funke Akindele)',
    status: 'PENDING_REVIEW',
    recommendation: 'Certified E-Waste Scrap through NESREA approved recycler',
    created_at: '2025-03-16T14:00:00Z',
  },
  {
    id: 'dsp-03',
    disposal_no: 'DSP-2024-0048',
    asset_id: 'ast-legacy-01',
    asset_tag: 'AST-000052',
    asset_name: 'Toyota Prado TXL (2015)',
    disposal_date: '2024-11-20',
    method: 'SALE',
    disposal_proceeds: 8_200_000,
    book_value: 5_500_000,
    gain_or_loss: 2_700_000,
    reason: 'Executive fleet retirement cycle completion.',
    approved_by: 'Babajide Adeleke',
    status: 'COMPLETED',
    recommendation: 'Sold to internal staff highest bidder',
    buyer_or_beneficiary: 'Alhaji Sani Bello (Verified Purchaser)',
    created_at: '2024-11-10T10:00:00Z',
  },
];

const DEFAULT_AUDIT_LOGS: AuditLogEntry[] = [
  {
    id: 'aud-01',
    timestamp: '2025-03-24 14:32:08 WAT',
    user_name: 'Babajide Adeleke',
    user_role: 'Head of Asset Accounting & Treasury',
    action: 'TRANSFER',
    entity: 'TRANSFER',
    entity_id: 'trf-02',
    entity_tag: 'AST-000007',
    description: 'Approved Inter-Facility Transfer TRF-2025-0042 (Komatsu WA380 Loader) from Warri Depot to Port Harcourt Hub.',
    previous_value: 'Warri Depot (Status: Pending Approval)',
    new_value: 'Port Harcourt Hub (Status: IN_TRANSIT)',
    ip_address: '105.112.48.91 (Lagos, NG)',
  },
  {
    id: 'aud-02',
    timestamp: '2025-03-24 10:15:22 WAT',
    user_name: 'Engr. Musa Danjuma, FNSE',
    user_role: 'Head of Engineering',
    action: 'MAINTENANCE',
    entity: 'MAINTENANCE',
    entity_id: 'mnt-01',
    entity_tag: 'AST-000002',
    description: 'Updated maintenance work order WO-2025-089 for Caterpillar 336 Excavator. Revised expected completion to March 30, 2025.',
    previous_value: 'Est Completion: 2025-03-28',
    new_value: 'Est Completion: 2025-03-30 (Pending OEM seal delivery)',
    ip_address: '197.210.65.12 (Warri, NG)',
  },
  {
    id: 'aud-03',
    timestamp: '2025-03-20 12:00:15 WAT',
    user_name: 'Babajide Adeleke',
    user_role: 'Head of Asset Accounting & Treasury',
    action: 'CAPITALIZE',
    entity: 'ASSET',
    entity_id: 'ast-1285',
    entity_tag: 'AST-001285',
    description: 'Capitalized Mikano Perkins 250kVA Diesel Generator under IAS 16. Recognized ₦44,000,000 at Trans-Amadi Hub.',
    previous_value: 'Work-in-Progress (Capex)',
    new_value: 'Capitalized Fixed Asset Ledger (1500-01)',
    ip_address: '105.112.48.91 (Lagos, NG)',
  },
  {
    id: 'aud-04',
    timestamp: '2025-03-18 16:40:02 WAT',
    user_name: 'Funke Akindele',
    user_role: 'Director of Technology',
    action: 'TRANSFER',
    entity: 'TRANSFER',
    entity_id: 'trf-03',
    entity_tag: 'AST-000003',
    description: 'Initiated Transfer Request TRF-2025-0043 for Dell PowerEdge R750 to Abuja Data Center DR site.',
    previous_value: 'Location: Lagos HQ',
    new_value: 'Location: Abuja Data Center (Requested)',
    ip_address: '102.164.22.4 (Abuja, NG)',
  },
  {
    id: 'aud-05',
    timestamp: '2025-03-15 12:10:48 WAT',
    user_name: 'Femi Lawson',
    user_role: 'Logistics Supervisor',
    action: 'DISPOSE',
    entity: 'DISPOSAL',
    entity_id: 'dsp-01',
    entity_tag: 'AST-000088',
    description: 'Submitted disposal recommendation for Ford Ranger AST-000088 via sealed auction. Carrying NBV ₦2,100,000.',
    previous_value: 'Status: Impaired Active',
    new_value: 'Status: Pending CFO Disposal Review',
    ip_address: '105.112.48.91 (Lagos, NG)',
  },
];

const DEFAULT_SETTINGS: SystemSettings = {
  asset_tag_prefix: 'AST-',
  capitalization_threshold: 500_000,
  default_depreciation_method: 'SLM',
  default_residual_rate_pct: 10,
  fiscal_year_start: 'January 1',
  currency: 'NGN',
  currency_symbol: '₦',
  company_name: 'AssetFlow Enterprise Systems Ltd',
  audit_firm: 'PwC Nigeria (PricewaterhouseCoopers)',
  accounting_standard: 'IAS 16 / IFRS Certified Institutional Ledger',
  backend_api_url: 'https://api.assetflow.ng/api/v1',
  use_mock_api: true,
};

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
