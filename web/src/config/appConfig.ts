/**
 * Configuration for the web application
 */

export interface AppConfig {
  api: {
    baseUrl: string;
    port: number;
    endpoints: {
      query: string;
      stream: string;
      health: string;
      freshness: string;
    };
  };
  features: {
    safety: {
      enabled: boolean;
      defaultState: boolean;
    };
    imageUpload: {
      enabled: boolean;
      maxSize: number; // in MB
      allowedTypes: string[];
    };
  };
}

// Get configuration based on environment
const getConfig = (): AppConfig => {
  // Default to nginx proxy routing, but allow local development to target orchestrator directly.
  const baseUrl = import.meta.env.REACT_APP_API_BASE_URL || '/api';
  return {
    api: {
      baseUrl: baseUrl,
      port: 80,
      endpoints: {
        query: '/query',
        stream: '/query/stream',
        health: '/health',
        freshness: '/config/freshness',
      },
    },
    features: {
      safety: {
        enabled: true,
        defaultState: true,
      },
      imageUpload: {
        enabled: true,
        maxSize: 10, // 10MB
        allowedTypes: ['image/jpeg', 'image/png'],
      },
    },
  };
};

export const config = getConfig();

// Helper functions
export const getApiUrl = (endpoint: keyof AppConfig['api']['endpoints']): string => {
  return `${config.api.baseUrl}${config.api.endpoints[endpoint]}`;
};
