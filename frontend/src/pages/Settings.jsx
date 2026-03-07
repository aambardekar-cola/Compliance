import { useState } from 'react';
import { useAuthSession } from '../auth/AuthProvider';
import { Save, Link, Key, Bell, Shield } from 'lucide-react';

export default function Settings() {
    const { sessionToken } = useAuthSession();

    const [gitlab, setGitlab] = useState({
        url: 'https://gitlab.com',
        token: '',
        project_ids: '',
    });

    const [jira, setJira] = useState({
        url: '',
        email: '',
        api_token: '',
        project_key: '',
    });

    return (
        <div className="animate-in">
            <div className="page-header">
                <h1 className="page-title">Settings</h1>
                <p className="page-description">
                    Configure integrations, notifications, and platform settings
                </p>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-6)' }}>
                {/* GitLab Configuration */}
                <div className="card">
                    <div className="card-header">
                        <h2 className="card-title" style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
                            <Link size={18} /> GitLab Integration
                        </h2>
                    </div>

                    <div className="settings-form">
                        <div className="settings-field">
                            <label>GitLab URL</label>
                            <input
                                type="url"
                                value={gitlab.url}
                                onChange={(e) => setGitlab({ ...gitlab, url: e.target.value })}
                                placeholder="https://gitlab.com"
                            />
                        </div>
                        <div className="settings-field">
                            <label>Personal Access Token</label>
                            <input
                                type="password"
                                value={gitlab.token}
                                onChange={(e) => setGitlab({ ...gitlab, token: e.target.value })}
                                placeholder="glpat-****"
                            />
                        </div>
                        <div className="settings-field">
                            <label>Project IDs (comma-separated)</label>
                            <input
                                type="text"
                                value={gitlab.project_ids}
                                onChange={(e) => setGitlab({ ...gitlab, project_ids: e.target.value })}
                                placeholder="123, 456, 789"
                            />
                        </div>
                        <button className="btn btn-primary" style={{ alignSelf: 'flex-start' }}>
                            <Save size={14} /> Save GitLab Settings
                        </button>
                    </div>
                </div>

                {/* Jira Configuration */}
                <div className="card">
                    <div className="card-header">
                        <h2 className="card-title" style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
                            <Key size={18} /> Jira Cloud Integration
                        </h2>
                    </div>

                    <div className="settings-form">
                        <div className="settings-field">
                            <label>Jira URL</label>
                            <input
                                type="url"
                                value={jira.url}
                                onChange={(e) => setJira({ ...jira, url: e.target.value })}
                                placeholder="https://your-domain.atlassian.net"
                            />
                        </div>
                        <div className="settings-field">
                            <label>Email</label>
                            <input
                                type="email"
                                value={jira.email}
                                onChange={(e) => setJira({ ...jira, email: e.target.value })}
                                placeholder="admin@company.com"
                            />
                        </div>
                        <div className="settings-field">
                            <label>API Token</label>
                            <input
                                type="password"
                                value={jira.api_token}
                                onChange={(e) => setJira({ ...jira, api_token: e.target.value })}
                                placeholder="Your Jira API token"
                            />
                        </div>
                        <div className="settings-field">
                            <label>Project Key</label>
                            <input
                                type="text"
                                value={jira.project_key}
                                onChange={(e) => setJira({ ...jira, project_key: e.target.value })}
                                placeholder="PCO"
                            />
                        </div>
                        <button className="btn btn-primary" style={{ alignSelf: 'flex-start' }}>
                            <Save size={14} /> Save Jira Settings
                        </button>
                    </div>
                </div>

                {/* Notification Preferences */}
                <div className="card" style={{ gridColumn: 'span 2' }}>
                    <div className="card-header">
                        <h2 className="card-title" style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
                            <Bell size={18} /> Notification Subscriptions
                        </h2>
                    </div>

                    <table className="data-table">
                        <thead>
                            <tr>
                                <th>Feature</th>
                                <th>Description</th>
                                <th>Status</th>
                            </tr>
                        </thead>
                        <tbody>
                            {[
                                { id: 'new_regulations', label: 'New Regulations', desc: 'Alerts when new PACE-relevant regulations are detected' },
                                { id: 'gap_alerts', label: 'Gap Alerts', desc: 'Notifications when compliance gaps are identified in the codebase' },
                                { id: 'deadline_reminders', label: 'Deadline Reminders', desc: 'Periodic reminders for approaching regulatory deadlines' },
                                { id: 'compliance_updates', label: 'Compliance Updates', desc: 'Updates on the status of compliance remediation work' },
                                { id: 'resolution_notices', label: 'Resolution Notices', desc: 'Notifications when compliance gaps are resolved' },
                            ].map((feature) => (
                                <tr key={feature.id}>
                                    <td style={{ fontWeight: 500, color: 'var(--color-text-primary)' }}>{feature.label}</td>
                                    <td>{feature.desc}</td>
                                    <td>
                                        <label style={{
                                            display: 'inline-flex', alignItems: 'center', gap: 'var(--space-2)',
                                            cursor: 'pointer', userSelect: 'none',
                                        }}>
                                            <input type="checkbox" defaultChecked style={{ accentColor: 'var(--color-accent)' }} />
                                            <span style={{ fontSize: 'var(--font-size-sm)' }}>Enabled</span>
                                        </label>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    );
}
