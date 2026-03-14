import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useAuthSession, useAuthUser } from '../auth/AuthProvider';
import {
    BarChart3, AlertTriangle, TrendingUp, CheckCircle, Send,
    Zap, Loader2, Mail, X, Plus, Calendar,
} from 'lucide-react';
import {
    LineChart, Line, AreaChart, Area,
    XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from 'recharts';
import apiClient from '../api/client';

const RANGE_PRESETS = [
    { label: '4 Weeks', weeks: 4 },
    { label: '8 Weeks', weeks: 8 },
    { label: '12 Weeks', weeks: 12 },
    { label: '26 Weeks', weeks: 26 },
];

const CHART_COLORS = [
    'hsl(220, 80%, 65%)',
    'hsl(160, 70%, 50%)',
    'hsl(280, 60%, 60%)',
    'hsl(30, 80%, 60%)',
    'hsl(340, 70%, 60%)',
    'hsl(190, 70%, 50%)',
];

export default function ExecSummary() {
    const { sessionToken } = useAuthSession();
    const { user } = useAuthUser();
    const queryClient = useQueryClient();
    apiClient.setToken(sessionToken);

    const isAdmin = user?.roles?.includes('internal_admin') || user?.role === 'INTERNAL_ADMIN';

    const [trendWeeks, setTrendWeeks] = useState(12);
    const [showEmailModal, setShowEmailModal] = useState(false);
    const [customRange, setCustomRange] = useState({ start: '', end: '' });

    // Queries
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

    const { data: trendsData } = useQuery({
        queryKey: ['report-trends', trendWeeks],
        queryFn: () => apiClient.getTrends(trendWeeks),
        enabled: !!sessionToken,
    });

    // Mutations
    const generateMutation = useMutation({
        mutationFn: (dateRange) => apiClient.generateReport(dateRange || null),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['reports'] });
            queryClient.invalidateQueries({ queryKey: ['compliance-scores'] });
            queryClient.invalidateQueries({ queryKey: ['report-trends'] });
        },
    });

    const sendMutation = useMutation({
        mutationFn: (id) => apiClient.sendReport(id),
    });

    const reports = data?.items || [];
    const moduleScores = scoresData?.module_scores || {};
    const overallScore = scoresData?.overall_score ?? null;

    // Build trend chart data
    const trendChartData = buildTrendChartData(trendsData);
    const gapChartData = buildGapChartData(trendsData);
    const moduleNames = trendsData?.module_scores ? Object.keys(trendsData.module_scores) : [];

    const handleGenerate = () => {
        if (customRange.start && customRange.end) {
            generateMutation.mutate({ weekStart: customRange.start, weekEnd: customRange.end });
        } else {
            generateMutation.mutate(null);
        }
    };

    return (
        <div className="animate-in">
            {/* Header */}
            <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 'var(--space-4)' }}>
                <div>
                    <h1 className="page-title">Executive Reports</h1>
                    <p className="page-description">
                        Weekly compliance progress summaries for leadership
                    </p>
                </div>
                {isAdmin && (
                    <div style={{ display: 'flex', gap: 'var(--space-2)', alignItems: 'center', flexWrap: 'wrap' }}>
                        {/* Custom date range */}
                        <div style={{ display: 'flex', gap: 'var(--space-2)', alignItems: 'center' }}>
                            <Calendar size={14} color="var(--color-text-muted)" />
                            <input
                                type="date"
                                value={customRange.start}
                                onChange={(e) => setCustomRange(prev => ({ ...prev, start: e.target.value }))}
                                style={dateInputStyle}
                                id="report-date-start"
                            />
                            <span style={{ color: 'var(--color-text-muted)', fontSize: 'var(--font-size-sm)' }}>to</span>
                            <input
                                type="date"
                                value={customRange.end}
                                onChange={(e) => setCustomRange(prev => ({ ...prev, end: e.target.value }))}
                                style={dateInputStyle}
                                id="report-date-end"
                            />
                        </div>
                        <button
                            className="btn btn-primary"
                            onClick={handleGenerate}
                            disabled={generateMutation.isPending}
                            style={{ display: 'flex', alignItems: 'center', gap: 6 }}
                            id="btn-generate-report"
                        >
                            {generateMutation.isPending ? (
                                <Loader2 size={16} className="spin" />
                            ) : (
                                <Zap size={16} />
                            )}
                            Generate Report
                        </button>
                        <button
                            className="btn btn-secondary"
                            onClick={() => setShowEmailModal(true)}
                            style={{ display: 'flex', alignItems: 'center', gap: 6 }}
                            id="btn-email-settings"
                        >
                            <Mail size={16} />
                            Email Settings
                        </button>
                    </div>
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
                            color: scoreColor(overallScore),
                        }}>
                            {overallScore}%
                        </div>
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
                        {Object.entries(moduleScores)
                            .sort(([, a], [, b]) => a - b)
                            .map(([mod, score]) => (
                                <div key={mod} style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
                                    <span style={{ width: 140, fontSize: 'var(--font-size-sm)', color: 'var(--color-text-secondary)', flexShrink: 0 }}>
                                        {mod}
                                    </span>
                                    <div style={{ flex: 1, height: 8, background: 'var(--color-bg-glass)', borderRadius: 4, overflow: 'hidden' }}>
                                        <div style={{
                                            width: `${score}%`, height: '100%',
                                            background: scoreColor(score),
                                            borderRadius: 4, transition: 'width 0.6s ease',
                                        }} />
                                    </div>
                                    <span style={{ width: 48, textAlign: 'right', fontSize: 'var(--font-size-sm)', fontWeight: 600, color: scoreColor(score) }}>
                                        {score}%
                                    </span>
                                </div>
                            ))}
                    </div>
                </div>
            )}

            {/* Trend Charts */}
            {trendChartData.length > 1 && (
                <div className="card" style={{ marginBottom: 'var(--space-6)' }}>
                    <div className="card-header" style={{ flexWrap: 'wrap', gap: 'var(--space-3)' }}>
                        <h2 className="card-title">
                            <TrendingUp size={18} style={{ marginRight: 8, verticalAlign: 'middle' }} />
                            Compliance Trends
                        </h2>
                        <div style={{ display: 'flex', gap: 'var(--space-1)' }}>
                            {RANGE_PRESETS.map(p => (
                                <button
                                    key={p.weeks}
                                    className={`btn ${trendWeeks === p.weeks ? 'btn-primary' : 'btn-secondary'}`}
                                    onClick={() => setTrendWeeks(p.weeks)}
                                    style={{ fontSize: 'var(--font-size-xs)', padding: '4px 10px' }}
                                    id={`btn-trend-${p.weeks}w`}
                                >
                                    {p.label}
                                </button>
                            ))}
                        </div>
                    </div>

                    {/* Overall score trend */}
                    <div style={{ marginBottom: 'var(--space-6)' }}>
                        <div className="detail-label" style={{ marginBottom: 'var(--space-3)' }}>Compliance Score Over Time</div>
                        <ResponsiveContainer width="100%" height={260}>
                            <LineChart data={trendChartData}>
                                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
                                <XAxis dataKey="label" tick={{ fontSize: 11, fill: 'var(--color-text-muted)' }} />
                                <YAxis domain={[0, 100]} tick={{ fontSize: 11, fill: 'var(--color-text-muted)' }} />
                                <Tooltip
                                    contentStyle={{ background: 'var(--color-bg-secondary)', border: '1px solid var(--color-border)', borderRadius: 8 }}
                                    labelStyle={{ color: 'var(--color-text-primary)' }}
                                />
                                <Legend />
                                <Line
                                    name="Overall"
                                    type="monotone"
                                    dataKey="overall"
                                    stroke="hsl(220, 80%, 65%)"
                                    strokeWidth={2.5}
                                    dot={{ r: 4 }}
                                    activeDot={{ r: 6 }}
                                />
                                {moduleNames.map((mod, i) => (
                                    <Line
                                        key={mod}
                                        name={mod}
                                        type="monotone"
                                        dataKey={mod}
                                        stroke={CHART_COLORS[(i + 1) % CHART_COLORS.length]}
                                        strokeWidth={1.5}
                                        dot={{ r: 2 }}
                                        strokeDasharray="5 3"
                                    />
                                ))}
                            </LineChart>
                        </ResponsiveContainer>
                    </div>

                    {/* Gaps identified vs resolved */}
                    {gapChartData.length > 1 && (
                        <div>
                            <div className="detail-label" style={{ marginBottom: 'var(--space-3)' }}>Gaps Found vs Resolved</div>
                            <ResponsiveContainer width="100%" height={200}>
                                <AreaChart data={gapChartData}>
                                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
                                    <XAxis dataKey="label" tick={{ fontSize: 11, fill: 'var(--color-text-muted)' }} />
                                    <YAxis tick={{ fontSize: 11, fill: 'var(--color-text-muted)' }} />
                                    <Tooltip
                                        contentStyle={{ background: 'var(--color-bg-secondary)', border: '1px solid var(--color-border)', borderRadius: 8 }}
                                        labelStyle={{ color: 'var(--color-text-primary)' }}
                                    />
                                    <Legend />
                                    <Area name="Identified" type="monotone" dataKey="identified" stroke="hsl(30, 80%, 60%)" fill="hsla(30, 80%, 60%, 0.15)" strokeWidth={2} />
                                    <Area name="Resolved" type="monotone" dataKey="resolved" stroke="hsl(160, 70%, 50%)" fill="hsla(160, 70%, 50%, 0.15)" strokeWidth={2} />
                                </AreaChart>
                            </ResponsiveContainer>
                        </div>
                    )}
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
                        <ReportCard
                            key={report.id}
                            report={report}
                            isAdmin={isAdmin}
                            sendMutation={sendMutation}
                        />
                    ))}
                </div>
            )}

            {/* Email Config Modal */}
            {showEmailModal && (
                <EmailConfigModal
                    onClose={() => setShowEmailModal(false)}
                    sessionToken={sessionToken}
                />
            )}
        </div>
    );
}


