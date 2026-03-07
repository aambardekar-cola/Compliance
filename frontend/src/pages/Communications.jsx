import { useQuery } from '@tanstack/react-query';
import { useAuthSession } from '../auth/AuthProvider';
import { Send, Check, Clock, Edit } from 'lucide-react';
import apiClient from '../api/client';

const MOCK_COMMS = [
    {
        id: '1', type: 'new_regulation', subject: 'Important: New PACE Service Delivery Timeframe Requirements',
        status: 'sent', sent_at: '2026-02-20T10:00:00', recipient_count: 45, approved_by: 'admin@collabrios.com', created_at: '2026-02-18',
    },
    {
        id: '2', type: 'compliance_update', subject: 'Update: Participant Rights & Grievance Process Changes',
        status: 'sent', sent_at: '2026-02-15T14:00:00', recipient_count: 45, approved_by: 'admin@collabrios.com', created_at: '2026-02-13',
    },
    {
        id: '3', type: 'deadline_reminder', subject: 'Reminder: Interoperability API Requirements — Comment Period Closing',
        status: 'pending_approval', sent_at: null, recipient_count: 0, approved_by: null, created_at: '2026-03-01',
    },
    {
        id: '4', type: 'new_regulation', subject: 'Draft: Personnel Medical Clearance Implementation Guide',
        status: 'draft', sent_at: null, recipient_count: 0, approved_by: null, created_at: '2026-03-05',
    },
];

export default function Communications() {
    const { sessionToken } = useAuthSession();
    apiClient.setToken(sessionToken);

    const { data, isLoading } = useQuery({
        queryKey: ['communications'],
        queryFn: () => apiClient.getCommunications(),
        enabled: !!sessionToken,
    });

    const comms = data?.items || MOCK_COMMS;

    return (
        <div className="animate-in">
            <div className="page-header">
                <h1 className="page-title">Client Communications</h1>
                <p className="page-description">
                    AI-generated compliance communications for PCO clients
                </p>
            </div>

            <div className="card">
                {comms.length === 0 ? (
                    <div className="empty-state">
                        <Send />
                        <h3>No communications yet</h3>
                        <p>Communications will be generated as new regulations are processed.</p>
                    </div>
                ) : (
                    <table className="data-table">
                        <thead>
                            <tr>
                                <th>Communication</th>
                                <th>Type</th>
                                <th>Status</th>
                                <th>Recipients</th>
                                <th>Sent</th>
                                <th>Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            {comms.map((c) => (
                                <tr key={c.id}>
                                    <td style={{ color: 'var(--color-text-primary)', fontWeight: 500, maxWidth: 400 }}>
                                        {c.subject}
                                    </td>
                                    <td>
                                        <span className="badge badge-accent">
                                            {c.type.replace(/_/g, ' ')}
                                        </span>
                                    </td>
                                    <td>
                                        <span className={`badge badge-${getCommStatusColor(c.status)}`}>
                                            <span className="badge-dot" />
                                            {formatStatus(c.status)}
                                        </span>
                                    </td>
                                    <td>{c.recipient_count || '—'}</td>
                                    <td style={{ fontSize: 'var(--font-size-xs)' }}>
                                        {c.sent_at ? new Date(c.sent_at).toLocaleDateString() : '—'}
                                    </td>
                                    <td>
                                        <div style={{ display: 'flex', gap: 'var(--space-2)' }}>
                                            {c.status === 'draft' && (
                                                <button className="btn btn-secondary" style={{ padding: '4px 12px', fontSize: 'var(--font-size-xs)' }}>
                                                    <Edit size={12} /> Edit
                                                </button>
                                            )}
                                            {c.status === 'pending_approval' && (
                                                <button className="btn btn-primary" style={{ padding: '4px 12px', fontSize: 'var(--font-size-xs)' }}>
                                                    <Check size={12} /> Approve
                                                </button>
                                            )}
                                            {c.status === 'approved' && (
                                                <button className="btn btn-primary" style={{ padding: '4px 12px', fontSize: 'var(--font-size-xs)' }}>
                                                    <Send size={12} /> Send
                                                </button>
                                            )}
                                        </div>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                )}
            </div>
        </div>
    );
}

function getCommStatusColor(s) {
    const m = { draft: 'medium', pending_approval: 'warning', approved: 'info', sent: 'success', failed: 'danger' };
    return m[s] || 'info';
}

function formatStatus(s) {
    return (s || '').replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}
