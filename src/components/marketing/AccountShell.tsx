import type { ReactNode } from 'react';
import { AssetFlowLogo } from '../common/AssetFlowLogo';

export function AccountShell({ title, children, login = false }: { title: string; children: ReactNode; login?: boolean }) {
  return <main className="auth-page"><div className="auth-layout">
    <aside className="auth-intro">
      <a href="#/" className="auth-brand" aria-label="AssetFlow home"><AssetFlowLogo className="h-10 w-10" /><span>AssetFlow</span></a>
      <p className="auth-eyebrow">FIXED ASSET MANAGEMENT</p>
      <p className="auth-statement">Keep every record<br />in context.</p>
      <p className="auth-intro-copy">A clear view of asset value, custody, and the work behind each change.</p>
      <p className="auth-intro-rule"><span /> For finance and operations teams</p>
    </aside>
    <section className="auth-card" aria-labelledby="account-heading">
      <a href="#/" className="auth-mobile-brand" aria-label="AssetFlow home"><AssetFlowLogo className="h-8 w-8" />AssetFlow</a>
      <p className="auth-card-kicker">YOUR ASSETFLOW ACCOUNT</p>
      <h1 id="account-heading">{title}</h1>
      {children}
      <nav className="auth-links" aria-label="Account navigation">
        {!login && <a href="#login">Sign in</a>}
        <a href="#/">Back to AssetFlow</a>
        {login && <a href="#get-started">Set up a workspace</a>}
      </nav>
    </section>
  </div></main>;
}
