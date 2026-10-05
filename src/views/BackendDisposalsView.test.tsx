import { beforeEach,describe,expect,it,vi } from 'vitest';
import { render,screen } from '@testing-library/react';
import { BackendDisposalsView } from './BackendDisposalsView';

const state=vi.hoisted(()=>({role:'ASSET_MANAGER',records:[] as unknown[],assets:[] as unknown[]}));
vi.mock('../auth/AuthProvider',()=>({useAuth:()=>({user:{email:'requester@example.test'},role:state.role,generation:3,isCurrent:()=>true})}));
vi.mock('../services/assetQueries',()=>({useAllAssets:()=>({data:{data:state.assets},isError:false,isPending:false,refetch:vi.fn()})}));
vi.mock('../services/disposalQueries',()=>({useDisposals:()=>({data:{count:state.records.length,next:null,previous:null,results:state.records},isPending:false,isError:false,isFetching:false,refetch:vi.fn()})}));
vi.mock('../services/disposalMutations',()=>({useDisposalAction:()=>({pending:false,run:async(action:()=>Promise<unknown>)=>action()})}));
vi.mock('../services/runtime',()=>({disposalRepository:{create:vi.fn(),list:vi.fn(),get:vi.fn(),submit:vi.fn(),approve:vi.fn(),reject:vi.fn(),cancel:vi.fn(),complete:vi.fn()}}));

const id='aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa';
const record={id,organizationId:id,assetId:id,assetTag:'A-1',assetName:'Pump',departmentName:null,locationName:'Plant',disposalDate:'2026-02-03',method:'SALE',reason:'Retired',proceeds:'1200.00',currency:'NGN',capitalizedCost:'1001.00',accumulatedDepreciation:'25.03',carryingAmount:'975.97',gainOrLoss:'224.03',status:'COMPLETED',requestedByEmail:'requester@example.test',submittedByEmail:'requester@example.test',submittedAt:'2026-02-02T10:00:00Z',approvedByEmail:'approver@example.test',approvedAt:'2026-02-02T11:00:00Z',rejectedBy:null,rejectedAt:null,cancelledBy:null,cancelledAt:null,completedAt:'2026-02-03T10:00:00Z',createdAt:'2026-02-02T09:00:00Z',updatedAt:'2026-02-03T10:00:00Z'};

describe('Django disposal operations view',()=>{
  beforeEach(()=>{state.role='ASSET_MANAGER';state.records=[];state.assets=[{id,tag:'A-1',name:'Pump',status:'ACTIVE'}];});
  it('provides a real active asset draft form and honest empty state for a writer',()=>{render(<BackendDisposalsView onNavigate={vi.fn()} onSelectAsset={vi.fn()}/>);expect(screen.getByRole('heading',{name:'Disposals & derecognition'})).toBeTruthy();expect(screen.getByRole('heading',{name:'Create disposal draft'})).toBeTruthy();expect(screen.getByRole('option',{name:'A-1 · Pump'})).toBeTruthy();expect(screen.getByRole('status').textContent).toContain('No disposal records');expect(screen.queryByText(/PENDING_REVIEW|IAS 16 \/ IFRS 5/)).toBeNull();});
  it('hides mutation inputs for read-only accountants and renders only authoritative financial snapshots',()=>{state.role='ACCOUNTANT';state.records=[record];render(<BackendDisposalsView onNavigate={vi.fn()} onSelectAsset={vi.fn()}/>);expect(screen.queryByRole('heading',{name:'Create disposal draft'})).toBeNull();expect(screen.getByText('NGN 975.97')).toBeTruthy();expect(screen.getByText('NGN 224.03')).toBeTruthy();expect(screen.queryByRole('button',{name:'Complete derecognition'})).toBeNull();});
});
