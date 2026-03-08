import {
    Server,
    Database,
    Globe,
    Shield,
    CloudCog,
    Activity,
    ExternalLink,
    Terminal,
} from 'lucide-react';

// Hardcoded architecture matrix
const ENVIRONMENTS = [
    {
        name: 'Development',
        key: 'dev',
        status: 'Active',
        description: 'Auto-deployed from main branch. Automated testing and local integration.',
        color: 'var(--color-info)',
        bg: 'rgba(56, 189, 248, 0.1)',
        resources: [
            { label: 'Frontend App', type: 'S3/CloudFront', icon: Globe, url: '#' },
            { label: 'FastAPI Backend', type: 'API Gateway + Lambda', icon: Server, url: '#' },
            { label: 'PostgreSQL DB', type: 'Aurora Serverless v2', icon: Database, url: '#' },
            { label: 'Auth Tenant', type: 'Descope', icon: Shield, url: '#' },
            { label: 'CI/CD Pipeline', type: 'GitHub Actions', icon: Terminal, url: '#' },
        ]
    },
    {
        name: 'Demo',
        key: 'demo',
        status: 'Active',
        description: 'Client-facing product demonstration environment. Auto-deployed from main.',
        color: 'var(--color-warning)',
        bg: 'rgba(245, 158, 11, 0.1)',
        resources: [
            { label: 'Frontend App', type: 'S3/CloudFront', icon: Globe, url: '#' },
            { label: 'FastAPI Backend', type: 'API Gateway + Lambda', icon: Server, url: '#' },
            { label: 'PostgreSQL DB', type: 'Aurora Serverless v2', icon: Database, url: '#' },
            { label: 'Auth Tenant', type: 'Descope', icon: Shield, url: '#' },
            { label: 'CI/CD Pipeline', type: 'GitHub Actions', icon: Terminal, url: '#' },
        ]
    },
    {
        name: 'Staging',
        key: 'staging',
        status: 'Standby',
        description: 'Pre-production validation testing. Manually promoted from dev.',
        color: 'var(--color-success)',
        bg: 'rgba(16, 185, 129, 0.1)',
        resources: [
            { label: 'Frontend App', type: 'S3/CloudFront', icon: Globe, url: '#' },
            { label: 'FastAPI Backend', type: 'API Gateway + Lambda', icon: Server, url: '#' },
            { label: 'PostgreSQL DB', type: 'Aurora Serverless v2', icon: Database, url: '#' },
            { label: 'Auth Tenant', type: 'Descope', icon: Shield, url: '#' },
            { label: 'CI/CD Pipeline', type: 'GitHub Actions', icon: Terminal, url: '#' },
        ]
    },
    {
        name: 'Production',
        key: 'prod',
        status: 'Active',
        description: 'Live client traffic. Manually promoted from staging.',
        color: 'var(--color-error)',
        bg: 'rgba(239, 68, 68, 0.1)',
        resources: [
            { label: 'Frontend App', type: 'S3/CloudFront', icon: Globe, url: '#' },
            { label: 'FastAPI Backend', type: 'API Gateway + Lambda', icon: Server, url: '#' },
            { label: 'PostgreSQL DB', type: 'Aurora Serverless v2', icon: Database, url: '#' },
            { label: 'Auth Tenant', type: 'Descope', icon: Shield, url: '#' },
            { label: 'CI/CD Pipeline', type: 'GitHub Actions', icon: Terminal, url: '#' },
        ]
    }
];

