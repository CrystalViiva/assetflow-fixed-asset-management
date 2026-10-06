import {describe,expect,it,vi} from 'vitest';
import {ApiClient} from './apiClient';
import {ApiError} from './apiError';
import {DjangoOrganizationAdminRepository} from './organizationAdminRepository';

const id='11111111-1111-4111-8111-111111111111',org='22222222-2222-4222-8222-222222222222',now='2026-10-06T10:00:00Z';
const reference={id,organization_id:org,name:'Finance',code:'FIN',is_active:true,created_at:now,updated_at:now};
const user={id:5,email:'worker@example.test',role:'DEPARTMENT_MANAGER',department_id:id,department_name:'Finance',is_active:true,created_at:now,last_login:null};
function repository(fetcher:typeof fetch){const api=new ApiClient('/api/v1',fetcher);api.session={accessToken:'token',generation:4,refresh:async()=>{},invalidate:()=>{}};return new DjangoOrganizationAdminRepository(api);}
describe('organization administration DTO and repository boundary',()=>{
 it('parses safe organization records and nullable user fields',async()=>{
  const fetcher=vi.fn<typeof fetch>().mockResolvedValueOnce(Response.json({count:1,next:null,previous:null,results:[reference]})).mockResolvedValueOnce(Response.json({count:1,next:null,previous:null,results:[user]}));
  const repo=repository(fetcher);expect((await repo.departments({page:1,pageSize:25,search:''})).results[0]).toMatchObject({id,organizationId:org,code:'FIN',isActive:true});
  expect((await repo.users({page:1,pageSize:25,search:''})).results[0]).toMatchObject({id:5,role:'DEPARTMENT_MANAGER',departmentId:id,lastLogin:null});
 });
 it.each([
  [{...user,role:'SUPERUSER'}],
  [{...user,department_id:'not-a-uuid'}],
  [{...user,email:'not-an-email'}],
  [{...user,created_at:'yesterday'}],
  [{...user,password:'must never be in the response'}],
 ])('rejects unsafe or malformed user contracts',async row=>{
  const fetcher=vi.fn<typeof fetch>().mockResolvedValue(Response.json({count:1,next:null,previous:null,results:row}));
  await expect(repository(fetcher).users({page:1,pageSize:25,search:''})).rejects.toMatchObject({kind:'contract'});
 });
 it('uses server routes, submits no client organization, and never retries an administrative write',async()=>{
  const fetcher=vi.fn<typeof fetch>().mockResolvedValue(Response.json(reference,{status:201}));const repo=repository(fetcher);
  await repo.createDepartment({name:'Finance',code:'FIN',is_active:true});
  expect(fetcher).toHaveBeenCalledTimes(1);const [,init]=fetcher.mock.calls[0]!;const body=JSON.parse(String(init?.body));
  expect(body).toEqual({name:'Finance',code:'FIN',is_active:true});expect(body).not.toHaveProperty('organization_id');
  expect(String(fetcher.mock.calls[0]![0])).toContain('/admin/departments/');
 });
 it('reconciles a lost create response by stable code without replaying the write',async()=>{
  const fetcher=vi.fn<typeof fetch>().mockRejectedValueOnce(new TypeError('connection lost')).mockResolvedValueOnce(Response.json({count:1,next:null,previous:null,results:[reference]}));
  const result=await repository(fetcher).createDepartment({name:'Finance',code:'FIN',is_active:true});
  expect(result.id).toBe(id);expect(fetcher).toHaveBeenCalledTimes(2);expect(fetcher.mock.calls[0]?.[1]?.method).toBe('POST');expect(fetcher.mock.calls[1]?.[1]?.method??'GET').toBe('GET');
 });
 it('blocks another create when authoritative state cannot resolve a lost response',async()=>{
  const fetcher=vi.fn<typeof fetch>().mockRejectedValue(new TypeError('offline'));const repo=repository(fetcher);
  await expect(repo.createDepartment({name:'Finance',code:'FIN',is_active:true})).rejects.toMatchObject({kind:'conflict'});
  expect(fetcher).toHaveBeenCalledTimes(2);expect(fetcher.mock.calls.filter(call=>call[1]?.method==='POST')).toHaveLength(1);
 });
 it('fails closed on malformed UUIDs before requesting an object',async()=>{
  const fetcher=vi.fn<typeof fetch>();await expect(repository(fetcher).updateDepartment('bad',{name:'x',code:'x',is_active:true})).rejects.toBeInstanceOf(ApiError);expect(fetcher).not.toHaveBeenCalled();
 });
});