// ---- Sub-components ----

function ReportCard({ report, isAdmin, sendMutation }) {
    return (
        <div className="card">
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
                            id={`btn-send-${report.id}`}
                        >
                            <Send size={14} /> Send
                        </button>
                    )}
                    <BarChart3 size={20} color="var(--color-accent-light)" />
                </div>
            </div>

            {/* Metrics Grid */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 'var(--space-4)', marginBottom: 'var(--space-6)' }}>
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


function EmailConfigModal({ onClose, sessionToken }) {
    const queryClient = useQueryClient();
    apiClient.setToken(sessionToken);

    const [newEmail, setNewEmail] = useState('');
    const [error, setError] = useState('');

    const { data, isLoading } = useQuery({
        queryKey: ['recipients'],
        queryFn: () => apiClient.getRecipients(),
        enabled: !!sessionToken,
    });

    const updateMutation = useMutation({
        mutationFn: (emails) => apiClient.updateRecipients(emails),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['recipients'] });
            setError('');
        },
        onError: (err) => setError(err.message),
    });

    const emails = data?.emails || [];

    const addEmail = () => {
        const trimmed = newEmail.trim();
        if (!trimmed) return;
        if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(trimmed)) {
            setError('Invalid email address');
            return;
        }
        if (emails.includes(trimmed)) {
            setError('Email already in list');
            return;
        }
        updateMutation.mutate([...emails, trimmed]);
        setNewEmail('');
    };

    const removeEmail = (email) => {
        updateMutation.mutate(emails.filter(e => e !== email));
    };

    return (
        <div
            style={{
                position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                zIndex: 1000, backdropFilter: 'blur(4px)',
            }}
            onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
            id="email-config-modal"
        >
            <div className="card" style={{ width: '100%', maxWidth: 520, maxHeight: '80vh', overflow: 'auto' }}>
                <div className="card-header">
                    <h2 className="card-title">
                        <Mail size={18} style={{ marginRight: 8, verticalAlign: 'middle' }} />
                        Email Recipients
                    </h2>
                    <button className="btn btn-secondary" onClick={onClose} style={{ padding: 4 }} id="btn-close-email-modal">
                        <X size={18} />
                    </button>
                </div>

                <p style={{ fontSize: 'var(--font-size-sm)', color: 'var(--color-text-muted)', marginBottom: 'var(--space-4)' }}>
                    Configure who receives executive compliance reports via email.
                </p>

                {/* Add email */}
                <div style={{ display: 'flex', gap: 'var(--space-2)', marginBottom: 'var(--space-4)' }}>
                    <input
                        type="email"
                        value={newEmail}
                        onChange={(e) => { setNewEmail(e.target.value); setError(''); }}
                        onKeyDown={(e) => e.key === 'Enter' && addEmail()}
                        placeholder="name@company.com"
                        style={textInputStyle}
                        id="input-add-email"
                    />
                    <button
                        className="btn btn-primary"
                        onClick={addEmail}
                        disabled={updateMutation.isPending || !newEmail.trim()}
                        style={{ display: 'flex', alignItems: 'center', gap: 4, whiteSpace: 'nowrap' }}
                        id="btn-add-email"
                    >
                        <Plus size={16} /> Add
                    </button>
                </div>

                {error && (
                    <div style={{
                        fontSize: 'var(--font-size-sm)', color: 'var(--color-danger)',
                        marginBottom: 'var(--space-3)', padding: 'var(--space-2) var(--space-3)',
                        background: 'rgba(239,68,68,0.08)', borderRadius: 'var(--radius-sm)',
                    }}>
                        {error}
                    </div>
                )}

                {/* Email list */}
                {isLoading ? (
                    <div style={{ textAlign: 'center', padding: 'var(--space-6)', color: 'var(--color-text-muted)' }}>
                        <Loader2 size={20} className="spin" />
                    </div>
                ) : emails.length === 0 ? (
                    <div style={{ textAlign: 'center', padding: 'var(--space-6)', color: 'var(--color-text-muted)', fontSize: 'var(--font-size-sm)' }}>
                        No recipients configured yet.
                    </div>
                ) : (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2)' }}>
                        {emails.map((email) => (
                            <div key={email} style={{
                                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                                padding: 'var(--space-2) var(--space-3)',
                                background: 'var(--color-bg-glass)',
                                border: '1px solid var(--color-border)',
                                borderRadius: 'var(--radius-sm)',
                                fontSize: 'var(--font-size-sm)',
                            }}>
                                <span style={{ color: 'var(--color-text-secondary)' }}>{email}</span>
                                <button
                                    onClick={() => removeEmail(email)}
                                    style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--color-text-muted)', padding: 2 }}
                                    title="Remove"
                                    disabled={updateMutation.isPending}
                                >
                                    <X size={14} />
                                </button>
                            </div>
                        ))}
                    </div>
                )}

                <div style={{ marginTop: 'var(--space-4)', fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)' }}>
                    {emails.length} recipient{emails.length !== 1 ? 's' : ''} configured
                </div>
            </div>
        </div>
    );
}


