import { createContext, useContext, useEffect, useSyncExternalStore, type ReactNode } from 'react';
import { Session } from '../services/session';
import { session } from '../services/authRuntime';

const AuthContext = createContext<Session>(session);
export function AuthProvider({ children, value = session }: { children: ReactNode; value?: Session }) {
  useEffect(() => { void value.initialize(); }, [value]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
export function useAuth() {
  const value = useContext(AuthContext);
  const snapshot = useSyncExternalStore(value.subscribe, value.getSnapshot, value.getSnapshot);
  return { ...snapshot, authenticated: snapshot.user !== null, role: snapshot.user?.role ?? null,
    login: value.login, logout: value.logout, generation: value.generation,
    isCurrent: (generation: number) => value.generation === generation && value.getSnapshot().user !== null };
}
