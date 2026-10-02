import { useCategories } from '../services/referenceQueries';
import { ErrorState, LoadingState } from '../components/common/AsyncState';
import { formatDecimal } from '../services/assetDtos';

export function BackendCategories() {
  const result = useCategories();
  if (result.isPending) return <LoadingState label="Loading asset categories…" />;
  if (result.isError) return <ErrorState error={result.error} retry={() => void result.refetch()} />;
  return <section className="p-6 space-y-5"><h1 className="text-2xl font-bold">Asset Categories & Classification</h1>
    <p className="text-sm text-slate-500">Django · Category accounting defaults · Read only</p>
    {!result.data.length && <p role="status">No categories available.</p>}
    <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">{result.data.map(category => <article key={category.id} className="p-5 bg-white border rounded-xl space-y-3">
      <div className="flex justify-between text-xs"><span className="font-mono text-blue-800">{category.code}</span><span>{category.active ? 'Active' : 'Inactive'}</span></div>
      <h2 className="font-bold text-lg">{category.name}</h2><p className="text-sm text-slate-500">{category.description || 'No description provided.'}</p>
      <dl className="text-sm space-y-2"><div><dt>Default useful life</dt><dd>{category.usefulLifeMonths} months</dd></div><div><dt>Default depreciation method</dt><dd>{category.depreciationMethod}{category.depreciationMethod !== 'SLM' ? ' — calculations not supported' : ''}</dd></div>
        <div><dt>Capitalization threshold</dt><dd className="font-mono">{formatDecimal(category.capitalizationThreshold)}</dd></div></dl>
    </article>)}</div>
  </section>;
}
