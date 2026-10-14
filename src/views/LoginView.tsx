import { useState, type FormEvent } from 'react';
import { Eye, EyeOff } from 'lucide-react';
import { useAuth } from '../auth/AuthProvider';
import { ApiError, errorMessage } from '../services/apiError';
import { AccountShell } from './IdentityViews';

export function LoginView({ sessionExpired = false }: { sessionExpired?: boolean }) {
  const { login } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
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
  return <AccountShell title="Sign in to your workspace">
    <p className="auth-description">Manage your organization's fixed assets.</p>
    {sessionExpired && <p role="status" className="auth-feedback auth-feedback-warning">Your session expired. Sign in again to continue.</p>}
    <form onSubmit={submit} className="auth-form" aria-busy={busy}>
      <label>Email<input id="login-email" name="email" type="email" autoComplete="username" required value={email} onChange={e => setEmail(e.target.value)} disabled={busy} /></label>
      <label htmlFor="login-password">Password</label><span className="auth-password-wrap"><input id="login-password" name="password" type={showPassword ? 'text' : 'password'} autoComplete="current-password" required value={password} onChange={e => setPassword(e.target.value)} disabled={busy} /><button type="button" className="auth-password-toggle" aria-label={showPassword ? 'Hide password' : 'Show password'} aria-pressed={showPassword} onClick={() => setShowPassword(value => !value)} disabled={busy}>{showPassword ? <EyeOff size={17} /> : <Eye size={17} />}</button></span>
      {error && <p role="alert" aria-live="polite" className="auth-feedback auth-feedback-error">{error}</p>}
      <button type="submit" disabled={busy}>{busy ? 'Signing in...' : 'Sign in'}</button>
    </form>
    <a href="#forgot-password" className="auth-recovery-link">Forgot password?</a>
    <p className="auth-privacy-note">Your organization access is checked by the AssetFlow service.</p>
  </AccountShell>;
}