// ---- Helpers ----

function scoreColor(score) {
    if (score >= 80) return 'var(--color-success)';
    if (score >= 60) return 'var(--color-warning)';
    return 'var(--color-danger)';
}

function buildTrendChartData(trendsData) {
    if (!trendsData?.labels?.length) return [];
    return trendsData.labels.map((label, i) => {
        const point = {
            label: formatWeekLabel(label),
            overall: trendsData.overall_score[i] || 0,
        };
        for (const [mod, scores] of Object.entries(trendsData.module_scores || {})) {
            point[mod] = scores[i] ?? null;
        }
        return point;
    });
}

function buildGapChartData(trendsData) {
    if (!trendsData?.labels?.length) return [];
    return trendsData.labels.map((label, i) => ({
        label: formatWeekLabel(label),
        identified: trendsData.gaps_identified[i] || 0,
        resolved: trendsData.gaps_resolved[i] || 0,
    }));
}

function formatWeekLabel(isoDate) {
    try {
        const d = new Date(isoDate);
        return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    } catch {
        return isoDate;
    }
}

const dateInputStyle = {
    padding: '6px 10px',
    fontSize: 'var(--font-size-sm)',
    background: 'var(--color-bg-secondary)',
    border: '1px solid var(--color-border)',
    borderRadius: 'var(--radius-sm)',
    color: 'var(--color-text-primary)',
    outline: 'none',
};

const textInputStyle = {
    flex: 1,
    padding: '8px 12px',
    fontSize: 'var(--font-size-sm)',
    background: 'var(--color-bg-secondary)',
    border: '1px solid var(--color-border)',
    borderRadius: 'var(--radius-sm)',
    color: 'var(--color-text-primary)',
    outline: 'none',
};
