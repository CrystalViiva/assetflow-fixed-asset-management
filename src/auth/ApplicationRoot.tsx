import { lazy, Suspense, useEffect, useState } from 'react';
import { QueryClientProvider } from '@tanstack/react-query';
import { AuthProvider, useAuth } from './AuthProvider';
import { queryClient } from '../services/authRuntime';
import { dataSource } from '../services/config';
import { LoadingState } from '../components/common/AsyncState';
import { ChunkLoadBoundary } from '../components/common/ChunkLoadBoundary';
import { readHashPath } from '../routing/hash';
import { PublicLandingPage } from '../views/PublicLandingPage';
import { MarketingPage, marketingRoutes } from '../views/MarketingPages';
const LoginView = lazy(() => import('../views/LoginView').then(module => ({ default: module.LoginView })));
const IdentityView = lazy(() => import('../views/IdentityViews').then(module => ({ default: module.IdentityView })));
const SignupView = lazy(() => import('../views/SaasViews').then(module => ({ default: module.SignupView })));
const PlatformView = lazy(() => import('../views/PlatformView').then(module => ({ default: module.PlatformView })));
const App = lazy(() => import('../App'));

const privateRoutes = new Set(['dashboard','all-assets','asset-categories','acquisitions','depreciation','assignments','transfers','maintenance','disposals','verification','assurance','reports','audit-log','departments','locations','users-and-roles','asset-create']);
const landingSections = new Set(['capabilities','controls','architecture','section-features','section-solutions','section-how-it-works','section-security','section-security-detail','section-pricing','section-product-preview','section-features-detail']);
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

function useHashPath() {
  const [path, setPath] = useState(readHashPath());
  useEffect(() => {
    const update = () => {
      const next = readHashPath();
      if (!next.startsWith('section-')) window.scrollTo({ top: 0, left: 0, behavior: 'instant' });
      setPath(next);
    };
    window.addEventListener('hashchange', update);
    return () => window.removeEventListener('hashchange', update);
  }, []);
  return path;
}
function navigate(route: string) { window.location.hash = route ? `#${route}` : '#/'; }
function LoginRoute() {
  const { authenticated, initializing, user } = useAuth();
  const params = new URLSearchParams(readHashPath().split('?')[1] ?? '');
  const destination = user?.isPlatformOperator ? 'platform' : safeReturnRoute(params.get('next')) ?? 'dashboard';
  useEffect(() => { if (!initializing && authenticated) navigate(destination); }, [initializing, authenticated, destination]);
  if (initializing) return <LoadingState label="Restoring your session..." />;
  if (authenticated) return <LoadingState label="Opening your workspace..." />;
  return <LoginView sessionExpired={params.get('expired') === '1'} />;
}

export function DjangoRoutes() {
  return <Suspense fallback={<LoadingState label="Opening AssetFlow..." />}><DjangoRouteContent /></Suspense>;
}

function DjangoRouteContent() {
  const auth = useAuth();
  const path = useHashPath();
  const route = path.split('?')[0];
  const publicRoot = route === '' || route === '/' || landingSections.has(route);
  const loginRoute = route === 'login';
  const identityRoute = identityRoutes.has(route);
  const marketingRoute = marketingRoutes.has(route);
  const signupRoute = route === 'signup' || route === 'verify-email';
  const returnRoute = safeReturnRoute(route);
  const knownRoute = publicRoot || loginRoute || identityRoute || marketingRoute || signupRoute || Boolean(returnRoute) || route === 'platform';
  const loginDestination = safeReturnRoute(new URLSearchParams(path.split('?')[1] ?? '').get('next')) ?? 'dashboard';
  useEffect(() => {
    if (identityRoute || marketingRoute || signupRoute || !knownRoute) return;
    if (auth.initializing) return;
    if (auth.authenticated) {
      if (loginRoute) navigate(auth.user?.isPlatformOperator ? 'platform' : loginDestination);
      else if (!publicRoot && !returnRoute) navigate('dashboard');
      return;
    }
    if (auth.error === 'signed-out' && !publicRoot && !loginRoute) { navigate(''); return; }
    if (!publicRoot && !loginRoute) {
      const next = returnRoute ?? 'dashboard';
      const expired = auth.error ? '&expired=1' : '';
      navigate(`login?next=${encodeURIComponent(next)}${expired}`);
    }
  }, [auth.initializing, auth.authenticated, auth.error, auth.user?.isPlatformOperator, publicRoot, loginRoute, loginDestination, returnRoute, identityRoute, marketingRoute, signupRoute, knownRoute]);

  if (!knownRoute) return <NotFound />;
  if (identityRoute) return <IdentityView key={route} route={route} />;
  if (marketingRoute) return <MarketingPage key={route} route={route} />;
  if (signupRoute) return <SignupView key={route} verify={route === 'verify-email'} />;
  if (publicRoot) return <PublicLandingPage authenticated={auth.authenticated} workspaceRoute={auth.user?.isPlatformOperator ? "#platform" : "#dashboard"} />;
  if (auth.initializing) return <LoadingState label="Restoring your session..." />;
  if (loginRoute && !auth.authenticated) return <LoginRoute />;
  if (!auth.authenticated) return <LoadingState label="Opening sign in..." />;
  if (route === 'platform') return <PlatformView />;
  if (loginRoute || publicRoot || !returnRoute) return <LoadingState label="Opening your workspace..." />;
  return <ChunkLoadBoundary><Suspense fallback={<LoadingState label="Opening your workspace..." />}><App key={`${auth.user?.id}:${auth.generation}`} /></Suspense></ChunkLoadBoundary>;
}

export function MockRoutes() {
  const path = useHashPath();
  const route = path.split('?')[0];
  if (!route || route === '/' || landingSections.has(route)) return <PublicLandingPage authenticated={false} mockMode />;
  if (marketingRoutes.has(route) || route === 'signup' || route === 'login') return <MarketingPage route={route} />;
  if (privateRoutes.has(route) || /^asset-detail\/[A-Za-z0-9_-]{1,120}$/.test(route) || /^asset-create\/[A-Za-z0-9_-]{1,120}$/.test(route)) return <ChunkLoadBoundary><Suspense fallback={<LoadingState label="Opening the demonstration workspace..." />}><App /></Suspense></ChunkLoadBoundary>;
  return <NotFound />;
}

function NotFound() { return <main className="route-not-found" role="alert"><div><p>ASSETFLOW  -  PAGE NOT FOUND</p><h1>This page isn't here.</h1><p>Check the address or return to the AssetFlow homepage.</p><a href="#/">Return to AssetFlow</a></div></main>; }

export function AuthenticatedApplication() {
  return <DjangoRoutes />;
}

export function ApplicationRoot() {
  return <QueryClientProvider client={queryClient}><ChunkLoadBoundary>{dataSource === 'django'
    ? <AuthProvider><DjangoRoutes /></AuthProvider> : <MockRoutes />}</ChunkLoadBoundary></QueryClientProvider>;
}
