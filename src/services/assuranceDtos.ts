import { ApiError, isRecord } from './apiError';
import { uuidPattern } from './assetDtos';

export const assuranceRunTypes=['FULL','PHYSICAL','FINANCIAL','OPERATIONAL'] as const;
export const assuranceRunStatuses=['PENDING','RUNNING','COMPLETED','FAILED','CANCELLED'] as const;
export const assurancePhases=['LEGACY','CAPTURE','EVALUATE','PUBLISH','DONE'] as const;
export const assuranceFindingTypes=['LOCATION_MISMATCH','DEPARTMENT_MISMATCH','CUSTODY_MISMATCH','MISSING_PHYSICAL_VERIFICATION','ASSET_NOT_FOUND','UNREGISTERED_ASSET','TAG_MISMATCH','DUPLICATE_TAG','CONDITION_EXCEPTION','LIFECYCLE_MISMATCH','DISPOSAL_STATUS_MISMATCH','DEPRECIATION_EXCEPTION','BOOK_VALUE_EXCEPTION','STALE_RECORD','OPEN_WORKFLOW','MISSING_EVIDENCE'] as const;
export const assuranceSeverities=['LOW','MEDIUM','HIGH','CRITICAL'] as const;
export const assuranceFindingStatuses=['OPEN','UNDER_REVIEW','RESOLVED','ACCEPTED','REJECTED'] as const;
export const assuranceFindingSources=['ASSET_MASTER','PHYSICAL_VERIFICATION','DEPRECIATION','DISPOSAL','MAINTENANCE','ASSIGNMENT','TRANSFER','EVIDENCE'] as const;
export type AssuranceRunType=typeof assuranceRunTypes[number];
export type AssuranceRunStatus=typeof assuranceRunStatuses[number];
export type AssurancePhase=typeof assurancePhases[number];
export type AssuranceFindingType=typeof assuranceFindingTypes[number];
export type AssuranceFindingStatus=typeof assuranceFindingStatuses[number];
export interface AssuranceRun {id:string;organizationId:string;runType:AssuranceRunType;status:AssuranceRunStatus;verificationCampaignId:string|null;staleAfterDays:number;scheduledFor:string|null;startedAt:string|null;completedAt:string|null;startedByEmail:string|null;completedByEmail:string|null;assetsEvaluated:number;findingsGenerated:number;findingsOpen:number;findingsResolved:number;failureMessage:string;phase:AssurancePhase;capturedAt:string|null;sealedAt:string|null;executorVersion:number;inputSchemaVersion:number;populationCount:number;unitCount:number;unitsCompleted:number;createdAt:string;updatedAt:string}
export interface AssuranceOccurrence {id:string;assuranceRunId:string;detectedAt:string;expectedValue:string;observedValue:string;description:string}
export interface AssuranceFinding {id:string;organizationId:string;assuranceRunId:string;lastDetectedRunId:string;assetId:string|null;assetTag:string|null;assetName:string|null;physicalVerificationId:string|null;departmentName:string|null;locationName:string|null;identityKey:string;type:AssuranceFindingType;severity:typeof assuranceSeverities[number];status:AssuranceFindingStatus;source:typeof assuranceFindingSources[number];expectedValue:string;observedValue:string;description:string;occurrenceCount:number;firstDetectedAt:string;lastDetectedAt:string;resolvedAt:string|null;resolvedByEmail:string|null;resolutionNotes:string;occurrences:AssuranceOccurrence[];createdAt:string;updatedAt:string}
export interface AssurancePage<T>{count:number;next:string|null;previous:string|null;results:T[]}

const fail=():never=>{throw new ApiError('contract','The assurance API response does not match the expected AssetFlow format.');};
const str=(value:unknown):string=>typeof value==='string'?value:fail();
const id=(value:unknown):string=>{const result=str(value);return uuidPattern.test(result)?result:fail();};
const nullableId=(value:unknown):string|null=>value===null?null:id(value);
const nullableText=(value:unknown):string|null=>value===null?null:str(value);
const time=(value:unknown):string=>{const result=str(value);return Number.isNaN(Date.parse(result))?fail():result;};
const nullableTime=(value:unknown):string|null=>value===null?null:time(value);
const date=(value:unknown):string|null=>{if(value===null)return null;const result=str(value),parsed=new Date(`${result}T00:00:00Z`);return /^\d{4}-\d{2}-\d{2}$/.test(result)&&!Number.isNaN(parsed.getTime())&&parsed.toISOString().slice(0,10)===result?result:fail();};
const natural=(value:unknown):number=>typeof value==='number'&&Number.isSafeInteger(value)&&value>=0?value:fail();
const positive=(value:unknown):number=>typeof value==='number'&&Number.isSafeInteger(value)&&value>0?value:fail();
const choice=<T extends string>(value:unknown,options:readonly T[]):T=>typeof value==='string'&&options.includes(value as T)?value as T:fail();

