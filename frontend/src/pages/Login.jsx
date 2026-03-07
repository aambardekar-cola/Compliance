import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Descope } from '@descope/react-sdk';
import { Shield, User, Building2, ChevronRight, Sparkles } from 'lucide-react';
import { isMockMode, useAuthContext } from '../auth/AuthProvider';

// Mock user personas for development
const PERSONAS = [
    {
        key: 'admin',
        label: 'Internal Admin',
        name: 'Sarah Mitchell',
        email: 'admin@collabrios.com',
        description: 'Full platform access, all tenants',
        icon: <Shield size={18} />,
        gradient: 'var(--gradient-primary)',
    },
    {
        key: 'internal',
        label: 'Internal User',
        name: 'James Reeves',
        email: 'dev@collabrios.com',
        description: 'Engineering team, read/write access',
        icon: <User size={18} />,
        gradient: 'var(--gradient-info)',
    },
    {
        key: 'client_admin',
        label: 'Client Admin',
        name: 'Maria Santos',
        email: 'admin@sunrisepace.org',
        description: 'Sunrise PACE org admin',
        icon: <Building2 size={18} />,
        gradient: 'var(--gradient-success)',
    },
    {
        key: 'client_user',
        label: 'Client User',
        name: 'David Chen',
        email: 'nurse@sunrisepace.org',
        description: 'Sunrise PACE, read-only',
        icon: <User size={18} />,
        gradient: 'var(--gradient-warning)',
    },
];

