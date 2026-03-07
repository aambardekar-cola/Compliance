import { useAuthUser, useAuthDescope, isMockMode } from '../auth/AuthProvider';
import { LogOut, Bell } from 'lucide-react';
import { useLocation } from 'react-router-dom';

const pageTitles = {
    '/': 'Dashboard',
    '/regulations': 'Regulatory Monitor',
    '/gaps': 'Gap Analysis',
    '/communications': 'Client Communications',
    '/reports': 'Executive Reports',
    '/settings': 'Settings',
};

export default function Header() {
    const { user } = useAuthUser();
    const sdk = useAuthDescope();
    const location = useLocation();

    const title = pageTitles[location.pathname] || 'PaceCareOnline Compliance';
    const userName = user?.name || user?.email || 'User';
    const initials = userName
        .split(' ')
        .map((n) => n[0])
        .join('')
        .toUpperCase()
        .slice(0, 2);

    const handleLogout = () => {
        sdk.logout();
        window.location.href = '/login';
    };

    return (
        <header className="header">
            <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
                <h1 className="header-title">{title}</h1>
                {isMockMode && (
                    <span style={{
                        padding: '2px 8px',
                        borderRadius: 'var(--radius-full)',
                        fontSize: 'var(--font-size-xs)',
                        fontWeight: 600,
                        background: 'rgba(245, 158, 11, 0.12)',
                        color: 'var(--color-warning)',
                        border: '1px solid rgba(245, 158, 11, 0.2)',
                    }}>
                        DEV
                    </span>
                )}
            </div>

            <div className="header-actions">
                <button
                    className="btn btn-secondary"
                    style={{ padding: '8px', borderRadius: 'var(--radius-full)' }}
                    title="Notifications"
                >
                    <Bell size={18} />
                </button>

                <div className="header-user">
                    <div className="header-user-avatar">{initials}</div>
                    <span className="header-user-name">{userName}</span>
                </div>

                <button
                    className="btn btn-secondary"
                    onClick={handleLogout}
                    style={{ padding: '8px', borderRadius: 'var(--radius-full)' }}
                    title="Sign Out"
                >
                    <LogOut size={18} />
                </button>
            </div>
        </header>
    );
}
