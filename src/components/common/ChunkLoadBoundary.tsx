import React from 'react';

interface State { failed: boolean }

/** Keeps a stale deployment chunk from leaving the workspace as a blank screen. */
export class ChunkLoadBoundary extends React.Component<React.PropsWithChildren, State> {
  state: State = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }

  render() {
    if (this.state.failed) return <section role="alert" className="m-5 rounded-xl border border-rose-200 bg-white p-6 text-slate-900">
      <h1 className="text-lg font-semibold">This page could not be loaded</h1>
      <p className="mt-2 text-sm text-slate-600">The application may have been updated. Reload to open the latest version.</p>
      <button type="button" onClick={() => window.location.reload()} className="mt-4 rounded bg-[#00288e] px-4 py-2 text-sm font-semibold text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-700">Reload application</button>
    </section>;
    return this.props.children;
  }
}
