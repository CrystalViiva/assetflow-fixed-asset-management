import { ApiError } from './apiError';
import { uuidPattern } from './assetDtos';
import { minorUnits, normalizeMoney, sumMoney } from './money';

export interface AcquisitionForm {
  tag: string; name: string; description: string; categoryId: string; departmentId: string; locationId: string;
  manufacturer: string; model: string; serialNumber: string;
  acquisitionDate: string; capitalizationDate: string; availableForUseDate: string;
  usefulLifeMonths: string; residualValue: string; depreciationMethod: string;
  purchase: string; freight: string; installation: string; civil: string; other: string;
  vendor: string; invoice: string; reference: string; notes: string;
}
export const emptyAcquisitionForm: AcquisitionForm = {
  tag: '', name: '', description: '', categoryId: '', departmentId: '', locationId: '', manufacturer: '', model: '', serialNumber: '',
  acquisitionDate: '', capitalizationDate: '', availableForUseDate: '', usefulLifeMonths: '', residualValue: '0.00', depreciationMethod: 'SLM',
  purchase: '', freight: '', installation: '', civil: '', other: '', vendor: '', invoice: '', reference: '', notes: '',
};
export interface CreateAssetDto {
  asset_tag: string; name: string; description: string; category_id: string; department_id: string | null; location_id: string | null;
  manufacturer: string; model_number: string; serial_number: string; acquisition_date: string; available_for_use_date: string | null;
  purchase_cost: string; residual_value: string; useful_life_months: number; depreciation_method: 'SLM';
}
export interface CreateAcquisitionDto {
  asset_id: string; vendor_name: string; invoice_number: string; reference: string; notes: string;
  acquisition_date: string; capitalization_date: string | null; purchase_price: string; freight_cost: string;
  installation_cost: string; civil_works_cost: string; other_capitalizable_cost: string;
}
export function validDate(value: string): boolean {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value) || value.startsWith('0000')) return false;
  const date = new Date(`${value}T00:00:00Z`);
  return Number.isFinite(date.getTime()) && date.toISOString().slice(0, 10) === value;
}
export function normalizedCosts(form: AcquisitionForm) {
  return { purchase: normalizeMoney(form.purchase), freight: normalizeMoney(form.freight, true),
    installation: normalizeMoney(form.installation, true), civil: normalizeMoney(form.civil, true), other: normalizeMoney(form.other, true) };
}
export function validateAcquisitionForm(form: AcquisitionForm): Record<string, string[]> {
  const errors: Record<string, string[]> = {};
  const required = (key: keyof AcquisitionForm, label: string) => { if (!form[key].trim()) errors[key] = [`${label} is required.`]; };
  required('name', 'Asset name'); required('tag', 'Asset tag');
  if (!/^[A-Za-z0-9_-]{1,64}$/.test(form.tag.trim())) errors.tag = ['Use 1–64 letters, digits, underscores or hyphens for the asset tag.'];
  if (!uuidPattern.test(form.categoryId)) errors.categoryId = ['Choose a category.'];
  for (const key of ['departmentId', 'locationId'] as const) if (form[key] && !uuidPattern.test(form[key])) errors[key] = ['Choose a valid reference.'];
  if (!validDate(form.acquisitionDate)) errors.acquisitionDate = ['Enter a valid date.'];
  if (form.capitalizationDate && !validDate(form.capitalizationDate)) errors.capitalizationDate = ['Enter a valid date.'];
  if (!errors.acquisitionDate && form.capitalizationDate && !errors.capitalizationDate && form.capitalizationDate < form.acquisitionDate) errors.capitalizationDate = ['Capitalization cannot precede acquisition.'];
  if (form.availableForUseDate && (!validDate(form.availableForUseDate) || !form.capitalizationDate || form.availableForUseDate < form.capitalizationDate)) errors.availableForUseDate = ['Enter capitalization first and choose an available-for-use date on or after it.'];
  if (!/^\d+$/.test(form.usefulLifeMonths) || BigInt(form.usefulLifeMonths) < 1n || BigInt(form.usefulLifeMonths) > 2147483647n) errors.usefulLifeMonths = ['Enter a positive whole number of months within the supported range.'];
  if (form.depreciationMethod !== 'SLM') errors.depreciationMethod = ['Straight Line is the supported method.'];
  for (const key of ['purchase', 'freight', 'installation', 'civil', 'other', 'residualValue'] as const) {
    try { normalizeMoney(form[key], !['purchase', 'residualValue'].includes(key)); }
    catch (error) { errors[key] = [error instanceof ApiError ? error.message : 'Invalid amount.']; }
  }
  if (!['purchase', 'freight', 'installation', 'civil', 'other'].some(key => errors[key])) {
    try {
      const total = sumMoney(Object.values(normalizedCosts(form)));
      if (minorUnits(total) <= 0n) errors.purchase = ['Total capitalizable cost must be greater than zero.'];
      if (!errors.residualValue && minorUnits(form.residualValue) > minorUnits(total)) errors.residualValue = ['Residual value cannot exceed capitalizable cost.'];
    } catch (error) { errors.purchase = [error instanceof ApiError ? error.message : 'Invalid total.']; }
  }
  return errors;
}
function validated(form: AcquisitionForm) {
  const errors = validateAcquisitionForm(form);
  if (Object.keys(errors).length) throw new ApiError('validation', 'Please correct the highlighted fields.', 400, errors);
}
export function createAssetDto(form: AcquisitionForm): CreateAssetDto {
  validated(form);
  return { asset_tag: form.tag.trim(), name: form.name.trim(), description: form.description,
    category_id: form.categoryId, department_id: form.departmentId || null, location_id: form.locationId || null,
    manufacturer: form.manufacturer, model_number: form.model, serial_number: form.serialNumber,
    acquisition_date: form.acquisitionDate, available_for_use_date: form.availableForUseDate || null,
    purchase_cost: sumMoney(Object.values(normalizedCosts(form))), residual_value: normalizeMoney(form.residualValue),
    useful_life_months: Number(form.usefulLifeMonths), depreciation_method: 'SLM' };
}
export function createAcquisitionDto(form: AcquisitionForm, assetId: string): CreateAcquisitionDto {
  validated(form);
  if (!uuidPattern.test(assetId)) throw new ApiError('validation', 'A valid asset is required.');
  const costs = normalizedCosts(form);
  return { asset_id: assetId, vendor_name: form.vendor, invoice_number: form.invoice, reference: form.reference, notes: form.notes,
    acquisition_date: form.acquisitionDate, capitalization_date: form.capitalizationDate || null,
    purchase_price: costs.purchase, freight_cost: costs.freight, installation_cost: costs.installation,
    civil_works_cost: costs.civil, other_capitalizable_cost: costs.other };
}
const fieldMap: Record<string, string> = {
  asset_tag: 'tag', category: 'categoryId', category_id: 'categoryId', department: 'departmentId', department_id: 'departmentId', location: 'locationId', location_id: 'locationId',
  model_number: 'model', serial_number: 'serialNumber', acquisition_date: 'acquisitionDate', capitalization_date: 'capitalizationDate', available_for_use_date: 'availableForUseDate',
  useful_life_months: 'usefulLifeMonths', residual_value: 'residualValue', depreciation_method: 'depreciationMethod', purchase_cost: 'purchase', purchase_price: 'purchase',
  freight_cost: 'freight', installation_cost: 'installation', civil_works_cost: 'civil', other_capitalizable_cost: 'other', vendor_name: 'vendor', invoice_number: 'invoice',
};
export function formErrors(error: unknown): Record<string, string[]> {
  if (!(error instanceof ApiError)) return {};
  return Object.fromEntries(Object.entries(error.fields).map(([field, messages]) => [fieldMap[field] || field, messages]));
}
