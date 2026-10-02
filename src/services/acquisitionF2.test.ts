import { describe, expect, it, vi } from 'vitest';
import { assetDto, deferred } from '../test/fixtures';
import { AssetRecord, mapAssetDto, mapAcquisitionDto, parseCategoryDto, parseReferenceDto, mapCategoryDto, mapReferenceDto } from './assetDtos';
import { AcquisitionForm, createAcquisitionDto, createAssetDto, emptyAcquisitionForm, validateAcquisitionForm } from './acquisitionForm';
import { AcquisitionWorkflow } from './acquisitionWorkflow';
import { minorUnits, normalizeMoney, sumMoney } from './money';
import { ApiClient } from './apiClient';
import { DjangoAssetRepository } from './djangoApiBridge';
import { json } from '../test/fixtures';

const id = assetDto.id;
const form: AcquisitionForm = { ...emptyAcquisitionForm, tag:'F2-001', name:'Pump', categoryId:assetDto.category_id,
  acquisitionDate:'2026-01-01', capitalizationDate:'2026-01-02', usefulLifeMonths:'120', purchase:'1000.01',
  freight:'0.99', residualValue:'100.00' };
const asset = mapAssetDto({ ...assetDto, status:'DRAFT', asset_tag:'F2-001', name:'Pump', purchase_cost:'1001.00', residual_value:'100.00', useful_life_months:120 });
const acquisition = mapAcquisitionDto({ id:'fbf15e95-1fac-4ee9-9851-8f4aef45be48', organization_id:assetDto.organization_id,
  asset_id:id, asset_tag:'F2-001', asset_name:'Pump', vendor_name:'', invoice_number:'', acquisition_date:'2026-01-01', capitalization_date:'2026-01-02',
  currency:'NGN', purchase_price:'1000.01', freight_cost:'0.99', installation_cost:'0.00', civil_works_cost:'0.00', other_capitalizable_cost:'0.00',
  total_cost:'1001.00', reference:'', notes:'', status:'DRAFT', created_at:'2026-01-02T00:00:00Z', updated_at:'2026-01-02T00:00:00Z' });

