// Run only from f1-smoke.py, which injects temporary credentials and an isolated API URL.
import assert from 'node:assert/strict';
import { ApiClient } from '../src/services/apiClient';
import { ApiError } from '../src/services/apiError';
import { Session } from '../src/services/session';
import { AcquisitionWorkflow } from '../src/services/acquisitionWorkflow';
import { emptyAcquisitionForm } from '../src/services/acquisitionForm';
import { DjangoAssetRepository, defaultAssetQuery } from '../src/services/djangoApiBridge';

let stage = 'session setup';
async function run() {
  const storage = new Map<string, string>();
  const api = new ApiClient(process.env.F1_SMOKE_URL!);
  const session = new Session(api, {
    getItem:key => storage.get(key) ?? null,
    setItem:(key, value) => { storage.set(key, value); },
    removeItem:key => { storage.delete(key); },
  }, () => {});
  await session.initialize();
  stage = 'JWT login and role';
  await session.login(process.env.F1_SMOKE_EMAIL!, process.env.F1_SMOKE_PASSWORD!);
  assert.equal(session.getSnapshot().user?.role, 'ASSET_MANAGER');
  const repository = new DjangoAssetRepository(api);
  stage = 'tenant reference lists';
  const [categories, departments, locations] = await Promise.all([
    repository.getCategories(), repository.getReferences('departments'), repository.getReferences('locations'),
  ]);
  assert.equal(categories.length, 1); assert.equal(departments.length, 1); assert.equal(locations.length, 1);
  assert.match(categories[0].organizationId, /^[0-9a-f-]{36}$/i);
  stage = 'real asset, acquisition and capitalization writes';
  const workflow = new AcquisitionWorkflow(repository, () => session.getSnapshot().user !== null, async () => {});
  const form = { ...emptyAcquisitionForm, tag:'F2-SMOKE-001', name:'Integration pump', description:'Disposable F2 API smoke',
    categoryId:categories[0].id, departmentId:departments[0].id, locationId:locations[0].id,
    acquisitionDate:'2026-01-01', capitalizationDate:'2026-01-02', usefulLifeMonths:'36', residualValue:'100.00',
    purchase:'1000.01', freight:'0.99' };
  await workflow.create(form);
  assert.equal(workflow.getSnapshot().phase, 'asset-created');
  const assetId = workflow.getSnapshot().asset!.id;
  assert.equal(workflow.getSnapshot().asset!.status, 'DRAFT');
  await workflow.record(form);
  assert.equal(workflow.getSnapshot().acquisition!.totalCost, '1001.00');
  await workflow.capitalize();
  assert.equal(workflow.getSnapshot().phase, 'capitalized');
  assert.equal(workflow.getSnapshot().asset!.id, assetId);
  assert.equal(workflow.getSnapshot().asset!.status, 'ACTIVE');
  assert.equal(workflow.getSnapshot().asset!.purchaseCost, '1001.00');
  assert.equal(workflow.getSnapshot().asset!.capitalizationDate, '2026-01-02');
  assert.equal(workflow.getSnapshot().asset!.availableForUseDate, '2026-01-02');
  assert.equal(workflow.getSnapshot().asset!.residualValue, '100.00');
  assert.equal(workflow.getSnapshot().asset!.usefulLifeMonths, 36);
  assert.equal(workflow.getSnapshot().asset!.depreciationMethod, 'SLM');
  await workflow.capitalize(); // Completed UI state cannot repeat the POST.
  assert.equal(workflow.getSnapshot().acquisition!.status, 'CAPITALIZED');
  stage = 'real register and detail reflect capitalized state';
  const page = await repository.getAssets({ ...defaultAssetQuery, search:'F2-SMOKE-001', status:'ACTIVE' });
  assert.equal(page.total, 1); assert.equal(page.data[0].id, assetId);
  const detail = await repository.getAssetById(assetId);
  const savedAcquisition = await repository.getAcquisitionForAsset(assetId);
  assert.equal(detail.purchaseCost, '1001.00'); assert.equal(savedAcquisition?.totalCost, '1001.00');
  assert.equal(detail.bookValue, '1001.00');
  assert.equal(detail.department?.id, departments[0].id); assert.equal(detail.location?.id, locations[0].id);
  assert.equal(savedAcquisition?.costs.purchase, '1000.01'); assert.equal(savedAcquisition?.costs.freight, '0.99');
  stage = 'backend duplicate and repeat protection';
  await assert.rejects(repository.createAcquisition({
    asset_id:assetId, vendor_name:'', invoice_number:'', reference:'', notes:'', acquisition_date:'2026-01-01', capitalization_date:'2026-01-02',
    purchase_price:'1000.01', freight_cost:'0.99', installation_cost:'0.00', civil_works_cost:'0.00', other_capitalizable_cost:'0.00',
  }), (error: unknown) => error instanceof ApiError && ['validation','conflict'].includes(error.kind));
  await assert.rejects(repository.capitalizeAcquisition(savedAcquisition!.id), (error: unknown) => error instanceof ApiError);
  stage = 'refresh and logout';
  await session.refresh(); session.logout(); assert.equal(storage.size, 0); assert.equal(session.getSnapshot().user, null);
  console.log('PASS: real JWT, categories/departments/locations, asset create, acquisition buildup, backend capitalization, register/detail refetch, duplicate/repeat protection, Decimal precision, refresh and logout.');
}
void run().catch(error => {
  console.log(`SMOKE: failed at ${stage}; ${error instanceof ApiError ? `${error.kind}, HTTP ${error.status ?? 'none'}` : 'assertion or runtime failure'}`);
  process.exitCode = 1;
});
