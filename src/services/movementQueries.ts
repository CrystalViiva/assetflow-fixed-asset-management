import { useQuery } from '@tanstack/react-query';
import { useAuth } from '../auth/AuthProvider';
import { movementRepository } from './runtime';
export const movementKeys={scope:(userId:number|undefined,generation:number)=>['django',userId,generation,'movements'] as const};
export function useAssignments(filters:{asset?:string;active?:boolean},enabled=true){const {user,generation}=useAuth();return useQuery({queryKey:[...movementKeys.scope(user?.id,generation),'assignments',filters],queryFn:({signal})=>movementRepository.assignments(filters,signal),enabled:!!user&&enabled});}
export function useTransfers(filters:{asset?:string;status?:string},enabled=true){const {user,generation}=useAuth();return useQuery({queryKey:[...movementKeys.scope(user?.id,generation),'transfers',filters],queryFn:({signal})=>movementRepository.transfers(filters,signal),enabled:!!user&&enabled});}
export function useCustodians(enabled=true){const {user,generation}=useAuth();return useQuery({queryKey:[...movementKeys.scope(user?.id,generation),'custodians'],queryFn:({signal})=>movementRepository.custodians(signal),enabled:!!user&&enabled,staleTime:60_000});}
