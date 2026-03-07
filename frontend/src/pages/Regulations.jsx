import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { useAuthSession } from '../auth/AuthProvider';
import { Search, Filter, FileText, ExternalLink } from 'lucide-react';
import apiClient from '../api/client';

const MOCK_REGULATIONS = [
    {
        id: '1', source: 'Federal Register', title: 'CY2026 PACE Final Rule — Service Delivery Timeframes & Care Coordination',
        summary: 'Establishes new maximum timeframes for service delivery, including 24-hour medication dispensing and 7-day service arrangement.',
        relevance_score: 0.95, status: 'final_rule', effective_date: '2026-01-01', agencies: ['CMS'], affected_areas: ['care_planning', 'service_delivery'],
    },
    {
        id: '2', source: 'Federal Register', title: 'PACE Participant Rights and Grievance Process Updates',
        summary: 'New formalized grievance process with 30-day resolution requirement. Disclosure of performance deficiencies to participants.',
        relevance_score: 0.88, status: 'effective', effective_date: '2025-01-01', agencies: ['CMS'], affected_areas: ['participant_rights', 'grievances'],
    },
    {
        id: '3', source: 'Federal Register', title: 'Interoperability and Prior Authorization API Requirements for PACE',
        summary: 'Mandates standards-based APIs for health data sharing. Patient access API and provider directory API requirements.',
        relevance_score: 0.82, status: 'proposed', effective_date: '2026-07-01', agencies: ['CMS', 'HHS'], affected_areas: ['interoperability', 'api'],
    },
    {
        id: '4', source: 'CMS', title: 'Personnel Medical Clearance Requirements for PACE Organizations',
        summary: 'Comprehensive medical clearance processes for staff with direct participant contact, including individual risk assessments.',
        relevance_score: 0.79, status: 'effective', effective_date: '2025-01-01', agencies: ['CMS'], affected_areas: ['personnel', 'compliance'],
    },
    {
        id: '5', source: 'Federal Register', title: 'PACE Application Evaluation and Compliance Actions Update',
        summary: 'Additional grounds for denying PACE applications. Point thresholds for compliance actions on deficiencies.',
        relevance_score: 0.71, status: 'final_rule', effective_date: '2025-07-01', agencies: ['CMS'], affected_areas: ['enrollment', 'compliance'],
    },
];

export default function Regulations() {
    const { sessionToken } = useAuthSession();
    const navigate = useNavigate();
    const [search, setSearch] = useState('');
    const [statusFilter, setStatusFilter] = useState('');

    apiClient.setToken(sessionToken);

    const { data, isLoading } = useQuery({
        queryKey: ['regulations', search, statusFilter],
        queryFn: () => apiClient.getRegulations({ search, status: statusFilter }),
        enabled: !!sessionToken,
    });

    const regulations = data?.items || MOCK_REGULATIONS;

    return (
        <div className="animate-in">
            <div className="page-header">
                <h1 className="page-title">Regulatory Monitor</h1>
                <p className="page-description">
                    PACE-relevant regulations tracked from CMS, Federal Register, and other federal sources
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

                    <select
                        className="select"
                        value={statusFilter}
                        onChange={(e) => setStatusFilter(e.target.value)}
                    >
                        <option value="">All Statuses</option>
                        <option value="proposed">Proposed</option>
                        <option value="comment_period">Comment Period</option>
                        <option value="final_rule">Final Rule</option>
                        <option value="effective">Effective</option>
                    </select>
                </div>
            </div>

            <div className="card">
                {isLoading ? (
                    <div className="loading-card"><div className="loading-spinner" /></div>
                ) : regulations.length === 0 ? (
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
                                <th>Source</th>
                                <th>Relevance</th>
                                <th>Status</th>
                                <th>Effective Date</th>
                                <th>Areas</th>
                            </tr>
                        </thead>
                        <tbody>
                            {regulations.map((reg) => (
                                <tr key={reg.id} onClick={() => navigate(`/regulations/${reg.id}`)}>
                                    <td>
                                        <div style={{ maxWidth: 400 }}>
                                            <div style={{ color: 'var(--color-text-primary)', fontWeight: 500, marginBottom: 4 }}>
                                                {reg.title}
                                            </div>
                                            <div style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)' }}>
                                                {reg.summary?.slice(0, 100)}...
                                            </div>
                                        </div>
                                    </td>
                                    <td>{reg.source}</td>
                                    <td>
                                        <RelevanceBar score={reg.relevance_score} />
                                    </td>
                                    <td>
                                        <span className={`badge badge-${getStatusColor(reg.status)}`}>
                                            <span className="badge-dot" />
                                            {formatStatus(reg.status)}
                                        </span>
                                    </td>
                                    <td>{reg.effective_date || '—'}</td>
                                    <td>
                                        <div className="detail-tags" style={{ maxWidth: 200 }}>
                                            {(reg.affected_areas || []).slice(0, 2).map((area) => (
                                                <span key={area} className="detail-tag">{area.replace(/_/g, ' ')}</span>
                                            ))}
                                        </div>
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

function RelevanceBar({ score }) {
    const pct = Math.round((score || 0) * 100);
    const color = pct >= 80 ? 'var(--color-critical)' : pct >= 60 ? 'var(--color-warning)' : 'var(--color-success)';

    return (
        <div className="relevance-bar">
            <div className="relevance-track">
                <div
                    className="relevance-fill"
                    style={{ width: `${pct}%`, background: color }}
                />
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
