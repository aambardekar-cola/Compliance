/**
 * Unified Auth Provider — auto-detects whether to use Mock or real Descope.
 *
 * Priority order for determining mock mode:
 * 1. Statsig `force_demo_mode` gate → overrides everything
 * 2. localStorage `pco_demo_mode` → user toggle
 * 3. VITE_FORCE_DEMO_MODE env var → deploy-time override
 * 4. Statsig `demo_mode` gate → runtime control
 * 5. No VITE_DESCOPE_PROJECT_ID → fallback to mock
 */
import { AuthProvider as DescopeAuthProvider, useSession, useUser, useDescope } from '@descope/react-sdk';
import { MockAuthProvider, useMockSession, useMockUser, useMockDescope, useMockAuth } from './MockAuthProvider';
import { useStatsigGate, STATSIG_CLIENT_KEY } from '../statsig/StatsigProvider';

const descopeProjectId = import.meta.env.VITE_DESCOPE_PROJECT_ID || '';
const envForceDemoMode = import.meta.env.VITE_FORCE_DEMO_MODE === 'true';

/**
 * Determine if mock mode is active, incorporating Statsig gates.
 * Falls back to env-var/localStorage logic if Statsig SDK is not configured.
 */
function useMockModeDecision() {
    // Statsig gates (return false if SDK not configured)
    const forceDemoGate = useStatsigGate('force_demo_mode');
    const demoModeGate = useStatsigGate('demo_mode');

    // localStorage override
    const savedDemoMode = localStorage.getItem('pco_demo_mode');

    // Priority cascade
    if (forceDemoGate) return true;                             // 1. Statsig force_demo_mode
    if (savedDemoMode !== null) return savedDemoMode === 'true'; // 2. localStorage
    if (envForceDemoMode) return true;                           // 3. Env var
    if (STATSIG_CLIENT_KEY && demoModeGate) return true;        // 4. Statsig demo_mode
    if (!descopeProjectId || descopeProjectId === 'YOUR_PROJECT_ID') return true; // 5. No Descope

    return false;
}

// Export a module-level fallback for non-hook contexts (e.g. conditional hook calls)
const savedDemoMode = localStorage.getItem('pco_demo_mode');
const isMockModeInitially = envForceDemoMode || !descopeProjectId || descopeProjectId === 'YOUR_PROJECT_ID';
const isMockMode = savedDemoMode !== null ? savedDemoMode === 'true' : isMockModeInitially;

// ---- Unified Provider ----

export function AuthProviderWrapper({ children }) {
    const mockMode = useMockModeDecision();
    if (mockMode) {
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
