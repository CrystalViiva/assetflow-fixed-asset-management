import { ApiClient } from './apiClient';
import { ApiError } from './apiError';
import { uuidPattern } from './assetDtos';
import { Page, ReportDefinition, ReportExport, ReportPage, ReportSnapshot, ReportSnapshotRow, parsePage, parseReportCatalog, parseReportExport, parseReportPage, parseReportSnapshot, parseSnapshotRow, reportTypes } from './reportDtos';

export interface ReportFilters{page:number;pageSize:number;department?:string;status?:string;date_from?:string;date_to?:string;asset_tag?:string;search?:string}
function validPage(page:number,pageSize:number){if(!Number.isSafeInteger(page)||page<1||!Number.isSafeInteger(pageSize)||pageSize<1||pageSize>100)throw new ApiError('validation','Invalid report pagination.');}
export class DjangoReportRepository{
 constructor(private readonly api:ApiClient){}
 async catalog(signal?:AbortSignal):Promise<ReportDefinition[]>{return parseReportCatalog(await this.api.request('/reports/',{signal}));}
 async report(type:string,filters:ReportFilters,signal?:AbortSignal,columns?:string[]):Promise<ReportPage>{if(!reportTypes.includes(type as typeof reportTypes[number]))throw new ApiError('validation','Invalid report type.');validPage(filters.page,filters.pageSize);return parseReportPage(await this.api.request(`/reports/${type}/`,{query:{page:filters.page,page_size:filters.pageSize,department:filters.department,status:filters.status,date_from:filters.date_from,date_to:filters.date_to,asset_tag:filters.asset_tag,search:filters.search},signal}),columns);}
 async snapshots(page:number,pageSize:number,signal?:AbortSignal):Promise<Page<ReportSnapshot>>{validPage(page,pageSize);return parsePage(await this.api.request('/report-snapshots/',{query:{page,page_size:pageSize},signal}),parseReportSnapshot);}
 async snapshot(id:string,signal?:AbortSignal):Promise<ReportSnapshot>{this.valid(id);return parseReportSnapshot(await this.api.request(`/report-snapshots/${id}/`,{signal}));}
 async snapshotRows(id:string,page:number,pageSize:number,signal?:AbortSignal):Promise<Page<ReportSnapshotRow>>{this.valid(id);validPage(page,pageSize);return parsePage(await this.api.request(`/report-snapshots/${id}/rows/`,{query:{page,page_size:pageSize},signal}),parseSnapshotRow);}
 async createSnapshot(input:{report_type:string;filters:Record<string,string>;idempotency_key:string}):Promise<ReportSnapshot>{if(!reportTypes.includes(input.report_type as typeof reportTypes[number])||!uuidPattern.test(input.idempotency_key))throw new ApiError('validation','Invalid snapshot request.');return parseReportSnapshot(await this.api.request('/report-snapshots/',{method:'POST',body:input}));}
 async exports(page:number,pageSize:number,signal?:AbortSignal):Promise<Page<ReportExport>>{validPage(page,pageSize);return parsePage(await this.api.request('/report-exports/',{query:{page,page_size:pageSize},signal}),parseReportExport);}
 async export(id:string,signal?:AbortSignal):Promise<ReportExport>{this.valid(id);return parseReportExport(await this.api.request(`/report-exports/${id}/`,{signal}));}
 async createExport(input:{source_snapshot_id:string;format:'CSV'|'JSON';idempotency_key:string}):Promise<ReportExport>{this.valid(input.source_snapshot_id);this.valid(input.idempotency_key);return parseReportExport(await this.api.request('/report-exports/',{method:'POST',body:input}));}
 async downloadExport(id:string,signal?:AbortSignal){this.valid(id);return this.api.download(`/report-exports/${id}/download/`,signal);}
 private valid(id:string){if(!uuidPattern.test(id))throw new ApiError('validation','Invalid reporting UUID.');}
}
