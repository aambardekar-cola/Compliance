/**
 * Mock Descope Auth Provider for local development.
 * Automatically switches to real Descope when VITE_DESCOPE_PROJECT_ID is set
 * to a valid project ID (not empty or 'YOUR_PROJECT_ID').
 */
import { createContext, useContext, useState, useCallback, useEffect } from 'react';

const STORAGE_KEY = 'pco_mock_auth';

// Mock users for development
const MOCK_USERS = {
    admin: {
        userId: 'mock-user-admin-001',
        email: 'admin@collabrios.com',
        name: 'Sarah Mitchell',
        tenantId: null,
        tenantName: null,
        roles: ['internal_admin'],
        permissions: ['read', 'write', 'admin'],
    },
    internal: {
        userId: 'mock-user-internal-001',
        email: 'dev@collabrios.com',
        name: 'James Reeves',
        tenantId: null,
        tenantName: null,
        roles: ['internal_user'],
        permissions: ['read', 'write'],
    },
    client_admin: {
        userId: 'mock-user-client-001',
        email: 'admin@sunrisepace.org',
        name: 'Maria Santos',
        tenantId: 'tenant-sunrise-001',
        tenantName: 'Sunrise PACE',
        roles: ['client_admin'],
        permissions: ['read', 'write'],
    },
    client_user: {
        userId: 'mock-user-client-002',
        email: 'nurse@sunrisepace.org',
        name: 'David Chen',
        tenantId: 'tenant-sunrise-001',
        tenantName: 'Sunrise PACE',
        roles: ['client_user'],
        permissions: ['read'],
    },
};

// Generate a mock JWT-like token
function generateMockToken(user) {
    const header = btoa(JSON.stringify({ alg: 'RS256', typ: 'JWT' }));
    const payload = btoa(JSON.stringify({
        sub: user.userId,
        email: user.email,
        name: user.name,
        roles: user.roles,
        permissions: user.permissions,
        tenants: user.tenantId ? {
            [user.tenantId]: {
                name: user.tenantName,
                roles: user.roles,
                permissions: user.permissions,
            }
        } : {},
        iat: Math.floor(Date.now() / 1000),
        exp: Math.floor(Date.now() / 1000) + 86400,
        iss: 'mock-descope-provider',
    }));
    const signature = btoa('mock-signature');
    return `${header}.${payload}.${signature}`;
}

// ---- Context ----
const MockAuthContext = createContext(null);

export function MockAuthProvider({ children }) {
    const [authState, setAuthState] = useState(() => {
        const stored = localStorage.getItem(STORAGE_KEY);
        if (stored) {
            try {
                const parsed = JSON.parse(stored);
                return { isAuthenticated: true, user: parsed.user, sessionToken: parsed.token };
            } catch { /* fall through */ }
        }
        return { isAuthenticated: false, user: null, sessionToken: null };
    });
    const [isLoading, setIsLoading] = useState(false);

    const login = useCallback((userKey) => {
        const mockUser = MOCK_USERS[userKey];
        if (!mockUser) return;

        setIsLoading(true);
        // Simulate network delay
        setTimeout(() => {
            const token = generateMockToken(mockUser);
            const state = { isAuthenticated: true, user: mockUser, sessionToken: token };
            setAuthState(state);
            localStorage.setItem(STORAGE_KEY, JSON.stringify({ user: mockUser, token }));
            setIsLoading(false);
        }, 600);
    }, []);

    const loginCustom = useCallback((userData) => {
        setIsLoading(true);
        setTimeout(() => {
            const user = {
                userId: `mock-custom-${Date.now()}`,
                email: userData.email,
                name: userData.name,
                tenantId: userData.tenantId || null,
                tenantName: userData.tenantName || null,
                roles: userData.roles || ['internal_user'],
                permissions: ['read', 'write'],
            };
            const token = generateMockToken(user);
            const state = { isAuthenticated: true, user, sessionToken: token };
            setAuthState(state);
            localStorage.setItem(STORAGE_KEY, JSON.stringify({ user, token }));
            setIsLoading(false);
        }, 600);
    }, []);

    const logout = useCallback(() => {
        setAuthState({ isAuthenticated: false, user: null, sessionToken: null });
        localStorage.removeItem(STORAGE_KEY);
    }, []);

    return (
        <MockAuthContext.Provider value={{ ...authState, isLoading, login, loginCustom, logout, MOCK_USERS }}>
            {children}
        </MockAuthContext.Provider>
    );
}

// ---- Hooks that mirror Descope SDK ----

export function useMockSession() {
    const ctx = useContext(MockAuthContext);
    return {
        isAuthenticated: ctx?.isAuthenticated ?? false,
        isSessionLoading: ctx?.isLoading ?? false,
        sessionToken: ctx?.sessionToken ?? null,
    };
}

export function useMockUser() {
    const ctx = useContext(MockAuthContext);
    return {
        user: ctx?.user ? {
            userId: ctx.user.userId,
            email: ctx.user.email,
            name: ctx.user.name,
            loginIds: [ctx.user.email],
        } : null,
        isUserLoading: ctx?.isLoading ?? false,
    };
}

export function useMockDescope() {
    const ctx = useContext(MockAuthContext);
    return {
        logout: ctx?.logout ?? (() => { }),
    };
}

export function useMockAuth() {
    return useContext(MockAuthContext);
}
