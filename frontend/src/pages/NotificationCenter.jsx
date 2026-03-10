import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Bell, CheckCheck, AlertTriangle, Check, XCircle, Info, FileText, Loader2 } from 'lucide-react';
import apiClient from '../api/client';

const NOTIF_STYLES = {
    pipeline_completed: { icon: <Check size={16} />, color: '#22c55e', bg: 'rgba(34,197,94,0.08)' },
    pipeline_failed: { icon: <XCircle size={16} />, color: '#ef4444', bg: 'rgba(239,68,68,0.08)' },
    new_regulations: { icon: <FileText size={16} />, color: '#3b82f6', bg: 'rgba(59,130,246,0.08)' },
    new_gaps: { icon: <AlertTriangle size={16} />, color: '#f59e0b', bg: 'rgba(245,158,11,0.08)' },
    error: { icon: <XCircle size={16} />, color: '#ef4444', bg: 'rgba(239,68,68,0.08)' },
    info: { icon: <Info size={16} />, color: '#6366f1', bg: 'rgba(99,102,241,0.08)' },
};

function formatDate(dateStr) {
    const d = new Date(dateStr);
    const now = new Date();
    const diffDays = Math.floor((now - d) / 86400000);
    if (diffDays === 0) return 'Today';
    if (diffDays === 1) return 'Yesterday';
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

function formatTime(dateStr) {
    return new Date(dateStr).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
}

export default function NotificationCenter() {
    const queryClient = useQueryClient();
    const [page, setPage] = useState(1);
    const [unreadOnly, setUnreadOnly] = useState(false);

    const { data, isLoading } = useQuery({
        queryKey: ['notifications-list', page, unreadOnly],
        queryFn: () => apiClient.getNotifications({ page, page_size: 20, unread_only: unreadOnly }),
    });

    const markRead = useMutation({
        mutationFn: (id) => apiClient.markNotificationRead(id),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['notifications-list'] });
            queryClient.invalidateQueries({ queryKey: ['notifications-unread'] });
        },
    });

    const markAllRead = useMutation({
        mutationFn: () => apiClient.markAllNotificationsRead(),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['notifications-list'] });
            queryClient.invalidateQueries({ queryKey: ['notifications-unread'] });
        },
    });

    const notifications = data?.items || [];
    const total = data?.total || 0;
    const unreadCount = data?.unread_count || 0;
    const totalPages = Math.ceil(total / 20);

    // Group by date
    const grouped = {};
    notifications.forEach((n) => {
        const dateKey = formatDate(n.created_at);
        if (!grouped[dateKey]) grouped[dateKey] = [];
        grouped[dateKey].push(n);
    });

    return (
        <div style={{ maxWidth: 800, margin: '0 auto' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
                <div>
                    <h2 style={{ margin: 0, fontSize: 24, fontWeight: 700 }}>
                        <Bell size={22} style={{ verticalAlign: 'middle', marginRight: 8 }} />
                        Notification Center
                    </h2>
                    <p style={{ margin: '4px 0 0', color: 'var(--color-text-muted, #94a3b8)', fontSize: 14 }}>
                        {total} total · {unreadCount} unread
                    </p>
                </div>
                <div style={{ display: 'flex', gap: 8 }}>
                    <button
                        className={`btn ${unreadOnly ? 'btn-primary' : 'btn-secondary'}`}
                        onClick={() => { setUnreadOnly(!unreadOnly); setPage(1); }}
                        style={{ fontSize: 13, padding: '6px 14px' }}
                    >
                        {unreadOnly ? 'Show All' : 'Unread Only'}
                    </button>
                    {unreadCount > 0 && (
                        <button
                            className="btn btn-secondary"
                            onClick={() => markAllRead.mutate()}
                            style={{ fontSize: 13, padding: '6px 14px', display: 'flex', alignItems: 'center', gap: 6 }}
                        >
                            <CheckCheck size={14} /> Mark All Read
                        </button>
                    )}
                </div>
            </div>

            {isLoading ? (
                <div style={{ textAlign: 'center', padding: 48, color: 'var(--color-text-muted, #94a3b8)' }}>
                    <Loader2 size={24} style={{ animation: 'spin 1s linear infinite' }} />
                </div>
            ) : notifications.length === 0 ? (
                <div className="card" style={{ textAlign: 'center', padding: 48, color: 'var(--color-text-muted, #94a3b8)' }}>
                    <Bell size={40} style={{ opacity: 0.3, marginBottom: 12 }} />
                    <p>No notifications {unreadOnly ? '(unread)' : 'yet'}</p>
                </div>
            ) : (
                Object.entries(grouped).map(([dateKey, items]) => (
                    <div key={dateKey} style={{ marginBottom: 24 }}>
                        <div style={{
                            fontSize: 12, fontWeight: 600, color: 'var(--color-text-muted, #94a3b8)',
                            textTransform: 'uppercase', letterSpacing: 1, marginBottom: 8,
                        }}>
                            {dateKey}
                        </div>
                        <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
                            {items.map((n, idx) => {
                                const style = NOTIF_STYLES[n.notification_type] || NOTIF_STYLES.info;
                                return (
                                    <div key={n.id} style={{
                                        padding: '14px 20px',
                                        borderBottom: idx < items.length - 1 ? '1px solid var(--color-border, #1e293b)' : 'none',
                                        background: n.is_read ? 'transparent' : style.bg,
                                        display: 'flex', gap: 12, alignItems: 'flex-start',
                                        cursor: n.is_read ? 'default' : 'pointer',
                                        transition: 'background 0.2s',
                                    }}
                                        onClick={() => !n.is_read && markRead.mutate(n.id)}
                                    >
                                        <div style={{
                                            width: 32, height: 32, borderRadius: 8,
                                            background: style.bg, color: style.color,
                                            display: 'flex', alignItems: 'center', justifyContent: 'center',
                                            flexShrink: 0,
                                        }}>
                                            {style.icon}
                                        </div>
                                        <div style={{ flex: 1, minWidth: 0 }}>
                                            <div style={{
                                                fontWeight: n.is_read ? 400 : 600, fontSize: 14,
                                                display: 'flex', justifyContent: 'space-between', gap: 8,
                                            }}>
                                                <span>{n.title}</span>
                                                <span style={{ fontSize: 11, color: 'var(--color-text-muted, #64748b)', flexShrink: 0 }}>
                                                    {formatTime(n.created_at)}
                                                </span>
                                            </div>
                                            <div style={{ fontSize: 13, color: 'var(--color-text-muted, #94a3b8)', marginTop: 4, lineHeight: 1.5 }}>
                                                {n.message}
                                            </div>
                                            {n.metadata_json && Object.keys(n.metadata_json).length > 0 && (
                                                <div style={{
                                                    display: 'flex', gap: 12, marginTop: 8, flexWrap: 'wrap',
                                                }}>
                                                    {n.metadata_json.regulations_added > 0 && (
                                                        <span style={{ fontSize: 12, padding: '2px 8px', borderRadius: 12, background: 'rgba(59,130,246,0.12)', color: '#60a5fa' }}>
                                                            +{n.metadata_json.regulations_added} regs
                                                        </span>
                                                    )}
                                                    {n.metadata_json.gaps_added > 0 && (
                                                        <span style={{ fontSize: 12, padding: '2px 8px', borderRadius: 12, background: 'rgba(245,158,11,0.12)', color: '#fbbf24' }}>
                                                            +{n.metadata_json.gaps_added} gaps
                                                        </span>
                                                    )}
                                                    {n.metadata_json.duration_seconds && (
                                                        <span style={{ fontSize: 12, padding: '2px 8px', borderRadius: 12, background: 'rgba(148,163,184,0.12)', color: '#94a3b8' }}>
                                                            {n.metadata_json.duration_seconds}s
                                                        </span>
                                                    )}
                                                </div>
                                            )}
                                        </div>
                                        {!n.is_read && (
                                            <div style={{
                                                width: 8, height: 8, borderRadius: '50%',
                                                background: 'var(--color-primary, #3b82f6)',
                                                flexShrink: 0, marginTop: 6,
                                            }} />
                                        )}
                                    </div>
                                );
                            })}
                        </div>
                    </div>
                ))
            )}

            {/* Pagination */}
            {totalPages > 1 && (
                <div style={{ display: 'flex', justifyContent: 'center', gap: 8, padding: '16px 0' }}>
                    <button className="btn btn-secondary" disabled={page <= 1} onClick={() => setPage(page - 1)} style={{ fontSize: 13 }}>
                        Previous
                    </button>
                    <span style={{ padding: '8px 16px', fontSize: 13, color: 'var(--color-text-muted)' }}>
                        Page {page} of {totalPages}
                    </span>
                    <button className="btn btn-secondary" disabled={page >= totalPages} onClick={() => setPage(page + 1)} style={{ fontSize: 13 }}>
                        Next
                    </button>
                </div>
            )}
        </div>
    );
}