export function parseAssuranceRun(value:unknown):AssuranceRun{
 if(!isRecord(value))return fail();
 const result:AssuranceRun={id:id(value.id),organizationId:id(value.organization_id),runType:choice(value.run_type,assuranceRunTypes),status:choice(value.status,assuranceRunStatuses),verificationCampaignId:nullableId(value.verification_campaign_id),staleAfterDays:positive(value.stale_after_days),scheduledFor:date(value.scheduled_for),startedAt:nullableTime(value.started_at),completedAt:nullableTime(value.completed_at),startedByEmail:nullableText(value.started_by_email),completedByEmail:nullableText(value.completed_by_email),assetsEvaluated:natural(value.assets_evaluated),findingsGenerated:natural(value.findings_generated),findingsOpen:natural(value.findings_open),findingsResolved:natural(value.findings_resolved),failureMessage:str(value.failure_message),phase:choice(value.execution_phase,assurancePhases),capturedAt:nullableTime(value.captured_at),sealedAt:nullableTime(value.sealed_at),executorVersion:natural(value.executor_version),inputSchemaVersion:natural(value.input_schema_version),populationCount:natural(value.population_count),unitCount:natural(value.unit_count),unitsCompleted:natural(value.units_completed),createdAt:time(value.created_at),updatedAt:time(value.updated_at)};
 if(result.unitsCompleted>result.unitCount)return fail();
 if(result.status==='PENDING'&&(result.startedAt!==null||result.completedAt!==null))return fail();
 if(result.status==='RUNNING'&&(!result.startedAt||result.completedAt!==null))return fail();
 if(['COMPLETED','FAILED'].includes(result.status)&&(!result.startedAt||!result.completedAt))return fail();
 if(result.status==='CANCELLED'&&result.completedAt===null)return fail();
 if(result.status!=='FAILED'&&result.failureMessage!=='')return fail();
 if(result.status==='RUNNING'&&result.sealedAt&&result.executorVersion===0)return fail();
 return result;
}
export function parseAssuranceOccurrence(value:unknown):AssuranceOccurrence{if(!isRecord(value))return fail();return{id:id(value.id),assuranceRunId:id(value.assurance_run),detectedAt:time(value.detected_at),expectedValue:str(value.expected_value),observedValue:str(value.observed_value),description:str(value.description)};}
export function parseAssuranceFinding(value:unknown):AssuranceFinding{
 if(!isRecord(value)||!Array.isArray(value.occurrences))return fail();
 const result:AssuranceFinding={id:id(value.id),organizationId:id(value.organization_id),assuranceRunId:id(value.assurance_run),lastDetectedRunId:id(value.last_detected_run),assetId:nullableId(value.asset),assetTag:nullableText(value.asset_tag),assetName:nullableText(value.asset_name),physicalVerificationId:nullableId(value.physical_verification),departmentName:nullableText(value.department_name),locationName:nullableText(value.location_name),identityKey:str(value.identity_key),type:choice(value.finding_type,assuranceFindingTypes),severity:choice(value.severity,assuranceSeverities),status:choice(value.status,assuranceFindingStatuses),source:choice(value.source,assuranceFindingSources),expectedValue:str(value.expected_value),observedValue:str(value.observed_value),description:str(value.description),occurrenceCount:positive(value.occurrence_count),firstDetectedAt:time(value.first_detected_at),lastDetectedAt:time(value.last_detected_at),resolvedAt:nullableTime(value.resolved_at),resolvedByEmail:nullableText(value.resolved_by_email),resolutionNotes:str(value.resolution_notes),occurrences:value.occurrences.map(parseAssuranceOccurrence),createdAt:time(value.created_at),updatedAt:time(value.updated_at)};
 if((result.assetId===null)===(result.physicalVerificationId===null))return fail();
 if(result.occurrences.length>result.occurrenceCount)return fail();
 if(['OPEN','UNDER_REVIEW'].includes(result.status)&&(result.resolvedAt!==null||result.resolvedByEmail!==null))return fail();
 if(['RESOLVED','ACCEPTED','REJECTED'].includes(result.status)&&(!result.resolvedAt||!result.resolvedByEmail))return fail();
 return result;
}
export function parseAssurancePage<T>(value:unknown,parse:(row:unknown)=>T):AssurancePage<T>{if(!isRecord(value)||!Array.isArray(value.results)||typeof value.count!=='number'||!Number.isSafeInteger(value.count)||value.count<0||(value.next!==null&&typeof value.next!=='string')||(value.previous!==null&&typeof value.previous!=='string'))return fail();return{count:value.count,next:value.next,previous:value.previous,results:value.results.map(parse)};}
