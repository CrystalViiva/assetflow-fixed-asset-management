import { useState, type FormEvent } from 'react';
import { useAuth } from '../auth/AuthProvider';
import { ApiError, errorMessage } from '../services/apiError';
import { AssetFlowLogo } from '../components/common/AssetFlowLogo';

export function LoginView({ sessionExpired = false }: { sessionExpired?: boolean }) {
  const { login } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (busy) return;
    setBusy(true); setError('');
    try { await login(email, password); }
    catch (cause) {
      setError(cause instanceof ApiError && cause.kind === 'authentication'
        ? 'Unable to sign in. Check your email and password.' : errorMessage(cause));
    } finally { setBusy(false); setPassword(''); }
  }
  return <main className="login-page min-h-screen bg-[#f8f9ff] flex items-center justify-center p-6">
    <section className="w-full max-w-md bg-white border border-slate-200 rounded-2xl shadow-xl p-8">
      <div className="flex items-center gap-3 text-[#00288e]"><AssetFlowLogo className="w-10 h-10" /><span className="text-2xl font-bold">AssetFlow</span></div>
      <h1 className="text-2xl font-semibold mt-8 text-slate-900">Sign in to your workspace</h1>
      <p className="text-sm text-slate-500 mt-2 mb-6">Manage your organization's fixed assets.</p>
      {sessionExpired && <p role="status" className="mb-5 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">Your session expired. Sign in again to continue.</p>}
      <form onSubmit={submit} className="space-y-5" aria-busy={busy}>
        <label className="block text-sm font-medium">Email<input id="login-email" name="email" type="email" autoComplete="username" required value={email} onChange={e => setEmail(e.target.value)} disabled={busy} className="login-input block mt-2 w-full border border-slate-300 rounded-lg p-3" /></label>
        <label className="block text-sm font-medium">Password<input id="login-password" name="password" type="password" autoComplete="current-password" required value={password} onChange={e => setPassword(e.target.value)} disabled={busy} className="login-input block mt-2 w-full border border-slate-300 rounded-lg p-3" /></label>
        {error && <p role="alert" aria-live="polite" className="text-sm text-rose-700">{error}</p>}
        <button type="submit" disabled={busy} className="w-full bg-[#00288e] text-white rounded-lg p-3 font-semibold disabled:opacity-60">{busy ? 'Signing in…' : 'Sign in'}</button>
      </form><div className="mt-6 flex items-center justify-between gap-4"><a href="#/" className="text-sm font-medium text-blue-800 underline-offset-2 hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-700">Back to AssetFlow</a><p className="text-right text-xs text-slate-500">Authenticated workspace</p></div>
    </section>
  </main>;
}
