import { useQuery } from '@tanstack/react-query';
import { useAuthSession } from '../auth/AuthProvider';
import {
    FileText,
    AlertTriangle,
    Send,
    TrendingUp,
    Shield,
    Activity,
    Layers,
} from 'lucide-react';
import apiClient from '../api/client';

// Module colors matching other pages
const MODULE_COLORS = {
    'IDT': '#6366f1', 'Care Plan': '#8b5cf6', 'Pharmacy': '#ec4899', 'Enrollment': '#f59e0b',
    'Claims': '#14b8a6', 'Transportation': '#06b6d4', 'Quality': '#22c55e', 'Billing': '#f97316',
    'Authorization': '#a855f7', 'Member Services': '#3b82f6', 'Provider Network': '#64748b',
    'Reporting': '#10b981', 'Administration': '#78716c',
};

const LAYER_STYLES = {
    frontend: { bg: 'rgba(99, 102, 241, 0.12)', color: '#818cf8', label: 'FE' },
    backend:  { bg: 'rgba(245, 158, 11, 0.12)', color: '#fbbf24', label: 'BE' },
    both:     { bg: 'rgba(236, 72, 153, 0.12)', color: '#f472b6', label: 'Both' },
    unknown:  { bg: 'rgba(100, 116, 139, 0.12)', color: '#94a3b8', label: '?' },
};

export default function Dashboard() {
    const { sessionToken } = useAuthSession();
    apiClient.setToken(sessionToken);

    const { data: dashboardData, isLoading: isDashboardLoading } = useQuery({
        queryKey: ['dashboard'],
        queryFn: () => apiClient.getDashboard(),
        enabled: !!sessionToken,
    });

    const { data: gapsData, isLoading: isGapsLoading } = useQuery({
        queryKey: ['gaps', { page_size: 10, status: 'open' }],
        queryFn: () => apiClient.getGaps({ page_size: 10, status: 'open' }),
        enabled: !!sessionToken,
    });

    const { data: regsData } = useQuery({
        queryKey: ['regulations', { page_size: 50 }],
        queryFn: () => apiClient.getRegulations({ page_size: 50 }),
        enabled: !!sessionToken,
    });

    const { data: gapsSummary } = useQuery({
        queryKey: ['gaps-summary'],
        queryFn: () => apiClient.getGapsSummary(),
        enabled: !!sessionToken,
    });

    if (isDashboardLoading || isGapsLoading) {
        return <div className="loading-card"><div className="loading-spinner" /></div>;
    }

    // Use mock only for dashboard API; regulations and gaps come from live data
    const dashboard = dashboardData || {
        communications: { total: 8, drafts: 2, pending_approval: 1, sent: 5 },
        isMock: true,
    };

    const recentGaps = gapsData?.items || [];
    const regulations = regsData?.items || [];
    const gapSummary = gapsSummary || { critical: 0, high: 0, medium: 0, low: 0, total: 0 };

    // Live statistics from actual data
    const regCount = regsData?.total || regulations.length || 0;
    const totalGaps = gapSummary.total || 0;
    const criticalGaps = gapSummary.critical || 0;

    // Module heatmap from all gaps
    const moduleHeatmap = {};
    recentGaps.forEach(g => {
        (g.affected_modules || []).forEach(m => {
            moduleHeatmap[m] = (moduleHeatmap[m] || 0) + 1;
        });
    });
    const sortedModules = Object.entries(moduleHeatmap).sort((a, b) => b[1] - a[1]);

    return (
        <div className="animate-in">
            <div className="page-header">
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <h1 className="page-title">Compliance Dashboard</h1>
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
                        Regulations Tracked
                    </div>
                    <div className="stat-value">{regCount}</div>
                    <div className="stat-change">
                        <TrendingUp size={12} />
                        from Federal Register AI analysis
                    </div>
                </div>

                <div className="stat-card animate-in stagger-2" style={{ '--stat-gradient': 'var(--gradient-danger)' }}>
                    <div className="stat-label">
                        <AlertTriangle size={14} style={{ display: 'inline', marginRight: 6, verticalAlign: 'middle' }} />
                        Open Gaps
                    </div>
                    <div className="stat-value">{totalGaps}</div>
                    <div className="stat-change" style={{ color: 'var(--color-critical)' }}>
                        {criticalGaps} critical
                    </div>
                </div>

                <div className="stat-card animate-in stagger-3" style={{ '--stat-gradient': 'var(--gradient-success)' }}>
                    <div className="stat-label">
                        <Send size={14} style={{ display: 'inline', marginRight: 6, verticalAlign: 'middle' }} />
                        Communications
                    </div>
                    <div className="stat-value">
                        {dashboard.communications?.sent || 0}
                        {dashboard.isMock && <PreviewBadge />}
                    </div>
                    <div className="stat-change">
                        {dashboard.communications?.drafts || 0} drafts pending
                    </div>
                </div>

                <div className="stat-card animate-in stagger-4" style={{ '--stat-gradient': 'var(--gradient-info)' }}>
                    <div className="stat-label">
                        <Activity size={14} style={{ display: 'inline', marginRight: 6, verticalAlign: 'middle' }} />
                        Module Impact
                    </div>
                    <div className="stat-value">{sortedModules.length}</div>
                    <div className="stat-change">
                        PCO modules affected
                    </div>
                </div>
            </div>

            {/* Module Heatmap */}
            {sortedModules.length > 0 && (
                <div style={{ marginTop: 'var(--space-6)' }}>
                    <div className="card">
                        <div className="card-header">
                            <div>
                                <h2 className="card-title">Module Impact Heatmap</h2>
                                <p className="card-subtitle">PCO modules ranked by number of compliance gaps</p>
                            </div>
                            <Shield size={20} color="var(--color-accent)" />
                        </div>
                        <div style={{ display: 'flex', gap: 'var(--space-3)', flexWrap: 'wrap', padding: '0 var(--space-4) var(--space-4)' }}>
                            {sortedModules.map(([mod, count]) => {
                                const maxCount = sortedModules[0]?.[1] || 1;
                                const intensity = Math.max(0.3, count / maxCount);
                                const color = MODULE_COLORS[mod] || '#64748b';
                                return (
                                    <div key={mod} style={{
                                        padding: '8px 14px', borderRadius: 'var(--radius-lg)',
                                        background: `${color}${Math.round(intensity * 30).toString(16).padStart(2, '0')}`,
                                        border: `1px solid ${color}${Math.round(intensity * 50).toString(16).padStart(2, '0')}`,
                                        display: 'flex', alignItems: 'center', gap: 8,
                                        transition: 'transform 0.2s', cursor: 'default',
                                    }}>
                                        <span style={{ color, fontWeight: 600, fontSize: 'var(--font-size-sm)' }}>{mod}</span>
                                        <span style={{
                                            background: color, color: '#fff', borderRadius: 'var(--radius-full)',
                                            padding: '1px 8px', fontSize: 'var(--font-size-xs)', fontWeight: 700,
                                            minWidth: 20, textAlign: 'center',
                                        }}>{count}</span>
                                    </div>
                                );
                            })}
                        </div>
                    </div>
                </div>
            )}




            {/* Bottom cards */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-6)', marginTop: 'var(--space-6)' }}>
                <div className="card">
                    <div className="card-header">
                        <h2 className="card-title">Severity Breakdown</h2>
                    </div>
                    <div style={{ padding: 'var(--space-4)' }}>
                        <SeverityBar label="Critical" count={gapSummary.critical} total={totalGaps} color="var(--color-critical)" />
                        <SeverityBar label="High" count={gapSummary.high} total={totalGaps} color="var(--color-danger)" />
                        <SeverityBar label="Medium" count={gapSummary.medium} total={totalGaps} color="var(--color-warning)" />
                        <SeverityBar label="Low" count={gapSummary.low} total={totalGaps} color="var(--color-success)" />
                    </div>
                </div>

                <div className="card">
                    <div className="card-header">
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                            <h2 className="card-title">Exec Reporting</h2>
                            <PreviewBadge />
                        </div>
                    </div>
                    <div style={{ textAlign: 'center', padding: 'var(--space-6)' }}>
                        <div style={{
                            fontSize: 'var(--font-size-4xl)', fontWeight: 800,
                            background: 'var(--gradient-primary)', WebkitBackgroundClip: 'text',
                            WebkitTextFillColor: 'transparent',
                        }}>
                            Phase 3
                        </div>
                        <p style={{ color: 'var(--color-text-muted)', fontSize: 'var(--font-size-sm)', marginTop: 'var(--space-2)' }}>
                            Executive dashboards & trend reports coming next
                        </p>
                    </div>
                </div>
            </div>
        </div>
    );
}

