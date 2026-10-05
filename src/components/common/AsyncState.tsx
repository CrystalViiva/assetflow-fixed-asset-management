import { errorMessage } from '../../services/apiError';

export function LoadingState({ label = 'Loading assets…' }: { label?: string }) {
  return <div role="status" className="p-12 text-center text-slate-600"><span className="material-symbols-outlined animate-spin mr-2 align-middle" aria-hidden="true">progress_activity</span>{label}</div>;
}
export function ErrorState({ error, retry }: { error: unknown; retry?: () => void }) {
  return <div role="alert" className="m-6 p-6 rounded-xl border border-rose-200 bg-rose-50 text-rose-900">
    <p>{errorMessage(error)}</p>{retry && <button onClick={retry} className="mt-3 rounded border px-4 py-2 font-semibold">Try again</button>}
  </div>;
}
export function EmptyState({ label = 'No assets match these filters.' }: { label?: string }) {
  return <div role="status" className="p-12 text-center text-slate-600">{label}</div>;
}
export function IntegrationPending() {
  return <div className="m-6 p-8 rounded-xl border bg-white"><h1 className="text-xl font-bold">Integration pending</h1>
    <p className="mt-2 text-slate-600">Django mode connects the Asset Register and Detail, acquisition/capitalization, depreciation/accounting periods, assignments/custody and transfers. Other workflows will be connected in later milestones.</p>
    <a className="inline-block mt-4 text-[#00288e] underline" href="#all-assets">Open Asset Register</a></div>;
}
