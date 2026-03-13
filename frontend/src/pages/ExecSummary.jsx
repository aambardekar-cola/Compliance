import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useAuthSession } from '../auth/AuthProvider';
import { BarChart3, AlertTriangle, TrendingUp, CheckCircle, Send, Zap, Loader2 } from 'lucide-react';
import apiClient from '../api/client';

export default function ExecSummary() {
    const { sessionToken, user } = useAuthSession();
    const queryClient = useQueryClient();
    apiClient.setToken(sessionToken);

    const isAdmin = user?.role === 'internal_admin';

    const { data, isLoading } = useQuery({
        queryKey: ['reports'],
        queryFn: () => apiClient.getReports(),
        enabled: !!sessionToken,
    });

    const { data: scoresData } = useQuery({
        queryKey: ['compliance-scores'],
        queryFn: () => apiClient.getComplianceScores(),
        enabled: !!sessionToken,
    });

    const generateMutation = useMutation({
        mutationFn: () => apiClient.generateReport(),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['reports'] });
            queryClient.invalidateQueries({ queryKey: ['compliance-scores'] });
        },
    });

    const sendMutation = useMutation({
        mutationFn: (id) => apiClient.sendReport(id),
    });

    const reports = data?.items || [];
    const moduleScores = scoresData?.module_scores || {};
    const overallScore = scoresData?.overall_score ?? null;

    return (
        <div className="animate-in">
            <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div>
                    <h1 className="page-title">Executive Reports</h1>
                    <p className="page-description">
                        Weekly compliance progress summaries for leadership
                    </p>
                </div>
                {isAdmin && (
                    <button
                        className="btn btn-primary"
                        onClick={() => generateMutation.mutate()}
                        disabled={generateMutation.isPending}
                        style={{ display: 'flex', alignItems: 'center', gap: 8 }}
                    >
                        {generateMutation.isPending ? (
                            <Loader2 size={16} className="spin" />
                        ) : (
                            <Zap size={16} />
                        )}
                        Generate Report
                    </button>
                )}
            </div>

            {/* Compliance Score Overview */}
            {overallScore !== null && (
                <div className="card" style={{ marginBottom: 'var(--space-6)' }}>
                    <div className="card-header">
                        <h2 className="card-title">Compliance Score Overview</h2>
                        <div style={{
                            fontSize: 'var(--font-size-2xl)',
                            fontWeight: 700,
                            color: overallScore >= 80 ? 'var(--color-success)' : overallScore >= 60 ? 'var(--color-warning)' : 'var(--color-danger)',
                        }}>
                            {overallScore}%
                        </div>
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
                        {Object.entries(moduleScores)
                            .sort(([, a], [, b]) => a - b)
                            .map(([mod, score]) => (
                                <div key={mod} style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
                                    <span style={{
                                        width: 140,
                                        fontSize: 'var(--font-size-sm)',
                                        color: 'var(--color-text-secondary)',
                                        flexShrink: 0,
                                    }}>
                                        {mod}
                                    </span>
                                    <div style={{
                                        flex: 1,
                                        height: 8,
                                        background: 'var(--color-bg-glass)',
                                        borderRadius: 4,
                                        overflow: 'hidden',
                                    }}>
                                        <div style={{
                                            width: `${score}%`,
                                            height: '100%',
                                            background: score >= 80
                                                ? 'var(--color-success)'
                                                : score >= 60
                                                    ? 'var(--color-warning)'
                                                    : 'var(--color-danger)',
                                            borderRadius: 4,
                                            transition: 'width 0.6s ease',
                                        }} />
                                    </div>
                                    <span style={{
                                        width: 48,
                                        textAlign: 'right',
                                        fontSize: 'var(--font-size-sm)',
                                        fontWeight: 600,
                                        color: score >= 80 ? 'var(--color-success)' : score >= 60 ? 'var(--color-warning)' : 'var(--color-danger)',
                                    }}>
                                        {score}%
                                    </span>
                                </div>
                            ))}
                    </div>
                </div>
            )}

            {/* Reports list */}
            {isLoading ? (
                <div style={{ textAlign: 'center', padding: 'var(--space-12)', color: 'var(--color-text-muted)' }}>
                    <Loader2 size={24} className="spin" />
                    <p style={{ marginTop: 'var(--space-3)' }}>Loading reports...</p>
                </div>
            ) : reports.length === 0 ? (
                <div className="card" style={{ textAlign: 'center', padding: 'var(--space-12)' }}>
                    <BarChart3 size={48} color="var(--color-text-muted)" style={{ margin: '0 auto var(--space-4)' }} />
                    <h3 style={{ color: 'var(--color-text-secondary)', marginBottom: 'var(--space-2)' }}>No reports yet</h3>
                    <p style={{ color: 'var(--color-text-muted)', fontSize: 'var(--font-size-sm)' }}>
                        {isAdmin
                            ? 'Click "Generate Report" to create the first executive summary.'
                            : 'Executive reports will appear here once generated.'}
                    </p>
                </div>
            ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-6)' }}>
                    {reports.map((report) => (
                        <div key={report.id} className="card">
                            <div className="card-header">
                                <div>
                                    <h2 className="card-title">
                                        Week of {report.week_start} — {report.week_end}
                                    </h2>
                                    <p className="card-subtitle">
                                        {report.sent_at
                                            ? `Sent ${new Date(report.sent_at).toLocaleDateString()}`
                                            : 'Not sent'}
                                    </p>
                                </div>
                                <div style={{ display: 'flex', gap: 'var(--space-2)', alignItems: 'center' }}>
                                    {isAdmin && !report.sent_at && (
                                        <button
                                            className="btn btn-secondary"
                                            onClick={() => sendMutation.mutate(report.id)}
                                            disabled={sendMutation.isPending}
                                            style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 'var(--font-size-sm)' }}
                                            title="Send via email"
                                        >
                                            <Send size={14} /> Send
                                        </button>
                                    )}
                                    <BarChart3 size={20} color="var(--color-accent-light)" />
                                </div>
                            </div>

                            {/* Metrics Grid */}
                            <div style={{
                                display: 'grid',
                                gridTemplateColumns: 'repeat(4, 1fr)',
                                gap: 'var(--space-4)',
                                marginBottom: 'var(--space-6)',
                            }}>
                                <MetricBox label="New Regs" value={report.metrics?.new_regulations ?? 0} icon={<BarChart3 size={14} />} />
                                <MetricBox label="Gaps Found" value={report.metrics?.gaps_identified ?? 0} icon={<AlertTriangle size={14} />} color="var(--color-warning)" />
                                <MetricBox label="Gaps Resolved" value={report.metrics?.gaps_resolved ?? 0} icon={<CheckCircle size={14} />} color="var(--color-success)" />
                                <MetricBox label="Score" value={`${report.metrics?.compliance_score ?? 0}%`} icon={<TrendingUp size={14} />} color="var(--color-accent-light)" />
                            </div>

                            {/* Risks */}
                            {report.risks?.length > 0 && (
                                <div style={{ marginBottom: 'var(--space-5)' }}>
                                    <div className="detail-label" style={{ marginBottom: 'var(--space-3)' }}>Risks</div>
                                    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2)' }}>
                                        {report.risks.map((risk, i) => (
                                            <div key={i} style={{
                                                display: 'flex', alignItems: 'center', gap: 'var(--space-3)',
                                                padding: 'var(--space-3) var(--space-4)',
                                                background: `rgba(${risk.severity === 'critical' ? '239,68,68' : risk.severity === 'high' ? '249,115,22' : '245,158,11'}, 0.08)`,
                                                border: `1px solid rgba(${risk.severity === 'critical' ? '239,68,68' : risk.severity === 'high' ? '249,115,22' : '245,158,11'}, 0.2)`,
                                                borderRadius: 'var(--radius-md)',
                                                fontSize: 'var(--font-size-sm)',
                                            }}>
                                                <span className={`badge badge-${risk.severity}`}>{risk.severity}</span>
                                                <span style={{ color: 'var(--color-text-secondary)' }}>{risk.title}</span>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            )}

                            {/* Highlights */}
                            {report.highlights?.length > 0 && (
                                <div>
                                    <div className="detail-label" style={{ marginBottom: 'var(--space-3)' }}>Highlights</div>
                                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--space-2)' }}>
                                        {report.highlights.map((h, i) => (
                                            <span key={i} className="detail-tag" style={{
                                                background: 'rgba(16, 185, 129, 0.1)',
                                                borderColor: 'rgba(16, 185, 129, 0.2)',
                                                color: 'var(--color-success)',
                                            }}>
                                                <CheckCircle size={12} style={{ marginRight: 4 }} />{h}
                                            </span>
                                        ))}
                                    </div>
                                </div>
                            )}
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}

function MetricBox({ label, value, icon, color = 'var(--color-text-primary)' }) {
    return (
        <div style={{
            padding: 'var(--space-3)',
            background: 'var(--color-bg-glass)',
            border: '1px solid var(--color-border)',
            borderRadius: 'var(--radius-md)',
            textAlign: 'center',
        }}>
            <div style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)', marginBottom: 4, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 4 }}>
                {icon} {label}
            </div>
            <div style={{ fontSize: 'var(--font-size-xl)', fontWeight: 700, color }}>{value}</div>
        </div>
    );
}
