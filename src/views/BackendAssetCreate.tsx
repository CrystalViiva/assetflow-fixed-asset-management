import { useEffect, useId, useState, type ReactNode } from 'react';
import { useAuth } from '../auth/AuthProvider';
import { ReferenceSelect } from '../components/common/ReferenceSelect';
import { AcquisitionForm, createAcquisitionDto, emptyAcquisitionForm, formErrors, normalizedCosts } from '../services/acquisitionForm';
import { canManageAssets, useAcquisitionWorkflow } from '../services/acquisitionQueries';
import { useCategories } from '../services/referenceQueries';
import { errorMessage } from '../services/apiError';
import { formatDecimal } from '../services/assetDtos';
import { sumMoney } from '../services/money';

function Section({ number, title, children, disabled }: { number: number; title: string; children: ReactNode; disabled?: boolean }) {
  return <fieldset disabled={disabled} className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
    <legend className="sr-only">{title}</legend><div className="px-5 py-3.5 bg-[#eff4ff] flex items-center gap-3 border-b border-slate-200">
      <span aria-hidden="true" className="w-6 h-6 rounded-full bg-[#00288e] text-white text-xs flex items-center justify-center">{number}</span><h2 className="font-semibold text-slate-900">{title}</h2>
    </div><div className="p-5 grid grid-cols-1 md:grid-cols-2 gap-4">{children}</div>
  </fieldset>;
}

