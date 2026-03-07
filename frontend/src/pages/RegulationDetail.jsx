import { useParams, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { useAuthSession } from '../auth/AuthProvider';
import { ArrowLeft, ExternalLink, Calendar, AlertTriangle } from 'lucide-react';
import apiClient from '../api/client';

const MOCK_DETAIL = {
    id: '1',
    source: 'Federal Register',
    title: 'CY2026 PACE Final Rule — Service Delivery Timeframes & Care Coordination',
    summary: 'This final rule establishes new maximum timeframes for service delivery in PACE organizations. Medications must be arranged and scheduled for dispensing within 24 hours of ordering, and other approved services must be arranged or scheduled within seven calendar days of approval by the interdisciplinary team (IDT). Also introduces new care plan update frequency requirements.',
    relevance_score: 0.95,
    status: 'final_rule',
    effective_date: '2026-01-01',
    published_date: '2024-04-04',
    comment_deadline: null,
    source_url: 'https://www.federalregister.gov/documents/2024/04/04/example',
    document_type: 'Final Rule',
    agencies: ['Centers for Medicare & Medicaid Services (CMS)'],
    cfr_references: ['42 CFR Part 460'],
    affected_areas: ['service_delivery', 'care_planning', 'medications', 'care_coordination'],
    key_requirements: [
        'Medications must be dispensed within 24 hours of ordering',
        'Other approved services arranged within 7 calendar days of IDT approval',
        'IDT must update care plans more frequently to reflect current health status',
        'New formalized care coordination documentation requirements',
    ],
    ai_analysis: {
        impact_level: 'critical',
        recommended_actions: [
            'Update service delivery tracking modules to enforce 24-hour/7-day timeframes',
            'Modify care plan module to support increased update frequency',
            'Add compliance monitoring dashboard for service delivery timeframes',
            'Update medication management workflows and alerts',
        ],
    },
};

export default function RegulationDetail() {
    const { id } = useParams();
    const navigate = useNavigate();
    const { sessionToken } = useAuthSession();

    apiClient.setToken(sessionToken);

    const { data, isLoading } = useQuery({
        queryKey: ['regulation', id],
        queryFn: () => apiClient.getRegulation(id),
        enabled: !!sessionToken,
    });

    const reg = data || MOCK_DETAIL;

    if (isLoading) {
        return <div className="loading-card"><div className="loading-spinner" /></div>;
    }

    const impactColor = {
        critical: 'var(--color-critical)',
        high: 'var(--color-high)',
        medium: 'var(--color-medium)',
        low: 'var(--color-low)',
    }[reg.ai_analysis?.impact_level] || 'var(--color-info)';

    return (
        <div className="animate-in">
            <button
                className="btn btn-secondary"
                onClick={() => navigate('/regulations')}
                style={{ marginBottom: 'var(--space-6)' }}
            >
                <ArrowLeft size={16} /> Back to Regulations
            </button>

            <div className="page-header" style={{ marginBottom: 'var(--space-6)' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)', marginBottom: 'var(--space-3)' }}>
                    <span className={`badge badge-${getStatusColor(reg.status)}`}>
                        <span className="badge-dot" />
                        {formatStatus(reg.status)}
                    </span>
                    {reg.ai_analysis?.impact_level && (
                        <span className={`badge badge-${reg.ai_analysis.impact_level}`}>
                            {reg.ai_analysis.impact_level.toUpperCase()} IMPACT
                        </span>
                    )}
                </div>
                <h1 className="page-title">{reg.title}</h1>
            </div>

            <div className="detail-grid">
                {/* Main Content */}
                <div>
                    <div className="card" style={{ marginBottom: 'var(--space-6)' }}>
                        <div className="card-header">
                            <h2 className="card-title">AI Analysis Summary</h2>
                        </div>
                        <div className="detail-value">{reg.summary}</div>
                    </div>

                    {/* Key Requirements */}
                    <div className="card" style={{ marginBottom: 'var(--space-6)' }}>
                        <div className="card-header">
                            <h2 className="card-title">Key Requirements</h2>
                        </div>
                        <ul style={{ listStyle: 'none', display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
                            {(reg.key_requirements || []).map((req, i) => (
                                <li key={i} style={{
                                    display: 'flex', alignItems: 'flex-start', gap: 'var(--space-3)',
                                    padding: 'var(--space-3) var(--space-4)',
                                    background: 'var(--color-bg-glass)',
                                    borderRadius: 'var(--radius-md)',
                                    border: '1px solid var(--color-border)',
                                    fontSize: 'var(--font-size-sm)',
                                    color: 'var(--color-text-secondary)',
                                }}>
                                    <AlertTriangle size={16} color={impactColor} style={{ flexShrink: 0, marginTop: 2 }} />
                                    {req}
                                </li>
                            ))}
                        </ul>
                    </div>

                    {/* Recommended Actions */}
                    {reg.ai_analysis?.recommended_actions && (
                        <div className="card">
                            <div className="card-header">
                                <h2 className="card-title">Recommended Actions</h2>
                            </div>
                            <ol style={{ listStyle: 'none', counterReset: 'action', display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
                                {reg.ai_analysis.recommended_actions.map((action, i) => (
                                    <li key={i} style={{
                                        display: 'flex', alignItems: 'flex-start', gap: 'var(--space-3)',
                                        padding: 'var(--space-3) var(--space-4)',
                                        background: 'rgba(99, 102, 241, 0.06)',
                                        borderRadius: 'var(--radius-md)',
                                        border: '1px solid rgba(99, 102, 241, 0.15)',
                                        fontSize: 'var(--font-size-sm)',
                                        color: 'var(--color-text-secondary)',
                                    }}>
                                        <span style={{
                                            width: 24, height: 24, borderRadius: '50%',
                                            background: 'var(--gradient-primary)',
                                            display: 'flex', alignItems: 'center', justifyContent: 'center',
                                            fontSize: 'var(--font-size-xs)', fontWeight: 700, color: 'white', flexShrink: 0,
                                        }}>
                                            {i + 1}
                                        </span>
                                        {action}
                                    </li>
                                ))}
                            </ol>
                        </div>
                    )}
                </div>

                {/* Sidebar Metadata */}
                <div>
                    <div className="card" style={{ marginBottom: 'var(--space-6)' }}>
                        <h3 className="card-title" style={{ marginBottom: 'var(--space-5)' }}>Details</h3>

                        <div className="detail-section">
                            <div className="detail-label">Source</div>
                            <div className="detail-value">{reg.source}</div>
                        </div>

                        <div className="detail-section">
                            <div className="detail-label">Relevance Score</div>
                            <div style={{ fontSize: 'var(--font-size-2xl)', fontWeight: 800, color: impactColor }}>
                                {Math.round((reg.relevance_score || 0) * 100)}%
                            </div>
                        </div>

                        <div className="detail-section">
                            <div className="detail-label">Effective Date</div>
                            <div className="detail-value" style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
                                <Calendar size={14} /> {reg.effective_date || 'TBD'}
                            </div>
                        </div>

                        <div className="detail-section">
                            <div className="detail-label">Published Date</div>
                            <div className="detail-value">{reg.published_date || 'N/A'}</div>
                        </div>

                        <div className="detail-section">
                            <div className="detail-label">Agencies</div>
                            <div className="detail-tags">
                                {(reg.agencies || []).map((a) => (
                                    <span key={a} className="detail-tag">{a}</span>
                                ))}
                            </div>
                        </div>

                        <div className="detail-section">
                            <div className="detail-label">CFR References</div>
                            <div className="detail-tags">
                                {(reg.cfr_references || []).map((r) => (
                                    <span key={r} className="detail-tag">{r}</span>
                                ))}
                            </div>
                        </div>

                        <div className="detail-section">
                            <div className="detail-label">Affected EHR Areas</div>
                            <div className="detail-tags">
                                {(reg.affected_areas || []).map((a) => (
                                    <span key={a} className="detail-tag">{a.replace(/_/g, ' ')}</span>
                                ))}
                            </div>
                        </div>

                        {reg.source_url && (
                            <a
                                href={reg.source_url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="btn btn-secondary"
                                style={{ width: '100%', marginTop: 'var(--space-4)' }}
                            >
                                <ExternalLink size={14} /> View Original Document
                            </a>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
}

function getStatusColor(status) {
    const map = { proposed: 'info', comment_period: 'warning', final_rule: 'accent', effective: 'success' };
    return map[status] || 'info';
}

function formatStatus(s) {
    return (s || '').replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}
