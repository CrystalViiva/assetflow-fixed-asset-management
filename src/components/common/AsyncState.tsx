import { ApiError, errorMessage } from '../../services/apiError';

export function LoadingState({ label = 'Loading assets…' }: { label?: string }) {
  return <div role="status" className="p-12 text-center text-slate-600"><span className="material-symbols-outlined animate-spin mr-2 align-middle" aria-hidden="true">progress_activity</span>{label}</div>;
}
export function ErrorState({ error, retry }: { error: unknown; retry?: () => void }) {
  if (error instanceof ApiError && error.kind === 'authorization') return <div role="alert" className="m-6 p-6 rounded-xl border border-amber-200 bg-amber-50 text-amber-950">
    <p>You don’t have access to this area.</p><a href="#all-assets" className="mt-3 inline-block font-semibold underline">Open Asset Register</a>
  </div>;
  return <div role="alert" className="m-6 p-6 rounded-xl border border-rose-200 bg-rose-50 text-rose-900">
    <p>{errorMessage(error)}</p>{retry && <button onClick={retry} className="mt-3 rounded border px-4 py-2 font-semibold">Try again</button>}
  </div>;
}
export function EmptyState({ label = 'No assets match these filters.' }: { label?: string }) {
  return <div role="status" className="p-12 text-center text-slate-600">{label}</div>;
}
export function IntegrationPending() {
  return <div className="m-6 rounded-xl border bg-white p-8"><h1 className="text-xl font-bold">This route is unavailable</h1>
    <p className="mt-2 text-slate-600">The current application configuration does not provide this workflow. No demonstration data is substituted in Django mode.</p>
    <a className="inline-block mt-4 text-[#00288e] underline" href="#all-assets">Open Asset Register</a></div>;
}
