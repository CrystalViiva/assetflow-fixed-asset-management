import { ApiClient } from './apiClient';
import { ApiError } from './apiError';
import { AssignmentRecord, CustodianRecord, TransferRecord, mapAssignmentDto, mapTransferDto, parseAssignmentDto, parseCustodianDto, parseMovementPage, parseTransferDto } from './movementDtos';
import { uuidPattern } from './assetDtos';

export class DjangoMovementRepository {
  constructor(private readonly api:ApiClient){}
  private async pages<T>(path:string,parse:(value:unknown)=>T,query:Record<string,string>,signal?:AbortSignal):Promise<T[]> { const rows:T[]=[]; const ids=new Set<string>(); let count:number|undefined; for(let page=1;;page++){ const dto=parseMovementPage(await this.api.request(path,{query:{...query,page,page_size:100},signal}),parse); if(count===undefined)count=dto.count; if(dto.count!==count||rows.length+dto.results.length>dto.count||(dto.next&&(!dto.results.length||page*100>=dto.count)))throw new ApiError('contract','Movement pagination changed unexpectedly. Reload the page.'); for(const row of dto.results){if(typeof row==='object'&&row!==null&&'id' in row){const id=String(row.id);if(ids.has(id))throw new ApiError('contract','Movement pagination returned duplicate records.');ids.add(id);} rows.push(row);} if(!dto.next){if(rows.length!==dto.count)throw new ApiError('contract','Movement data is incomplete. Reload the page.');return rows;} } }
  assignments(filters:{asset?:string;active?:boolean},signal?:AbortSignal):Promise<AssignmentRecord[]> { const query:Record<string,string>={}; if(filters.asset)query.asset=filters.asset;if(filters.active!==undefined)query.active=String(filters.active);return this.pages('/assets/assignments/',row=>mapAssignmentDto(parseAssignmentDto(row)),query,signal); }
  transfers(filters:{asset?:string;status?:string},signal?:AbortSignal):Promise<TransferRecord[]> { const query:Record<string,string>={};if(filters.asset)query.asset=filters.asset;if(filters.status)query.status=filters.status;return this.pages('/assets/transfers/',row=>mapTransferDto(parseTransferDto(row)),query,signal); }
  async transfer(id:string,signal?:AbortSignal):Promise<TransferRecord>{this.validId(id);return mapTransferDto(parseTransferDto(await this.api.request(`/assets/transfers/${id}/`,{signal})));}
  custodians(signal?:AbortSignal):Promise<CustodianRecord[]> { return this.pages('/custodians/',parseCustodianDto,{},signal); }
  async createAssignment(input:{asset_id:string;assigned_to_id:number|null;notes:string}):Promise<AssignmentRecord>{return mapAssignmentDto(parseAssignmentDto(await this.api.request('/assets/assignments/',{method:'POST',body:input})));}
  async returnAssignment(id:string):Promise<AssignmentRecord>{this.validId(id);return mapAssignmentDto(parseAssignmentDto(await this.api.request(`/assets/assignments/${id}/return/`,{method:'POST'})));}
  async createTransfer(input:{asset_id:string;to_department_id:string;to_location_id:string;reason:string;notes:string}):Promise<TransferRecord>{return mapTransferDto(parseTransferDto(await this.api.request('/assets/transfers/',{method:'POST',body:input})));}
  async transition(id:string,action:'approve'|'reject'|'cancel'|'complete'):Promise<TransferRecord>{this.validId(id);return mapTransferDto(parseTransferDto(await this.api.request(`/assets/transfers/${id}/${action}/`,{method:'POST'})));}
  private validId(id:string){if(!uuidPattern.test(id))throw new ApiError('validation','Invalid movement record UUID.');}
}
