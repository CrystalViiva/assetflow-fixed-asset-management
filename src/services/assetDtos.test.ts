import { describe, expect, it, vi } from 'vitest';
import { assetDto, json } from '../test/fixtures';
import { formatDecimal, mapAssetDto, mapAssetPage, parseAssetDto, parsePageDto } from './assetDtos';
import { assetQueryParams, defaultAssetQuery, DjangoAssetRepository } from './djangoApiBridge';
import { ApiClient } from './apiClient';
import { parseApiBase, parseDataSource } from './config';
import { MockAssetRepository } from './assetRepository';

describe('asset DTO boundary', () => {
  it('maps backend naming to a dedicated frontend model', () => {
    const asset = mapAssetDto(parseAssetDto(assetDto));
    expect(asset).toMatchObject({ id:assetDto.id, tag:'REAL-001', name:'Office generator', model:'GEN-2',
      category:{ name:'Equipment',code:'EQ' }, acquisitionDate:'2026-01-01', status:'ACTIVE' });
    expect(asset).not.toHaveProperty('asset_tag'); expect(asset).not.toHaveProperty('currency');
  });
  it('preserves null relations, dates and useful life without making up values', () => {
    expect(mapAssetDto(assetDto)).toMatchObject({ department:null,location:null,capitalizationDate:null,availableForUseDate:null,usefulLifeMonths:null });
  });
  it('maps real related identifiers and labels', () => {
    expect(mapAssetDto({ ...assetDto,department_id:assetDto.id,department_name:'Operations',department_code:'OPS' }).department)
      .toEqual({ id:assetDto.id,name:'Operations',code:'OPS' });
  });
  it.each(['status','condition','depreciation_method'] as const)('rejects an unknown %s enum', field => {
    expect(() => mapAssetDto({ ...assetDto,[field]:'FUTURE' })).toThrow('unsupported asset response');
  });
  it.each(['DRAFT','PENDING_CAPITALIZATION'])('supports the backend-only lifecycle state %s', status => {
    expect(mapAssetDto({ ...assetDto,status }).status).toBe(status);
  });
  it('preserves all Decimal digits without Number conversion', () => {
    expect(mapAssetDto(assetDto).purchaseCost).toBe('999999999999999999.99');
    expect(formatDecimal(assetDto.purchase_cost)).toBe('999,999,999,999,999,999.99');
    expect(formatDecimal('0.00')).toBe('0.00'); expect(formatDecimal('1234.50')).toBe('1,234.50');
  });
  it('rejects numeric money and malformed successful responses', () => {
    expect(() => parseAssetDto({ ...assetDto,purchase_cost:12.34 })).toThrow();
    expect(() => parseAssetDto({ id:assetDto.id })).toThrow();
    expect(() => parseAssetDto(null)).toThrow();
  });
  it.each([[1,25,26,true,false,2],[2,25,26,false,true,2],[1,25,0,false,false,1],[1,10,10,false,false,1]])(
    'maps page %s, size %s and count %s without off-by-one errors', (page,size,count,next,previous,totalPages) => {
      const dto = parsePageDto({ count,next:next ? '/next/' : null,previous:previous ? '/previous/' : null,results:[] },parseAssetDto);
      expect(mapAssetPage(dto,Number(page),Number(size))).toMatchObject({ page,pageSize:size,total:count,totalPages,hasNext:next,hasPrevious:previous });
    });
  it('requires the DRF pagination envelope', () => {
    expect(() => parsePageDto({ data:[],total:0 },parseAssetDto)).toThrow();
  });
  it('maps filters, one-based pages, bounded size and ordering explicitly', () => {
    expect(assetQueryParams({ ...defaultAssetQuery,page:2,pageSize:999,category:'Equipment',department:'Operations',location:'Lagos',search:'pump',ordering:'-bookValue' }))
      .toEqual({ page:2,page_size:100,category:'Equipment',department:'Operations',location:'Lagos',search:'pump',status:'',ordering:'-current_book_value' });
    expect(() => assetQueryParams({ ...defaultAssetQuery,page:0 })).toThrow();
    expect(() => assetQueryParams({ ...defaultAssetQuery,ordering:'unsupported' })).toThrow();
  });
  it('fetches actual detail and list endpoints with mapped results', async () => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValueOnce(json({ count:1,next:null,previous:null,results:[assetDto] })).mockResolvedValueOnce(json(assetDto));
    const api = new ApiClient('/api/v1',fetcher);
    api.session = { accessToken:'test-access',generation:1,refresh:async () => {},invalidate:() => {} };
    const repository = new DjangoAssetRepository(api);
    expect((await repository.getAssets(defaultAssetQuery)).data[0].tag).toBe('REAL-001');
    expect((await repository.getAssetById(assetDto.id)).name).toBe('Office generator');
    expect(fetcher.mock.calls[1][0]).toBe(`/api/v1/assets/${assetDto.id}/`);
    expect(fetcher.mock.calls[0][0]).toBe('/api/v1/assets/?page=1&page_size=25&ordering=asset_tag');
  });
  it('rejects Django failures and never substitutes mock records', async () => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(json({},500)); const api = new ApiClient('/api/v1',fetcher);
    api.session = { accessToken:'test-access',generation:1,refresh:async () => {},invalidate:() => {} };
    await expect(new DjangoAssetRepository(api).getAssets(defaultAssetQuery)).rejects.toMatchObject({ kind:'server' });
  });
  it('rejects invalid detail UUIDs without an API request', async () => {
    const fetcher = vi.fn<typeof fetch>(); const repository = new DjangoAssetRepository(new ApiClient('/api/v1',fetcher));
    await expect(repository.getAssetById('AST-000002')).rejects.toMatchObject({ kind:'not-found' });
    expect(fetcher).not.toHaveBeenCalled();
  });
});
describe('explicit source configuration', () => {
  it('accepts mock/default and django only', () => {
    expect(parseDataSource(undefined)).toBe('mock'); expect(parseDataSource('mock')).toBe('mock'); expect(parseDataSource('django')).toBe('django');
  });
  it.each(['','DJANGO','production','false'])('fails clearly for invalid source %s', value => {
    expect(() => parseDataSource(value)).toThrow('Invalid VITE_DATA_SOURCE');
  });
  it('accepts the same-origin proxy and deliberate remote bases', () => {
    expect(parseApiBase(undefined)).toBe('/api/v1'); expect(parseApiBase('https://api.example.test/api/v1/')).toBe('https://api.example.test/api/v1');
  });
  it('rejects backslashes and whitespace that browsers can normalize into unsafe URLs', () => {
    expect(() => parseApiBase('/\\evil.test/api')).toThrow();
    expect(() => parseApiBase(' https://api.example.test')).toThrow();
  });
  it.each(['//evil.test/api','https://user:pass@example.test/api','https://api.example.test/?token=secret','javascript:alert(1)'])('rejects unsafe API base %s', value => {
    expect(() => parseApiBase(value)).toThrow();
  });
  it('retains a functioning localStorage-backed mock repository', async () => {
    const repository = new MockAssetRepository(); const page = await repository.getAssets({ page:1,pageSize:2 });
    expect(page.data).toHaveLength(2); expect(page.total).toBeGreaterThan(2);
    expect((await repository.getAssetById(page.data[0].id))?.tag).toBe(page.data[0].tag);
    await repository.updateAsset(page.data[0].id,{ name:'Mock edited' });
    expect((await new MockAssetRepository().getAssetById(page.data[0].id))?.name).toBe('Mock edited');
  });
});
