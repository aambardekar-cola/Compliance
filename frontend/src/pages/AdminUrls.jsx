import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useAuthSession } from '../auth/AuthProvider';
import { Plus, Edit2, Trash2, X, CheckCircle, Globe } from 'lucide-react';
import apiClient from '../api/client';

export default function AdminUrls() {
    const { sessionToken } = useAuthSession();
    apiClient.setToken(sessionToken);
    const queryClient = useQueryClient();

    const [isSourceModalOpen, setIsSourceModalOpen] = useState(false);
    const [editingSource, setEditingSource] = useState(null);

    const { data: urls = [], isLoading } = useQuery({
        queryKey: ['admin-urls'],
        queryFn: () => apiClient.getAdminUrls(),
        enabled: !!sessionToken,
    });

    const createMutation = useMutation({
        mutationFn: (data) => apiClient.createAdminUrl(data),
        onSuccess: () => {
            queryClient.invalidateQueries(['admin-urls']);
            closeModal();
        },
    });

    const updateMutation = useMutation({
        mutationFn: ({ id, data }) => apiClient.updateAdminUrl(id, data),
        onSuccess: () => {
            queryClient.invalidateQueries(['admin-urls']);
            closeModal();
        },
    });

    const deleteMutation = useMutation({
        mutationFn: (id) => apiClient.deleteAdminUrl(id),
        onSuccess: () => {
            queryClient.invalidateQueries(['admin-urls']);
        },
    });

    const handleSave = (e) => {
        e.preventDefault();
        const formData = new FormData(e.target);
        const data = {
            name: formData.get('name'),
            url: formData.get('url'),
            description: formData.get('description'),
            is_active: formData.get('is_active') === 'on',
        };

        if (editingSource) {
            updateMutation.mutate({ id: editingSource.id, data });
        } else {
            createMutation.mutate(data);
        }
    };

    const handleDelete = (id) => {
        if (window.confirm("Are you sure you want to delete this URL?")) {
            deleteMutation.mutate(id);
        }
    };

    const openModal = (source = null) => {
        setEditingSource(source);
        setIsSourceModalOpen(true);
    };

    const closeModal = () => {
        setEditingSource(null);
        setIsSourceModalOpen(false);
    };

    return (
        <div className="animate-in">
            <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                    <h1 className="page-title">Compliance Sources</h1>
                    <p className="page-description">Manage external URLs to monitor for regulatory changes</p>
                </div>
                <button className="btn btn-primary" onClick={() => openModal()}>
                    <Plus size={16} /> Add Source
                </button>
            </div>

            <div className="card">
                {isLoading ? (
                    <div className="empty-state">Loading sources...</div>
                ) : urls.length === 0 ? (
                    <div className="empty-state">
                        <Globe />
                        <h3>No sources configured</h3>
                        <p>Add URLs that the system should crawl for compliance rule changes.</p>
                        <button className="btn btn-primary" onClick={() => openModal()} style={{ marginTop: '1rem' }}>
                            Add Your First Source
                        </button>
                    </div>
                ) : (
                    <table className="data-table">
                        <thead>
                            <tr>
                                <th>Name</th>
                                <th>URL</th>
                                <th>Status</th>
                                <th>Description</th>
                                <th style={{ textAlign: 'right' }}>Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            {urls.map((source) => (
                                <tr key={source.id}>
                                    <td style={{ fontWeight: 500, color: 'var(--color-text-primary)' }}>{source.name}</td>
                                    <td>
                                        <a href={source.url} target="_blank" rel="noopener noreferrer" style={{ color: 'var(--color-primary)' }}>
                                            {source.url.length > 50 ? source.url.substring(0, 50) + '...' : source.url}
                                        </a>
                                    </td>
                                    <td>
                                        {source.is_active ? (
                                            <span className="badge badge-success"><span className="badge-dot" /> Active</span>
                                        ) : (
                                            <span className="badge badge-medium">Inactive</span>
                                        )}
                                    </td>
                                    <td style={{ fontSize: 'var(--font-size-sm)', opacity: 0.8 }}>
                                        {source.description || '—'}
                                    </td>
                                    <td>
                                        <div style={{ display: 'flex', gap: 'var(--space-2)', justifyContent: 'flex-end' }}>
                                            <button className="btn btn-secondary" onClick={() => openModal(source)} style={{ padding: '6px' }}>
                                                <Edit2 size={14} />
                                            </button>
                                            <button className="btn btn-secondary" onClick={() => handleDelete(source.id)} style={{ padding: '6px', color: 'var(--color-danger)' }}>
                                                <Trash2 size={14} />
                                            </button>
                                        </div>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                )}
            </div>

            {/* Form Modal */}
            {isSourceModalOpen && (
                <div className="modal-overlay">
                    <div className="modal-content animate-in" style={{ maxWidth: '500px' }}>
                        <div className="modal-header">
                            <h2>{editingSource ? 'Edit Source' : 'Add Compliance Source'}</h2>
                            <button className="btn-icon" onClick={closeModal}><X size={20} /></button>
                        </div>
                        <form onSubmit={handleSave}>
                            <div className="modal-body" style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
                                
                                <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2)' }}>
                                    <label style={{ fontWeight: 500, fontSize: 'var(--font-size-sm)' }}>Name *</label>
                                    <input 
                                        type="text" 
                                        name="name" 
                                        defaultValue={editingSource?.name || ''} 
                                        required 
                                        className="form-input" 
                                        placeholder="e.g. CMS Federal Register" 
                                    />
                                </div>

                                <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2)' }}>
                                    <label style={{ fontWeight: 500, fontSize: 'var(--font-size-sm)' }}>URL *</label>
                                    <input 
                                        type="url" 
                                        name="url" 
                                        defaultValue={editingSource?.url || ''} 
                                        required 
                                        className="form-input" 
                                        placeholder="https://..." 
                                    />
                                </div>

                                <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2)' }}>
                                    <label style={{ fontWeight: 500, fontSize: 'var(--font-size-sm)' }}>Description</label>
                                    <textarea 
                                        name="description" 
                                        defaultValue={editingSource?.description || ''} 
                                        className="form-input"
                                        rows="3"
                                        placeholder="Optional notes about this source"
                                    />
                                </div>

                                <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
                                    <input 
                                        type="checkbox" 
                                        name="is_active" 
                                        id="is_active" 
                                        defaultChecked={editingSource ? editingSource.is_active : true} 
                                    />
                                    <label htmlFor="is_active" style={{ fontSize: 'var(--font-size-sm)' }}>Active (Monitor this URL)</label>
                                </div>

                            </div>
                            <div className="modal-footer" style={{ marginTop: 'var(--space-6)', display: 'flex', justifyContent: 'flex-end', gap: 'var(--space-3)' }}>
                                <button type="button" className="btn btn-secondary" onClick={closeModal}>Cancel</button>
                                <button type="submit" className="btn btn-primary" disabled={createMutation.isPending || updateMutation.isPending}>
                                    {editingSource ? 'Save Changes' : 'Add Source'}
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            )}
        </div>
    );
}