function PreviewBadge() {
    return (
        <span style={{
            display: 'inline-flex', alignItems: 'center', gap: 4, padding: '2px 8px',
            borderRadius: 20, fontSize: '10px', fontWeight: 600,
            background: 'linear-gradient(135deg, rgba(245, 158, 11, 0.15), rgba(249, 115, 22, 0.15))',
            color: '#f59e0b', border: '1px solid rgba(245, 158, 11, 0.3)',
        }}>
            <Layers size={8} />
            Preview
        </span>
    );
}

function LayerBadge({ layer }) {
    const style = LAYER_STYLES[layer] || LAYER_STYLES.unknown;
    return (
        <span style={{
            display: 'inline-flex', padding: '2px 8px', borderRadius: 'var(--radius-full)',
            fontSize: '10px', fontWeight: 600, background: style.bg, color: style.color,
        }}>
            {style.label}
        </span>
    );
}

function SeverityBar({ label, count, total, color }) {
    const pct = total > 0 ? (count / total) * 100 : 0;
    return (
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 12 }}>
            <span style={{ width: 60, fontSize: 'var(--font-size-sm)', color: 'var(--color-text-secondary)' }}>{label}</span>
            <div style={{ flex: 1, height: 8, background: 'var(--color-border)', borderRadius: 4, overflow: 'hidden' }}>
                <div style={{ width: `${pct}%`, height: '100%', background: color, borderRadius: 4, transition: 'width 0.5s ease' }} />
            </div>
            <span style={{ width: 30, textAlign: 'right', fontWeight: 700, fontSize: 'var(--font-size-sm)', color }}>{count}</span>
        </div>
    );
}

function formatStatus(status) {
    return (status || '').replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}
