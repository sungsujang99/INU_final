import axios from "axios";

export function setToken(t) {
  localStorage.setItem('inu_token', t)
}

async function req(path, options = {}) {
  const headers = { ...(options.headers || {}) }
  // Always get fresh token from localStorage for each request
  const token = localStorage.getItem('inu_token');
  if (token) headers['Authorization'] = `Bearer ${token}`
  
  const res = await fetch('/api' + path, { ...options, headers })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

// 사용 예
export const login = (u, p) =>
  req('/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: u, password: p })
  })

export const uploadCsv = file => {
  const form = new FormData()
  form.append('file', file)
  return req('/upload-csv', { method: 'POST', body: form })
}

export const getInventory = (rack) =>
  req('/inventory' + (rack ? `?rack=${rack}` : ''))

export const getTimeline = (from, to) =>
  req(`/timeline?from=${from}&to=${to}`)

// Function to ping the backend
export const pingBackend = () => req('/ping');

// Function to get task queues - use req function for consistency
export const getTaskQueues = () => req('/task-queues');

export const uploadTasksBatch = async (tasks) => {
  const token = localStorage.getItem('inu_token');
  const url = '/api/upload-tasks';
  console.log('Attempting to POST to URL:', url, 'with token:', token ? "Token Present" : "Token MISSING/NULL");
  const response = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`,
    },
    body: JSON.stringify(tasks),
  });

  // Always try to parse JSON, as our backend sends JSON for errors too (like 207 or 4xx)
  const responseData = await response.json().catch(e => {
    // If JSON parsing fails, create a placeholder error object
    console.error("Failed to parse JSON response:", e);
    // Return a structure that includes a message, consistent with expected errorData
    return { 
      message: `Request failed with status ${response.status}. No parseable JSON error body.`,
      errors: [`Request failed with status ${response.status}. No parseable JSON error body.`], // Make it an array for consistency
      processed_tasks: [] // Empty array for consistency
    };
  });

  if (!response.ok) { // e.g. 400, 401, 422, 500. For 207, response.ok is true.
    console.error("uploadTasksBatch HTTP error:", response.status, responseData);
    // Throw an error with the message from the parsed JSON body, or a default
    // Ensure the error thrown has a .message property
    const errorMessage = responseData.message || `HTTP error ${response.status}`;
    const error = new Error(errorMessage);
    // Optionally attach the full responseData to the error object if needed elsewhere
    // error.data = responseData; 
    throw error;
  }

  // For 2xx responses (including 207), return the parsed JSON data.
  // The calling component will be responsible for interpreting the content of 'responseData',
  // including checking for 'errors' arrays or 'status' fields within it for 207.
  return responseData;
};

/**
 * Sends an array of inventory records to the backend to be added to the database
 * and to enqueue corresponding tasks.
 * @param {Array<Object>} records - An array of record objects.
 *   Each object should match the structure expected by backend's add_records:
 *   {
 *     product_code: string,
 *     product_name: string,
 *     rack: string ('A', 'B', or 'C'),
 *     slot: number (1-80),
 *     movement: string ('IN' or 'OUT'),
 *     quantity: number,
 *     cargo_owner: string,
 *     // user_id: string (optional)
 *   }
 * @returns {Promise<Object>} - The response from the backend.
 */
export const saveInventoryRecordsAndQueueTasks = async (records) => {
  try {
    const token = localStorage.getItem('inu_token');
    const response = await fetch('/api/record', { // Ensure this matches your backend route
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
      body: JSON.stringify(records), // Send the array of records directly
    });
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ message: response.statusText }));
      throw new Error(`HTTP error ${response.status}: ${errorData.message || 'Failed to save records'}`);
    }
    return await response.json();
  } catch (error) {
    console.error('Error in saveInventoryRecordsAndQueueTasks:', error);
    throw error; // Re-throw to be caught by the calling component
  }
};

export const getActivityLogs = (params = {}) => {
  // Construct query string from params if needed (e.g., limit, date_from, order)
  // Example: params = { limit: 10, order: 'desc' }
  //          becomes "?limit=10&order=desc"
  const queryString = new URLSearchParams(params).toString();
  return req(`/activity-logs${queryString ? `?${queryString}` : ''}`);
};

// Remove or comment out the hardcoded API_BASE_URL
// const API_BASE_URL = 'http://localhost:5001'; 

export const getApiBaseUrl = () => {
  // This returns the origin (protocol, hostname, port) of the current page.
  // e.g., "http://192.168.1.102" or "http://raspberrypi.local"
  // If your frontend is served by Vite dev server, this will include the port
  // For production, adjust as needed
  return window.location.origin; 
};

export const loginUser = async (username, password) => {
  // ... your login logic
};

export const checkUser = (username) => 
  req('/check-user', { // Path is just '/check-user'
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username })
  });

// Updated to use req function for consistency instead of axios
export async function getWorkTasksByStatus(status) {
  return req(`/work-tasks?status=${status}`);
}

export const getPendingTaskCounts = () => req('/pending-task-counts');

// Logout function
export const logout = () => 
  req('/logout', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' }
  });

// Session status function
export const getSessionStatus = () => req('/session-status');

// Enhanced error handler for session invalidation
export const handleApiError = (error, navigate) => {
  try {
    const errorData = JSON.parse(error.message);
    if (errorData.code === 'session_invalidated') {
      // Clear local storage and redirect to login
      console.log('🔥🔥🔥 handleApiError is clearing token! 🔥🔥🔥');
      console.trace('Token cleared by handleApiError');
      localStorage.removeItem('inu_token');
      alert('다른 사용자가 로그인했습니다. 다시 로그인해주세요.');
      if (navigate) {
        navigate('/');
      }
      return true; // Indicates session was invalidated
    }
  } catch (e) {
    // Error message is not JSON, handle normally
  }
  return false; // Normal error, not session invalidation
};
