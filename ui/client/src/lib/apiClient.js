import axios from 'axios';

export const DASHBOARD_BACKEND_MODE = (import.meta.env.VITE_DASHBOARD_BACKEND || 'demo')
  .trim()
  .toLowerCase() === 'real'
  ? 'real'
  : 'demo';

export const IS_REAL_PREVIEW = DASHBOARD_BACKEND_MODE === 'real';
export const REAL_APPROVALS_ENABLED =
  IS_REAL_PREVIEW &&
  ['1', 'true', 'yes', 'on'].includes(
    (import.meta.env.VITE_REAL_APPROVALS_ENABLED || '').trim().toLowerCase()
  );

export const DASHBOARD_MODE = !IS_REAL_PREVIEW
  ? 'demo'
  : REAL_APPROVALS_ENABLED
    ? 'real-live'
    : 'real-preview';

export const DASHBOARD_MODE_LABEL = {
  demo: 'Demo mode',
  'real-preview': 'Live preview',
  'real-live': 'Live approvals',
}[DASHBOARD_MODE];

export const DASHBOARD_MODE_HINT = {
  demo: 'Local demo data',
  'real-preview': 'Live backend, write actions disabled',
  'real-live': 'Live approvals enabled; other write actions may still be disabled',
}[DASHBOARD_MODE];

export const AUTH_STORAGE_KEY = 'myos_token';

const REAL_API_BASE_URL = (import.meta.env.VITE_REAL_API_BASE_URL || '/api/live').trim();

const REAL_GET_ROUTE_MAP = new Map([
  ['/api/notifications', '/dashboard/notifications'],
  ['/api/approvals', '/dashboard/approvals'],
  ['/api/activity', '/dashboard/activity'],
  ['/api/summaries', '/dashboard/summaries'],
  ['/api/agents', '/dashboard/agents'],
  ['/api/agents/stats', '/dashboard/agents/stats'],
  ['/api/finances/stats', '/dashboard/finances/stats'],
]);

const REAL_PATCH_ROUTE_MAP = new Map([
  ['/api/approvals', '/dashboard/approvals'],
]);

const REAL_DELETE_ROUTE_MAP = new Map([
  ['/api/approvals', '/dashboard/approvals'],
  ['/api/notifications', '/dashboard/notifications'],
  ['/api/summaries', '/dashboard/summaries'],
]);

const READ_ONLY_WRITE_PREFIXES = [
  '/api/notifications',
  '/api/summaries',
];

const demoClient = axios.create();
const realClient = axios.create({
  baseURL: REAL_API_BASE_URL,
});

const getPath = (url) => {
  try {
    return new URL(url, 'http://local.test').pathname;
  } catch {
    return url.split('?')[0];
  }
};

const isAuthRequest = (path) => path.startsWith('/api/auth');

const getToken = () => {
  if (typeof window === 'undefined') return null;
  return window.localStorage.getItem(AUTH_STORAGE_KEY);
};

demoClient.interceptors.request.use((config) => {
  const token = getToken();
  if (token) {
    config.headers = config.headers || {};
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

realClient.interceptors.request.use((config) => {
  const token = getToken();
  if (token) {
    config.headers = config.headers || {};
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

demoClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401 && typeof window !== 'undefined') {
      window.localStorage.removeItem(AUTH_STORAGE_KEY);
    }
    return Promise.reject(error);
  }
);

realClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401 && typeof window !== 'undefined') {
      window.localStorage.removeItem(AUTH_STORAGE_KEY);
    }
    return Promise.reject(error);
  }
);

export const isReadOnlyPreviewMutation = (url) => {
  if (!IS_REAL_PREVIEW) return false;
  const path = getPath(url);
  if (REAL_APPROVALS_ENABLED && path.startsWith('/api/approvals')) return false;
  return READ_ONLY_WRITE_PREFIXES.some((prefix) => path.startsWith(prefix));
};

const resolveRequestTarget = (method, url) => {
  const path = getPath(url);
  const normalizedMethod = method.toLowerCase();

  if (isAuthRequest(path)) {
    return { client: demoClient, url: path };
  }

  if (IS_REAL_PREVIEW && normalizedMethod === 'get' && REAL_GET_ROUTE_MAP.has(path)) {
    return {
      client: realClient,
      url: REAL_GET_ROUTE_MAP.get(path) || path,
    };
  }

  if (IS_REAL_PREVIEW && REAL_APPROVALS_ENABLED && normalizedMethod === 'patch') {
    for (const [prefix, targetPrefix] of REAL_PATCH_ROUTE_MAP.entries()) {
      if (path.startsWith(prefix)) {
        return {
          client: realClient,
          url: path.replace(prefix, targetPrefix),
        };
      }
    }
  }

  if (IS_REAL_PREVIEW && normalizedMethod === 'delete') {
    for (const [prefix, targetPrefix] of REAL_DELETE_ROUTE_MAP.entries()) {
      if (path.startsWith(prefix)) {
        if (prefix === '/api/approvals' && !REAL_APPROVALS_ENABLED) {
          continue;
        }
        return {
          client: realClient,
          url: path.replace(prefix, targetPrefix),
        };
      }
    }
  }

  return { client: demoClient, url: path };
};

export async function apiRequest(method, url, config = {}) {
  const target = resolveRequestTarget(method, url);
  return target.client.request({
    method,
    url: target.url,
    ...config,
  });
}

export const apiGet = (url, config = {}) => apiRequest('get', url, config);
export const apiPost = (url, data, config = {}) => apiRequest('post', url, { ...config, data });
export const apiPatch = (url, data, config = {}) => apiRequest('patch', url, { ...config, data });
export const apiDelete = (url, config = {}) => apiRequest('delete', url, config);

export const authApi = {
  get: (url, config = {}) => demoClient.get(getPath(url), config),
  post: (url, data, config = {}) => demoClient.post(getPath(url), data, config),
};
