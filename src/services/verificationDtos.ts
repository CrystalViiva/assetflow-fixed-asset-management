import { ApiError, isRecord } from './apiError';
import { uuidPattern } from './assetDtos';

export const campaignStatuses = ['DRAFT','OPEN','IN_PROGRESS','COMPLETED','CANCELLED'] as const;
export const campaignScopes = ['ORGANIZATION','DEPARTMENT','LOCATION'] as const;
export const verificationResults = ['VERIFIED','LOCATION_MISMATCH','CUSTODY_MISMATCH','CONDITION_MISMATCH','ASSET_NOT_FOUND','TAG_MISSING','DAMAGED','UNREGISTERED_ASSET','DUPLICATE_TAG','OTHER_EXCEPTION'] as const;
export const physicalConditions = ['GOOD','FAIR','DAMAGED','CRITICAL','UNKNOWN'] as const;
export const verificationExceptionTypes = ['LOCATION_MISMATCH','DEPARTMENT_MISMATCH','CUSTODY_MISMATCH','CONDITION_MISMATCH','TAG_MISSING','TAG_MISMATCH','ASSET_NOT_FOUND','DAMAGED_ASSET','UNREGISTERED_ASSET','DUPLICATE_TAG','LIFECYCLE_MISMATCH','OTHER'] as const;
export const verificationExceptionStatuses = ['OPEN','UNDER_REVIEW','RESOLVED','ACCEPTED','REJECTED'] as const;
export const verificationSeverities = ['LOW','MEDIUM','HIGH','CRITICAL'] as const;
export const evidenceTypes=['PHOTO','DOCUMENT','SCAN','NOTE'] as const;
export const evidenceIntegrityStatuses=['METADATA_ONLY','LEGACY_UNVERIFIED','PENDING','VERIFIED','FAILED','CORRUPT'] as const;
export type CampaignStatus = typeof campaignStatuses[number];
export type CampaignScope = typeof campaignScopes[number];
export type VerificationResult = typeof verificationResults[number];
export type PhysicalCondition = typeof physicalConditions[number];
export type VerificationExceptionType = typeof verificationExceptionTypes[number];
export type VerificationExceptionStatus = typeof verificationExceptionStatuses[number];
export interface Campaign { id:string; organizationId:string; name:string; description:string; status:CampaignStatus; scope:CampaignScope; departmentId:string|null; locationId:string|null; startDate:string; dueDate:string|null; openedAt:string|null; completedAt:string|null; createdByEmail:string; expected:number; verified:number; unverified:number; exceptionCount:number; resolvedExceptionCount:number; percentage:string; createdAt:string; updatedAt:string }
export interface ObservationExceptionSummary { id:string; type:VerificationExceptionType; severity:typeof verificationSeverities[number]; status:VerificationExceptionStatus; description:string }
export interface Observation { id:string; organizationId:string; campaignId:string; assetId:string|null; assetTag:string|null; verifiedAt:string; verifiedByEmail:string; result:VerificationResult; observedLocationId:string|null; observedDepartmentId:string|null; observedCustodianId:number|null; condition:PhysicalCondition; observedAssetTag:string; observedDescription:string; notes:string; exceptions:ObservationExceptionSummary[]; createdAt:string; updatedAt:string }
export interface VerificationException { id:string; organizationId:string; campaignId:string; verificationId:string; assetId:string|null; assetTag:string|null; type:VerificationExceptionType; severity:typeof verificationSeverities[number]; status:VerificationExceptionStatus; description:string; assignedToId:string|null; assignedToEmail:string|null; assignedAt:string|null; startedAt:string|null; resolutionNotes:string; resolutionReference:string; resolvedByEmail:string|null; resolvedAt:string|null; createdAt:string; updatedAt:string }
export interface VerificationPage<T> { count:number; next:string|null; previous:string|null; results:T[] }
export interface VerificationEvidence {id:string;organizationId:string;verificationId:string;exceptionId:string|null;type:typeof evidenceTypes[number];fileName:string;contentType:string;externalReference:string;capturedAt:string;capturedByEmail:string;description:string;integrity:typeof evidenceIntegrityStatuses[number];byteSize:number|null;sha256:string;uploadedAt:string|null;integrityVerifiedAt:string|null;createdAt:string}
const fail=():never=>{throw new ApiError('contract','The verification API response does not match the expected AssetFlow format.');};
const str=(v:unknown):string=>typeof v==='string'?v:fail();
const id=(v:unknown):string=>{const s=str(v);return uuidPattern.test(s)?s:fail();};
const nullableId=(v:unknown):string|null=>v===null?null:id(v);
const nullableText=(v:unknown):string|null=>v===null?null:str(v);
const timestamp=(v:unknown):string=>{const s=str(v);return !Number.isNaN(Date.parse(s))?s:fail();};
const nullableTime=(v:unknown):string|null=>v===null?null:timestamp(v);
const date=(v:unknown):string=>{const s=str(v),d=new Date(`${s}T00:00:00Z`);return /^\d{4}-\d{2}-\d{2}$/.test(s)&&!Number.isNaN(d.getTime())&&d.toISOString().slice(0,10)===s?s:fail();};
const en=<T extends string>(v:unknown,values:readonly T[]):T=>typeof v==='string'&&values.includes(v as T)?v as T:fail();
const natural=(v:unknown):number=>typeof v==='number'&&Number.isSafeInteger(v)&&v>=0?v:fail();
const actor=(v:unknown):number|null=>v===null?null:(typeof v==='number'&&Number.isSafeInteger(v)&&v>0?v:fail());
export function parseCampaign(v:unknown):Campaign { if(!isRecord(v))return fail(); const scope=en(v.scope_type,campaignScopes),departmentId=nullableId(v.department_id),locationId=nullableId(v.location_id); if((scope==='ORGANIZATION'&&(departmentId||locationId))||(scope==='DEPARTMENT'&&(!departmentId||locationId))||(scope==='LOCATION'&&(departmentId||!locationId)))return fail(); const percentage=str(v.verification_percentage);if(!/^\d{1,3}(\.\d{1,2})?$/.test(percentage)||Number(percentage)>100)return fail();return{id:id(v.id),organizationId:id(v.organization_id),name:str(v.name),description:str(v.description),status:en(v.status,campaignStatuses),scope,departmentId,locationId,startDate:date(v.start_date),dueDate:nullableDate(v.due_date),openedAt:nullableTime(v.opened_at),completedAt:nullableTime(v.completed_at),createdByEmail:str(v.created_by_email),expected:natural(v.expected_asset_count),verified:natural(v.verified_asset_count),unverified:natural(v.unverified_asset_count),exceptionCount:natural(v.exception_count),resolvedExceptionCount:natural(v.resolved_exception_count),percentage,createdAt:timestamp(v.created_at),updatedAt:timestamp(v.updated_at)}; }
function nullableDate(v:unknown):string|null{return v===null?null:date(v);}
function parseSummary(v:unknown):ObservationExceptionSummary {if(!isRecord(v))return fail();return{id:id(v.id),type:en(v.exception_type,verificationExceptionTypes),severity:en(v.severity,verificationSeverities),status:en(v.status,verificationExceptionStatuses),description:str(v.description)};}
export function parseObservation(v:unknown):Observation {if(!isRecord(v)||!Array.isArray(v.exceptions))return fail();const assetId=nullableId(v.asset_id),result=en(v.result,verificationResults);if((result==='UNREGISTERED_ASSET')!==(assetId===null))return fail();return{id:id(v.id),organizationId:id(v.organization_id),campaignId:id(v.campaign_id),assetId,assetTag:nullableText(v.asset_tag),verifiedAt:timestamp(v.verified_at),verifiedByEmail:str(v.verified_by_email),result,observedLocationId:nullableId(v.observed_location_id),observedDepartmentId:nullableId(v.observed_department_id),observedCustodianId:actor(v.observed_custodian_id),condition:en(v.observed_condition,physicalConditions),observedAssetTag:str(v.observed_asset_tag),observedDescription:str(v.observed_description),notes:str(v.notes),exceptions:v.exceptions.map(parseSummary),createdAt:timestamp(v.created_at),updatedAt:timestamp(v.updated_at)};}
export function parseVerificationException(v:unknown):VerificationException {if(!isRecord(v))return fail();return{id:id(v.id),organizationId:id(v.organization_id),campaignId:id(v.campaign_id),verificationId:id(v.verification_id),assetId:nullableId(v.asset_id),assetTag:nullableText(v.asset_tag),type:en(v.exception_type,verificationExceptionTypes),severity:en(v.severity,verificationSeverities),status:en(v.status,verificationExceptionStatuses),description:str(v.description),assignedToId:nullableId(v.assigned_to_id),assignedToEmail:nullableText(v.assigned_to_email),assignedAt:nullableTime(v.assigned_at),startedAt:nullableTime(v.started_at),resolutionNotes:str(v.resolution_notes),resolutionReference:str(v.resolution_reference),resolvedByEmail:nullableText(v.resolved_by_email),resolvedAt:nullableTime(v.resolved_at),createdAt:timestamp(v.created_at),updatedAt:timestamp(v.updated_at)};}
export function parseVerificationEvidence(v:unknown):VerificationEvidence {
 if(!isRecord(v))return fail();
 const size=v.byte_size;
 if(size!==null&&(typeof size!=='number'||!Number.isSafeInteger(size)||size<1))return fail();
 const sha=str(v.sha256),integrity=en(v.integrity_status,evidenceIntegrityStatuses),contentType=str(v.content_type);
 if(sha!==''&&!/^[a-f0-9]{64}$/.test(sha))return fail();
 const uploadedAt=nullableTime(v.uploaded_at),integrityVerifiedAt=nullableTime(v.integrity_verified_at);
 const stored=integrity==='VERIFIED'||integrity==='CORRUPT';
 if(stored){
  if(size===null||sha===''||uploadedAt===null||integrityVerifiedAt===null||!['application/pdf','image/jpeg','image/png'].includes(contentType))return fail();
 }else if(size!==null||sha!==''||uploadedAt!==null||integrityVerifiedAt!==null)return fail();
 return{id:id(v.id),organizationId:id(v.organization_id),verificationId:id(v.verification_id),exceptionId:nullableId(v.exception_id),type:en(v.evidence_type,evidenceTypes),fileName:str(v.file_name),contentType,externalReference:str(v.external_reference),capturedAt:timestamp(v.captured_at),capturedByEmail:str(v.captured_by_email),description:str(v.description),integrity,byteSize:size as number|null,sha256:sha,uploadedAt,integrityVerifiedAt,createdAt:timestamp(v.created_at)};
}
export function parseVerificationPage<T>(v:unknown,parse:(row:unknown)=>T):VerificationPage<T>{if(!isRecord(v)||!Array.isArray(v.results)||(v.next!==null&&typeof v.next!=='string')||(v.previous!==null&&typeof v.previous!=='string'))return fail();return{count:natural(v.count),next:v.next,previous:v.previous,results:v.results.map(parse)};}
