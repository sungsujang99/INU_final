import { useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { getSessionStatus } from '../lib/api';

// Override localStorage methods to track all operations
const originalRemoveItem = localStorage.removeItem;
const originalSetItem = localStorage.setItem;
const originalClear = localStorage.clear;

localStorage.removeItem = function(key) {
  if (key === 'inu_token') {
    console.log('🔥🔥🔥 TOKEN BEING REMOVED! 🔥🔥🔥');
    console.trace('Token removal stack trace');
  }
  console.log(`[localStorage] removeItem called for key: ${key}`);
  return originalRemoveItem.call(this, key);
};

localStorage.setItem = function(key, value) {
  if (key === 'inu_token') {
    console.log('🟢🟢🟢 TOKEN BEING SET! 🟢🟢🟢');
    console.log('Token value:', value ? value.substring(0, 20) + '...' : 'null');
  }
  console.log(`[localStorage] setItem called for key: ${key}`);
  return originalSetItem.call(this, key, value);
};

localStorage.clear = function() {
  console.log('🔥🔥🔥 LOCALSTORAGE BEING CLEARED! 🔥🔥🔥');
  console.trace('localStorage clear stack trace');
  return originalClear.call(this);
};

// Track page visibility changes
document.addEventListener('visibilitychange', () => {
  console.log(`[PageVisibility] Page visibility changed to: ${document.visibilityState}`);
  const token = localStorage.getItem('inu_token');
  console.log(`[PageVisibility] Token status: ${token ? 'EXISTS' : 'MISSING'}`);
});

// Track page unload
window.addEventListener('beforeunload', () => {
  console.log('[PageUnload] Page is about to unload');
  const token = localStorage.getItem('inu_token');
  console.log(`[PageUnload] Token status: ${token ? 'EXISTS' : 'MISSING'}`);
});

const SessionMonitor = () => {
  console.log('🚨🚨🚨 SessionMonitor component is loading! 🚨🚨🚨');
  console.log('[SessionMonitor] Component mount - checking initial token status');
  const initialToken = localStorage.getItem('inu_token');
  console.log(`[SessionMonitor] Initial token status: ${initialToken ? 'EXISTS' : 'MISSING'}`);
  
  const navigate = useNavigate();
  const consecutiveFailures = useRef(0);
  const isAlertShown = useRef(false);
  const lastCheckTime = useRef(0);

  useEffect(() => {
    console.log('🚨🚨🚨 SessionMonitor useEffect is running! 🚨🚨🚨');
    
    // Check session status every 30 seconds
    const checkSession = async () => {
      const now = Date.now();
      const timeSinceLastCheck = now - lastCheckTime.current;
      lastCheckTime.current = now;
      
      console.log(`[SessionMonitor] Starting session check (${timeSinceLastCheck}ms since last check)`);
      console.log(`[SessionMonitor] Current state: consecutiveFailures=${consecutiveFailures.current}, isAlertShown=${isAlertShown.current}`);
      
      // Debug localStorage contents
      console.log('[SessionMonitor] Checking localStorage contents...');
      console.log('[SessionMonitor] All localStorage keys:', Object.keys(localStorage));
      console.log('[SessionMonitor] localStorage contents:', localStorage);
      
      try {
        const token = localStorage.getItem('inu_token');
        console.log(`[SessionMonitor] Token lookup result: ${token ? 'FOUND' : 'NOT FOUND'}`);
        console.log(`[SessionMonitor] Token value: ${token}`);
        
        if (!token) {
          console.log('[SessionMonitor] No token found, resetting state');
          console.log('[SessionMonitor] DEBUG: This is why no session check is happening!');
          consecutiveFailures.current = 0;
          isAlertShown.current = false; // Reset alert flag when no token
          return; // No token, no need to check
        }

        console.log(`[SessionMonitor] Token found: ${token.substring(0, 20)}...`);
        
        const sessionData = await getSessionStatus();
        console.log('[SessionMonitor] Session status response:', sessionData);
        
        // If we get here, session is valid - reset failure counter AND alert flag
        consecutiveFailures.current = 0;
        isAlertShown.current = false; // Reset alert flag on successful check
        console.log('[SessionMonitor] Session check successful - state reset');
        
      } catch (error) {
        consecutiveFailures.current++;
        console.error(`[SessionMonitor] Session check failed (attempt ${consecutiveFailures.current}):`, error);
        console.log(`[SessionMonitor] Error type: ${typeof error}, message: ${error.message}`);
        
        // Only act on consecutive failures to avoid false positives from network issues
        if (consecutiveFailures.current < 2) {
          console.log('[SessionMonitor] Ignoring single failure, waiting for confirmation');
          return;
        }
        
        // Only show alert if we haven't already shown one
        if (isAlertShown.current) {
          console.log('[SessionMonitor] Alert already shown, skipping');
          return;
        }
        
        console.log('[SessionMonitor] Processing error after consecutive failures...');
        
        // Check if it's a session invalidation error
        try {
          const errorData = JSON.parse(error.message);
          console.log('[SessionMonitor] Parsed error data:', errorData);
          
          if (errorData.code === 'session_invalidated') {
            console.log('[SessionMonitor] *** TRIGGERING SESSION INVALIDATED ALERT ***');
            isAlertShown.current = true;
            localStorage.removeItem('inu_token');
            alert('다른 사용자가 로그인했습니다. 로그인 페이지로 이동합니다.');
            navigate('/');
            return;
          }
        } catch (e) {
          console.log('[SessionMonitor] Error parsing failed, checking for 401 status');
          console.log('[SessionMonitor] Parse error:', e);
          
          // Error parsing, check for 401 status
          if (error.message.includes('401')) {
            console.log('[SessionMonitor] *** TRIGGERING 401 ERROR ALERT ***');
            isAlertShown.current = true;
            localStorage.removeItem('inu_token');
            alert('세션이 만료되었습니다. 다시 로그인해주세요.');
            navigate('/');
            return;
          }
        }
        
        // For other errors (network issues, etc.), don't immediately logout
        console.log('[SessionMonitor] Non-session error, continuing to monitor');
      }
    };

    console.log('[SessionMonitor] Initializing session monitor...');
    
    // Initial check after a short delay to avoid immediate checks on page load
    const initialTimeout = setTimeout(() => {
      console.log('[SessionMonitor] Running initial session check...');
      checkSession();
    }, 5000); // Wait 5 seconds before first check

    // Set up interval for periodic checks
    const interval = setInterval(() => {
      console.log('[SessionMonitor] Running periodic session check...');
      checkSession();
    }, 30000); // Check every 30 seconds

    return () => {
      console.log('[SessionMonitor] Cleaning up session monitor...');
      clearTimeout(initialTimeout);
      clearInterval(interval);
    };
  }, [navigate]);

  return null; // This component doesn't render anything
};

export default SessionMonitor; 