export function BackendAssetCreate({ onNavigate, resumeAssetId }: { onNavigate: (route: string) => void; resumeAssetId?: string }) {
  const { role } = useAuth();
  const { workflow, state, run } = useAcquisitionWorkflow();
  const categories = useCategories();
  const [form, setForm] = useState<AcquisitionForm>({ ...emptyAcquisitionForm });
  const prefix = useId();
  const errors = formErrors(state.error);
  const set = (field: keyof AcquisitionForm, value: string) => setForm(current => ({ ...current, [field]: value }));
  useEffect(() => { if (resumeAssetId && canManageAssets(role)) run(() => workflow.resumeById(resumeAssetId)); }, [resumeAssetId, workflow]);
  useEffect(() => {
    const asset = state.asset;
    if (asset) setForm(current => ({ ...current, tag: asset.tag, name: asset.name, description: asset.description,
      categoryId: asset.category.id, departmentId: asset.department?.id || '', locationId: asset.location?.id || '',
      manufacturer: asset.manufacturer, serialNumber: asset.serialNumber, model: asset.model,
      acquisitionDate: asset.acquisitionDate || current.acquisitionDate, capitalizationDate: asset.capitalizationDate || current.capitalizationDate,
      availableForUseDate: asset.availableForUseDate || '', residualValue: asset.residualValue,
      usefulLifeMonths: asset.usefulLifeMonths === null ? current.usefulLifeMonths : String(asset.usefulLifeMonths), depreciationMethod: asset.depreciationMethod }));
  }, [state.asset?.id]);
  useEffect(() => {
    const acquisition = state.acquisition;
    if (acquisition) setForm(current => ({ ...current, ...acquisition.costs, vendor: acquisition.vendor, invoice: acquisition.invoice,
      reference: acquisition.reference, notes: acquisition.notes, acquisitionDate: acquisition.acquisitionDate,
      capitalizationDate: acquisition.capitalizationDate || current.capitalizationDate }));
  }, [state.acquisition]);

  if (!canManageAssets(role)) return <div role="alert" className="m-6 p-6 bg-white border rounded-xl">Asset creation and capitalization require an Administrator or Asset Manager role.</div>;
  const frozen = !!state.asset;
  const finished = state.phase === 'capitalized';
  const draft = !state.asset || ['DRAFT', 'PENDING_CAPITALIZATION'].includes(state.asset.status);
  const unsupportedPolicy = frozen && form.depreciationMethod !== 'SLM';
  const locked = state.busy || !!state.uncertain || state.phase === 'review-existing' || finished || !draft || unsupportedPolicy;
  let acquisitionMatchesForm = false;
  if (state.asset && state.acquisition) {
    try {
      const dto = createAcquisitionDto(form, state.asset.id);
      acquisitionMatchesForm = dto.asset_id === state.acquisition.assetId && dto.acquisition_date === state.acquisition.acquisitionDate &&
        dto.capitalization_date === state.acquisition.capitalizationDate && dto.purchase_price === state.acquisition.costs.purchase &&
        dto.freight_cost === state.acquisition.costs.freight && dto.installation_cost === state.acquisition.costs.installation &&
        dto.civil_works_cost === state.acquisition.costs.civil && dto.other_capitalizable_cost === state.acquisition.costs.other &&
        dto.vendor_name === state.acquisition.vendor && dto.invoice_number === state.acquisition.invoice &&
        dto.reference === state.acquisition.reference && dto.notes === state.acquisition.notes;
    } catch { acquisitionMatchesForm = false; }
  }
  let preview: string | null = null;
  try { preview = sumMoney(Object.values(normalizedCosts(form))); } catch { /* Invalid editable input has no fabricated total. */ }
  const input = (key: keyof AcquisitionForm, label: string, options: { type?: string; disabled?: boolean; required?: boolean; maxLength?: number } = {}) => {
    const id = `${prefix}-${key}`;
    return <div key={key}><label htmlFor={id} className="block text-xs font-semibold text-slate-600 mb-1">{label}{options.required ? ' *' : ''}</label>
      <input id={id} type={options.type || 'text'} inputMode={['purchase','freight','installation','civil','other','residualValue'].includes(key) ? 'decimal' : undefined}
        value={form[key]} onChange={event => set(key, event.target.value)} disabled={options.disabled} required={options.required} maxLength={options.maxLength}
        aria-invalid={!!errors[key]} aria-describedby={errors[key] ? `${id}-error` : undefined}
        className="w-full rounded-md border border-slate-300 p-2 text-sm bg-[#eff4ff]/40 disabled:bg-slate-100 disabled:text-slate-500" />
      {errors[key] && <p id={`${id}-error`} className="text-xs text-rose-700 mt-1">{errors[key].join(' ')}</p>}
    </div>;
  };
  const save = () => { if (state.phase === 'editing') run(() => workflow.create(form)); else run(() => workflow.record(form)); };
  return <section className="w-full p-4 md:p-6 space-y-5">
    <div className="bg-white border rounded-xl p-5"><button className="text-sm text-[#00288e] underline" onClick={() => onNavigate('all-assets')}>Back to Asset Register</button>
      <h1 className="text-2xl font-bold text-slate-900 mt-3">Register Fixed Asset</h1><p className="text-sm text-slate-500 mt-1">Django · Draft asset → Acquisition cost buildup → Capitalization</p></div>
    {state.notice && <p role="status" className="p-4 rounded-lg border bg-blue-50 text-blue-900">{state.notice}</p>}
    {unsupportedPolicy && !finished && <p role="alert" className="p-4 rounded-lg border bg-amber-50 text-amber-900">This saved asset uses {form.depreciationMethod}; F2 capitalization supports SLM only. The existing asset is unchanged, and this workflow is disabled.</p>}
    {!!state.error && <div role="alert" className="p-4 bg-rose-50 border border-rose-200 rounded-lg text-rose-900"><p>{errorMessage(state.error)}</p>
      <ul className="mt-2 list-disc pl-5 text-sm">{Object.entries(errors).map(([field, messages]) => <li key={field}>{messages.join(' ')}</li>)}</ul></div>}
    {state.uncertain && <div role="alert" className="p-4 bg-amber-50 border rounded-lg">The {state.uncertain} request may have committed. Do not submit again until the saved state has been checked.
      <button type="button" disabled={state.busy} onClick={() => run(workflow.reconcile)} className="block mt-3 underline font-semibold">Check saved state</button></div>}
    {state.phase === 'review-existing' && state.asset && <div className="p-5 bg-white border rounded-xl"><h2 className="font-bold">Review existing asset</h2>
      <p>{state.asset.tag} — {state.asset.name} · {state.asset.category.name} · {state.asset.status}</p><p className="text-xs mt-2">UUID: {state.asset.id}</p>
      <button type="button" disabled={state.busy} onClick={() => run(workflow.acceptExisting)} className="mt-3 bg-[#00288e] text-white p-2 rounded">Resume this asset</button></div>}
    {finished ? <div className="p-6 bg-emerald-50 border rounded-xl"><h2 className="text-xl font-bold">Asset capitalized</h2>
      <p className="mt-2">{state.asset?.tag} · {state.acquisition?.currency} {state.acquisition && formatDecimal(state.acquisition.totalCost)} · {state.acquisition?.capitalizationDate}</p>
      <button className="mt-4 bg-[#00288e] text-white rounded px-4 py-2" onClick={() => onNavigate(`asset-detail/${state.asset?.id}`)}>Open asset detail</button>
      {!!state.error && <button className="ml-3 underline" disabled={state.busy} onClick={() => run(workflow.reconcile)}>Refresh saved state</button>}</div> :
    <form noValidate aria-busy={state.busy} onSubmit={event => { event.preventDefault(); if (!locked) save(); }} className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
      <div className="lg:col-span-8 space-y-6">
        <Section number={1} title="Basic Information & Identification" disabled={locked || frozen}>
          {input('name','Asset name',{ required: true, maxLength: 200 })}{input('tag','Asset tag',{ required: true, disabled: !!state.reservedTag, maxLength:64 })}
          <ReferenceSelect kind="categories" label="Category" required activeOnly value={form.categoryId} error={errors.categoryId?.join(' ')} onChange={value => {
            const category = categories.data?.find(row => row.id === value); setForm(current => ({ ...current, categoryId:value, usefulLifeMonths:category ? String(category.usefulLifeMonths) : current.usefulLifeMonths, depreciationMethod:'SLM' }));
          }} />
          {input('manufacturer','Manufacturer',{ maxLength:160 })}{input('model','Model',{ maxLength:128 })}{input('serialNumber','Serial number',{ maxLength:128 })}{input('description','Description')}
        </Section>
        <Section number={2} title="Organizational Placement" disabled={locked || frozen}>
          <ReferenceSelect kind="departments" label="Department" activeOnly value={form.departmentId} error={errors.departmentId?.join(' ')} onChange={value => set('departmentId',value)} />
          <ReferenceSelect kind="locations" label="Location" activeOnly value={form.locationId} error={errors.locationId?.join(' ')} onChange={value => set('locationId',value)} />
        </Section>
        <Section number={3} title="Acquisition & Capitalizable Cost" disabled={locked}>
          {input('vendor','Vendor',{ maxLength:200 })}{input('invoice','Invoice number',{ maxLength:128 })}{input('reference','Reference',{ maxLength:128 })}{input('notes','Acquisition notes')}
          {input('acquisitionDate','Acquisition date',{ type:'date', required:true, disabled:frozen })}{input('capitalizationDate','Capitalization date',{ type:'date' })}
          <p className="text-xs text-slate-500 md:col-span-2">Capitalization date may be recorded later; it must be saved before capitalizing. Available-for-use date must be on or after it.</p>
          {input('purchase','Purchase price',{ required:true })}{input('freight','Freight / haulage')}{input('installation','Installation')}{input('civil','Civil works')}{input('other','Other directly attributable costs')}
          <p className="text-xs text-slate-500 md:col-span-2">Enter plain decimal amounts, without commas, currency symbols or exponent notation. Blank optional costs mean zero. Currency defaults to the organization's backend currency.</p>
        </Section>
        <Section number={4} title="Accounting Policy" disabled={locked || frozen}>
          {input('residualValue','Residual value',{ required:true })}{input('usefulLifeMonths','Useful life (months)',{ required:true })}
          {input('availableForUseDate','Available-for-use date',{ type:'date' })}
          <div><span className="text-xs font-semibold text-slate-600">Depreciation method</span><p className="mt-2 text-sm">Straight Line (SLM)</p><p className="text-xs text-slate-500">Only SLM calculations are supported. No depreciation is calculated or posted by this workflow.</p></div>
        </Section>
      </div>
      <aside className="lg:col-span-4 bg-white border rounded-xl p-5 space-y-4 lg:sticky lg:top-16">
        <h2 className="font-bold text-lg">Capitalization ledger</h2><p className="text-sm">Step: {state.phase.replaceAll('-',' ')}</p>
        <p className="text-xs text-slate-500">Each step commits separately. Saved drafts remain if a later step fails. Resume by asset tag or from Asset Detail after leaving this page.</p>
        <div><p className="text-xs uppercase text-slate-500">Exact cost preview</p><p className="font-mono text-xl mt-1">{preview ? formatDecimal(preview) : '—'}</p><p className="text-xs text-slate-500 mt-1">Backend calculates and stores the authoritative total.</p></div>
        {state.acquisition && <div className="p-3 bg-blue-50 rounded"><p className="text-xs">Saved backend total</p><p className="font-mono font-bold">{state.acquisition.currency} {formatDecimal(state.acquisition.totalCost)}</p><p className="text-xs mt-1">{state.acquisition.status}</p></div>}
        {!draft && <p role="alert">This asset is not in a draft lifecycle state. It cannot receive a new acquisition or be capitalized here.</p>}
        <button type="submit" disabled={locked} className="w-full px-4 py-3 bg-[#00288e] text-white font-semibold rounded-lg disabled:opacity-40">{state.busy ? 'Saving…' : state.phase === 'editing' ? 'Create draft asset' : state.acquisition ? 'Save acquisition changes' : 'Record acquisition'}</button>
        {state.phase === 'acquisition-recorded' && <button type="button" disabled={locked || !acquisitionMatchesForm || !state.acquisition?.capitalizationDate} onClick={() => run(workflow.capitalize)} className="w-full px-4 py-3 bg-emerald-700 text-white rounded-lg disabled:opacity-40">Capitalize saved acquisition</button>}
        {state.acquisition && <p className="text-xs text-slate-600">Capitalization uses the saved acquisition. {acquisitionMatchesForm ? 'Saved values match the form.' : 'Save valid edits before capitalizing.'}</p>}
        {state.phase === 'editing' && <button type="button" disabled={state.busy || !!state.uncertain || !form.tag.trim()} className="w-full underline text-sm" onClick={() => run(() => workflow.findExisting(form.tag))}>Find existing asset by tag</button>}
        {state.asset && <button type="button" disabled={state.busy} className="w-full underline text-sm" onClick={() => run(workflow.reconcile)}>Reload saved state</button>}
      </aside>
    </form>}
  </section>;
}
