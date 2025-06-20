import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { getSessionStatus } from '../lib/api';

const SessionMonitor = () => {
  const navigate = useNavigate();

  useEffect(() => {
    // Check session status every 30 seconds
    const checkSession = async () => {
      try {
        const token = localStorage.getItem('inu_token');
        if (!token) {
          return; // No token, no need to check
        }

        await getSessionStatus();
        // If we get here, session is valid
      } catch (error) {
        console.log('Session check failed:', error);
        
        // Check if it's a session invalidation error
        try {
          const errorData = JSON.parse(error.message);
          if (errorData.code === 'session_invalidated') {
            localStorage.removeItem('inu_token');
            alert('다른 사용자가 로그인했습니다. 로그인 페이지로 이동합니다.');
            navigate('/');
            return;
          }
        } catch (e) {
          // Error parsing, check for 401 status
          if (error.message.includes('401')) {
            localStorage.removeItem('inu_token');
            alert('세션이 만료되었습니다. 다시 로그인해주세요.');
            navigate('/');
            return;
          }
        }
      }
    };

    // Initial check
    checkSession();

    // Set up interval for periodic checks
    const interval = setInterval(checkSession, 30000); // Check every 30 seconds

    return () => clearInterval(interval);
  }, [navigate]);

  return null; // This component doesn't render anything
};

export default SessionMonitor; 