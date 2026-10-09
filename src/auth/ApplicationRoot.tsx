import { lazy, Suspense, useEffect, useState } from 'react';
import { QueryClientProvider } from '@tanstack/react-query';
import { AuthProvider, useAuth } from './AuthProvider';
import { queryClient } from '../services/authRuntime';
import { dataSource } from '../services/config';
import { LoadingState } from '../components/common/AsyncState';
import { ChunkLoadBoundary } from '../components/common/ChunkLoadBoundary';
import { LoginView } from '../views/LoginView';
import { PublicLandingPage } from '../views/PublicLandingPage';
import { IdentityView } from '../views/IdentityViews';
import { MarketingPage, marketingRoutes } from '../views/MarketingPages';
import { SignupView } from '../views/SaasViews';
import { PlatformView } from '../views/PlatformView';
const App = lazy(() => import('../App'));

const privateRoutes = new Set(['dashboard','all-assets','asset-categories','acquisitions','depreciation','assignments','transfers','maintenance','disposals','verification','assurance','reports','audit-log','departments','locations','users-and-roles','asset-create']);
const landingSections = new Set(['capabilities','controls','architecture']);
privateRoutes.add('settings');
privateRoutes.add('billing');
privateRoutes.add('onboarding');
privateRoutes.add('platform');
const identityRoutes = new Set(['forgot-password', 'reset-password', 'accept-invitation']);

/** Only application-owned hash routes are valid post-login destinations. */
export function safeReturnRoute(value: string | null | undefined): string | null {
  if (!value || value.length > 240 || value.startsWith('/') || value.startsWith('//') || /[\\\u0000-\u001f]/.test(value)) return null;
  if (/^[a-z][a-z\d+.-]*:/i.test(value) || value.includes('#')) return null;
  const [route, ...rest] = value.split('?');
  if (rest.length || route === 'login' || route === '' || route === 'index.html') return null;
  if (privateRoutes.has(route)) return route;
  if (/^asset-detail\/[A-Za-z0-9_-]{1,120}$/.test(route)) return route;
  if (/^asset-create\/[A-Za-z0-9_-]{1,120}$/.test(route)) return route;
  return null;
}

function hashPath() { return window.location.hash.slice(1); }
function navigate(route: string) { window.location.hash = route ? `#${route}` : '#/'; }
function LoginRoute() {
  const { authenticated, initializing, user } = useAuth();
  const params = new URLSearchParams(hashPath().split('?')[1] ?? '');
  const destination = user?.isPlatformOperator ? 'platform' : safeReturnRoute(params.get('next')) ?? 'dashboard';
  useEffect(() => { if (!initializing && authenticated) navigate(destination); }, [initializing, authenticated, destination]);
  if (initializing) return <LoadingState label="Restoring your session…" />;
  if (authenticated) return <LoadingState label="Opening your workspace…" />;
  return <LoginView sessionExpired={params.get('expired') === '1'} />;
}

export function DjangoRoutes() {
  const auth = useAuth();
  const [path, setPath] = useState(hashPath());
  useEffect(() => { const update = () => setPath(hashPath()); window.addEventListener('hashchange', update); return () => window.removeEventListener('hashchange', update); }, []);
  const route = path.split('?')[0];
  const publicRoot = route === '' || route === '/' || landingSections.has(route);
  const loginRoute = route === 'login';
  const identityRoute = identityRoutes.has(route);
  const marketingRoute = marketingRoutes.has(route);
  const signupRoute = route === 'signup' || route === 'verify-email';
  const returnRoute = safeReturnRoute(route);
  const loginDestination = safeReturnRoute(new URLSearchParams(path.split('?')[1] ?? '').get('next')) ?? 'dashboard';
  useEffect(() => {
    if (identityRoute || marketingRoute || signupRoute) return;
    if (auth.initializing) return;
    if (auth.authenticated) {
      if (publicRoot) navigate(auth.user?.isPlatformOperator ? 'platform' : 'dashboard');
      else if (loginRoute) navigate(auth.user?.isPlatformOperator ? 'platform' : loginDestination);
      else if (!returnRoute) navigate('dashboard');
      return;
    }
    if (auth.error === 'signed-out' && !publicRoot && !loginRoute) { navigate(''); return; }
    if (!publicRoot && !loginRoute) {
      const next = returnRoute ?? 'dashboard';
      const expired = auth.error ? '&expired=1' : '';
      navigate(`login?next=${encodeURIComponent(next)}${expired}`);
    }
  }, [auth.initializing, auth.authenticated, auth.error, auth.user?.isPlatformOperator, publicRoot, loginRoute, loginDestination, returnRoute, identityRoute, marketingRoute, signupRoute]);

  if (identityRoute) return <IdentityView key={route} route={route} />;
  if (marketingRoute) return <MarketingPage key={route} route={route} />;
  if (signupRoute) return <SignupView key={route} verify={route === 'verify-email'} />;
  if (publicRoot && (!auth.authenticated || auth.initializing)) return <PublicLandingPage authenticated={auth.authenticated} />;
  if (auth.initializing) return <LoadingState label="Restoring your session…" />;
  if (loginRoute && !auth.authenticated) return <LoginRoute />;
  if (!auth.authenticated) return <LoadingState label="Opening sign in…" />;
  if (route === 'platform') return <PlatformView />;
  if (loginRoute || publicRoot || !returnRoute) return <LoadingState label="Opening your workspace…" />;
  return <ChunkLoadBoundary><Suspense fallback={<LoadingState label="Opening your workspace…" />}><App key={`${auth.user?.id}:${auth.generation}`} /></Suspense></ChunkLoadBoundary>;
}

function MockRoutes() {
  const [path, setPath] = useState(hashPath());
  useEffect(() => { const update = () => setPath(hashPath()); window.addEventListener('hashchange', update); return () => window.removeEventListener('hashchange', update); }, []);
  if (!path || path === '/' || landingSections.has(path)) return <PublicLandingPage authenticated={false} mockMode />;
  if (marketingRoutes.has(path)) return <MarketingPage route={path} />;
  if (path === 'signup' || path === 'login') return <MarketingPage route="get-started" />;
  return <ChunkLoadBoundary><Suspense fallback={<LoadingState label="Opening the demonstration workspace…" />}><App /></Suspense></ChunkLoadBoundary>;
}

export function AuthenticatedApplication() {
  return <DjangoRoutes />;
}

export function ApplicationRoot() {
  return <QueryClientProvider client={queryClient}>{dataSource === 'django'
    ? <AuthProvider><DjangoRoutes /></AuthProvider> : <MockRoutes />}</QueryClientProvider>;
}
