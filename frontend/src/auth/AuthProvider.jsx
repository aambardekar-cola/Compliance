/**
 * Unified Auth Provider — auto-detects whether to use Mock or real Descope.
 *
 * Mock mode is determined by (in priority order):
 * 1. VITE_FORCE_DEMO_MODE env var → deploy-time override
 * 2. localStorage `pco_demo_mode` → user toggle
 * 3. No VITE_DESCOPE_PROJECT_ID → fallback to mock
 *
 * Note: Statsig gates (demo_mode, force_demo_mode) are NOT used here.
 * Auth mode must be decided synchronously at module load — Statsig SDK is
 * async and not guaranteed to be ready when AuthProvider first renders.
 * To toggle demo mode via Statsig, set VITE_FORCE_DEMO_MODE at deploy time.
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