describe('F2 reference, DTO and exact money boundaries', () => {
  it('maps actual tenant reference and category contract including inactive state and accounting defaults', () => {
    const reference = { id:assetDto.category_id, organization_id:assetDto.organization_id, name:'Equipment', code:'EQ', is_active:false };
    expect(mapReferenceDto(parseReferenceDto(reference))).toMatchObject({ id:reference.id, organizationId:reference.organization_id, active:false });
    expect(mapCategoryDto(parseCategoryDto({ ...reference, organization_name:'Org', description:'Plant', default_useful_life_months:120,
      default_depreciation_method:'SLM', capitalization_threshold:'2500.00', created_at:'now', updated_at:'now' })))
      .toMatchObject({ usefulLifeMonths:120, depreciationMethod:'SLM', capitalizationThreshold:'2500.00' });
    expect(() => parseReferenceDto({ ...reference, id:'not-a-uuid' })).toThrow();
  });
  it('loads every reference page and passes cancellation while preserving reference UUIDs', async () => {
    const rows = Array.from({ length:100 }, (_, index) => ({ id:`ca291303-1e7a-4bc1-a563-${String(index + 1).padStart(12,'0')}`,
      organization_id:assetDto.organization_id,name:`Location ${index}`,code:`L${index}`,is_active:true }));
    const first = { count:101,next:'/locations/?page=2',previous:null,results:rows };
    const second = { count:101,next:null,previous:'/locations/?page=1',results:[{ id:'a2ea38f0-989c-462f-947f-501c21ef6b55',organization_id:assetDto.organization_id,name:'Last',code:'LAST',is_active:true }] };
    const fetcher = vi.fn<typeof fetch>().mockResolvedValueOnce(json(first)).mockResolvedValueOnce(json(second));
    const api = new ApiClient('/api/v1',fetcher);
    api.session = { accessToken:'test-access',generation:1,refresh:async () => {},invalidate:() => {} };
    const repository = new DjangoAssetRepository(api);
    const result = await repository.getReferences('locations');
    expect(result).toHaveLength(101); expect(result[0].id).toBe(first.results[0].id); expect(result[100].id).toBe(second.results[0].id);
    expect(fetcher.mock.calls.map(([url]) => String(url))).toEqual(['/api/v1/locations/?page=1&page_size=100','/api/v1/locations/?page=2&page_size=100']);
  });
  it('normalizes decimal strings exactly, including zero, cents and large values', () => {
    expect(normalizeMoney('0')).toBe('0.00'); expect(normalizeMoney('0.01')).toBe('0.01');
    expect(normalizeMoney('1000.5')).toBe('1000.50');
    expect(normalizeMoney('999999999999999999.99')).toBe('999999999999999999.99');
    expect(sumMoney(['1000.01','0.99','0.00'])).toBe('1001.00');
    expect(minorUnits(sumMoney(['999999999999999999.98','0.01']))).toBe(99999999999999999999n);
  });
  it.each(['-1','1e3','Infinity','1,000','NaN','1.234'])('rejects ambiguous or unsupported money %s', value => {
    expect(() => normalizeMoney(value)).toThrow();
  });
  it('builds explicit API request DTOs and preserves backend Decimal representations', () => {
    expect(createAssetDto(form)).toMatchObject({ asset_tag:'F2-001', category_id:assetDto.category_id, purchase_cost:'1001.00', residual_value:'100.00', depreciation_method:'SLM' });
    expect(createAcquisitionDto(form,id)).toMatchObject({ asset_id:id, purchase_price:'1000.01', freight_cost:'0.99', installation_cost:'0.00', capitalization_date:'2026-01-02' });
    expect(createAssetDto(form)).not.toHaveProperty('organization_id');
  });
  it('validates dates, residual relationship, useful life and unsupported methods', () => {
    expect(validateAcquisitionForm(form)).toEqual({});
    expect(validateAcquisitionForm({ ...form, capitalizationDate:'2025-12-31' })).toHaveProperty('capitalizationDate');
    expect(validateAcquisitionForm({ ...form, capitalizationDate:'', availableForUseDate:'2026-01-03' })).toHaveProperty('availableForUseDate');
    expect(validateAcquisitionForm({ ...form, acquisitionDate:'2026-02-30' })).toHaveProperty('acquisitionDate');
    expect(validateAcquisitionForm({ ...form, residualValue:'1001.01' })).toHaveProperty('residualValue');
    expect(validateAcquisitionForm({ ...form, usefulLifeMonths:'0' })).toHaveProperty('usefulLifeMonths');
    expect(validateAcquisitionForm({ ...form, depreciationMethod:'RBM' })).toHaveProperty('depreciationMethod');
    expect(validateAcquisitionForm({ ...form, capitalizationDate:'' })).not.toHaveProperty('capitalizationDate');
  });
  it('maps backend field errors to editable form fields', async () => {
    const { formErrors } = await import('./acquisitionForm');
    expect(formErrors(new (await import('./apiError')).ApiError('validation','Correct fields.',400,{ capitalization_date:['Invalid date.'], purchase_price:['Too high.'] })))
      .toEqual({ capitalizationDate:['Invalid date.'], purchase:['Too high.'] });
  });
});

