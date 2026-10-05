import { useMutation,useQueryClient } from '@tanstack/react-query';
import { useRef } from 'react';
import { useAuth } from '../auth/AuthProvider';
import { ApiError } from './apiError';
import { assetKeys } from './assetQueries';
import { disposalKeys } from './disposalQueries';
import { disposalRepository } from './runtime';

export const disposalMutationRetry=false as const;
export function useDisposalAction(){const{user,generation,isCurrent}=useAuth();const client=useQueryClient();const lock=useRef(false);const mutation=useMutation<unknown,Error,{action:()=>Promise<unknown>;assetMayChange:boolean}>({retry:disposalMutationRetry,mutationFn:async({action})=>{if(!isCurrent(generation))throw new ApiError('authentication','Your session has ended. Please sign in again.');const result=await action();if(!isCurrent(generation))throw new ApiError('authentication','Your session has ended. Please sign in again.');return result;},onSettled:async(_data,_error,variables)=>{if(!isCurrent(generation)||user?.id===undefined)return;await Promise.all([client.invalidateQueries({queryKey:disposalKeys.scope(user.id,generation)}),...(variables?.assetMayChange?[client.invalidateQueries({queryKey:assetKeys.scope(user.id,generation)})]:[])]);}});return{pending:mutation.isPending,run:<T,>(action:()=>Promise<T>,assetMayChange=false)=>{if(lock.current)return Promise.reject(new ApiError('conflict','A disposal operation is already in progress.'));lock.current=true;return mutation.mutateAsync({action,assetMayChange}).then(value=>value as T).finally(()=>{lock.current=false;});}};}
