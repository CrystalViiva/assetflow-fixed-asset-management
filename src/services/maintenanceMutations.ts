import { useMutation,useQueryClient } from '@tanstack/react-query';
import { useRef } from 'react';
import { useAuth } from '../auth/AuthProvider';
import { ApiError } from './apiError';
import { invalidateMaintenance,MaintenanceArea } from './maintenanceQueries';
import { maintenanceRepository } from './runtime';

export const maintenanceMutationRetry=false as const;
export function useMaintenanceAction(defaultAssetId?:string){const{user,generation,isCurrent}=useAuth();const client=useQueryClient();const locked=useRef(false);const mutation=useMutation<unknown,Error,{action:()=>Promise<unknown>;assetId?:string;areas:MaintenanceArea[]}>({retry:maintenanceMutationRetry,mutationFn:async({action})=>{if(!isCurrent(generation))throw new ApiError('authentication','Your session has ended. Please sign in again.');const result=await action();if(!isCurrent(generation))throw new ApiError('authentication','Your session has ended. Please sign in again.');return result;},onSettled:async(_data,_error,variables)=>{if(isCurrent(generation))await invalidateMaintenance(client,user?.id,generation,variables?.areas??['work-orders'],variables?.assetId??defaultAssetId);}});return{pending:mutation.isPending,error:mutation.error,run:<T,>(action:()=>Promise<T>,assetId?:string,areas:MaintenanceArea[]=['work-orders'])=>{if(locked.current)return Promise.reject(new ApiError('conflict','A maintenance operation is already in progress.'));locked.current=true;return mutation.mutateAsync({action,assetId,areas}).then(value=>value as T).finally(()=>{locked.current=false;});}};}
export { maintenanceRepository };
