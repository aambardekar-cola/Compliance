/**
 * API client for the PCO Compliance backend.
 */

const API_BASE = window.ENV?.API_URL || import.meta.env.VITE_API_URL || 'http://localhost:8000';

class ApiClient {
    constructor() {
        // Strip out any trailing slashes to prevent double-slashes when appending routes
        this.baseUrl = API_BASE.replace(/\/$/, '');
        this.token = null;
    }

    setToken(token) {
        this.token = token;
    }

    async request(path, options = {}) {
        const url = `${this.baseUrl}${path}`;
        const headers = {
            'Content-Type': 'application/json',
            ...(this.token && { Authorization: `Bearer ${this.token}` }),
            ...options.headers,
        };

        const response = await fetch(url, { ...options, headers });

        if (!response.ok) {
            const error = await response.json().catch(() => ({}));
            throw new Error(error.detail || `API error: ${response.status}`);
        }

        return response.json();
    }

    // Dashboard
    getDashboard() {
        return this.request('/dashboard');
    }

    // Regulations
    getRegulations(params = {}) {
        const query = new URLSearchParams(params).toString();
        return this.request(`/regulations${query ? `?${query}` : ''}`);
    }

    getRegulation(id) {
        return this.request(`/regulations/${id}`);
    }

    // Gap Analysis
    getGaps(params = {}) {
        const query = new URLSearchParams(params).toString();
        return this.request(`/gaps${query ? `?${query}` : ''}`);
    }

    getGapsSummary() {
        return this.request('/gaps/summary');
    }

    getGap(id) {
        return this.request(`/gaps/${id}`);
    }

    // Communications
    getCommunications(params = {}) {
        const query = new URLSearchParams(params).toString();
        return this.request(`/communications${query ? `?${query}` : ''}`);
    }

    getCommunication(id) {
        return this.request(`/communications/${id}`);
    }

    approveCommunication(id) {
        return this.request(`/communications/${id}/approve`, { method: 'POST' });
    }

    sendCommunication(id) {
        return this.request(`/communications/${id}/send`, {
            method: 'POST',
            body: JSON.stringify({ send_now: true }),
        });
    }

    // Reports
    getReports(params = {}) {
        const query = new URLSearchParams(params).toString();
        return this.request(`/reports${query ? `?${query}` : ''}`);
    }

    getReport(id) {
        return this.request(`/reports/${id}`);
    }

    // Subscriptions
    getSubscriptions() {
        return this.request('/subscriptions');
    }

    updateSubscription(feature, data) {
        return this.request(`/subscriptions/${feature}`, {
            method: 'PUT',
            body: JSON.stringify(data),
        });
    }

    // Admin URLs
    getAdminUrls() {
        return this.request('/admin/urls');
    }

    createAdminUrl(data) {
        return this.request('/admin/urls', {
            method: 'POST',
            body: JSON.stringify(data),
        });
    }

    updateAdminUrl(id, data) {
        return this.request(`/admin/urls/${id}`, {
            method: 'PUT',
            body: JSON.stringify(data),
        });
    }

    deleteAdminUrl(id) {
        return this.request(`/admin/urls/${id}`, {
            method: 'DELETE',
        });
    }

    // Admin Notifications
    getNotifications(params = {}) {
        const query = new URLSearchParams(params).toString();
        return this.request(`/admin/notifications${query ? `?${query}` : ''}`);
    }

    getUnreadCount() {
        return this.request('/admin/notifications/unread-count');
    }

    markNotificationRead(id) {
        return this.request(`/admin/notifications/${id}/read`, { method: 'POST' });
    }

    markAllNotificationsRead() {
        return this.request('/admin/notifications/read-all', { method: 'POST' });
    }

    // Pipeline Runs
    getPipelineRuns(params = {}) {
        const query = new URLSearchParams(params).toString();
        return this.request(`/admin/pipeline-runs${query ? `?${query}` : ''}`);
    }

    getPipelineRun(id) {
        return this.request(`/admin/pipeline-runs/${id}`);
    }

    // Admin Triggers
    triggerAnalysis() {
        return this.request('/admin/trigger-analysis', { method: 'POST' });
    }

    triggerScraper() {
        return this.request('/admin/trigger-scraper', { method: 'POST' });
    }
}

export const apiClient = new ApiClient();
export default apiClient;
