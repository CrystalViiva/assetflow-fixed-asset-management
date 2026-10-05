import { useMutation,useQueryClient } from '@tanstack/react-query';
import { useAuth } from '../auth/AuthProvider';
import { ApiError } from './apiError';
import { movementRepository } from './runtime';
import { assetKeys } from './assetQueries';
import { movementKeys } from './movementQueries';

export const movementMutationRetry = false as const;
export function useMovementAction(resource:'assignments'|'transfers'){const {user,generation,isCurrent}=useAuth();const client=useQueryClient();const scope=movementKeys.scope(user?.id,generation);const mutate=useMutation({retry:movementMutationRetry,mutationFn:async(variables:{action:()=>Promise<unknown>;assetPlacementChanged:boolean})=>{if(!isCurrent(generation))throw new ApiError('authentication','Your session has ended. Please sign in again.');const result=await variables.action();if(!isCurrent(generation))throw new ApiError('authentication','Your session has ended. Please sign in again.');return result;},onSettled:async(_data,_error,variables)=>{if(!isCurrent(generation)||user?.id===undefined)return;await Promise.all([client.invalidateQueries({queryKey:[...scope,resource]}),...(variables?.assetPlacementChanged?[client.invalidateQueries({queryKey:assetKeys.scope(user.id,generation)})]:[])]);}});return {pending:mutate.isPending,error:mutate.error,run:(action:()=>Promise<unknown>,assetPlacementChanged=false)=>mutate.mutateAsync({action,assetPlacementChanged})};}
