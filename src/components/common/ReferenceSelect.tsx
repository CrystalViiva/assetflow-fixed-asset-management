import { useId } from 'react';
import { ReferenceKind } from '../../services/assetDtos';
import { useReferences } from '../../services/referenceQueries';
import { errorMessage } from '../../services/apiError';

export function ReferenceSelect({ kind, label, value, onChange, disabled = false, required = false, activeOnly = false, error }: {
  kind: ReferenceKind; label: string; value: string; onChange: (value: string) => void;
  disabled?: boolean; required?: boolean; activeOnly?: boolean; error?: string;
}) {
  const id = useId();
  const result = useReferences(kind);
  const choices = result.data || [];
  const available = choices.filter(row => !activeOnly || row.active);
  const unavailable = value && !available.some(row => row.id === value);
  return <div className="space-y-1">
    <label htmlFor={id} className="block text-xs font-semibold text-slate-600">{label}{required ? ' *' : ''}</label>
    <select id={id} value={value} onChange={event => onChange(event.target.value)} required={required}
      disabled={disabled || result.isPending || result.isError} aria-invalid={!!error} aria-describedby={`${id}-help`}
      className="w-full rounded-md border border-slate-300 bg-white p-2 text-sm disabled:bg-slate-100 disabled:text-slate-500">
      <option value="">{result.isPending ? 'Loading choices…' : required ? 'Choose…' : 'All / not assigned'}</option>
      {unavailable && !choices.some(row => row.id === value) && <option value={value} disabled>Unavailable reference ({value})</option>}
      {choices.filter(row => !activeOnly || row.active || row.id === value).map(row => <option key={row.id} value={row.id} disabled={activeOnly && !row.active}>{row.name} ({row.code}){row.active ? '' : ' — inactive'}</option>)}
    </select>
    <div id={`${id}-help`} className="text-xs">
      {result.isError ? <div role="alert" className="text-rose-700">{errorMessage(result.error)} <button type="button" className="underline" disabled={disabled} onClick={() => void result.refetch()}>Reload {label.toLowerCase()}</button></div>
        : result.isPending ? <span role="status">Loading {label.toLowerCase()}…</span>
          : !available.length ? <span role="status">No {activeOnly ? 'active ' : ''}{kind} available.</span> : null}
      {error && <p className="text-rose-700">{error}</p>}
    </div>
  </div>;
}
