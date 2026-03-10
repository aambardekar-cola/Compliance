import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Activity, Play, RefreshCw, Check, X, AlertTriangle, Clock, Loader2 } from 'lucide-react';
import apiClient from '../api/client';

const STATUS_STYLES = {
    completed: { color: '#22c55e', bg: 'rgba(34,197,94,0.12)', icon: <Check size={14} />, label: 'Completed' },
    failed: { color: '#ef4444', bg: 'rgba(239,68,68,0.12)', icon: <X size={14} />, label: 'Failed' },
    started: { color: '#3b82f6', bg: 'rgba(59,130,246,0.12)', icon: <Loader2 size={14} style={{ animation: 'spin 1s linear infinite' }} />, label: 'Running' },
    partial: { color: '#f59e0b', bg: 'rgba(245,158,11,0.12)', icon: <AlertTriangle size={14} />, label: 'Partial' },
};

const TYPE_LABELS = { scraper: 'Scraper', ingestion: 'Ingestion', analysis: 'Analysis' };

function formatDuration(secs) {
    if (!secs) return '—';
    if (secs < 60) return `${Math.round(secs)}s`;
    return `${Math.floor(secs / 60)}m ${Math.round(secs % 60)}s`;
}

function formatTime(dateStr) {
    if (!dateStr) return '—';
    return new Date(dateStr).toLocaleString('en-US', {
        month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
    });
}

