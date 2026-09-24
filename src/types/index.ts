/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 * AssetFlow Fixed Asset Management System - Enterprise Domain Types
 * Designed to cleanly map 1:1 with future Django REST Framework models & serializers.
 */

export type AssetStatus = 'ACTIVE' | 'IN_MAINTENANCE' | 'TRANSFERRED' | 'IMPAIRED' | 'DISPOSED';
export type DepreciationMethod = 'SLM' | 'RBM' | 'UOP' | 'SYD';
export type MaintenanceType = 'PREVENTIVE' | 'CORRECTIVE' | 'INSPECTION' | 'EMERGENCY';
export type MaintenanceStatus = 'SCHEDULED' | 'IN_PROGRESS' | 'COMPLETED' | 'OVERDUE';
export type TransferStatus = 'PENDING' | 'APPROVED' | 'IN_TRANSIT' | 'COMPLETED' | 'REJECTED';
export type DisposalMethod = 'SALE' | 'SCRAP' | 'DONATION' | 'WRITE_OFF' | 'TRANSFER_OUT';
export type DisposalStatus = 'PENDING_REVIEW' | 'APPROVED' | 'COMPLETED' | 'REJECTED';
export type UserRole = 'ADMIN' | 'ASSET_MANAGER' | 'ACCOUNTANT' | 'DEPT_MANAGER' | 'EMPLOYEE';
export type AuditAction = 'CREATE' | 'UPDATE' | 'TRANSFER' | 'MAINTENANCE' | 'DEPRECIATE' | 'DISPOSE' | 'CAPITALIZE';
export type AuditEntity = 'ASSET' | 'CATEGORY' | 'TRANSFER' | 'MAINTENANCE' | 'DISPOSAL' | 'USER' | 'SETTING';

export interface CostComponents {
  base_purchase: number;
  freight: number;
  installation: number;
  civil_works: number;
  other_costs: number;
}

export interface AttachedDocument {
  id: string;
  name: string;
  type: 'PDF' | 'DOCX' | 'IMAGE';
  size: string;
  date: string;
  description: string;
  url?: string;
  verified?: boolean;
}

export interface Asset {
  id: string;
  tag: string;
  name: string;
  spec: string;
  description: string;
  category_id: string;
  category_name: string;
  category_code: string;
  manufacturer: string;
  model: string;
  serial_number: string;
  engine_model?: string;
  year_of_manufacture?: number;
  net_power?: string;
  operating_weight?: string;
  operating_hours?: number;
  voltage?: string;
  department_id: string;
  department_name: string;
  department_head: string;
  location_id: string;
  location_name: string;
  sub_location: string;
  coordinates?: string;
  custodian_id: string;
  custodian_name: string;
  custodian_staff_id: string;
  custodian_title: string;
  custodian_avatar?: string;
  custody_handover_date: string;
  custody_signed_ack: boolean;
  vendor: string;
  vendor_branch?: string;
  purchase_order_ref: string;
  commercial_invoice_ref: string;
  acquisition_date: string;
  capitalization_date: string;
  currency: 'NGN' | 'USD';
  cost_components: CostComponents;
  total_acquisition_cost: number;
  depreciation_method: DepreciationMethod;
  useful_life_years: number;
  useful_life_months: number;
  residual_rate_pct: number;
  salvage_value: number;
  depreciable_base: number;
  monthly_depreciation: number;
  annual_depreciation: number;
  accumulated_depreciation: number;
  net_book_value: number;
  carrying_rate_pct: number;
  status: AssetStatus;
  is_capitalized: boolean;
  ledger_code: string;
  insurance_policy: string;
  insurance_carrier: string;
  rfid_tag: string;
  image_url: string;
  health_score: number;
  next_inspection_hours?: number;
  created_at: string;
  updated_at: string;
  documents?: AttachedDocument[];
}

export interface AssetCategory {
  id: string;
  code: string;
  name: string;
  description: string;
  standard_useful_life_months: number;
  default_depreciation_method: DepreciationMethod;
  default_residual_rate_pct: number;
  asset_count: number;
  total_cost: number;
  total_nbv: number;
}

export interface Department {
  id: string;
  code: string;
  name: string;
  head_name: string;
  head_staff_id: string;
  email: string;
  asset_count: number;
  total_cost: number;
  total_nbv: number;
}

