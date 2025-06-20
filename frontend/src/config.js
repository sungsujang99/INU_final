/**
 * Configuration file for dynamic backend URL detection
 * Automatically detects the backend URL based on current environment
 */

// Get the current host (IP address or hostname)
const getCurrentHost = () => {
  if (typeof window !== 'undefined') {
    return window.location.hostname;
  }
  return 'localhost';
};

// Get the backend URL (backend runs on port 5001)
export const getBackendUrl = () => {
  // Check if there's an environment variable for backend URL
  if (import.meta.env.VITE_BACKEND_URL) {
    return import.meta.env.VITE_BACKEND_URL;
  }
  
  // Auto-detect based on current host
  const host = getCurrentHost();
  return `http://${host}:5001`;
};

// Get the socket URL (same as backend URL for Socket.IO)
export const getSocketUrl = () => {
  return getBackendUrl();
};

// Get the API base URL (same as backend URL)
export const getApiBaseUrl = () => {
  return getBackendUrl();
};

// Export default configuration object
export default {
  getBackendUrl,
  getSocketUrl,
  getApiBaseUrl
}; 