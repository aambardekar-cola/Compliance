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

    const { data: dashboardData, isLoading: isDashboardLoading } = useQuery({
        queryKey: ['dashboard'],
        queryFn: () => apiClient.getDashboard(),
        enabled: !!sessionToken,
    });

    const { data: gapsData, isLoading: isGapsLoading } = useQuery({
        queryKey: ['gaps', { page_size: 5 }],
        queryFn: () => apiClient.getGaps({ page_size: 5 }),
        enabled: !!sessionToken,
    });

    if (isDashboardLoading || isGapsLoading) {
        return <div className="loading-card"><div className="loading-spinner" /></div>;
    }

    // Use mock data if API isn't connected yet
    const dashboard = dashboardData || {
        regulations: { total: 12, proposed: 3, comment_period: 2, final_rule: 5, effective: 2, avg_relevance: 0.78 },
        gaps: { total: 24, critical: 3, high: 7, open: 14, resolved: 10, total_effort_hours: 320 },
        communications: { total: 8, drafts: 2, pending_approval: 1, sent: 5 },
        isMock: true,
    };
    
    // AI generated gaps from DB
    const recentGaps = gapsData?.items || [];

    return (
        <div className="animate-in">
            <div className="page-header">
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <h1 className="page-title">Compliance Dashboard</h1>
                    {dashboard.isMock && <span className="badge badge-medium">MOCK DATA</span>}
                </div>
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

            {/* AI Identified Gaps */}
            <div className="card">
                <div className="card-header">
                    <div>
                        <h2 className="card-title">AI Identified Gaps</h2>
                        <p className="card-subtitle">Recent actionable requirements extracted by Claude 3 Bedrock</p>
                    </div>
                    <AlertTriangle size={20} color="var(--color-critical)" />
                </div>

                <table className="data-table">
                    <thead>
                        <tr>
                            <th>Requirement Title</th>
                            <th>Target Modules</th>
                            <th>Severity</th>
                            <th>Status</th>
                        </tr>
                    </thead>
                    <tbody>
                        {recentGaps.length === 0 ? (
                            <tr>
                                <td colSpan="4" style={{ textAlign: 'center', padding: 'var(--space-8)' }}>
                                    No compliance gaps identified yet. (Waiting for scraper AI analysis)
                                </td>
                            </tr>
                        ) : recentGaps.map((g) => (
                            <tr key={g.id}>
                                <td style={{ color: 'var(--color-text-primary)', fontWeight: 500, maxWidth: '400px', whiteSpace: 'normal' }}>
                                    {g.title}
                                    {g.is_new_requirement && (
                                        <span className="badge badge-accent" style={{ marginLeft: '8px', fontSize: '10px' }}>NEW</span>
                                    )}
                                </td>
                                <td>{g.affected_modules && g.affected_modules.length > 0 ? g.affected_modules.join(', ') : 'Unassigned'}</td>
                                <td>
                                    <span style={{ 
                                        color: g.severity === 'critical' ? 'var(--color-critical)' : g.severity === 'high' ? 'var(--color-danger)' : 'var(--color-warning)',
                                        fontWeight: 600
                                    }}>
                                        {formatStatus(g.severity)}
                                    </span>
                                </td>
                                <td>
                                    <span className="badge badge-info">
                                        <span className="badge-dot" />
                                        {formatStatus(g.status)}
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
