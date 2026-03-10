import { useState, useRef, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useAuthUser, useAuthDescope, isMockMode } from '../auth/AuthProvider';
import { LogOut, Bell, CheckCheck, ExternalLink } from 'lucide-react';
import { useLocation, useNavigate } from 'react-router-dom';
import apiClient from '../api/client';

const pageTitles = {
    '/': 'Dashboard',
    '/regulations': 'Regulatory Monitor',
    '/gaps': 'Gap Analysis',
    '/communications': 'Client Communications',
    '/reports': 'Executive Reports',
    '/settings': 'Settings',
    '/admin/notifications': 'Notification Center',
    '/admin/pipeline-health': 'Pipeline Health',
};

const NOTIF_ICONS = {
    pipeline_completed: '✅',
    pipeline_failed: '❌',
    new_regulations: '📜',
    new_gaps: '⚠️',
    error: '🚨',
    info: 'ℹ️',
};

function timeAgo(dateStr) {
    const now = new Date();
    const d = new Date(dateStr);
    const secs = Math.floor((now - d) / 1000);
    if (secs < 60) return 'just now';
    if (secs < 3600) return `${Math.floor(secs / 60)}m ago`;
    if (secs < 86400) return `${Math.floor(secs / 3600)}h ago`;
    return `${Math.floor(secs / 86400)}d ago`;
}

export default function Header() {
    const { user } = useAuthUser();
    const sdk = useAuthDescope();
    const location = useLocation();
    const navigate = useNavigate();
    const queryClient = useQueryClient();
    const [showDropdown, setShowDropdown] = useState(false);
    const dropdownRef = useRef(null);

    const title = pageTitles[location.pathname] || 'PaceCareOnline Compliance';
    const userName = user?.name || user?.email || 'User';
    const initials = userName
        .split(' ')
        .map((n) => n[0])
        .join('')
        .toUpperCase()
        .slice(0, 2);

    // Fetch unread count every 30 seconds
    const { data: unreadData } = useQuery({
        queryKey: ['notifications-unread'],
        queryFn: () => apiClient.getUnreadCount(),
        refetchInterval: 30000,
        staleTime: 10000,
    });

    // Fetch latest 5 notifications for dropdown
    const { data: notifData } = useQuery({
        queryKey: ['notifications-latest'],
        queryFn: () => apiClient.getNotifications({ page_size: 5 }),
        enabled: showDropdown,
        staleTime: 5000,
    });

    const markAllRead = useMutation({
        mutationFn: () => apiClient.markAllNotificationsRead(),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['notifications-unread'] });
            queryClient.invalidateQueries({ queryKey: ['notifications-latest'] });
        },
    });

    const unreadCount = unreadData?.unread_count || 0;
    const notifications = notifData?.items || [];

    // Close dropdown on outside click
    useEffect(() => {
        function handleClick(e) {
            if (dropdownRef.current && !dropdownRef.current.contains(e.target)) {
                setShowDropdown(false);
            }
        }
        if (showDropdown) document.addEventListener('mousedown', handleClick);
        return () => document.removeEventListener('mousedown', handleClick);
    }, [showDropdown]);

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
                {/* Notification Bell */}
                <div ref={dropdownRef} style={{ position: 'relative' }}>
                    <button
                        className="btn btn-secondary"
                        style={{ padding: '8px', borderRadius: 'var(--radius-full)', position: 'relative' }}
                        title="Notifications"
                        onClick={() => setShowDropdown(!showDropdown)}
                    >
                        <Bell size={18} />
                        {unreadCount > 0 && (
                            <span style={{
                                position: 'absolute', top: 2, right: 2,
                                width: 16, height: 16, borderRadius: '50%',
                                background: 'var(--color-danger, #ef4444)',
                                color: '#fff', fontSize: '10px', fontWeight: 700,
                                display: 'flex', alignItems: 'center', justifyContent: 'center',
                                lineHeight: 1,
                            }}>
                                {unreadCount > 9 ? '9+' : unreadCount}
                            </span>
                        )}
                    </button>

                    {/* Dropdown */}
                    {showDropdown && (
                        <div style={{
                            position: 'absolute', right: 0, top: '100%', marginTop: 8,
                            width: 380, maxHeight: 420, overflowY: 'auto',
                            background: 'var(--color-bg-secondary, #1e293b)',
                            border: '1px solid var(--color-border, #334155)',
                            borderRadius: 'var(--radius-lg, 12px)',
                            boxShadow: '0 20px 60px rgba(0,0,0,0.5)',
                            zIndex: 1000,
                        }}>
                            <div style={{
                                padding: '12px 16px', borderBottom: '1px solid var(--color-border, #334155)',
                                display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                            }}>
                                <span style={{ fontWeight: 600, fontSize: 14 }}>Notifications</span>
                                <div style={{ display: 'flex', gap: 8 }}>
                                    {unreadCount > 0 && (
                                        <button onClick={() => markAllRead.mutate()} style={{
                                            background: 'none', border: 'none', color: 'var(--color-primary, #3b82f6)',
                                            cursor: 'pointer', fontSize: 12, display: 'flex', alignItems: 'center', gap: 4,
                                        }}>
                                            <CheckCheck size={14} /> Mark all read
                                        </button>
                                    )}
                                </div>
                            </div>

                            {notifications.length === 0 ? (
                                <div style={{ padding: 24, textAlign: 'center', color: 'var(--color-text-muted, #94a3b8)', fontSize: 13 }}>
                                    No notifications yet
                                </div>
                            ) : (
                                notifications.map((n) => (
                                    <div key={n.id} style={{
                                        padding: '10px 16px',
                                        borderBottom: '1px solid var(--color-border, #1e293b)',
                                        opacity: n.is_read ? 0.6 : 1,
                                        background: n.is_read ? 'transparent' : 'rgba(59, 130, 246, 0.05)',
                                    }}>
                                        <div style={{ display: 'flex', gap: 8, alignItems: 'flex-start' }}>
                                            <span style={{ fontSize: 16, flexShrink: 0 }}>{NOTIF_ICONS[n.notification_type] || 'ℹ️'}</span>
                                            <div style={{ flex: 1, minWidth: 0 }}>
                                                <div style={{ fontWeight: n.is_read ? 400 : 600, fontSize: 13, marginBottom: 2 }}>
                                                    {n.title}
                                                </div>
                                                <div style={{ fontSize: 12, color: 'var(--color-text-muted, #94a3b8)', lineHeight: 1.4 }}>
                                                    {n.message}
                                                </div>
                                                <div style={{ fontSize: 11, color: 'var(--color-text-muted, #64748b)', marginTop: 4 }}>
                                                    {timeAgo(n.created_at)}
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                ))
                            )}

                            <div style={{
                                padding: '10px 16px', textAlign: 'center',
                                borderTop: '1px solid var(--color-border, #334155)',
                            }}>
                                <button onClick={() => { setShowDropdown(false); navigate('/admin/notifications'); }}
                                    style={{
                                        background: 'none', border: 'none', color: 'var(--color-primary, #3b82f6)',
                                        cursor: 'pointer', fontSize: 13, fontWeight: 500,
                                        display: 'flex', alignItems: 'center', gap: 4, margin: '0 auto',
                                    }}>
                                    View All <ExternalLink size={12} />
                                </button>
                            </div>
                        </div>
                    )}
                </div>

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
