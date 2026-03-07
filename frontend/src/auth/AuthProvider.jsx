/**
 * Unified Auth Provider — auto-detects whether to use Mock or real Descope.
 *
 * If VITE_DESCOPE_PROJECT_ID is a valid project ID → uses real Descope SDK.
 * Otherwise → uses built-in mock auth for local development.
 */
import { AuthProvider as DescopeAuthProvider, useSession, useUser, useDescope } from '@descope/react-sdk';
import { MockAuthProvider, useMockSession, useMockUser, useMockDescope, useMockAuth } from './MockAuthProvider';

const descopeProjectId = import.meta.env.VITE_DESCOPE_PROJECT_ID || '';
const forceDemoMode = import.meta.env.VITE_FORCE_DEMO_MODE === 'true';

// We start in mock mode if forced, or if no project ID is provided
const isMockModeInitially = forceDemoMode || !descopeProjectId || descopeProjectId === 'YOUR_PROJECT_ID';

// We allow localStorage to override this for local testing/demo toggling
const savedDemoMode = localStorage.getItem('pco_demo_mode');
const isMockMode = savedDemoMode !== null ? savedDemoMode === 'true' : isMockModeInitially;

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
