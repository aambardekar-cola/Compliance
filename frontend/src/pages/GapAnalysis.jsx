import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useAuthSession } from '../auth/AuthProvider';
import { AlertTriangle, Layers, Filter, FileText, BarChart3 } from 'lucide-react';
import apiClient from '../api/client';

const MOCK_GAPS = [
    {
        id: '1', title: 'Service delivery timeframe tracking not enforced',
        description: 'Current system does not enforce the 24-hour medication dispensing or 7-day service arrangement timeframes.',
        severity: 'critical', status: 'identified', affected_modules: ['Care Plan', 'IDT'],
        affected_layer: 'backend', regulation: { id: '1', title: 'PACE Service Delivery Timeframes', cfr_references: ['42 CFR §460.100'] },
        created_at: '2026-02-15', isMock: true,
    },
    {
        id: '2', title: 'Care plan update frequency insufficient',
        description: 'IDT care plan module does not prompt for updates at the frequency required by the new rule.',
        severity: 'high', status: 'in_progress', affected_modules: ['Care Plan'],
        affected_layer: 'frontend', regulation: { id: '1', title: 'PACE Service Delivery Timeframes', cfr_references: ['42 CFR §460.100'] },
        created_at: '2026-02-16', isMock: true,
    },
    {
        id: '3', title: 'Grievance process missing 30-day resolution tracking',
        description: 'Participant grievance module lacks a 30-day resolution countdown.',
        severity: 'high', status: 'identified', affected_modules: ['Member Services', 'Quality'],
        affected_layer: 'both', regulation: { id: '2', title: 'Grievance Process Updates', cfr_references: ['42 CFR §460.120'] },
        created_at: '2026-02-18', isMock: true,
    },
];

// Module colors matching Regulations page
const MODULE_COLORS = {
    'IDT': '#6366f1', 'Care Plan': '#8b5cf6', 'Pharmacy': '#ec4899', 'Enrollment': '#f59e0b',
    'Claims': '#14b8a6', 'Transportation': '#06b6d4', 'Quality': '#22c55e', 'Billing': '#f97316',
    'Authorization': '#a855f7', 'Member Services': '#3b82f6', 'Provider Network': '#64748b',
    'Reporting': '#10b981', 'Administration': '#78716c',
};

const LAYER_STYLES = {
    frontend: { bg: 'rgba(99, 102, 241, 0.12)', color: '#818cf8', label: 'Frontend' },
    backend:  { bg: 'rgba(245, 158, 11, 0.12)', color: '#fbbf24', label: 'Backend' },
    both:     { bg: 'rgba(236, 72, 153, 0.12)', color: '#f472b6', label: 'Both' },
    unknown:  { bg: 'rgba(100, 116, 139, 0.12)', color: '#94a3b8', label: 'Unknown' },
};

