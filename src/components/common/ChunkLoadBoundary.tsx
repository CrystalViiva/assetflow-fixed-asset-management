import React from 'react';

interface State { failed: boolean }

/** Keeps a stale deployment chunk from leaving the workspace as a blank screen. */
export class ChunkLoadBoundary extends React.Component<React.PropsWithChildren, State> {
  state: State = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }

  render() {
    if (this.state.failed) return <section role="alert" className="route-not-found">
      <div><p>ASSETFLOW  -  RECOVERY</p><h1>This page could not be loaded.</h1>
      <p>The application may have been updated. Return home or reload to try the latest version.</p>
      <div className="mt-5 flex flex-wrap gap-3"><a href="#/" className="rounded bg-[#315ee7] px-4 py-2 text-sm font-semibold text-white">Return home</a><button type="button" onClick={() => window.location.reload()} className="rounded border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-800">Reload application</button></div></div>
    </section>;
    return this.props.children;
  }
}
