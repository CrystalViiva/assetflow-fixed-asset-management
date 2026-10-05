import { useQuery } from '@tanstack/react-query';
import { useAuth } from '../auth/AuthProvider';
import { verificationRepository, queryClient } from './runtime';
import { VerificationFilters } from './verificationRepository';

export const verificationKeys={scope:(userId:number|undefined,generation:number)=>['django',userId,generation,'verification'] as const,list:(userId:number|undefined,generation:number,kind:string,filters:VerificationFilters)=>[...verificationKeys.scope(userId,generation),kind,filters] as const,detail:(userId:number|undefined,generation:number,id:string)=>[...verificationKeys.scope(userId,generation),'detail',id] as const,evidence:(userId:number|undefined,generation:number,id:string)=>[...verificationKeys.scope(userId,generation),'evidence',id] as const};
export function useVerificationCampaigns(filters:VerificationFilters){const{user,generation}=useAuth();return useQuery({queryKey:verificationKeys.list(user?.id,generation,'campaigns',filters),queryFn:({signal})=>verificationRepository.campaigns(filters,signal),enabled:!!user});}
export function useVerificationObservations(filters:VerificationFilters,enabled=true){const{user,generation}=useAuth();return useQuery({queryKey:verificationKeys.list(user?.id,generation,'observations',filters),queryFn:({signal})=>verificationRepository.observations(filters,signal),enabled:!!user&&enabled});}
export function useVerificationExceptions(filters:VerificationFilters,enabled=true){const{user,generation}=useAuth();return useQuery({queryKey:verificationKeys.list(user?.id,generation,'exceptions',filters),queryFn:({signal})=>verificationRepository.exceptions(filters,signal),enabled:!!user&&enabled});}
export function useVerificationEvidence(id:string,enabled=true){const{user,generation}=useAuth();return useQuery({queryKey:verificationKeys.evidence(user?.id,generation,id),queryFn:({signal})=>verificationRepository.evidence(id,signal),enabled:!!user&&enabled&&!!id});}
export async function invalidateVerification(userId:number,generation:number){await queryClient.invalidateQueries({queryKey:verificationKeys.scope(userId,generation)});}
