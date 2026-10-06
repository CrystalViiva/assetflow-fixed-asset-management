import {afterEach,expect,it,vi} from 'vitest';
import {fireEvent,render,screen} from '@testing-library/react';
import {QueryClient,QueryClientProvider} from '@tanstack/react-query';
import {AuthProvider} from '../auth/AuthProvider';
import {Session} from '../services/session';
import {apiClient} from '../services/runtime';
import {BackendOrganizationAdminView} from './BackendOrganizationAdminView';

const org='22222222-2222-4222-8222-222222222222',dept='11111111-1111-4111-8111-111111111111',now='2026-10-06T10:00:00Z';
const empty={count:0,next:null,previous:null,results:[]};
function ref(id:string,name:string,code:string){return{id,organization_id:org,name,code,is_active:true,created_at:now,updated_at:now};}
async function setup(role:string){
 const client=new QueryClient({defaultOptions:{queries:{retry:false,gcTime:0}}}),fetcher=vi.fn<typeof fetch>();vi.stubGlobal('fetch',fetcher);
 const session=new Session(apiClient,{getItem:()=>null,setItem:()=>{},removeItem:()=>{}},()=>client.clear());
 await session.initialize();
 fetcher.mockResolvedValueOnce(Response.json({access:'access',refresh:'refresh'})).mockResolvedValueOnce(Response.json({id:7,email:'admin@example.test',role}));
 await session.login('admin@example.test','A-test-password');fetcher.mockReset();return{client,session,fetcher};
}
function renderView(client:QueryClient,session:Session,section:'departments'|'locations'|'users'){
 return render(<QueryClientProvider client={client}><AuthProvider value={session}><BackendOrganizationAdminView section={section}/></AuthProvider></QueryClientProvider>);
}
afterEach(()=>vi.unstubAllGlobals());
it('loads authoritative department rows in Django mode and creates without organization override',async()=>{
 const c=await setup('ADMIN');const rows={...empty,count:1,results:[ref(dept,'Finance','FIN')]};
 c.fetcher.mockImplementation(async(input,init)=>{const url=String(input);if(url.includes('/admin/departments/')&&init?.method==='POST')return Response.json(ref('33333333-3333-4333-8333-333333333333','Operations','OPS'),{status:201});if(url.includes('/admin/departments/'))return Response.json(rows);return Response.json(empty);});
 renderView(c.client,c.session,'departments');expect((await screen.findAllByText('Finance')).length).toBeGreaterThan(0);expect(screen.getByText(/1 records/)).toBeTruthy();
 fireEvent.change(screen.getByLabelText('Name'),{target:{value:'Operations'}});fireEvent.change(screen.getByLabelText('Code'),{target:{value:'OPS'}});fireEvent.click(screen.getByRole('button',{name:'Create department'}));
 expect(await screen.findByText(/Django has recorded/)).toBeTruthy();const write=c.fetcher.mock.calls.find(call=>String(call[0]).includes('/admin/departments/')&&((call[1] as RequestInit|undefined)?.method==='POST'))!;
 expect(JSON.parse(String((write[1] as RequestInit).body))).toEqual({name:'Operations',code:'OPS',is_active:true});
});
it('keeps administration server-gated for an employee without falling back to mock records',async()=>{
 const c=await setup('EMPLOYEE');renderView(c.client,c.session,'users');expect(await screen.findByRole('status')).toHaveProperty('textContent',expect.stringContaining('current role does not have access'));
 expect(c.fetcher.mock.calls.some(call=>String(call[0]).includes('/admin/'))).toBe(false);expect(screen.queryByText('Babajide Adeleke')).toBeNull();
});
it('keeps an initial password out of TanStack mutation/query state',async()=>{
 const c=await setup('ADMIN');const department=ref(dept,'Finance','FIN');
 const ownUser={id:7,email:'admin@example.test',role:'ADMIN',department_id:null,department_name:null,is_active:true,created_at:now,last_login:null};
 const created={...ownUser,id:8,email:'new.user@example.test',role:'EMPLOYEE',department_id:dept,department_name:'Finance'};
 c.fetcher.mockImplementation(async(input,init)=>{const url=String(input);if(url.endsWith('/departments/'))return Response.json({count:1,next:null,previous:null,results:[department]});if(url.includes('/admin/users/')&&init?.method==='POST')return Response.json(created,{status:201});if(url.includes('/admin/users/'))return Response.json({count:1,next:null,previous:null,results:[ownUser]});return Response.json(empty);});
 renderView(c.client,c.session,'users');await screen.findByText('admin@example.test');
 fireEvent.change(screen.getByLabelText('Email'),{target:{value:'new.user@example.test'}});fireEvent.change(screen.getByLabelText('Initial password'),{target:{value:'Secure-initial-password-2026!'}});fireEvent.click(screen.getByRole('button',{name:'Create user'}));
 expect(await screen.findByText(/User created/)).toBeTruthy();expect(JSON.stringify(c.client.getMutationCache().getAll()).includes('Secure-initial-password-2026!')).toBe(false);expect(screen.getByLabelText('Initial password')).toHaveProperty('value','');
});
