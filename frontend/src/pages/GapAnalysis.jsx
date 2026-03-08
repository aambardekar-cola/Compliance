import { useQuery } from '@tanstack/react-query';
import { useAuthSession } from '../auth/AuthProvider';
import { AlertTriangle, Users, Clock } from 'lucide-react';
import apiClient from '../api/client';

const MOCK_GAPS = [
    {
        id: '1', regulation_id: '1', title: 'Service delivery timeframe tracking not enforced',
        description: 'Current system does not enforce the 24-hour medication dispensing or 7-day service arrangement timeframes.',
        severity: 'critical', status: 'identified', assigned_team: 'backend', effort_hours: 40, effort_story_points: 8,
        jira_epic_key: null, created_at: '2026-02-15', isMock: true,
    },
    {
        id: '2', regulation_id: '1', title: 'Care plan update frequency insufficient',
        description: 'IDT care plan module does not prompt for updates at the frequency required by the new rule.',
        severity: 'high', status: 'in_progress', assigned_team: 'frontend', effort_hours: 24, effort_story_points: 5,
        jira_epic_key: 'PCO-1234', jira_epic_url: '#', created_at: '2026-02-16', isMock: true,
    },
    {
        id: '3', regulation_id: '2', title: 'Grievance process missing 30-day resolution tracking',
        description: 'Participant grievance module lacks a 30-day resolution countdown and automated escalation.',
        severity: 'high', status: 'identified', assigned_team: 'backend', effort_hours: 32, effort_story_points: 5,
        jira_epic_key: null, created_at: '2026-02-18', isMock: true,
    },
    {
        id: '4', regulation_id: '3', title: 'Patient Access API endpoint not implemented',
        description: 'No FHIR-based Patient Access API exists. Required for interoperability compliance.',
        severity: 'medium', status: 'identified', assigned_team: 'backend', effort_hours: 80, effort_story_points: 13,
        jira_epic_key: null, created_at: '2026-03-01', isMock: true,
    },
    {
        id: '5', regulation_id: '4', title: 'Staff clearance tracking incomplete',
        description: 'Personnel module does not track medical clearance status or individual risk assessments.',
        severity: 'medium', status: 'resolved', assigned_team: 'frontend', effort_hours: 16, effort_story_points: 3,
        jira_epic_key: 'PCO-1100', jira_epic_url: '#', created_at: '2026-01-20', isMock: true,
    },
];

export default function GapAnalysis() {
    const { sessionToken } = useAuthSession();
    apiClient.setToken(sessionToken);

    const { data, isLoading } = useQuery({
        queryKey: ['gaps'],
        queryFn: () => apiClient.getGaps(),
        enabled: !!sessionToken,
    });

    const gaps = data?.items || MOCK_GAPS;

    const teamSummary = gaps.reduce((acc, g) => {
        const team = g.assigned_team || 'unassigned';
        if (!acc[team]) acc[team] = { count: 0, hours: 0 };
        acc[team].count++;
        acc[team].hours += g.effort_hours || 0;
        return acc;
    }, {});

    return (
        <div className="animate-in">
            <div className="page-header">
                <h1 className="page-title">Gap Analysis</h1>
                <p className="page-description">
                    Compliance gaps identified between PACE regulations and the PCO codebase
                </p>
            </div>

            {/* Team Summary Cards */}
            <div className="stats-grid" style={{ marginBottom: 'var(--space-6)' }}>
                {Object.entries(teamSummary).map(([team, stats]) => (
                    <div key={team} className="stat-card" style={{ '--stat-gradient': 'var(--gradient-info)' }}>
                        <div className="stat-label">
                            <Users size={14} style={{ display: 'inline', marginRight: 6, verticalAlign: 'middle' }} />
                            {team.charAt(0).toUpperCase() + team.slice(1)} Team
                        </div>
                        <div className="stat-value" style={{ fontSize: 'var(--font-size-2xl)' }}>{stats.count} gaps</div>
                        <div className="stat-change">
                            <Clock size={12} /> {stats.hours}h estimated
                        </div>
                    </div>
                ))}
            </div>

            {/* Gaps Table */}
            <div className="card">
                <table className="data-table">
                    <thead>
                        <tr>
                            <th>Gap</th>
                            <th>Severity</th>
                            <th>Status</th>
                            <th>Team</th>
                            <th>Effort</th>
                            <th>Jira</th>
                        </tr>
                    </thead>
                    <tbody>
                        {gaps.map((gap) => (
                            <tr key={gap.id}>
                                <td>
                                    <div style={{ maxWidth: 350 }}>
                                        <div style={{ color: 'var(--color-text-primary)', fontWeight: 500 }}>
                                            {gap.title}
                                            {gap.isMock && (
                                                <span className="badge badge-medium" style={{ marginLeft: '8px', fontSize: '10px' }}>MOCK</span>
                                            )}
                                        </div>
                                        <div style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)', marginTop: 2 }}>
                                            {gap.description?.slice(0, 80)}...
                                        </div>
                                    </div>
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
                                <td style={{ textTransform: 'capitalize' }}>{gap.assigned_team}</td>
                                <td>
                                    <div style={{ fontSize: 'var(--font-size-sm)', fontWeight: 600 }}>{gap.effort_hours}h</div>
                                    <div style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)' }}>{gap.effort_story_points} pts</div>
                                </td>
                                <td>
                                    {gap.jira_epic_key ? (
                                        <a href={gap.jira_epic_url} target="_blank" rel="noopener" className="badge badge-accent">
                                            {gap.jira_epic_key}
                                        </a>
                                    ) : (
                                        <span style={{ color: 'var(--color-text-muted)', fontSize: 'var(--font-size-xs)' }}>—</span>
                                    )}
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
}

function getGapStatusColor(s) {
    const m = { identified: 'warning', in_progress: 'info', resolved: 'success', accepted_risk: 'medium' };
    return m[s] || 'info';
}

function formatStatus(s) {
    return (s || '').replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}
