import { useQuery } from '@tanstack/react-query';
import { useAuth } from '../auth/AuthProvider';
import { disposalRepository } from './runtime';

export const disposalKeys={scope:(userId:number|undefined,generation:number)=>['django',userId,generation,'disposals'] as const,list:(userId:number|undefined,generation:number,filters:object)=>[...disposalKeys.scope(userId,generation),'list',filters] as const,detail:(userId:number|undefined,generation:number,id:string)=>[...disposalKeys.scope(userId,generation),'detail',id] as const};
export function useDisposals(filters:{page:number;pageSize:number;asset?:string;status?:string;disposal_method?:string;search?:string;ordering?:string;department?:string;location?:string},enabled=true){const{user,generation}=useAuth();return useQuery({queryKey:disposalKeys.list(user?.id,generation,filters),queryFn:({signal})=>disposalRepository.list(filters,signal),enabled:!!user&&enabled});}
export function useDisposal(id:string,enabled=true){const{user,generation}=useAuth();return useQuery({queryKey:disposalKeys.detail(user?.id,generation,id),queryFn:({signal})=>disposalRepository.get(id,signal),enabled:!!user&&enabled&&!!id});}
