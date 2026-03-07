import { useQuery } from '@tanstack/react-query';
import { useAuthSession } from '../auth/AuthProvider';
import {
    FileText,
    AlertTriangle,
    Send,
    Clock,
    TrendingUp,
    Shield,
    Activity,
} from 'lucide-react';
import apiClient from '../api/client';

export default function Dashboard() {
    const { sessionToken } = useAuthSession();
    apiClient.setToken(sessionToken);

    const { data, isLoading, error } = useQuery({
        queryKey: ['dashboard'],
        queryFn: () => apiClient.getDashboard(),
        enabled: !!sessionToken,
    });

    if (isLoading) {
        return <div className="loading-card"><div className="loading-spinner" /></div>;
    }

    // Use mock data if API isn't connected yet
    const dashboard = data || {
        regulations: { total: 12, proposed: 3, comment_period: 2, final_rule: 5, effective: 2, avg_relevance: 0.78 },
        gaps: { total: 24, critical: 3, high: 7, open: 14, resolved: 10, total_effort_hours: 320 },
        communications: { total: 8, drafts: 2, pending_approval: 1, sent: 5 },
        upcoming_deadlines: [
            { id: '1', title: 'CY2026 PACE Final Rule — Service Delivery Timeframes', effective_date: '2026-01-01', status: 'final_rule' },
            { id: '2', title: 'PACE Participant Rights Updates', effective_date: '2026-04-01', status: 'proposed' },
            { id: '3', title: 'Interoperability & Prior Auth API Requirements', effective_date: '2026-07-01', status: 'comment_period' },
        ],
    };

    return (
        <div className="animate-in">
            <div className="page-header">
                <h1 className="page-title">Compliance Dashboard</h1>
                <p className="page-description">
                    Real-time overview of PACE regulatory compliance posture for PaceCareOnline
                </p>
            </div>

            {/* Stat Cards */}
            <div className="stats-grid">
                <div className="stat-card animate-in stagger-1" style={{ '--stat-gradient': 'var(--gradient-primary)' }}>
                    <div className="stat-label">
                        <FileText size={14} style={{ display: 'inline', marginRight: 6, verticalAlign: 'middle' }} />
                        Tracked Regulations
                    </div>
                    <div className="stat-value">{dashboard.regulations.total}</div>
                    <div className="stat-change">
                        <TrendingUp size={12} />
                        {dashboard.regulations.proposed} proposed
                    </div>
                </div>

                <div className="stat-card animate-in stagger-2" style={{ '--stat-gradient': 'var(--gradient-danger)' }}>
                    <div className="stat-label">
                        <AlertTriangle size={14} style={{ display: 'inline', marginRight: 6, verticalAlign: 'middle' }} />
                        Open Gaps
                    </div>
                    <div className="stat-value">{dashboard.gaps.open}</div>
                    <div className="stat-change" style={{ color: 'var(--color-critical)' }}>
                        {dashboard.gaps.critical} critical
                    </div>
                </div>

                <div className="stat-card animate-in stagger-3" style={{ '--stat-gradient': 'var(--gradient-success)' }}>
                    <div className="stat-label">
                        <Send size={14} style={{ display: 'inline', marginRight: 6, verticalAlign: 'middle' }} />
                        Communications Sent
                    </div>
                    <div className="stat-value">{dashboard.communications.sent}</div>
                    <div className="stat-change">
                        {dashboard.communications.drafts} drafts pending
                    </div>
                </div>

                <div className="stat-card animate-in stagger-4" style={{ '--stat-gradient': 'var(--gradient-info)' }}>
                    <div className="stat-label">
                        <Activity size={14} style={{ display: 'inline', marginRight: 6, verticalAlign: 'middle' }} />
                        Estimated Effort
                    </div>
                    <div className="stat-value">{dashboard.gaps.total_effort_hours}h</div>
                    <div className="stat-change">
                        {dashboard.gaps.resolved} gaps resolved
                    </div>
                </div>
            </div>

            {/* Upcoming Deadlines */}
            <div className="card">
                <div className="card-header">
                    <div>
                        <h2 className="card-title">Upcoming Deadlines</h2>
                        <p className="card-subtitle">Regulations with approaching effective dates</p>
                    </div>
                    <Clock size={20} color="var(--color-text-muted)" />
                </div>

                <table className="data-table">
                    <thead>
                        <tr>
                            <th>Regulation</th>
                            <th>Effective Date</th>
                            <th>Status</th>
                        </tr>
                    </thead>
                    <tbody>
                        {dashboard.upcoming_deadlines.map((d) => (
                            <tr key={d.id}>
                                <td style={{ color: 'var(--color-text-primary)', fontWeight: 500 }}>
                                    {d.title}
                                </td>
                                <td>{d.effective_date}</td>
                                <td>
                                    <span className={`badge badge-${getStatusColor(d.status)}`}>
                                        <span className="badge-dot" />
                                        {formatStatus(d.status)}
                                    </span>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>

            {/* Relevance Overview */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-6)', marginTop: 'var(--space-6)' }}>
                <div className="card">
                    <div className="card-header">
                        <h2 className="card-title">Compliance Score</h2>
                    </div>
                    <div style={{ textAlign: 'center', padding: 'var(--space-6)' }}>
                        <div style={{
                            fontSize: 'var(--font-size-4xl)',
                            fontWeight: 800,
                            background: 'var(--gradient-success)',
                            WebkitBackgroundClip: 'text',
                            WebkitTextFillColor: 'transparent',
                        }}>
                            {Math.round((dashboard.gaps.resolved / Math.max(dashboard.gaps.total, 1)) * 100)}%
                        </div>
                        <p style={{ color: 'var(--color-text-muted)', fontSize: 'var(--font-size-sm)', marginTop: 'var(--space-2)' }}>
                            of identified gaps resolved
                        </p>
                    </div>
                </div>

                <div className="card">
                    <div className="card-header">
                        <h2 className="card-title">Avg. Relevance Score</h2>
                    </div>
                    <div style={{ textAlign: 'center', padding: 'var(--space-6)' }}>
                        <div style={{
                            fontSize: 'var(--font-size-4xl)',
                            fontWeight: 800,
                            background: 'var(--gradient-primary)',
                            WebkitBackgroundClip: 'text',
                            WebkitTextFillColor: 'transparent',
                        }}>
                            {(dashboard.regulations.avg_relevance * 100).toFixed(0)}%
                        </div>
                        <p style={{ color: 'var(--color-text-muted)', fontSize: 'var(--font-size-sm)', marginTop: 'var(--space-2)' }}>
                            average PACE relevance across {dashboard.regulations.total} regulations
                        </p>
                    </div>
                </div>
            </div>
        </div>
    );
}

function getStatusColor(status) {
    const map = {
        proposed: 'info',
        comment_period: 'warning',
        final_rule: 'accent',
        effective: 'success',
    };
    return map[status] || 'info';
}

function formatStatus(status) {
    return status.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}