describe('F2 write workflow recovery and duplicate protection', () => {
  function setup() {
    let current = true;
    const repository = {
      createAsset:vi.fn(async () => asset), getAssetByTag:vi.fn<() => Promise<AssetRecord | null>>(async () => null), getAssetById:vi.fn(async () => asset),
      getAcquisitionForAsset:vi.fn<() => Promise<typeof acquisition | null>>(async () => null), createAcquisition:vi.fn(async () => acquisition),
      updateAcquisition:vi.fn(async () => acquisition), capitalizeAcquisition:vi.fn(async () => ({ ...acquisition, status:'CAPITALIZED' as const })),
    };
    const invalidate = vi.fn(async () => {});
    const workflow = new AcquisitionWorkflow(repository, () => current, invalidate);
    return { workflow, repository, invalidate, logout:() => { current = false; } };
  }
  it('commits the real sequence, invalidates scoped data and never duplicates simultaneous submissions', async () => {
    const s = setup();
    await Promise.all([s.workflow.create(form), s.workflow.create(form)]);
    expect(s.repository.createAsset).toHaveBeenCalledTimes(1);
    await s.workflow.record(form); expect(s.repository.createAcquisition).toHaveBeenCalledTimes(1);
    await s.workflow.capitalize();
    expect(s.repository.capitalizeAcquisition).toHaveBeenCalledTimes(1);
    expect(s.workflow.getSnapshot()).toMatchObject({ phase:'capitalized', asset:{ id }, acquisition:{ status:'CAPITALIZED' } });
    expect(s.invalidate).toHaveBeenCalledTimes(3);
    await s.workflow.capitalize(); expect(s.repository.capitalizeAcquisition).toHaveBeenCalledTimes(1);
  });
  it('keeps a created asset after acquisition failure and reconciles before retry', async () => {
    const s = setup(); s.repository.createAcquisition.mockRejectedValueOnce(new Error('connection lost'));
    await s.workflow.create(form); await s.workflow.record(form);
    expect(s.workflow.getSnapshot()).toMatchObject({ phase:'asset-created', uncertain:'acquisition', asset:{ id } });
    await s.workflow.reconcile();
    expect(s.workflow.getSnapshot()).toMatchObject({ phase:'asset-created', uncertain:null });
    await s.workflow.record(form); expect(s.repository.createAcquisition).toHaveBeenCalledTimes(2);
  });
  it('adopts an existing acquisition after an ambiguous POST and does not duplicate it', async () => {
    const s = setup(); s.repository.createAcquisition.mockRejectedValueOnce(new Error('connection lost'));
    s.repository.getAcquisitionForAsset.mockResolvedValueOnce(null).mockResolvedValueOnce(acquisition);
    await s.workflow.create(form); await s.workflow.record(form);
    expect(s.workflow.getSnapshot().uncertain).toBe('acquisition');
    await s.workflow.reconcile();
    expect(s.workflow.getSnapshot()).toMatchObject({ phase:'acquisition-recorded', acquisition:{ id:acquisition.id } });
    expect(s.repository.createAcquisition).toHaveBeenCalledTimes(1);
  });
  it('requires explicit review before adopting an existing asset found during recovery', async () => {
    const s = setup(); s.repository.createAsset.mockRejectedValueOnce(new Error('connection lost'));
    s.repository.getAssetByTag.mockResolvedValue(asset);
    await s.workflow.create(form); expect(s.workflow.getSnapshot().uncertain).toBe('asset');
    await s.workflow.reconcile(); expect(s.workflow.getSnapshot().phase).toBe('review-existing');
    expect(s.workflow.getSnapshot().asset?.id).toBe(asset.id);
    expect(s.repository.createAsset).toHaveBeenCalledTimes(1);
    await s.workflow.acceptExisting(); expect(s.workflow.getSnapshot().phase).toBe('asset-created');
  });
  it('never replays an ambiguous capitalization and ignores a late write response after logout', async () => {
    const s = setup(); s.repository.capitalizeAcquisition.mockRejectedValueOnce(new Error('timeout'));
    await s.workflow.create(form); await s.workflow.record(form); await s.workflow.capitalize();
    expect(s.workflow.getSnapshot().uncertain).toBe('capitalization');
    s.repository.getAcquisitionForAsset.mockResolvedValue(acquisition);
    await s.workflow.reconcile(); expect(s.repository.capitalizeAcquisition).toHaveBeenCalledTimes(1);
    const pending = deferred<typeof asset>(); s.repository.createAsset.mockReturnValue(pending.promise);
    const before = s.workflow.getSnapshot();
    // A separate user-scoped workflow proves an in-flight result cannot mutate a newer session.
    const late = setup(); late.repository.createAsset.mockReturnValue(pending.promise);
    const request = late.workflow.create(form);
    late.logout(); pending.resolve(asset); await request;
    expect(late.workflow.getSnapshot().asset).toBeNull();
    expect(late.invalidate).not.toHaveBeenCalled();
    expect(before.phase).toBe('acquisition-recorded');
  });
});
