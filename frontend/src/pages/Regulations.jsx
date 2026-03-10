import { useState, useCallback } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { useAuthSession } from '../auth/AuthProvider';
import { Search, FileText, AlertTriangle, Layers, Crosshair, ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight } from 'lucide-react';
import apiClient from '../api/client';

const MOCK_REGULATIONS = [
    {
        id: '1', source: 'federal_register', title: 'CY2026 PACE Final Rule — Service Delivery Timeframes & Care Coordination',
        summary: 'Establishes new maximum timeframes for service delivery, including 24-hour medication dispensing and 7-day service arrangement.',
        relevance_score: 0.95, status: 'final_rule', effective_date: '2026-01-01', agencies: ['CMS'],
        affected_areas: ['Care Plan', 'IDT'], program_area: ['PACE'], cfr_references: ['42 CFR §460.100'], gap_count: 4, isMock: true,
    },
    {
        id: '2', source: 'federal_register', title: 'PACE Participant Rights and Grievance Process Updates',
        summary: 'New formalized grievance process with 30-day resolution requirement.',
        relevance_score: 0.88, status: 'effective', effective_date: '2025-01-01', agencies: ['CMS'],
        affected_areas: ['Member Services', 'Quality'], program_area: ['PACE', 'MA'], cfr_references: ['42 CFR §460.120'], gap_count: 3, isMock: true,
    },
    {
        id: '3', source: 'federal_register', title: 'Interoperability and Prior Authorization API Requirements for PACE',
        summary: 'Mandates standards-based APIs for health data sharing.',
        relevance_score: 0.82, status: 'proposed', effective_date: '2026-07-01', agencies: ['CMS', 'HHS'],
        affected_areas: ['Administration', 'Reporting'], program_area: ['General'], cfr_references: [], gap_count: 5, isMock: true,
    },
];

// Color map for PCO module tags
const MODULE_COLORS = {
    'IDT': '#6366f1', 'Care Plan': '#8b5cf6', 'Pharmacy': '#ec4899', 'Enrollment': '#f59e0b',
    'Claims': '#14b8a6', 'Transportation': '#06b6d4', 'Quality': '#22c55e', 'Billing': '#f97316',
    'Authorization': '#a855f7', 'Member Services': '#3b82f6', 'Provider Network': '#64748b',
    'Reporting': '#10b981', 'Administration': '#78716c',
};

// Color map for program area tags
const PROGRAM_AREA_COLORS = {
    'MA': '#6366f1', 'Part D': '#ec4899', 'PACE': '#22c55e', 'Medicaid': '#f59e0b', 'General': '#64748b',
};

