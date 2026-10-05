import { ApiError, isRecord } from './apiError';
import { uuidPattern } from './assetDtos';

export const disposalMethods = ['SALE','SCRAP','DONATION','WRITE_OFF','TRANSFER_OUT'] as const;
export const disposalStatuses = ['DRAFT','PENDING_APPROVAL','APPROVED','REJECTED','CANCELLED','COMPLETED'] as const;
export type DisposalMethod = typeof disposalMethods[number];
export type DisposalStatus = typeof disposalStatuses[number];
export interface DisposalRecord {
  id:string; organizationId:string; assetId:string; assetTag:string; assetName:string;
  departmentName:string|null; locationName:string|null; disposalDate:string; method:DisposalMethod;
  reason:string; proceeds:string; currency:string; capitalizedCost:string|null;
  accumulatedDepreciation:string|null; carryingAmount:string|null; gainOrLoss:string|null;
  status:DisposalStatus; requestedByEmail:string; submittedByEmail:string|null; submittedAt:string|null;
  approvedByEmail:string|null; approvedAt:string|null; rejectedBy:number|null; rejectedAt:string|null;
  cancelledBy:number|null; cancelledAt:string|null; completedAt:string|null; createdAt:string; updatedAt:string;
}
export interface DisposalPage { count:number; next:string|null; previous:string|null; results:DisposalRecord[] }

const fail=():never=>{throw new ApiError('contract','The disposal API response does not match the expected AssetFlow format.');};
const str=(v:unknown):string=>typeof v==='string'?v:fail();
const id=(v:unknown):string=>{const x=str(v);return uuidPattern.test(x)?x:fail();};
const nullable=(v:unknown):string|null=>v===null?null:str(v);
const money=(v:unknown):string|null=>v===null?null:typeof v==='string'&&/^\d{1,18}\.\d{2}$/.test(v)?v:fail();
const signedMoney=(v:unknown):string|null=>v===null?null:typeof v==='string'&&/^-?\d{1,18}\.\d{2}$/.test(v)?v:fail();
const actorId=(v:unknown):number|null=>v===null?null:typeof v==='number'&&Number.isSafeInteger(v)&&v>0?v:fail();
const date=(v:unknown):string=>{const x=str(v);const parsed=new Date(`${x}T00:00:00Z`);return /^\d{4}-\d{2}-\d{2}$/.test(x)&&!Number.isNaN(parsed.getTime())&&parsed.toISOString().slice(0,10)===x?x:fail();};
const timestamp=(v:unknown):string=>{const x=str(v);return !Number.isNaN(Date.parse(x))?x:fail();};
const choice=<T extends string>(v:unknown,values:readonly T[]):T=>typeof v==='string'&&values.includes(v as T)?v as T:fail();
export function parseDisposal(value:unknown):DisposalRecord {
  if(!isRecord(value))return fail();
  const currency=str(value.currency); if(!/^[A-Z]{3}$/.test(currency))return fail();
  const result:DisposalRecord = {id:id(value.id),organizationId:id(value.organization_id),assetId:id(value.asset_id),assetTag:str(value.asset_tag),assetName:str(value.asset_name),
    departmentName:nullable(value.department_name),locationName:nullable(value.location_name),disposalDate:date(value.disposal_date),method:choice(value.disposal_method,disposalMethods),
    reason:str(value.reason),proceeds:money(value.proceeds)??fail(),currency,capitalizedCost:money(value.capitalized_cost_at_disposal),
    accumulatedDepreciation:money(value.accumulated_depreciation_at_disposal),carryingAmount:money(value.carrying_amount),gainOrLoss:signedMoney(value.gain_or_loss),
    status:choice(value.status,disposalStatuses),requestedByEmail:str(value.requested_by_email),submittedByEmail:nullable(value.submitted_by_email),submittedAt:value.submitted_at===null?null:timestamp(value.submitted_at),
    approvedByEmail:nullable(value.approved_by_email),approvedAt:value.approved_at===null?null:timestamp(value.approved_at),rejectedBy:actorId(value.rejected_by),rejectedAt:value.rejected_at===null?null:timestamp(value.rejected_at),
    cancelledBy:actorId(value.cancelled_by),cancelledAt:value.cancelled_at===null?null:timestamp(value.cancelled_at),completedAt:value.completed_at===null?null:timestamp(value.completed_at),createdAt:timestamp(value.created_at),updatedAt:timestamp(value.updated_at)};
  const snapshot=[result.capitalizedCost,result.accumulatedDepreciation,result.carryingAmount,result.gainOrLoss];
  if(result.status==='COMPLETED'&&(!result.submittedAt||!result.submittedByEmail||!result.approvedAt||!result.approvedByEmail||!result.completedAt||snapshot.some(part=>part===null)))return fail();
  if(result.status!=='COMPLETED'&&snapshot.some(part=>part!==null))return fail();
  if(['PENDING_APPROVAL','APPROVED','REJECTED'].includes(result.status)&&(!result.submittedAt||!result.submittedByEmail))return fail();
  if(['APPROVED','COMPLETED'].includes(result.status)&&(!result.approvedAt||!result.approvedByEmail||result.approvedByEmail.toLowerCase()===result.requestedByEmail.toLowerCase()))return fail();
  if(result.status==='REJECTED'&&(!result.rejectedAt||result.rejectedBy===null))return fail();
  if(result.status==='CANCELLED'&&(!result.cancelledAt||result.cancelledBy===null))return fail();
  return result;
}
export function parseDisposalPage(value:unknown):DisposalPage {
  if(!isRecord(value)||typeof value.count!=='number'||!Number.isSafeInteger(value.count)||value.count<0||!Array.isArray(value.results)||(value.next!==null&&typeof value.next!=='string')||(value.previous!==null&&typeof value.previous!=='string'))return fail();
  return {count:value.count,next:value.next,previous:value.previous,results:value.results.map(parseDisposal)};
}
export function formatDisposalMoney(value:string):string {const parsed=signedMoney(value);if(parsed===null)return fail();const negative=parsed.startsWith('-');const unsigned=negative?parsed.slice(1):parsed;const [whole,fraction]=unsigned.split('.');return `${negative?'-':''}${whole.replace(/\B(?=(\d{3})+(?!\d))/g,',')}.${fraction}`;}
