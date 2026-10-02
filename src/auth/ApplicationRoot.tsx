import { QueryClientProvider } from '@tanstack/react-query';
import { AuthProvider, useAuth } from './AuthProvider';
import { queryClient } from '../services/runtime';
import { dataSource } from '../services/config';
import { LoadingState } from '../components/common/AsyncState';
import { LoginView } from '../views/LoginView';
import App from '../App';

export function AuthenticatedApplication() {
  const { initializing, authenticated, user, generation } = useAuth();
  if (initializing) return <LoadingState label="Restoring your session…" />;
  if (!authenticated) return <LoginView />;
  return <App key={`${user?.id}:${generation}`} />;
}
export function ApplicationRoot() {
  return <QueryClientProvider client={queryClient}>{dataSource === 'django'
    ? <AuthProvider><AuthenticatedApplication /></AuthProvider> : <App />}</QueryClientProvider>;
}