export default function AdminEnvironments() {
    return (
        <div className="page-container">
            <div className="page-header" style={{ marginBottom: 'var(--space-6)' }}>
                <div>
                    <h1 className="page-title">
                        <CloudCog style={{ display: 'inline', marginRight: 'var(--space-2)', verticalAlign: 'text-bottom' }} />
                        System Architecture
                    </h1>
                    <p className="page-subtitle">Directory of deployed environments and infrastructure links</p>
                </div>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-6)' }}>
                {ENVIRONMENTS.map((env) => (
                    <div key={env.key} className="card" style={{ padding: 'var(--space-5)' }}>
                        <div style={{ 
                            display: 'flex', 
                            justifyContent: 'space-between', 
                            alignItems: 'flex-start',
                            marginBottom: 'var(--space-4)',
                            borderBottom: '1px solid var(--color-border)',
                            paddingBottom: 'var(--space-4)'
                        }}>
                            <div>
                                <h2 style={{ 
                                    fontSize: 'var(--font-size-lg)', 
                                    fontWeight: 600, 
                                    color: 'var(--color-text-primary)',
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: 'var(--space-2)'
                                }}>
                                    {env.name}
                                    <span style={{ 
                                        fontSize: 'var(--font-size-xs)',
                                        padding: '2px 8px',
                                        borderRadius: '12px',
                                        background: env.bg,
                                        color: env.color,
                                        fontWeight: 600,
                                        display: 'flex',
                                        alignItems: 'center',
                                        gap: '4px'
                                    }}>
                                        <Activity size={12} />
                                        {env.status}
                                    </span>
                                </h2>
                                <p style={{ 
                                    fontSize: 'var(--font-size-sm)', 
                                    color: 'var(--color-text-muted)',
                                    marginTop: 'var(--space-1)'
                                }}>
                                    {env.description}
                                </p>
                            </div>
                        </div>

                        <div style={{ 
                            display: 'grid', 
                            gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', 
                            gap: 'var(--space-4)' 
                        }}>
                            {env.resources.map((resource, idx) => (
                                <a 
                                    key={idx}
                                    href={resource.url} 
                                    target="_blank" 
                                    rel="noreferrer"
                                    style={{
                                        display: 'flex',
                                        alignItems: 'center',
                                        gap: 'var(--space-3)',
                                        padding: 'var(--space-3)',
                                        background: 'var(--color-bg-glass)',
                                        border: '1px solid var(--color-border)',
                                        borderRadius: 'var(--radius-md)',
                                        textDecoration: 'none',
                                        color: 'inherit',
                                        transition: 'all var(--transition-fast)'
                                    }}
                                    onMouseEnter={(e) => {
                                        e.currentTarget.style.borderColor = 'var(--color-border-hover)';
                                        e.currentTarget.style.background = 'var(--color-bg-card-hover)';
                                        e.currentTarget.style.transform = 'translateY(-2px)';
                                    }}
                                    onMouseLeave={(e) => {
                                        e.currentTarget.style.borderColor = 'var(--color-border)';
                                        e.currentTarget.style.background = 'var(--color-bg-glass)';
                                        e.currentTarget.style.transform = 'none';
                                    }}
                                >
                                    <div style={{
                                        width: 36,
                                        height: 36,
                                        borderRadius: 'var(--radius-sm)',
                                        background: 'rgba(99, 102, 241, 0.1)',
                                        color: 'var(--color-accent-light)',
                                        display: 'flex',
                                        alignItems: 'center',
                                        justifyContent: 'center',
                                        flexShrink: 0
                                    }}>
                                        <resource.icon size={18} />
                                    </div>
                                    <div style={{ flex: 1, minWidth: 0 }}>
                                        <div style={{ 
                                            fontSize: 'var(--font-size-sm)', 
                                            fontWeight: 600,
                                            color: 'var(--color-text-primary)'
                                        }}>
                                            {resource.label}
                                        </div>
                                        <div style={{ 
                                            fontSize: 'var(--font-size-xs)', 
                                            color: 'var(--color-text-muted)',
                                            whiteSpace: 'nowrap',
                                            overflow: 'hidden',
                                            textOverflow: 'ellipsis'
                                        }}>
                                            {resource.type}
                                        </div>
                                    </div>
                                    <ExternalLink size={14} color="var(--color-text-muted)" />
                                </a>
                            ))}
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
}