export default function GapAnalysis() {
    const { sessionToken } = useAuthSession();
    const [severityFilter, setSeverityFilter] = useState('');
    const [layerFilter, setLayerFilter] = useState('');
    const [regulationFilter, setRegulationFilter] = useState('');
    apiClient.setToken(sessionToken);

    const { data, isLoading } = useQuery({
        queryKey: ['gaps', severityFilter, layerFilter, regulationFilter],
        queryFn: () => apiClient.getGaps({
            page_size: 50,
            ...(severityFilter && { severity: severityFilter }),
            ...(layerFilter && { affected_layer: layerFilter }),
            ...(regulationFilter && { regulation_id: regulationFilter }),
        }),
        enabled: !!sessionToken,
    });

    // Fetch regulations for the dropdown filter
    const { data: regsData } = useQuery({
        queryKey: ['regulations-list'],
        queryFn: () => apiClient.getRegulations({ page_size: 200 }),
        enabled: !!sessionToken,
    });

    const gaps = data?.items || MOCK_GAPS;
    const isMockData = !data?.items;
    const totalCount = data?.total || gaps.length;
    const availableRegs = regsData?.items || [];

    // Module heatmap: count gaps per PCO module
    const moduleHeatmap = {};
    gaps.forEach(g => {
        (g.affected_modules || []).forEach(m => {
            moduleHeatmap[m] = (moduleHeatmap[m] || 0) + 1;
        });
    });
    const sortedModules = Object.entries(moduleHeatmap).sort((a, b) => b[1] - a[1]);

    // Severity summary
    const sevCounts = { critical: 0, high: 0, medium: 0, low: 0 };
    gaps.forEach(g => { if (g.severity && sevCounts[g.severity] !== undefined) sevCounts[g.severity]++; });

    return (
        <div className="animate-in">
            <div className="page-header">
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <h1 className="page-title">Gap Analysis</h1>
                    {isMockData && <PreviewBadge />}
                </div>
                <p className="page-description">
                    PACE compliance gaps identified per regulation — each gap tagged with affected PCO modules and application layer
                </p>

                {/* Count Summary Bar */}
                <div style={{
                    display: 'flex', gap: 'var(--space-4)', marginTop: 'var(--space-3)',
                    padding: 'var(--space-3) var(--space-4)', borderRadius: 'var(--radius-md)',
                    background: 'var(--color-bg-secondary)', border: '1px solid var(--color-border)',
                }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
                        <BarChart3 size={16} style={{ color: 'var(--color-critical)' }} />
                        <span style={{ fontSize: 'var(--font-size-lg)', fontWeight: 700, color: 'var(--color-text-primary)' }}>
                            {totalCount}
                        </span>
                        <span style={{ color: 'var(--color-text-muted)', fontSize: 'var(--font-size-sm)' }}>
                            Compliance Gaps Identified
                        </span>
                    </div>
                </div>
            </div>

            {/* Module Heatmap */}
            {sortedModules.length > 0 && (
                <div className="stats-grid" style={{ marginBottom: 'var(--space-6)' }}>
                    {sortedModules.slice(0, 6).map(([module, count]) => (
                        <div key={module} className="stat-card" style={{
                            '--stat-gradient': `linear-gradient(135deg, ${MODULE_COLORS[module] || '#64748b'}33, ${MODULE_COLORS[module] || '#64748b'}11)`,
                        }}>
                            <div className="stat-label" style={{ color: MODULE_COLORS[module] || '#94a3b8' }}>
                                {module}
                            </div>
                            <div className="stat-value" style={{ fontSize: 'var(--font-size-2xl)' }}>{count}</div>
                            <div className="stat-change">gaps identified</div>
                        </div>
                    ))}
                </div>
            )}

            {/* Severity chips + filters */}
            <div style={{ display: 'flex', gap: 'var(--space-3)', alignItems: 'center', marginBottom: 'var(--space-4)', flexWrap: 'wrap' }}>
                <SeverityChip label="Critical" count={sevCounts.critical} color="var(--color-critical)" />
                <SeverityChip label="High" count={sevCounts.high} color="var(--color-danger)" />
                <SeverityChip label="Medium" count={sevCounts.medium} color="var(--color-warning)" />
                <SeverityChip label="Low" count={sevCounts.low} color="var(--color-success)" />

                <div style={{ flex: 1 }} />

                <select className="select" value={severityFilter} onChange={(e) => setSeverityFilter(e.target.value)}>
                    <option value="">All Severities</option>
                    <option value="critical">Critical</option>
                    <option value="high">High</option>
                    <option value="medium">Medium</option>
                    <option value="low">Low</option>
                </select>

                <select className="select" value={layerFilter} onChange={(e) => setLayerFilter(e.target.value)}>
                    <option value="">All Layers</option>
                    <option value="frontend">Frontend</option>
                    <option value="backend">Backend</option>
                    <option value="both">Both</option>
                </select>

                <select className="select" value={regulationFilter} onChange={(e) => setRegulationFilter(e.target.value)} style={{ maxWidth: 240 }}>
                    <option value="">All Regulations</option>
                    {availableRegs.map(r => (
                        <option key={r.id} value={r.id}>{r.title?.slice(0, 50)}{r.title?.length > 50 ? '...' : ''}</option>
                    ))}
                </select>
            </div>

            {/* Gaps Table */}
            <div className="card">
                {isLoading ? (
                    <div className="loading-card"><div className="loading-spinner" /></div>
                ) : (
                    <table className="data-table">
                        <thead>
                            <tr>
                                <th>Gap</th>
                                <th>Regulation</th>
                                <th>Modules</th>
                                <th>Layer</th>
                                <th>Severity</th>
                                <th>Status</th>
                            </tr>
                        </thead>
                        <tbody>
                            {gaps.length === 0 ? (
                                <tr>
                                    <td colSpan="6" style={{ textAlign: 'center', padding: 'var(--space-8)' }}>
                                        <FileText size={20} style={{ marginBottom: 8, opacity: 0.5 }} />
                                        <div>No compliance gaps found. Run analysis to identify gaps.</div>
                                    </td>
                                </tr>
                            ) : gaps.map((gap) => (
                                <tr key={gap.id}>
                                    <td>
                                        <div style={{ maxWidth: 300 }}>
                                            <div style={{ color: 'var(--color-text-primary)', fontWeight: 500 }}>
                                                {gap.title}
                                                {gap.isMock && (
                                                    <span className="badge badge-medium" style={{ marginLeft: '8px', fontSize: '10px' }}>PREVIEW</span>
                                                )}
                                            </div>
                                            <div style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)', marginTop: 2 }}>
                                                {gap.description?.slice(0, 80)}...
                                            </div>
                                        </div>
                                    </td>
                                    <td>
                                        {gap.regulation ? (
                                            <div style={{ maxWidth: 200, fontSize: 'var(--font-size-xs)' }}>
                                                <div style={{ color: 'var(--color-text-secondary)', fontWeight: 500 }}>
                                                    {gap.regulation.title?.slice(0, 60)}{gap.regulation.title?.length > 60 ? '...' : ''}
                                                </div>
                                                {gap.regulation.cfr_references?.length > 0 && (
                                                    <div style={{ color: 'var(--color-text-muted)', marginTop: 2 }}>
                                                        {gap.regulation.cfr_references[0]}
                                                    </div>
                                                )}
                                            </div>
                                        ) : (
                                            <span style={{ color: 'var(--color-text-muted)', fontSize: 'var(--font-size-xs)' }}>—</span>
                                        )}
                                    </td>
                                    <td>
                                        <div className="detail-tags" style={{ maxWidth: 150 }}>
                                            {(gap.affected_modules || []).slice(0, 2).map((m) => (
                                                <span key={m} className="detail-tag" style={{
                                                    background: `${MODULE_COLORS[m] || '#64748b'}22`,
                                                    color: MODULE_COLORS[m] || '#64748b',
                                                    border: `1px solid ${MODULE_COLORS[m] || '#64748b'}44`,
                                                    fontSize: 'var(--font-size-xs)',
                                                }}>
                                                    {m}
                                                </span>
                                            ))}
                                        </div>
                                    </td>
                                    <td>
                                        <LayerBadge layer={gap.affected_layer} />
                                    </td>
                                    <td>
                                        <span className={`badge badge-${gap.severity}`}>
                                            <span className="badge-dot" />
                                            {gap.severity}
                                        </span>
                                    </td>
                                    <td>
                                        <span className={`badge badge-${getGapStatusColor(gap.status)}`}>
                                            {formatStatus(gap.status)}
                                        </span>
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

function PreviewBadge() {
    return (
        <span style={{
            display: 'inline-flex', alignItems: 'center', gap: 4, padding: '3px 10px',
            borderRadius: 20, fontSize: 'var(--font-size-xs)', fontWeight: 600,
            background: 'linear-gradient(135deg, rgba(245, 158, 11, 0.15), rgba(249, 115, 22, 0.15))',
            color: '#f59e0b', border: '1px solid rgba(245, 158, 11, 0.3)',
        }}>
            <Layers size={10} />
            Preview
        </span>
    );
}

function SeverityChip({ label, count, color }) {
    return (
        <div style={{
            display: 'flex', alignItems: 'center', gap: 6, padding: '4px 12px',
            borderRadius: 'var(--radius-full)', background: `${color}15`,
            border: `1px solid ${color}30`, fontSize: 'var(--font-size-sm)',
        }}>
            <span style={{ width: 6, height: 6, borderRadius: '50%', background: color }} />
            <span style={{ color: 'var(--color-text-secondary)' }}>{label}</span>
            <span style={{ fontWeight: 700, color }}>{count}</span>
        </div>
    );
}

function LayerBadge({ layer }) {
    const style = LAYER_STYLES[layer] || LAYER_STYLES.unknown;
    return (
        <span style={{
            display: 'inline-flex', padding: '2px 8px', borderRadius: 'var(--radius-full)',
            fontSize: 'var(--font-size-xs)', fontWeight: 600,
            background: style.bg, color: style.color,
        }}>
            {style.label}
        </span>
    );
}

function getGapStatusColor(s) {
    const m = { identified: 'warning', in_progress: 'info', resolved: 'success', accepted_risk: 'medium' };
    return m[s] || 'info';
}

function formatStatus(s) {
    return (s || '').replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}