export default function Regulations() {
    const { sessionToken } = useAuthSession();
    const navigate = useNavigate();
    const queryClient = useQueryClient();
    const [search, setSearch] = useState('');
    const [statusFilter, setStatusFilter] = useState('');
    const [moduleFilter, setModuleFilter] = useState('');
    const [programAreaFilter, setProgramAreaFilter] = useState('');
    const [page, setPage] = useState(1);
    const pageSize = 20;

    // Reset page when filters change
    const handleSearch = useCallback((val) => { setSearch(val); setPage(1); }, []);
    const handleStatusFilter = useCallback((val) => { setStatusFilter(val); setPage(1); }, []);
    const handleProgramAreaFilter = useCallback((val) => { setProgramAreaFilter(val); setPage(1); }, []);

    apiClient.setToken(sessionToken);

    const { data, isLoading } = useQuery({
        queryKey: ['regulations', search, statusFilter, programAreaFilter, page],
        queryFn: () => apiClient.getRegulations({ search, status: statusFilter, program_area: programAreaFilter, page, page_size: pageSize }),
        enabled: !!sessionToken,
    });

    const gapAnalysisMutation = useMutation({
        mutationFn: (regulationId) => apiClient.requestGapAnalysis(regulationId),
        onSuccess: () => queryClient.invalidateQueries({ queryKey: ['regulations'] }),
    });

    const regulations = data?.items || MOCK_REGULATIONS;
    const isMockData = !data?.items;
    const totalCount = data?.total || regulations.length;
    const totalPages = data?.total_pages || 1;

    // Filter by module client-side (API doesn't have this filter yet)
    const filtered = moduleFilter
        ? regulations.filter(r => (r.affected_areas || []).includes(moduleFilter))
        : regulations;

    return (
        <div className="animate-in">
            <div className="page-header">
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <h1 className="page-title">Regulatory Monitor</h1>
                    {isMockData && <PreviewBadge />}
                </div>
                <p className="page-description">
                    Regulations extracted from CMS, Federal Register, and other federal sources — linked to compliance gaps
                </p>

                {/* Count Summary Bar */}
                <div style={{
                    display: 'flex', gap: 'var(--space-4)', marginTop: 'var(--space-3)',
                    padding: 'var(--space-3) var(--space-4)', borderRadius: 'var(--radius-md)',
                    background: 'var(--color-bg-secondary)', border: '1px solid var(--color-border)',
                }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
                        <FileText size={16} style={{ color: 'var(--color-accent)' }} />
                        <span style={{ fontSize: 'var(--font-size-lg)', fontWeight: 700, color: 'var(--color-text-primary)' }}>
                            {totalCount}
                        </span>
                        <span style={{ color: 'var(--color-text-muted)', fontSize: 'var(--font-size-sm)' }}>
                            Regulations Tracked
                        </span>
                    </div>
                </div>

                <div className="page-actions">
                    <div className="input-group" style={{ minWidth: 300 }}>
                        <Search size={16} />
                        <input
                            type="text"
                            placeholder="Search regulations..."
                            value={search}
                            onChange={(e) => handleSearch(e.target.value)}
                        />
                    </div>

                    <select className="select" value={statusFilter} onChange={(e) => handleStatusFilter(e.target.value)}>
                        <option value="">All Statuses</option>
                        <option value="proposed">Proposed</option>
                        <option value="comment_period">Comment Period</option>
                        <option value="final_rule">Final Rule</option>
                        <option value="effective">Effective</option>
                        <option value="unknown">Unknown</option>
                    </select>

                    <select className="select" value={programAreaFilter} onChange={(e) => handleProgramAreaFilter(e.target.value)}>
                        <option value="">All Program Areas</option>
                        <option value="MA">Medicare Advantage (MA)</option>
                        <option value="Part D">Part D</option>
                        <option value="PACE">PACE</option>
                        <option value="Medicaid">Medicaid</option>
                        <option value="General">General</option>
                    </select>

                    <select className="select" value={moduleFilter} onChange={(e) => setModuleFilter(e.target.value)}>
                        <option value="">All Modules</option>
                        {Object.keys(MODULE_COLORS).map(m => <option key={m} value={m}>{m}</option>)}
                    </select>
                </div>
            </div>

            <div className="card">
                {isLoading ? (
                    <div className="loading-card"><div className="loading-spinner" /></div>
                ) : filtered.length === 0 ? (
                    <div className="empty-state">
                        <FileText />
                        <h3>No regulations found</h3>
                        <p>Adjust your filters or check back later for new regulatory updates.</p>
                    </div>
                ) : (
                    <table className="data-table">
                        <thead>
                            <tr>
                                <th>Regulation</th>
                                <th>Program</th>
                                <th>Modules</th>
                                <th>Gaps</th>
                                <th>Relevance</th>
                                <th>Status</th>
                                <th>Effective</th>
                                <th style={{ width: 40 }}></th>
                            </tr>
                        </thead>
                        <tbody>
                            {filtered.map((reg) => (
                                <tr key={reg.id} onClick={() => navigate(`/regulations/${reg.id}`)} style={{ cursor: 'pointer' }}>
                                    <td>
                                        <div style={{ maxWidth: 300 }}>
                                            <div style={{ color: 'var(--color-text-primary)', fontWeight: 500, marginBottom: 4 }}>
                                                {reg.title}
                                                {reg.isMock && (
                                                    <span className="badge badge-medium" style={{ marginLeft: '8px', fontSize: '10px' }}>PREVIEW</span>
                                                )}
                                            </div>
                                            <div style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)' }}>
                                                {reg.summary?.slice(0, 80)}...
                                            </div>
                                        </div>
                                    </td>
                                    <td>
                                        <div className="detail-tags" style={{ maxWidth: 140 }}>
                                            {(reg.program_area || []).map((area) => (
                                                <span key={area} className="detail-tag" style={{
                                                    background: `${PROGRAM_AREA_COLORS[area] || '#64748b'}22`,
                                                    color: PROGRAM_AREA_COLORS[area] || '#64748b',
                                                    border: `1px solid ${PROGRAM_AREA_COLORS[area] || '#64748b'}44`,
                                                    fontSize: 'var(--font-size-xs)',
                                                }}>
                                                    {area}
                                                </span>
                                            ))}
                                        </div>
                                    </td>
                                    <td>
                                        <div className="detail-tags" style={{ maxWidth: 180 }}>
                                            {(reg.affected_areas || []).slice(0, 3).map((area) => (
                                                <span key={area} className="detail-tag" style={{
                                                    background: `${MODULE_COLORS[area] || '#64748b'}22`,
                                                    color: MODULE_COLORS[area] || '#64748b',
                                                    border: `1px solid ${MODULE_COLORS[area] || '#64748b'}44`,
                                                }}>
                                                    {area}
                                                </span>
                                            ))}
                                            {(reg.affected_areas || []).length > 3 && (
                                                <span className="detail-tag" style={{ opacity: 0.6 }}>+{reg.affected_areas.length - 3}</span>
                                            )}
                                        </div>
                                    </td>
                                    <td>
                                        {reg.gap_count > 0 ? (
                                            <span style={{
                                                display: 'inline-flex', alignItems: 'center', gap: 4,
                                                color: 'var(--color-critical)', fontWeight: 600, fontSize: 'var(--font-size-sm)',
                                            }}>
                                                <AlertTriangle size={12} />
                                                {reg.gap_count}
                                            </span>
                                        ) : (
                                            <span style={{ color: 'var(--color-text-muted)', fontSize: 'var(--font-size-sm)' }}>0</span>
                                        )}
                                    </td>
                                    <td><RelevanceBar score={reg.relevance_score} /></td>
                                    <td>
                                        <span className={`badge badge-${getStatusColor(reg.status)}`}>
                                            <span className="badge-dot" />
                                            {formatStatus(reg.status)}
                                        </span>
                                    </td>
                                    <td style={{ fontSize: 'var(--font-size-sm)' }}>{reg.effective_date || '—'}</td>
                                    <td>
                                        <button
                                            title={reg.gap_analysis_requested ? 'Gap analysis requested — click to cancel' : 'Request gap analysis for this regulation'}
                                            onClick={(e) => {
                                                e.stopPropagation();
                                                gapAnalysisMutation.mutate(reg.id);
                                            }}
                                            style={{
                                                background: 'none', border: 'none', cursor: 'pointer', padding: 4,
                                                color: reg.gap_analysis_requested ? 'var(--color-accent)' : 'var(--color-text-muted)',
                                                opacity: reg.gap_analysis_requested ? 1 : 0.5,
                                                transition: 'all 0.2s ease',
                                            }}
                                        >
                                            <Crosshair size={16} />
                                        </button>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                )}

                {/* Pagination Controls */}
                {!isLoading && totalPages > 1 && (
                    <div style={{
                        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                        padding: 'var(--space-3) var(--space-4)',
                        borderTop: '1px solid var(--color-border)',
                        background: 'var(--color-bg-secondary)',
                        borderRadius: '0 0 var(--radius-md) var(--radius-md)',
                    }}>
                        <span style={{ fontSize: 'var(--font-size-sm)', color: 'var(--color-text-muted)' }}>
                            Showing {((page - 1) * pageSize) + 1}–{Math.min(page * pageSize, totalCount)} of {totalCount}
                        </span>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
                            <button className="btn btn-sm btn-ghost" disabled={page <= 1} onClick={() => setPage(1)} title="First page">
                                <ChevronsLeft size={16} />
                            </button>
                            <button className="btn btn-sm btn-ghost" disabled={page <= 1} onClick={() => setPage(p => Math.max(1, p - 1))} title="Previous page">
                                <ChevronLeft size={16} />
                            </button>
                            <span style={{
                                fontSize: 'var(--font-size-sm)', fontWeight: 600,
                                color: 'var(--color-text-primary)',
                                padding: '0 var(--space-2)',
                            }}>
                                {page} / {totalPages}
                            </span>
                            <button className="btn btn-sm btn-ghost" disabled={page >= totalPages} onClick={() => setPage(p => Math.min(totalPages, p + 1))} title="Next page">
                                <ChevronRight size={16} />
                            </button>
                            <button className="btn btn-sm btn-ghost" disabled={page >= totalPages} onClick={() => setPage(totalPages)} title="Last page">
                                <ChevronsRight size={16} />
                            </button>
                        </div>
                    </div>
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

function RelevanceBar({ score }) {
    const pct = Math.round((score || 0) * 100);
    const color = pct >= 80 ? 'var(--color-critical)' : pct >= 60 ? 'var(--color-warning)' : 'var(--color-success)';

    return (
        <div className="relevance-bar">
            <div className="relevance-track">
                <div className="relevance-fill" style={{ width: `${pct}%`, background: color }} />
            </div>
            <span className="relevance-score" style={{ color }}>{pct}%</span>
        </div>
    );
}

function getStatusColor(status) {
    const map = { proposed: 'info', comment_period: 'warning', final_rule: 'accent', effective: 'success', archived: 'medium', unknown: 'medium' };
    return map[status] || 'info';
}

function formatStatus(s) {
    return (s || '').replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}
