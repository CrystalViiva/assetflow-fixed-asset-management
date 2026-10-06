import assert from 'node:assert/strict';
import {ApiClient} from '../src/services/apiClient';
import {Session} from '../src/services/session';
import {DjangoAuditRepository} from '../src/services/auditRepository';
import {ApiError} from '../src/services/apiError';

let stage='session setup';
async function run(){
 const storage=new Map<string,string>(),api=new ApiClient(process.env.F1_SMOKE_URL!);
 const session=new Session(api,{getItem:key=>storage.get(key)??null,setItem:(key,value)=>storage.set(key,value),removeItem:key=>storage.delete(key)},()=>{});
 await session.initialize();stage='authorized manager login';await session.login(process.env.F1_SMOKE_EMAIL!,process.env.F1_SMOKE_PASSWORD!);
 assert.equal(session.getSnapshot().user?.role,'ASSET_MANAGER');const audit=new DjangoAuditRepository(api);
 stage='load real organization references';
 const [categories,departments,locations]=await Promise.all([
  api.request('/assets/categories/') as Promise<{results:Array<{id:string}>}>,
  api.request('/departments/') as Promise<{results:Array<{id:string}>}>,
  api.request('/locations/') as Promise<{results:Array<{id:string}>}>,
 ]);
 const category=categories.results[0]!,department=departments.results[0]!,location=locations.results[0]!;
 async function createAsset(tag:string,name:string){return await api.request('/assets/',{method:'POST',body:{asset_tag:tag,name,category_id:category.id,department_id:department.id,location_id:location.id,purchase_cost:'100.00',residual_value:'0.00'}}) as {id:string;asset_tag:string};}
 stage='create asset through the actual Django domain service';const asset=await createAsset('F10-AUDIT-001','F10 audit smoke asset');
 stage='verify backend-generated creation event and historical actor';
 const first=await audit.events({page:1,pageSize:25,action:'ASSET_CREATED',entityType:'ASSET',entityId:asset.id,actor:'',search:'',dateFrom:'',dateTo:'',ordering:'-timestamp'});
 assert.equal(first.count,1);assert.equal(first.results[0]?.actorEmail,process.env.F1_SMOKE_EMAIL!.toLowerCase());assert.ok(Number.isFinite(Date.parse(first.results[0]!.timestamp)));
 stage='create and capitalize an acquisition through its domain workflow';
 const acquisition=await api.request('/assets/acquisitions/',{method:'POST',body:{asset_id:asset.id,vendor_name:'F10 Smoke Vendor',invoice_number:'F10-INV-001',reference:'F10-PO-001',acquisition_date:'2026-01-01',capitalization_date:'2026-01-02',purchase_price:'1000.00',freight_cost:'0.00',installation_cost:'0.00',civil_works_cost:'0.00',other_capitalizable_cost:'0.00'}}) as {id:string};
 await api.request(`/assets/acquisitions/${acquisition.id}/capitalize/`,{method:'POST'});
 const acquisitionEvent=await audit.events({page:1,pageSize:25,action:'ACQUISITION_CREATED',entityType:'ACQUISITION',entityId:acquisition.id,actor:'',search:'',dateFrom:'',dateTo:'',ordering:'-timestamp'});
 assert.equal(acquisitionEvent.count,1);assert.equal(acquisitionEvent.results[0]?.actorEmail,process.env.F1_SMOKE_EMAIL!.toLowerCase());
 stage='update asset through domain API to generate second backend event';await api.request(`/assets/${asset.id}/`,{method:'PATCH',body:{name:'F10 audit smoke asset updated'}});
 const ordered=await audit.events({page:1,pageSize:25,action:'',entityType:'',entityId:asset.id,actor:'',search:'',dateFrom:'',dateTo:'',ordering:'-timestamp'});
 assert.ok(ordered.count>=3);assert.ok(ordered.results.some(row=>row.action==='ASSET_UPDATED'));assert.ok(ordered.results.some(row=>row.action==='ASSET_CAPITALIZED'));assert.ok(Date.parse(ordered.results[0]!.timestamp)>=Date.parse(ordered.results[1]!.timestamp));
 stage='verify immutable audit API rejects all mutation methods';
 for(const method of ['POST','PUT','PATCH','DELETE'] as const){await assert.rejects(api.request('/audit/events/',{method,body:{action:'FAKE_EVENT'}}),error=>error instanceof ApiError&&error.status===405);}
 stage='create event under a separate tenant';session.logout();await session.login('foreign-manager@example.test',process.env.F1_SMOKE_PASSWORD!);
 const foreignCategories=await api.request('/assets/categories/') as {results:Array<{id:string}>};const foreign=await api.request('/assets/',{method:'POST',body:{asset_tag:'F10-FOREIGN-ONLY-NEW',name:'Foreign event',category_id:foreignCategories.results[0]!.id,purchase_cost:'100.00',residual_value:'0.00'}}) as {id:string};
 stage='switch back and verify tenant filter hides foreign event';session.logout();await session.login(process.env.F1_SMOKE_EMAIL!,process.env.F1_SMOKE_PASSWORD!);
 const hidden=await audit.events({page:1,pageSize:25,action:'',entityType:'',entityId:foreign.id,actor:'',search:'',dateFrom:'',dateTo:'',ordering:'-timestamp'});assert.equal(hidden.count,0);
 stage='logout';session.logout();assert.equal(storage.size,0);assert.equal(session.getSnapshot().user,null);
 console.log('PASS: isolated TypeScript → Django → PostgreSQL asset create/update plus acquisition capitalization generated domain-service audit events with Django actor/time; exact asset filter and ordering verified; POST/PUT/PATCH/DELETE rejected; second-tenant event hidden after user switch; logout completed.');
}
void run().catch(error=>{const safe=error instanceof Error?error.name:'runtime failure';const detail=error instanceof Error&&'kind' in error?`${String((error as {kind:unknown}).kind)}${'status' in error?` HTTP ${String((error as {status:unknown}).status)}`:''}${'message' in error?`; ${String((error as {message:unknown}).message)}`:''}`:error instanceof Error&&error.name==='AssertionError'?`; ${error.message.slice(0,400)}`:'';console.log(`SMOKE: failed at ${stage}; ${safe}${detail?`; ${detail}`:''}`);process.exitCode=1;});