export default function PipelineHealth() {
    const queryClient = useQueryClient();
    const [typeFilter, setTypeFilter] = useState('');
    const [page, setPage] = useState(1);

    const { data, isLoading } = useQuery({
        queryKey: ['pipeline-runs', page, typeFilter],
        queryFn: () => {
            const params = { page, page_size: 15 };
            if (typeFilter) params.run_type = typeFilter;
            return apiClient.getPipelineRuns(params);
        },
    });

    const triggerScraper = useMutation({
        mutationFn: () => apiClient.triggerScraper(),
        onSuccess: () => queryClient.invalidateQueries({ queryKey: ['pipeline-runs'] }),
    });

    const triggerAnalysis = useMutation({
        mutationFn: () => apiClient.triggerAnalysis(),
        onSuccess: () => queryClient.invalidateQueries({ queryKey: ['pipeline-runs'] }),
    });

    const runs = data?.items || [];
    const total = data?.total || 0;
    const totalPages = Math.ceil(total / 15);

    // Stats
    const completedCount = runs.filter((r) => r.status === 'completed').length;
    const failedCount = runs.filter((r) => r.status === 'failed').length;
    const totalRegsAdded = runs.reduce((s, r) => s + (r.regulations_added || 0), 0);
    const totalGapsAdded = runs.reduce((s, r) => s + (r.gaps_added || 0), 0);

    return (
        <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 24 }}>
                <div>
                    <h2 style={{ margin: 0, fontSize: 24, fontWeight: 700 }}>
                        <Activity size={22} style={{ verticalAlign: 'middle', marginRight: 8 }} />
                        Pipeline Health
                    </h2>
                    <p style={{ margin: '4px 0 0', color: 'var(--color-text-muted, #94a3b8)', fontSize: 14 }}>
                        Monitor nightly pipeline runs — scraper, ingestion, and analysis
                    </p>
                </div>
                <div style={{ display: 'flex', gap: 8 }}>
                    <button
                        className="btn btn-secondary"
                        onClick={() => triggerScraper.mutate()}
                        disabled={triggerScraper.isPending}
                        style={{ fontSize: 13, padding: '8px 16px', display: 'flex', alignItems: 'center', gap: 6 }}
                    >
                        <Play size={14} /> Run Scraper
                    </button>
                    <button
                        className="btn btn-primary"
                        onClick={() => triggerAnalysis.mutate()}
                        disabled={triggerAnalysis.isPending}
                        style={{ fontSize: 13, padding: '8px 16px', display: 'flex', alignItems: 'center', gap: 6 }}
                    >
                        <RefreshCw size={14} /> Run Analysis
                    </button>
                </div>
            </div>

            {/* Summary cards */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16, marginBottom: 24 }}>
                {[
                    { label: 'Total Runs', value: total, color: '#6366f1' },
                    { label: 'Successful', value: completedCount, color: '#22c55e' },
                    { label: 'Failed', value: failedCount, color: '#ef4444' },
                    { label: 'Regs + Gaps Added', value: `${totalRegsAdded} / ${totalGapsAdded}`, color: '#3b82f6' },
                ].map((s) => (
                    <div key={s.label} className="card" style={{ padding: 16 }}>
                        <div style={{ fontSize: 12, color: 'var(--color-text-muted, #94a3b8)', marginBottom: 4 }}>{s.label}</div>
                        <div style={{ fontSize: 24, fontWeight: 700, color: s.color }}>{s.value}</div>
                    </div>
                ))}
            </div>

            {/* Filter */}
            <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
                {['', 'scraper', 'ingestion', 'analysis'].map((t) => (
                    <button key={t}
                        className={`btn ${typeFilter === t ? 'btn-primary' : 'btn-secondary'}`}
                        onClick={() => { setTypeFilter(t); setPage(1); }}
                        style={{ fontSize: 13, padding: '6px 14px' }}
                    >
                        {t ? TYPE_LABELS[t] : 'All'}
                    </button>
                ))}
            </div>

            {/* Runs table */}
            {isLoading ? (
                <div style={{ textAlign: 'center', padding: 48, color: 'var(--color-text-muted, #94a3b8)' }}>
                    <Loader2 size={24} style={{ animation: 'spin 1s linear infinite' }} />
                </div>
            ) : runs.length === 0 ? (
                <div className="card" style={{ textAlign: 'center', padding: 48, color: 'var(--color-text-muted, #94a3b8)' }}>
                    <Activity size={40} style={{ opacity: 0.3, marginBottom: 12 }} />
                    <p>No pipeline runs recorded yet</p>
                    <p style={{ fontSize: 13 }}>Runs will appear after the nightly pipeline executes or you trigger one manually.</p>
                </div>
            ) : (
                <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
                    <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                        <thead>
                            <tr style={{ textAlign: 'left', fontSize: 12, color: 'var(--color-text-muted, #94a3b8)', borderBottom: '1px solid var(--color-border, #1e293b)' }}>
                                <th style={{ padding: '12px 16px' }}>TYPE</th>
                                <th style={{ padding: '12px 16px' }}>STATUS</th>
                                <th style={{ padding: '12px 16px' }}>STARTED</th>
                                <th style={{ padding: '12px 16px' }}>DURATION</th>
                                <th style={{ padding: '12px 16px' }}>CHUNKS</th>
                                <th style={{ padding: '12px 16px' }}>REGS</th>
                                <th style={{ padding: '12px 16px' }}>GAPS</th>
                                <th style={{ padding: '12px 16px' }}>ERRORS</th>
                            </tr>
                        </thead>
                        <tbody>
                            {runs.map((run) => {
                                const ss = STATUS_STYLES[run.status] || STATUS_STYLES.started;
                                return (
                                    <tr key={run.id} style={{ borderBottom: '1px solid var(--color-border, #0f172a)', fontSize: 14 }}>
                                        <td style={{ padding: '12px 16px' }}>
                                            <span style={{
                                                padding: '3px 10px', borderRadius: 12, fontSize: 12, fontWeight: 600,
                                                background: 'rgba(99,102,241,0.12)', color: '#818cf8',
                                            }}>
                                                {TYPE_LABELS[run.run_type] || run.run_type}
                                            </span>
                                        </td>
                                        <td style={{ padding: '12px 16px' }}>
                                            <span style={{
                                                display: 'inline-flex', alignItems: 'center', gap: 4,
                                                padding: '3px 10px', borderRadius: 12, fontSize: 12, fontWeight: 600,
                                                background: ss.bg, color: ss.color,
                                            }}>
                                                {ss.icon} {ss.label}
                                            </span>
                                        </td>
                                        <td style={{ padding: '12px 16px', fontSize: 13, color: 'var(--color-text-muted, #94a3b8)' }}>
                                            {formatTime(run.started_at)}
                                        </td>
                                        <td style={{ padding: '12px 16px', fontSize: 13 }}>
                                            <Clock size={12} style={{ marginRight: 4, opacity: 0.5, verticalAlign: 'middle' }} />
                                            {formatDuration(run.duration_seconds)}
                                        </td>
                                        <td style={{ padding: '12px 16px', fontSize: 13 }}>{run.chunks_processed}</td>
                                        <td style={{ padding: '12px 16px', fontSize: 13 }}>
                                            {run.regulations_added > 0 ? (
                                                <span style={{ color: '#22c55e', fontWeight: 600 }}>+{run.regulations_added}</span>
                                            ) : '0'}
                                        </td>
                                        <td style={{ padding: '12px 16px', fontSize: 13 }}>
                                            {run.gaps_added > 0 ? (
                                                <span style={{ color: '#f59e0b', fontWeight: 600 }}>+{run.gaps_added}</span>
                                            ) : '0'}
                                        </td>
                                        <td style={{ padding: '12px 16px', fontSize: 13 }}>
                                            {run.errors_count > 0 ? (
                                                <span style={{ color: '#ef4444', fontWeight: 600 }}>{run.errors_count}</span>
                                            ) : (
                                                <span style={{ color: '#22c55e' }}>0</span>
                                            )}
                                        </td>
                                    </tr>
                                );
                            })}
                        </tbody>
                    </table>
                </div>
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
