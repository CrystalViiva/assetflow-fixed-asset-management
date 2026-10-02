// Run through f1-smoke.py: credentials and API URL exist only in the child environment.
import assert from 'node:assert/strict';
import { ApiClient } from '../src/services/apiClient';
import { Session } from '../src/services/session';
import { DjangoAssetRepository, defaultAssetQuery } from '../src/services/djangoApiBridge';
import { ApiError } from '../src/services/apiError';

let stage = 'initialization';
async function run() {
const storage = new Map<string,string>();
const api = new ApiClient(process.env.F1_SMOKE_URL!);
const session = new Session(api, {
  getItem: key => storage.get(key) ?? null,
  setItem: (key,value) => { storage.set(key,value); },
  removeItem: key => { storage.delete(key); },
}, () => {});
await session.initialize();
stage = 'login and identity';
await session.login(process.env.F1_SMOKE_EMAIL!,process.env.F1_SMOKE_PASSWORD!);
assert.equal(session.getSnapshot().user?.role,'ASSET_MANAGER');
const repository = new DjangoAssetRepository(api);
stage = 'register pagination';
const first = await repository.getAssets({ ...defaultAssetQuery,pageSize:1 });
assert.equal(first.total,2); assert.equal(first.hasNext,true);
const second = await repository.getAssets({ ...defaultAssetQuery,pageSize:1,page:2 });
assert.equal(second.hasPrevious,true); assert.notEqual(second.data[0].id,first.data[0].id);
const detail = await repository.getAssetById(first.data[0].id);
stage = 'detail mapping';
assert.equal(detail.tag,first.data[0].tag); assert.equal(detail.purchaseCost,'999999999999999999.99');
assert.equal(detail.department,null);
const filtered = await repository.getAssets({ ...defaultAssetQuery,search:'F1-SMOKE-02',status:'DRAFT',category:'Equipment' });
stage = 'filter result';
assert.equal(filtered.total,1);
await session.refresh();
stage = 'refresh and logout';
assert.equal((await repository.getAssets(defaultAssetQuery)).total,2);
session.logout(); assert.equal(storage.size,0); assert.equal(session.getSnapshot().user,null);
console.log('PASS: real JWT login/me, asset pagination/search/filter/detail, Decimal mapping, rotating refresh, logout.');
}
void run().catch(error => {
  console.log(`SMOKE: failed at ${stage}; ${error instanceof ApiError ? `${error.kind}, HTTP ${error.status ?? 'none'}` : 'assertion or runtime failure'}`);
  process.exitCode = 1;
});