export default function Login() {
    const navigate = useNavigate();
    const mockAuth = useAuthContext();
    const [activeTab, setActiveTab] = useState('preset');
    const [customForm, setCustomForm] = useState({ name: '', email: '', role: 'internal_user' });
    const [hoveredPersona, setHoveredPersona] = useState(null);

    const handleMockLogin = (userKey) => {
        if (mockAuth) {
            mockAuth.login(userKey);
            setTimeout(() => navigate('/'), 700);
        }
    };

    const handleCustomLogin = (e) => {
        e.preventDefault();
        if (mockAuth && customForm.name && customForm.email) {
            mockAuth.loginCustom({
                name: customForm.name,
                email: customForm.email,
                roles: [customForm.role],
                tenantId: customForm.role.startsWith('client') ? 'tenant-custom-001' : null,
                tenantName: customForm.role.startsWith('client') ? 'Custom Organization' : null,
            });
            setTimeout(() => navigate('/'), 700);
        }
    };

    return (
        <div className="login-page">
            <div className="login-container" style={{ maxWidth: isMockMode ? 520 : 420 }}>
                <div className="login-header">
                    <div className="login-logo">
                        <Shield size={28} color="white" />
                    </div>
                    <h1 className="login-title">PaceCareOnline</h1>
                    <p className="login-subtitle">Compliance Intelligence Platform</p>
                </div>

                {isMockMode ? (
                    /* ---- MOCK LOGIN ---- */
                    <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
                        {/* Mock Mode Badge */}
                        <div style={{
                            padding: 'var(--space-3) var(--space-5)',
                            background: 'rgba(245, 158, 11, 0.08)',
                            borderBottom: '1px solid rgba(245, 158, 11, 0.15)',
                            display: 'flex',
                            alignItems: 'center',
                            gap: 'var(--space-2)',
                            fontSize: 'var(--font-size-xs)',
                            color: 'var(--color-warning)',
                        }}>
                            <Sparkles size={14} />
                            <span style={{ fontWeight: 600 }}>Development Mode</span>
                            <span style={{ color: 'var(--color-text-muted)', marginLeft: 4 }}>
                                Set VITE_DESCOPE_PROJECT_ID for live auth
                            </span>
                        </div>

                        {/* Tabs */}
                        <div style={{
                            display: 'flex',
                            borderBottom: '1px solid var(--color-border)',
                        }}>
                            <button
                                onClick={() => setActiveTab('preset')}
                                style={{
                                    flex: 1,
                                    padding: 'var(--space-3) var(--space-4)',
                                    background: activeTab === 'preset' ? 'rgba(99, 102, 241, 0.08)' : 'transparent',
                                    border: 'none',
                                    borderBottom: activeTab === 'preset' ? '2px solid var(--color-accent)' : '2px solid transparent',
                                    color: activeTab === 'preset' ? 'var(--color-accent-light)' : 'var(--color-text-muted)',
                                    fontSize: 'var(--font-size-sm)',
                                    fontWeight: 600,
                                    fontFamily: 'var(--font-family)',
                                    cursor: 'pointer',
                                    transition: 'all var(--transition-fast)',
                                }}
                            >
                                Quick Login
                            </button>
                            <button
                                onClick={() => setActiveTab('custom')}
                                style={{
                                    flex: 1,
                                    padding: 'var(--space-3) var(--space-4)',
                                    background: activeTab === 'custom' ? 'rgba(99, 102, 241, 0.08)' : 'transparent',
                                    border: 'none',
                                    borderBottom: activeTab === 'custom' ? '2px solid var(--color-accent)' : '2px solid transparent',
                                    color: activeTab === 'custom' ? 'var(--color-accent-light)' : 'var(--color-text-muted)',
                                    fontSize: 'var(--font-size-sm)',
                                    fontWeight: 600,
                                    fontFamily: 'var(--font-family)',
                                    cursor: 'pointer',
                                    transition: 'all var(--transition-fast)',
                                }}
                            >
                                Custom User
                            </button>
                        </div>

                        <div style={{ padding: 'var(--space-5)' }}>
                            {activeTab === 'preset' ? (
                                /* Preset Personas */
                                <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
                                    {PERSONAS.map((persona) => (
                                        <button
                                            key={persona.key}
                                            onClick={() => handleMockLogin(persona.key)}
                                            onMouseEnter={() => setHoveredPersona(persona.key)}
                                            onMouseLeave={() => setHoveredPersona(null)}
                                            style={{
                                                display: 'flex',
                                                alignItems: 'center',
                                                gap: 'var(--space-4)',
                                                padding: 'var(--space-4)',
                                                background: hoveredPersona === persona.key
                                                    ? 'var(--color-bg-card-hover)'
                                                    : 'var(--color-bg-glass)',
                                                border: `1px solid ${hoveredPersona === persona.key ? 'var(--color-border-hover)' : 'var(--color-border)'}`,
                                                borderRadius: 'var(--radius-md)',
                                                cursor: 'pointer',
                                                transition: 'all var(--transition-fast)',
                                                fontFamily: 'var(--font-family)',
                                                width: '100%',
                                                textAlign: 'left',
                                                transform: hoveredPersona === persona.key ? 'translateX(4px)' : 'none',
                                            }}
                                        >
                                            <div style={{
                                                width: 40,
                                                height: 40,
                                                borderRadius: 'var(--radius-md)',
                                                background: persona.gradient,
                                                display: 'flex',
                                                alignItems: 'center',
                                                justifyContent: 'center',
                                                color: 'white',
                                                flexShrink: 0,
                                            }}>
                                                {persona.icon}
                                            </div>
                                            <div style={{ flex: 1 }}>
                                                <div style={{
                                                    fontSize: 'var(--font-size-sm)',
                                                    fontWeight: 600,
                                                    color: 'var(--color-text-primary)',
                                                }}>
                                                    {persona.label}
                                                </div>
                                                <div style={{
                                                    fontSize: 'var(--font-size-xs)',
                                                    color: 'var(--color-text-muted)',
                                                    marginTop: 2,
                                                }}>
                                                    {persona.name} &bull; {persona.description}
                                                </div>
                                            </div>
                                            <ChevronRight size={16} color="var(--color-text-muted)" style={{
                                                opacity: hoveredPersona === persona.key ? 1 : 0,
                                                transition: 'opacity var(--transition-fast)',
                                            }} />
                                        </button>
                                    ))}
                                </div>
                            ) : (
                                /* Custom User Form */
                                <form onSubmit={handleCustomLogin} className="settings-form">
                                    <div className="settings-field">
                                        <label>Full Name</label>
                                        <input
                                            type="text"
                                            value={customForm.name}
                                            onChange={(e) => setCustomForm({ ...customForm, name: e.target.value })}
                                            placeholder="Your Name"
                                            required
                                        />
                                    </div>
                                    <div className="settings-field">
                                        <label>Email</label>
                                        <input
                                            type="email"
                                            value={customForm.email}
                                            onChange={(e) => setCustomForm({ ...customForm, email: e.target.value })}
                                            placeholder="you@example.com"
                                            required
                                        />
                                    </div>
                                    <div className="settings-field">
                                        <label>Role</label>
                                        <select
                                            className="select"
                                            value={customForm.role}
                                            onChange={(e) => setCustomForm({ ...customForm, role: e.target.value })}
                                            style={{ width: '100%' }}
                                        >
                                            <option value="internal_admin">Internal Admin</option>
                                            <option value="internal_user">Internal User</option>
                                            <option value="client_admin">Client Admin</option>
                                            <option value="client_user">Client User</option>
                                        </select>
                                    </div>
                                    <button type="submit" className="btn btn-primary" style={{ width: '100%', padding: 'var(--space-3)' }}>
                                        Sign In as Custom User
                                    </button>
                                </form>
                            )}
                        </div>
                    </div>
                ) : (
                    /* ---- LIVE DESCOPE ---- */
                    <div className="card" style={{ padding: 'var(--space-6)', minHeight: 400 }}>
                        <Descope
                            flowId="default-sign-in"
                            onSuccess={() => navigate('/')}
                            onError={(e) => console.error('Login error:', e)}
                            theme="dark"
                        />
                    </div>
                )}

                <p style={{
                    textAlign: 'center',
                    marginTop: 'var(--space-6)',
                    fontSize: 'var(--font-size-xs)',
                    color: 'var(--color-text-muted)',
                }}>
                    Powered by Collabrios Health
                </p>
            </div>
        </div>
    );
}
