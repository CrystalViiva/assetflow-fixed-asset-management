import { ApiClient } from './apiClient';
import { ApiError } from './apiError';
import { uuidPattern } from './assetDtos';
import { DisposalPage, DisposalRecord, parseDisposal, parseDisposalPage } from './disposalDtos';

export interface DisposalFilters {page:number;pageSize:number;asset?:string;status?:string;disposal_method?:string;search?:string;ordering?:string;department?:string;location?:string}
export class DjangoDisposalRepository {
  constructor(private readonly api:ApiClient){}
  async list(filters:DisposalFilters,signal?:AbortSignal):Promise<DisposalPage>{if(!Number.isInteger(filters.page)||filters.page<1||!Number.isInteger(filters.pageSize)||filters.pageSize<1||filters.pageSize>100)throw new ApiError('validation','Invalid disposal pagination.');return parseDisposalPage(await this.api.request('/assets/disposals/',{query:{page:filters.page,page_size:filters.pageSize,asset:filters.asset,status:filters.status,disposal_method:filters.disposal_method,search:filters.search,ordering:filters.ordering,department:filters.department,location:filters.location},signal}));}
  async get(id:string,signal?:AbortSignal):Promise<DisposalRecord>{this.valid(id);return parseDisposal(await this.api.request(`/assets/disposals/${id}/`,{signal}));}
  async create(input:{asset_id:string;disposal_date:string;disposal_method:string;reason:string;proceeds:string}){this.valid(input.asset_id);if(!/^\d{4}-\d{2}-\d{2}$/.test(input.disposal_date)||!/^\d{1,18}\.\d{2}$/.test(input.proceeds)||input.proceeds.startsWith('-'))throw new ApiError('validation','Enter a valid disposal date and nonnegative amount with two decimal places.');return parseDisposal(await this.api.request('/assets/disposals/',{method:'POST',body:input}));}
  async submit(id:string){return this.transition(id,'submit');}
  async approve(id:string){return this.transition(id,'approve');}
  async reject(id:string,reason:string){return this.transition(id,'reject',{reason});}
  async cancel(id:string,reason:string){return this.transition(id,'cancel',{reason});}
  async complete(id:string){return this.transition(id,'complete');}
  private async transition(id:string,action:string,body?:unknown){this.valid(id);return parseDisposal(await this.api.request(`/assets/disposals/${id}/${action}/`,{method:'POST',...(body===undefined?{}:{body})}));}
  private valid(id:string){if(!uuidPattern.test(id))throw new ApiError('validation','Invalid disposal UUID.');}
}
