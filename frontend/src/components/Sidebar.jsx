import { NavLink } from 'react-router-dom';
import { useAuthUser } from '../auth/AuthProvider';
import {
    LayoutDashboard,
    FileText,
    AlertTriangle,
    Send,
    BarChart3,
    Settings,
    Shield,
    Globe,
    Server,
    Bell,
    Activity,
} from 'lucide-react';

const navItems = [
    {
        section: 'Overview',
        items: [
            { to: '/', icon: LayoutDashboard, label: 'Dashboard' },
            { to: '/regulations', icon: FileText, label: 'Regulations' },
        ],
    },
    {
        section: 'Analysis',
        items: [
            { to: '/gaps', icon: AlertTriangle, label: 'Gap Analysis' },
        ],
    },
    {
        section: 'Communication',
        items: [
            { to: '/communications', icon: Send, label: 'Communications' },
            { to: '/reports', icon: BarChart3, label: 'Exec Reports' },
        ],
    },
    {
        section: 'System',
        items: [
            { to: '/settings', icon: Settings, label: 'Settings' },
        ],
    },
];

export default function Sidebar() {
    const { user } = useAuthUser();
    const isInternalAdmin = user?.roles?.includes('internal_admin') || user?.role === 'INTERNAL_ADMIN';

    return (
        <aside className="sidebar">
            <div className="sidebar-logo">
                <div className="sidebar-logo-icon">
                    <Shield size={20} color="white" />
                </div>
                <div className="sidebar-logo-text">
                    <span className="sidebar-logo-title">PaceCareOnline</span>
                    <span className="sidebar-logo-subtitle">Compliance Intel</span>
                </div>
            </div>

            <nav className="sidebar-nav">
                {navItems.map((section) => (
                    <div key={section.section}>
                        <div className="sidebar-section">{section.section}</div>
                        {section.items.map((item) => (
                            <NavLink
                                key={item.to}
                                to={item.to}
                                end={item.to === '/'}
                                className={({ isActive }) =>
                                    `sidebar-link${isActive ? ' active' : ''}`
                                }
                            >
                                <item.icon />
                                <span>{item.label}</span>
                            </NavLink>
                        ))}
                    </div>
                ))}

                {isInternalAdmin && (
                    <div>
                        <div className="sidebar-section">Admin</div>
                        <NavLink
                            to="/admin/urls"
                            className={({ isActive }) => `sidebar-link${isActive ? ' active' : ''}`}
                        >
                            <Globe />
                            <span>Compliance Sources</span>
                        </NavLink>
                        <NavLink
                            to="/admin/environments"
                            className={({ isActive }) => `sidebar-link${isActive ? ' active' : ''}`}
                        >
                            <Server />
                            <span>Environments</span>
                        </NavLink>
                        <NavLink
                            to="/admin/notifications"
                            className={({ isActive }) => `sidebar-link${isActive ? ' active' : ''}`}
                        >
                            <Bell />
                            <span>Notifications</span>
                        </NavLink>
                        <NavLink
                            to="/admin/pipeline-health"
                            className={({ isActive }) => `sidebar-link${isActive ? ' active' : ''}`}
                        >
                            <Activity />
                            <span>Pipeline Health</span>
                        </NavLink>
                    </div>
                )}
            </nav>
        </aside>
    );
}
