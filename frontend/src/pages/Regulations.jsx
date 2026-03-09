import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { useAuthSession } from '../auth/AuthProvider';
import { Search, FileText, AlertTriangle, Layers } from 'lucide-react';
import apiClient from '../api/client';

const MOCK_REGULATIONS = [
    {
        id: '1', source: 'federal_register', title: 'CY2026 PACE Final Rule — Service Delivery Timeframes & Care Coordination',
        summary: 'Establishes new maximum timeframes for service delivery, including 24-hour medication dispensing and 7-day service arrangement.',
        relevance_score: 0.95, status: 'final_rule', effective_date: '2026-01-01', agencies: ['CMS'],
        affected_areas: ['Care Plan', 'IDT'], cfr_references: ['42 CFR §460.100'], gap_count: 4, isMock: true,
    },
    {
        id: '2', source: 'federal_register', title: 'PACE Participant Rights and Grievance Process Updates',
        summary: 'New formalized grievance process with 30-day resolution requirement.',
        relevance_score: 0.88, status: 'effective', effective_date: '2025-01-01', agencies: ['CMS'],
        affected_areas: ['Member Services', 'Quality'], cfr_references: ['42 CFR §460.120'], gap_count: 3, isMock: true,
    },
    {
        id: '3', source: 'federal_register', title: 'Interoperability and Prior Authorization API Requirements for PACE',
        summary: 'Mandates standards-based APIs for health data sharing.',
        relevance_score: 0.82, status: 'proposed', effective_date: '2026-07-01', agencies: ['CMS', 'HHS'],
        affected_areas: ['Administration', 'Reporting'], cfr_references: [], gap_count: 5, isMock: true,
    },
];

// Color map for PCO module tags
const MODULE_COLORS = {
    'IDT': '#6366f1', 'Care Plan': '#8b5cf6', 'Pharmacy': '#ec4899', 'Enrollment': '#f59e0b',
    'Claims': '#14b8a6', 'Transportation': '#06b6d4', 'Quality': '#22c55e', 'Billing': '#f97316',
    'Authorization': '#a855f7', 'Member Services': '#3b82f6', 'Provider Network': '#64748b',
    'Reporting': '#10b981', 'Administration': '#78716c',
};

export default function Regulations() {
    const { sessionToken } = useAuthSession();
    const navigate = useNavigate();
    const [search, setSearch] = useState('');
    const [statusFilter, setStatusFilter] = useState('');
    const [moduleFilter, setModuleFilter] = useState('');

    apiClient.setToken(sessionToken);

    const { data, isLoading } = useQuery({
        queryKey: ['regulations', search, statusFilter],
        queryFn: () => apiClient.getRegulations({ search, status: statusFilter }),
        enabled: !!sessionToken,
    });

    const regulations = data?.items || MOCK_REGULATIONS;
    const isMockData = !data?.items;

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

                <div className="page-actions">
                    <div className="input-group" style={{ minWidth: 300 }}>
                        <Search size={16} />
                        <input
                            type="text"
                            placeholder="Search regulations..."
                            value={search}
                            onChange={(e) => setSearch(e.target.value)}
                        />
                    </div>

                    <select className="select" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
                        <option value="">All Statuses</option>
                        <option value="proposed">Proposed</option>
                        <option value="comment_period">Comment Period</option>
                        <option value="final_rule">Final Rule</option>
                        <option value="effective">Effective</option>
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
                                <th>CFR</th>
                                <th>Modules</th>
                                <th>Gaps</th>
                                <th>Relevance</th>
                                <th>Status</th>
                                <th>Effective</th>
                            </tr>
                        </thead>
                        <tbody>
                            {filtered.map((reg) => (
                                <tr key={reg.id} onClick={() => navigate(`/regulations/${reg.id}`)} style={{ cursor: 'pointer' }}>
                                    <td>
                                        <div style={{ maxWidth: 350 }}>
                                            <div style={{ color: 'var(--color-text-primary)', fontWeight: 500, marginBottom: 4 }}>
                                                {reg.title}
                                                {reg.isMock && (
                                                    <span className="badge badge-medium" style={{ marginLeft: '8px', fontSize: '10px' }}>PREVIEW</span>
                                                )}
                                            </div>
                                            <div style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)' }}>
                                                {reg.summary?.slice(0, 100)}...
                                            </div>
                                        </div>
                                    </td>
                                    <td>
                                        <div style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-secondary)', maxWidth: 150 }}>
                                            {(reg.cfr_references || []).length > 0 ? reg.cfr_references[0] : '—'}
                                        </div>
                                    </td>
                                    <td>
                                        <div className="detail-tags" style={{ maxWidth: 200 }}>
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
    const map = { proposed: 'info', comment_period: 'warning', final_rule: 'accent', effective: 'success', archived: 'medium' };
    return map[status] || 'info';
}

function formatStatus(s) {
    return (s || '').replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}
