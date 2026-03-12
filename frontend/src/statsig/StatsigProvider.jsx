/**
 * Statsig SDK provider for feature gates and dynamic configs.
 *
 * Uses the new @statsig/react-bindings + @statsig/js-client packages
 * (the older statsig-react is deprecated).
 *
 * Wraps the app to enable:
 * - Feature gates (demo_mode, force_demo_mode, api_docs_enabled)
 * - Dynamic configs (pagination, ai_models, etc.)
 * - Future: experiments and product analytics events
 *
 * Falls back gracefully if VITE_STATSIG_CLIENT_KEY is not set.
 */
import { StatsigProvider as BaseStatsigProvider, useGateValue, useDynamicConfig } from '@statsig/react-bindings';

const STATSIG_CLIENT_KEY = import.meta.env.VITE_STATSIG_CLIENT_KEY || '';
const STATSIG_ENV = import.meta.env.VITE_APP_ENV || 'development';

/**
 * Wraps children in Statsig SDK context.
 * If no client key is set, renders children without Statsig (local dev).
 */
export function StatsigProvider({ children }) {
  if (!STATSIG_CLIENT_KEY) {
    return <>{children}</>;
  }

  return (
    <BaseStatsigProvider
      sdkKey={STATSIG_CLIENT_KEY}
      user={{ userID: 'anonymous' }}
      options={{
        environment: { tier: STATSIG_ENV },
      }}
    >
      {children}
    </BaseStatsigProvider>
  );
}

/**
 * Hook to check a Statsig feature gate.
 * Returns false if Statsig is not initialized.
 */
export function useStatsigGate(gateName) {
  if (!STATSIG_CLIENT_KEY) {
    return false;
  }
  return useGateValue(gateName);
}

/**
 * Hook to get a Statsig dynamic config value.
 * Returns defaultValue if Statsig is not initialized.
 */
export function useStatsigConfig(configName) {
  if (!STATSIG_CLIENT_KEY) {
    return {};
  }
  const config = useDynamicConfig(configName);
  return config.value || {};
}

export { STATSIG_CLIENT_KEY };
