// Run only from f1-smoke.py against its random, disposable PostgreSQL database.
import assert from 'node:assert/strict';
import { ApiClient } from '../src/services/apiClient';
import { ApiError } from '../src/services/apiError';
import { Session } from '../src/services/session';
import { AcquisitionWorkflow } from '../src/services/acquisitionWorkflow';
import { emptyAcquisitionForm } from '../src/services/acquisitionForm';
import { DjangoAssetRepository } from '../src/services/djangoApiBridge';
import { DjangoDepreciationRepository } from '../src/services/depreciationRepository';

let stage = 'session setup';
async function run() {
  const storage = new Map<string,string>();
  const api = new ApiClient(process.env.F1_SMOKE_URL!);
  const session = new Session(api, { getItem:key => storage.get(key) ?? null, setItem:(key,value) => { storage.set(key,value); }, removeItem:key => { storage.delete(key); } }, () => {});
  await session.initialize(); stage = 'JWT login'; await session.login(process.env.F1_SMOKE_EMAIL!,process.env.F1_SMOKE_PASSWORD!);
  assert.equal(session.getSnapshot().user?.role,'ASSET_MANAGER');
  const assets = new DjangoAssetRepository(api); const depreciation = new DjangoDepreciationRepository(api);
  stage = 'tenant references and capitalization';
  const [categories,departments,locations] = await Promise.all([assets.getCategories(),assets.getReferences('departments'),assets.getReferences('locations')]);
  const form = { ...emptyAcquisitionForm,tag:'F3-SMOKE-001',name:'Disposable F3 depreciation pump',description:'Isolated depreciation integration smoke',categoryId:categories[0].id,departmentId:departments[0].id,locationId:locations[0].id,acquisitionDate:'2026-01-01',capitalizationDate:'2026-01-02',usefulLifeMonths:'36',residualValue:'100.00',purchase:'1000.01',freight:'0.99' };
  const workflow = new AcquisitionWorkflow(assets,() => session.getSnapshot().user !== null,async () => {});
  await workflow.create(form); await workflow.record(form); await workflow.capitalize();
  const assetId = workflow.getSnapshot().asset!.id;
  assert.equal(workflow.getSnapshot().asset!.availableForUseDate,'2026-01-02');
  stage = 'period, schedule, posting and authoritative refetch';
  stage = 'list and create accounting period'; assert.equal((await depreciation.getPeriods()).length,0);
  const period = await depreciation.createPeriod(2026,1); assert.equal(period.status,'OPEN');
  stage = 'create backend schedule'; const schedule = await depreciation.createSchedule(assetId); assert.equal(schedule.startDate,'2026-01-02');
  stage = 'post first period';
  const posted = await depreciation.post(assetId,period.id);
  assert.deepEqual([posted.openingBookValue,posted.depreciationAmount,posted.accumulatedDepreciation,posted.closingBookValue],['1001.00','25.03','25.03','975.97']);
  stage = 'refetch posted entry and asset';
  const [entryRows,asset] = await Promise.all([depreciation.getEntries({asset:assetId,period:period.id}),assets.getAssetById(assetId)]);
  assert.equal(entryRows.length,1); assert.equal(asset.accumulatedDepreciation,'25.03'); assert.equal(asset.bookValue,'975.97');
  stage = 'duplicate posting and closed-period behavior';
  stage = 'reject duplicate posting'; await assert.rejects(depreciation.post(assetId,period.id),(error:unknown) => error instanceof ApiError && error.kind === 'validation');
  assert.equal((await depreciation.getEntries({asset:assetId,period:period.id})).length,1);
  stage = 'close period'; const closed = await depreciation.closePeriod(period.id); assert.equal(closed.status,'CLOSED');
  await assert.rejects(depreciation.post(assetId,period.id),(error:unknown) => error instanceof ApiError && error.kind === 'validation');
  stage = 'logout'; session.logout(); assert.equal(storage.size,0); assert.equal(session.getSnapshot().user,null);
  console.log('PASS: isolated TypeScript-to-Django-to-PostgreSQL F3 workflow; January available-for-use start, exact Decimal posting, asset balance refresh, duplicate rejection, close behavior, and logout.');
}
void run().catch(error => {
  console.log(`SMOKE: failed at ${stage}; ${error instanceof ApiError ? `${error.kind}, HTTP ${error.status ?? 'none'}` : 'assertion or runtime failure'}`);
  process.exitCode = 1;
});