export interface LocationHub {
  id: string;
  code: string;
  name: string;
  city: string;
  state: string;
  address: string;
  coordinates: string;
  hub_manager: string;
  asset_count: number;
  total_cost: number;
  total_nbv: number;
  percentage_of_total: number;
}

export interface CustodyAssignment {
  id: string;
  asset_id: string;
  asset_tag: string;
  asset_name: string;
  custodian_id: string;
  custodian_name: string;
  custodian_staff_id: string;
  custodian_title: string;
  department_name: string;
  location_name: string;
  assigned_date: string;
  signed_ack: boolean;
  ack_date?: string;
  notes?: string;
}

export interface Transfer {
  id: string;
  transfer_no: string;
  asset_id: string;
  asset_tag: string;
  asset_name: string;
  from_department_id: string;
  from_department_name: string;
  from_location_id: string;
  from_location_name: string;
  to_department_id: string;
  to_department_name: string;
  to_location_id: string;
  to_location_name: string;
  requested_by: string;
  approved_by: string;
  transfer_date: string;
  reason: string;
  notes: string;
  status: TransferStatus;
  waybill_no: string;
  created_at: string;
}

export interface MaintenanceRecord {
  id: string;
  work_order_no: string;
  asset_id: string;
  asset_tag: string;
  asset_name: string;
  maintenance_type: MaintenanceType;
  description: string;
  vendor: string;
  start_date: string;
  completion_date?: string;
  expected_completion_date: string;
  budget_cost: number;
  actual_cost?: number;
  status: MaintenanceStatus;
  notes?: string;
  work_scope?: string;
  overdue_days?: number;
  created_at: string;
}

export interface DisposalRecord {
  id: string;
  disposal_no: string;
  asset_id: string;
  asset_tag: string;
  asset_name: string;
  disposal_date: string;
  method: DisposalMethod;
  disposal_proceeds: number;
  book_value: number;
  gain_or_loss: number;
  reason: string;
  approved_by: string;
  status: DisposalStatus;
  recommendation: string;
  buyer_or_beneficiary?: string;
  notes?: string;
  created_at: string;
}

export interface AuditLogEntry {
  id: string;
  timestamp: string;
  user_name: string;
  user_role: string;
  action: AuditAction;
  entity: AuditEntity;
  entity_id: string;
  entity_tag?: string;
  description: string;
  previous_value?: string;
  new_value?: string;
  ip_address?: string;
}

export interface DepreciationScheduleItem {
  period_index: number;
  year: number;
  month: number;
  period_label: string;
  opening_book_value: number;
  depreciation_expense: number;
  accumulated_depreciation: number;
  closing_book_value: number;
}

export interface UserProfile {
  id: string;
  staff_id: string;
  name: string;
  email: string;
  role: UserRole;
  department_name: string;
  location_name: string;
  avatar_url: string;
  is_active: boolean;
}

export interface DashboardMetrics {
  total_assets: number;
  active_assets: number;
  maintenance_assets: number;
  transferred_assets: number;
  impaired_assets: number;
  disposed_assets: number;
  total_acquisition_cost: number;
  current_book_value: number;
  accumulated_depreciation: number;
  carrying_retention_pct: number;
  monthly_run_rate: number;
  scheduled_posting_date: string;
  category_breakdown: Array<{
    category_id: string;
    category_name: string;
    total_value: number;
    unit_count: number;
    percentage: number;
    color: string;
  }>;
  hub_breakdown: Array<{
    code: string;
    name: string;
    asset_count: number;
    total_value: number;
    percentage: number;
  }>;
  monthly_trend: Array<{
    month: string;
    capitalization: number;
    depreciation: number;
    notes?: string;
    is_projected?: boolean;
  }>;
}

export interface SystemSettings {
  asset_tag_prefix: string;
  capitalization_threshold: number;
  default_depreciation_method: DepreciationMethod;
  default_residual_rate_pct: number;
  fiscal_year_start: string;
  currency: string;
  currency_symbol: string;
  company_name: string;
  audit_firm: string;
  accounting_standard: string;
  backend_api_url: string;
  use_mock_api: boolean;
}
