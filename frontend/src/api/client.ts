import axios from 'axios';

// Create axios instance with default config
const api = axios.create({
  baseURL: '/api',  // This will use the proxy configuration from vite.config.js
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor for adding auth token
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Response interceptor for handling errors
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

// API endpoints
export const authAPI = {
  login: (username: string, password: string) =>
    api.post('/login', { username, password }),
};

export const inventoryAPI = {
  getAll: () => api.get('/inventory'),
  getByRack: (rack: string) => api.get(`/inventory?rack=${rack}`),
  getByRackAndSlot: (rack: string, slot: number) =>
    api.get(`/inventory?rack=${rack}&slot=${slot}`),
};

export const timelineAPI = {
  get: (from: string, to: string, format: 'json' | 'csv' = 'json') =>
    api.get(`/timeline?from=${from}&to=${to}&format=${format}`),
};

export const recordAPI = {
  add: (records: any[]) => api.post('/record', records),
  uploadCSV: (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return api.post('/upload-csv', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
};

export const commandAPI = {
  send: (rack: string, code: string, wait: boolean = true) =>
    api.post('/send-command', { rack, code, wait }),
};

export const queueAPI = {
  getStatus: () => api.get('/queue-status'),
};

export default api; 