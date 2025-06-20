import { useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { getSessionStatus } from '../lib/api';

const SessionMonitor = () => {
  const navigate = useNavigate();
  const consecutiveFailures = useRef(0);
  const isAlertShown = useRef(false);

  useEffect(() => {
    // Check session status every 30 seconds
    const checkSession = async () => {
      try {
        const token = localStorage.getItem('inu_token');
        if (!token) {
          consecutiveFailures.current = 0;
          return; // No token, no need to check
        }

        await getSessionStatus();
        // If we get here, session is valid - reset failure counter
        consecutiveFailures.current = 0;
        console.log('[SessionMonitor] Session check successful');
        
      } catch (error) {
        consecutiveFailures.current++;
        console.log(`[SessionMonitor] Session check failed (attempt ${consecutiveFailures.current}):`, error);
        
        // Only act on consecutive failures to avoid false positives from network issues
        if (consecutiveFailures.current < 2) {
          console.log('[SessionMonitor] Ignoring single failure, waiting for confirmation');
          return;
        }
        
        // Check if it's a session invalidation error
        try {
          const errorData = JSON.parse(error.message);
          if (errorData.code === 'session_invalidated') {
            console.log('[SessionMonitor] Session invalidated by another login');
            if (!isAlertShown.current) {
              isAlertShown.current = true;
              localStorage.removeItem('inu_token');
              alert('다른 사용자가 로그인했습니다. 로그인 페이지로 이동합니다.');
              navigate('/');
            }
            return;
          }
        } catch (e) {
          // Error parsing, check for 401 status
          if (error.message.includes('401')) {
            console.log('[SessionMonitor] Session expired (401 error)');
            if (!isAlertShown.current) {
              isAlertShown.current = true;
              localStorage.removeItem('inu_token');
              alert('세션이 만료되었습니다. 다시 로그인해주세요.');
              navigate('/');
            }
            return;
          }
        }
        
        // For other errors (network issues, etc.), don't immediately logout
        console.log('[SessionMonitor] Non-session error, continuing to monitor');
      }
    };

    // Initial check after a short delay to avoid immediate checks on page load
    const initialTimeout = setTimeout(checkSession, 5000); // Wait 5 seconds before first check

    // Set up interval for periodic checks
    const interval = setInterval(checkSession, 30000); // Check every 30 seconds

    return () => {
      clearTimeout(initialTimeout);
      clearInterval(interval);
    };
  }, [navigate]);

  return null; // This component doesn't render anything
};

export default SessionMonitor; 