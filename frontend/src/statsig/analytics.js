/**
 * Statsig product analytics utility.
 *
 * Provides a thin wrapper around Statsig.logEvent for tracking user actions.
 * Falls back silently if Statsig SDK is not initialized.
 *
 * Usage:
 *   import { trackEvent } from '../statsig/analytics';
 *   trackEvent('regulation_viewed', { id: reg.id, source: 'dashboard' });
 */

let _client = null;

/**
 * Initialize the analytics module with the Statsig client instance.
 * Called automatically by StatsigProvider after SDK init.
 */
export function setAnalyticsClient(client) {
  _client = client;
}

/**
 * Track a product analytics event.
 *
 * @param {string} eventName - Event name (e.g. 'regulation_viewed', 'gap_export')
 * @param {Record<string, string|number|boolean>} metadata - Key-value metadata
 * @param {number|null} value - Optional numeric value (e.g. count, duration)
 */
export function trackEvent(eventName, metadata = {}, value = null) {
  if (!_client) return;

  try {
    _client.logEvent(eventName, value, metadata);
  } catch {
    // Silently fail — analytics should never break the app
  }
}

// ──────────────────────────────────────────────
// Pre-defined event helpers for common actions
// ──────────────────────────────────────────────

/** Track when a user views a regulation detail page */
export function trackRegulationView(regulationId, source = 'list') {
  trackEvent('regulation_viewed', { regulation_id: regulationId, source });
}

/** Track when a user views a gap detail */
export function trackGapView(gapId, regulationId) {
  trackEvent('gap_viewed', { gap_id: gapId, regulation_id: regulationId });
}

/** Track when a user exports a report */
export function trackReportExport(reportType, format = 'pdf') {
  trackEvent('report_exported', { report_type: reportType, format });
}

/** Track when a user searches regulations */
export function trackSearch(query, resultsCount) {
  trackEvent('search_performed', { query_length: query.length }, resultsCount);
}

/** Track when a user changes a page (pagination) */
export function trackPageChange(section, page) {
  trackEvent('page_changed', { section, page });
}

/** Track when a user toggles demo mode */
export function trackDemoModeToggle(enabled) {
  trackEvent('demo_mode_toggled', { enabled: String(enabled) });
}

/** Track when a pipeline run is triggered */
export function trackPipelineRun(type) {
  trackEvent('pipeline_triggered', { pipeline_type: type });
}

/** Track navigation to a section */
export function trackNavigation(section) {
  trackEvent('section_navigated', { section });
}
