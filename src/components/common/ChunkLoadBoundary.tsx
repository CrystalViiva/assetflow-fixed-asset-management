import React from 'react';
import { RecoveryActions } from './RecoveryActions';

interface State { failed: boolean }

/** Keeps a stale deployment chunk from leaving the workspace as a blank screen. */
export class ChunkLoadBoundary extends React.Component<React.PropsWithChildren, State> {
  state: State = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }

  render() {
    if (this.state.failed) return <main role="alert" className="route-not-found">
      <div><p>ASSETFLOW  -  RECOVERY</p><h1>This page could not be loaded.</h1>
      <p>The application may have been updated. Return home or reload to try the latest version.</p>
      <RecoveryActions /></div>
    </main>;
    return this.props.children;
  }
}
