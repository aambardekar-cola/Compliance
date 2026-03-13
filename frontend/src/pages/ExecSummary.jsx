import { useQuery } from '@tanstack/react-query';
import { useAuthSession } from '../auth/AuthProvider';
import { BarChart3, AlertTriangle, TrendingUp, CheckCircle } from 'lucide-react';
import apiClient from '../api/client';

const MOCK_REPORTS = [
    {
        id: '1', week_start: '2026-02-24', week_end: '2026-03-02',
        metrics: { new_regulations: 2, gaps_identified: 5, gaps_resolved: 3, compliance_score: 72 },
        risks: [
            { title: 'API Interoperability deadline approaching', severity: 'high', description: 'FHIR API implementation behind schedule' },
            { title: 'Service delivery module refactor scope expansion', severity: 'medium', description: 'Additional edge cases identified' },
        ],
        highlights: ['Resolved grievance tracking gap', 'Completed personnel clearance module'],
        sent_at: '2026-03-03T08:00:00', created_at: '2026-03-03',
    },
    {
        id: '2', week_start: '2026-02-17', week_end: '2026-02-23',
        metrics: { new_regulations: 1, gaps_identified: 3, gaps_resolved: 2, compliance_score: 68 },
        risks: [
            { title: 'CY2026 Final Rule implementation critical gaps', severity: 'critical', description: '3 critical gaps in service delivery timeframes' },
        ],
        highlights: ['Ingested CY2026 PACE Final Rule'],
        sent_at: '2026-02-24T08:00:00', created_at: '2026-02-24',
    },
];

export default function ExecSummary() {
    const { sessionToken } = useAuthSession();
    apiClient.setToken(sessionToken);

    const { data, isLoading } = useQuery({
        queryKey: ['reports'],
        queryFn: () => apiClient.getReports(),
        enabled: !!sessionToken,
    });

    const reports = data?.items || MOCK_REPORTS;

    return (
        <div className="animate-in">
            <div className="page-header">
                <h1 className="page-title">Executive Reports</h1>
                <p className="page-description">
                    Weekly compliance progress summaries for leadership
                </p>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-6)' }}>
                {reports.map((report) => (
                    <div key={report.id} className="card">
                        <div className="card-header">
                            <div>
                                <h2 className="card-title">
                                    Week of {report.week_start} — {report.week_end}
                                </h2>
                                <p className="card-subtitle">
                                    Sent {report.sent_at ? new Date(report.sent_at).toLocaleDateString() : 'Not sent'}
                                </p>
                            </div>
                            <BarChart3 size={20} color="var(--color-accent-light)" />
                        </div>

                        {/* Metrics Grid */}
                        <div style={{
                            display: 'grid',
                            gridTemplateColumns: 'repeat(5, 1fr)',
                            gap: 'var(--space-4)',
                            marginBottom: 'var(--space-6)',
                        }}>
                            <MetricBox label="New Regs" value={report.metrics.new_regulations} icon={<BarChart3 size={14} />} />
                            <MetricBox label="Gaps Found" value={report.metrics.gaps_identified} icon={<AlertTriangle size={14} />} color="var(--color-warning)" />
                            <MetricBox label="Gaps Resolved" value={report.metrics.gaps_resolved} icon={<CheckCircle size={14} />} color="var(--color-success)" />
                            <MetricBox label="Score" value={`${report.metrics.compliance_score}%`} icon={<TrendingUp size={14} />} color="var(--color-accent-light)" />
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
