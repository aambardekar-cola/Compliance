/**
 * Unified Auth Provider — auto-detects whether to use Mock or real Descope.
 *
 * If VITE_DESCOPE_PROJECT_ID is a valid project ID → uses real Descope SDK.
 * Otherwise → uses built-in mock auth for local development.
 */
import { AuthProvider as DescopeAuthProvider, useSession, useUser, useDescope } from '@descope/react-sdk';
import { MockAuthProvider, useMockSession, useMockUser, useMockDescope, useMockAuth } from './MockAuthProvider';

const descopeProjectId = import.meta.env.VITE_DESCOPE_PROJECT_ID || '';
const isMockMode = !descopeProjectId || descopeProjectId === 'YOUR_PROJECT_ID';

// ---- Unified Provider ----

export function AuthProviderWrapper({ children }) {
    if (isMockMode) {
        return <MockAuthProvider>{children}</MockAuthProvider>;
    }
    return <DescopeAuthProvider projectId={descopeProjectId}>{children}</DescopeAuthProvider>;
}

// ---- Unified Hooks ----

export function useAuthSession() {
    if (isMockMode) {
        return useMockSession();
    }
    const { isAuthenticated, isSessionLoading } = useSession();
    return { isAuthenticated, isSessionLoading, sessionToken: null };
}

export function useAuthUser() {
    if (isMockMode) {
        return useMockUser();
    }
    return useUser();
}

export function useAuthDescope() {
    if (isMockMode) {
        return useMockDescope();
    }
    return useDescope();
}

export function useAuthContext() {
    if (isMockMode) {
        return useMockAuth();
    }
    return null;
}

export { isMockMode };
