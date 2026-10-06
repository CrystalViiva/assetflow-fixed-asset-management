import { ApiClient } from './apiClient';
import { ApiError } from './apiError';
import { uuidPattern } from './assetDtos';
import { AssuranceFinding, AssurancePage, AssuranceRun, parseAssuranceFinding, parseAssurancePage, parseAssuranceRun } from './assuranceDtos';

export interface AssuranceFilters {page:number;pageSize:number;search?:string;run_type?:string;status?:string;verification_campaign?:string;finding_type?:string;severity?:string;source?:string;run?:string;asset?:string;department?:string;location?:string;ordering?:string}
export class DjangoAssuranceRepository{
 constructor(private readonly api:ApiClient){}
 runs(filters:AssuranceFilters,signal?:AbortSignal):Promise<AssurancePage<AssuranceRun>>{return this.page('/assurance/runs/',filters,parseAssuranceRun,signal);}
 findings(filters:AssuranceFilters,signal?:AbortSignal):Promise<AssurancePage<AssuranceFinding>>{return this.page('/assurance/findings/',filters,parseAssuranceFinding,signal);}
 runFindings(id:string,filters:AssuranceFilters,signal?:AbortSignal):Promise<AssurancePage<AssuranceFinding>>{this.valid(id);return this.page(`/assurance/runs/${id}/findings/`,filters,parseAssuranceFinding,signal);}
 async run(id:string,signal?:AbortSignal):Promise<AssuranceRun>{this.valid(id);return parseAssuranceRun(await this.api.request(`/assurance/runs/${id}/`,{signal}));}
 async finding(id:string,signal?:AbortSignal):Promise<AssuranceFinding>{this.valid(id);return parseAssuranceFinding(await this.api.request(`/assurance/findings/${id}/`,{signal}));}
 async createRun(input:{run_type:string;verification_campaign_id?:string;stale_after_days:number}):Promise<AssuranceRun>{if(input.verification_campaign_id)this.valid(input.verification_campaign_id);if(!Number.isSafeInteger(input.stale_after_days)||input.stale_after_days<1||input.stale_after_days>32767)throw new ApiError('validation','Invalid stale-record threshold.');return parseAssuranceRun(await this.api.request('/assurance/runs/',{method:'POST',body:input}));}
 async executeRun(id:string):Promise<AssuranceRun>{return this.runAction(id,'execute');}
 async cancelRun(id:string):Promise<AssuranceRun>{return this.runAction(id,'cancel');}
 async findingAction(id:string,action:'review'|'resolve'|'accept'|'reject',resolution_notes=''):Promise<AssuranceFinding>{this.valid(id);return parseAssuranceFinding(await this.api.request(`/assurance/findings/${id}/${action}/`,{method:'POST',...(['resolve','accept','reject'].includes(action)?{body:{resolution_notes}}:{})}));}
 private async runAction(id:string,action:'execute'|'cancel'){this.valid(id);return parseAssuranceRun(await this.api.request(`/assurance/runs/${id}/${action}/`,{method:'POST'}));}
 private async page<T>(path:string,filters:AssuranceFilters,parse:(value:unknown)=>T,signal?:AbortSignal){if(!Number.isInteger(filters.page)||filters.page<1||!Number.isInteger(filters.pageSize)||filters.pageSize<1||filters.pageSize>100)throw new ApiError('validation','Invalid assurance pagination.');return parseAssurancePage(await this.api.request(path,{query:{page:filters.page,page_size:filters.pageSize,search:filters.search,run_type:filters.run_type,status:filters.status,verification_campaign:filters.verification_campaign,finding_type:filters.finding_type,severity:filters.severity,source:filters.source,run:filters.run,asset:filters.asset,department:filters.department,location:filters.location,ordering:filters.ordering},signal}),parse);}
 private valid(id:string){if(!uuidPattern.test(id))throw new ApiError('validation','Invalid assurance UUID.');}
}
