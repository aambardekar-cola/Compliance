import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AuthProviderWrapper } from './auth/AuthProvider';
import App from './App.jsx';
import './index.css';

// Datadog RUM — production only (saves ~$2/mo in non-prod)
if (import.meta.env.PROD && import.meta.env.VITE_DD_RUM_APP_ID) {
  import('@datadog/browser-rum').then(({ datadogRum }) => {
    datadogRum.init({
      applicationId: import.meta.env.VITE_DD_RUM_APP_ID,
      clientToken: import.meta.env.VITE_DD_RUM_CLIENT_TOKEN,
      site: import.meta.env.VITE_DD_SITE || 'datadoghq.com',
      service: 'pco-compliance-frontend',
      env: import.meta.env.VITE_DD_ENV || 'production',
      version: import.meta.env.VITE_APP_VERSION || '1.0.0',
      sessionSampleRate: 100,
      sessionReplaySampleRate: 20, // Only replay 20% of sessions to save costs
      trackUserInteractions: true,
      trackResources: true,
      trackLongTasks: true,
      defaultPrivacyLevel: 'mask-user-input', // Mask PII in session replays
      allowedTracingUrls: [
        // Connect frontend traces to backend APM traces
        { match: /\/api\//, propagatorTypes: ['datadog'] },
      ],
    });
  });
}

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30000,
      retry: 2,
    },
  },
});

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <AuthProviderWrapper>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <App />
        </BrowserRouter>
      </QueryClientProvider>
    </AuthProviderWrapper>
  </StrictMode>
);
