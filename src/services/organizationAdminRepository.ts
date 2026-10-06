import { ApiClient } from './apiClient';
import { ApiError, isRecord } from './apiError';
import { parsePageDto, uuidPattern } from './assetDtos';

export const organizationRoles = ['ADMIN','ASSET_MANAGER','ACCOUNTANT','DEPARTMENT_MANAGER','EMPLOYEE'] as const;
export type OrganizationRole = typeof organizationRoles[number];
export interface AdminReference { id:string; organizationId:string; name:string; code:string; isActive:boolean; address?:string; city?:string; state?:string; country?:string; createdAt:string; updatedAt:string }
export interface AdminUser { id:number; email:string; role:OrganizationRole; departmentId:string|null; departmentName:string|null; isActive:boolean; createdAt:string; lastLogin:string|null }
export interface AdminPage<T>{count:number;next:string|null;previous:string|null;results:T[]}
export interface AdminFilters {page:number;pageSize:number;search:string;is_active?:boolean}
export interface UserFilters extends AdminFilters {role?:OrganizationRole;department?:string}
const fail=():never=>{throw new ApiError('contract','The organization administration API returned an unsupported response.');};
const str=(v:unknown):string=>typeof v==='string'?v:fail();
const time=(v:unknown,nullable=false):string|null=>{if(nullable&&v===null)return null;const s=str(v);return Number.isNaN(Date.parse(s))?fail():s;};
function parseReference(v:unknown,location:boolean):AdminReference{
 if(!isRecord(v)||typeof v.is_active!=='boolean')return fail();
 const id=str(v.id),organizationId=str(v.organization_id);if(!uuidPattern.test(id)||!uuidPattern.test(organizationId))return fail();
 const base={id,organizationId,name:str(v.name),code:str(v.code),isActive:v.is_active,createdAt:str(time(v.created_at)!),updatedAt:str(time(v.updated_at)!)};
 if(!location)return base;
 return {...base,address:str(v.address),city:str(v.city),state:str(v.state),country:str(v.country)};
}
function parseUser(v:unknown):AdminUser{
 if(!isRecord(v)||typeof v.id!=='number'||!Number.isSafeInteger(v.id)||v.id<1||typeof v.is_active!=='boolean')return fail();
 const email=str(v.email),role=str(v.role),departmentId=v.department_id===null?null:str(v.department_id),departmentName=v.department_name===null?null:str(v.department_name);
 if(!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)||!(organizationRoles as readonly string[]).includes(role)||(departmentId!==null&&!uuidPattern.test(departmentId))||(departmentId===null)!==(departmentName===null))return fail();
 return{id:v.id,email,role:role as OrganizationRole,departmentId,departmentName,isActive:v.is_active,createdAt:str(time(v.created_at)!),lastLogin:time(v.last_login,true)};
}
function page<T>(raw:unknown,parse:(row:unknown)=>T):AdminPage<T>{const result=parsePageDto(raw,parse);return{count:result.count,next:result.next,previous:result.previous,results:result.results};}
export class DjangoOrganizationAdminRepository{
 constructor(private readonly api:ApiClient){}
 departments(f:AdminFilters,signal?:AbortSignal){return this.list('/admin/departments/',f,v=>parseReference(v,false),signal);}
 locations(f:AdminFilters,signal?:AbortSignal){return this.list('/admin/locations/',f,v=>parseReference(v,true),signal);}
 users(f:UserFilters,signal?:AbortSignal){return this.list('/admin/users/',f,parseUser,signal);}
 private async list<T>(path:string,f:AdminFilters,parse:(v:unknown)=>T,signal?:AbortSignal,extra:Record<string,string|number|boolean|undefined>={}){if(!Number.isInteger(f.page)||f.page<1||!Number.isInteger(f.pageSize)||f.pageSize<1||f.pageSize>100)throw new ApiError('validation','Invalid organization pagination.');return page(await this.api.request(path,{signal,query:{page:f.page,page_size:f.pageSize,search:f.search,is_active:f.is_active,...extra}}),parse);}
 private async reconcile<T>(send:()=>Promise<T>,refetch:()=>Promise<T>,committed:(value:T)=>boolean){try{return await send();}catch(error){if(!(error instanceof ApiError)||!['network','server'].includes(error.kind))throw error;try{const current=await refetch();if(committed(current))return current;}catch{/* Keep the authoritative state uncertain when it cannot be read. */}throw new ApiError('conflict','The save outcome is uncertain. Refresh the list and inspect the current record before trying again.');}}
 async createDepartment(input:{name:string;code:string;is_active:boolean}){return this.reconcile(async()=>parseReference(await this.api.request('/admin/departments/',{method:'POST',body:input}),false),async()=>{const rows=await this.departments({page:1,pageSize:100,search:input.code});const found=rows.results.filter(row=>row.code===input.code);if(found.length!==1)throw new Error('Department outcome uncertain');return found[0]!;},row=>row.name===input.name&&row.code===input.code&&row.isActive===input.is_active);}
 async updateDepartment(id:string,input:{name:string;code:string;is_active:boolean}){this.valid(id);const body={name:input.name,code:input.code,is_active:input.is_active};return this.reconcile(async()=>parseReference(await this.api.request(`/admin/departments/${id}/`,{method:'PATCH',body}),false),async()=>parseReference(await this.api.request(`/admin/departments/${id}/`),false),row=>row.name===input.name&&row.code===input.code&&row.isActive===input.is_active);}
 async createLocation(input:{name:string;code:string;address:string;city:string;state:string;country:string;is_active:boolean}){return this.reconcile(async()=>parseReference(await this.api.request('/admin/locations/',{method:'POST',body:input}),true),async()=>{const rows=await this.locations({page:1,pageSize:100,search:input.code});const found=rows.results.filter(row=>row.code===input.code);if(found.length!==1)throw new Error('Location outcome uncertain');return found[0]!;},row=>row.name===input.name&&row.code===input.code&&row.address===input.address&&row.city===input.city&&row.state===input.state&&row.country===input.country&&row.isActive===input.is_active);}
 async updateLocation(id:string,input:{name:string;code:string;address:string;city:string;state:string;country:string;is_active:boolean}){this.valid(id);const body={name:input.name,code:input.code,address:input.address,city:input.city,state:input.state,country:input.country,is_active:input.is_active};return this.reconcile(async()=>parseReference(await this.api.request(`/admin/locations/${id}/`,{method:'PATCH',body}),true),async()=>parseReference(await this.api.request(`/admin/locations/${id}/`),true),row=>row.name===input.name&&row.code===input.code&&row.address===input.address&&row.city===input.city&&row.state===input.state&&row.country===input.country&&row.isActive===input.is_active);}
 async createUser(input:{email:string;password:string;role:OrganizationRole;department_id:string|null}){const email=input.email.trim().toLowerCase();return this.reconcile(async()=>parseUser(await this.api.request('/admin/users/',{method:'POST',body:{...input,email}})),async()=>{const rows=await this.users({page:1,pageSize:100,search:email});if(rows.count>100)throw new Error('Too many matches');const found=rows.results.filter(row=>row.email.toLowerCase()===email);if(found.length!==1)throw new Error('User outcome uncertain');return found[0];},row=>row.email.toLowerCase()===email&&row.role===input.role&&row.departmentId===input.department_id);}
 async updateUser(id:number,input:{role:OrganizationRole;department_id:string|null;is_active:boolean}){if(!Number.isSafeInteger(id)||id<1)throw new ApiError('validation','Invalid user identifier.');return this.reconcile(async()=>parseUser(await this.api.request(`/admin/users/${id}/`,{method:'PATCH',body:input})),async()=>parseUser(await this.api.request(`/admin/users/${id}/`)),row=>row.role===input.role&&row.departmentId===input.department_id&&row.isActive===input.is_active);}
 private valid(id:string){if(!uuidPattern.test(id))throw new ApiError('validation','Invalid organization reference identifier.');}
}
