import React, { useState, useEffect } from "react";
import { Group } from "../../components/Group";
import { Menu } from "../../components/Menu";
import { Rectangle } from "../../components/Rectangle";
import { Ic162Thone1 } from "../../icons/Ic162Thone1";
import { Ic162Thone2 } from "../../icons/Ic162Thone2";
import { Ic162Thone4 } from "../../icons/Ic162Thone4";
import { Ic162Thone6 } from "../../icons/Ic162Thone6";
import { Property1LogOut } from "../../icons/Property1LogOut";
import { Property1Variant5 } from "../../icons/Property1Variant5";
import "./style.css";
import { useNavigate } from "react-router-dom";
import { getActivityLogs, getCameraHistory, logout, handleApiError } from "../../lib/api";
import { jwtDecode } from "jwt-decode";
import { getBackendUrl, getApiBaseUrl } from "../../config";

// Helper to format time to "HH : mm : ss"
const formatHms = (timestamp) => {
  if (!timestamp) return "00 : 00 : 00";
  try {
    const d = new Date(timestamp);
    const hh = String(d.getHours()).padStart(2, '0');
    const mm = String(d.getMinutes()).padStart(2, '0');
    const ss = String(d.getSeconds()).padStart(2, '0');
    return `${hh} : ${mm} : ${ss}`;
  } catch (_) {
    return "00 : 00 : 00";
  }
};

export const Camera = () => {
  const navigate = useNavigate();
  const [selectedCamera, setSelectedCamera] = useState('M');
  const [availableCameras, setAvailableCameras] = useState(['M', 'A', 'B', 'C']);
  const [groupedActivityLogs, setGroupedActivityLogs] = useState({});
  const [cameraHistory, setCameraHistory] = useState([]);
  const [userDisplayName, setUserDisplayName] = useState('');

  const handleDashboard = () => navigate('/dashboard');
  const handleWorkStatus = () => navigate('/work-status');
  const handleLogout = () => {
    logout()
      .then(() => {
        localStorage.removeItem('inu_token');
        navigate('/login');
      })
      .catch(error => {
        console.error('Logout error:', error);
        localStorage.removeItem('inu_token');
        navigate('/login');
      });
  };

  const handleReset = () => {
    const apiUrl = getApiBaseUrl();
    const resetUrl = apiUrl ? `${apiUrl}/api/reset` : '/api/reset';
    fetch(resetUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${localStorage.getItem('inu_token')}`
      }
    }).catch(() => {});
  };

  // Camera helpers and UI (restored)
  const getCameraName = (cameraNum) => {
    const names = { M: '메인화면', A: 'A 랙', B: 'B 랙', C: 'C 랙' };
    return names[cameraNum] || `카메라 ${cameraNum}`;
  };

  const handleCameraSelect = (cameraNumber) => {
    setSelectedCamera(cameraNumber);
  };

  const renderCameraStream = () => {
    const mjpegStreamUrl = `${getBackendUrl()}/api/camera/${selectedCamera}/mjpeg_feed`;

    if (availableCameras.includes(selectedCamera)) {
      return (
        <div style={{ position: 'relative', width: '100%', height: '100%' }}>
          <img
            key={selectedCamera}
            src={mjpegStreamUrl}
            alt={`${getCameraName(selectedCamera)} 라이브 스트림`}
            className="camera-mjpeg-stream"
            style={{ width: '100%', height: '100%', objectFit: 'cover' }}
            onError={(e) => {
              e.target.style.display = 'none';
              if (e.target.nextSibling) e.target.nextSibling.style.display = 'flex';
            }}
          />
          <div
            className="camera-error-message"
            style={{
              display: 'none',
              position: 'absolute',
              top: 0,
              left: 0,
              right: 0,
              bottom: 0,
              backgroundColor: '#f5f5f5',
              color: '#666',
              justifyContent: 'center',
              alignItems: 'center',
              textAlign: 'center',
              padding: '20px'
            }}
          >
            {getCameraName(selectedCamera)} 은(는) 현재 사용할 수 없습니다.
          </div>
        </div>
      );
    }

    return (
      <div className="camera-stream-placeholder">
        {getCameraName(selectedCamera)} 은(는) 현재 사용할 수 없습니다.
      </div>
    );
  };

  const renderSmallCameraStream = (cameraId) => {
    if (!availableCameras.includes(cameraId)) {
      return <div className="small-camera-unavailable">사용불가</div>;
    }

    return (
      <div
        className="small-camera-preview"
        style={{
          position: 'relative',
          width: '100%',
          height: '100%',
          backgroundColor: '#f5f5f5',
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          color: '#666',
          fontSize: '0.9em'
        }}
      >
        <div>{getCameraName(cameraId)} 선택</div>
      </div>
    );
  };

  const renderMainCamera = () => (
    <div className="frame-wrapper">
      <div className="frame-16 camera-button camera-selected">
        <div className="text-wrapper-31">{getCameraName(selectedCamera)}</div>
      </div>
      <div className="camera-display">{renderCameraStream()}</div>
    </div>
  );

  const renderCameraButtons = () => {
    const allCameras = ['M', 'A', 'B', 'C'];
    return allCameras
      .filter((camId) => camId !== selectedCamera)
      .map((camId) => (
        <div
          key={camId}
          className="small-camera-wrapper"
          onClick={() => handleCameraSelect(camId)}
          style={{ cursor: 'pointer' }}
        >
          <div className="small-camera-button">
            <div className="small-camera-text">{getCameraName(camId)}</div>
          </div>
          <div className="small-camera-display">{renderSmallCameraStream(camId)}</div>
        </div>
      ));
  };

  const handleDownloadBatch = async (batchId) => {
    if (!batchId) return;
    const token = localStorage.getItem('inu_token');
    const apiBaseUrl = getBackendUrl();
    const downloadUrl = `${apiBaseUrl}/api/download-batch-task/${batchId}`;
    try {
      const response = await fetch(downloadUrl, {
        method: 'GET',
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (!response.ok) return;
      const blob = await response.blob();
      const suggestedFilename = response.headers.get('content-disposition')?.split('filename=')[1]?.replace(/"/g, '') || `batch_task_${batchId}.csv`;
      const link = document.createElement('a');
      link.href = window.URL.createObjectURL(blob);
      link.setAttribute('download', suggestedFilename);
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(link.href);
    } catch (e) {
      console.error('Download error:', e);
    }
  };

  // Periodic refresh for activity logs and camera history
  useEffect(() => {
    const fetchData = async () => {
      try {
        const rawLogs = await getActivityLogs({ limit: 50, order: 'desc' });
        const historyData = await getCameraHistory({ limit: 50 });

        // Minimal grouping preserved for logs section (unchanged UI below)
        const logsByDate = rawLogs.reduce((acc, log) => {
          const dateKey = new Date(log.timestamp).toLocaleDateString('ko-KR', { year: 'numeric', month: '2-digit', day: '2-digit' });
          if (!acc[dateKey]) acc[dateKey] = [];
          acc[dateKey].push(log);
          return acc;
        }, {});

        setGroupedActivityLogs(logsByDate);
        setCameraHistory(historyData);
      } catch (error) {
        console.error('Error fetching data:', error);
        if (handleApiError(error, navigate)) return;
      }
    };

    fetchData();
    const intervalId = setInterval(fetchData, 2000);
    return () => clearInterval(intervalId);
  }, [navigate]);

  useEffect(() => {
    const token = localStorage.getItem('inu_token');
    if (token) {
      try {
        const decoded = jwtDecode(token);
        setUserDisplayName(decoded.display_name || 'Unknown User');
      } catch (error) {
        setUserDisplayName('Unknown User');
      }
    }
  }, []);

  useEffect(() => {
    const fetchAvailableCameras = async () => {
      try {
        const apiUrl = getApiBaseUrl();
        const camerasUrl = apiUrl ? `${apiUrl}/api/cameras/available` : '/api/cameras/available';
        const response = await fetch(camerasUrl, { headers: { 'Authorization': `Bearer ${localStorage.getItem('inu_token')}` } });
        if (response.ok) {
          const data = await response.json();
          if (data.success && data.cameras.length > 0) setAvailableCameras(data.cameras);
        }
      } catch (_) {}
    };
    fetchAvailableCameras();
  }, []);

  // Find latest batchId for global download button
  const latestBatchId = cameraHistory.find(h => h.batch_id)?.batch_id;

  return (
    <div className="camera">
      <div className="div-5">
        <div className="container-2">
          <div className="text-wrapper-30">Camera</div>

          <div className="frame-15">
            {renderMainCamera()}
            {renderCameraButtons()}
          </div>

          <div className="frame-17">
            <div className="camera-history-list">
              <div className="batch-history-container">
                {cameraHistory.map(item => (
                  <div key={item.id} className="group-10">
                    <div className="overlap-6">
                      <div className="group-11">
                        <div className="overlap-group-6">
                          <div className="log-title">{item.rack}랙 {item.slot}칸 {item.movement_type === 'IN' ? '입고' : '출고'}</div>
                        </div>
                      </div>
                      <div className="log-times-container">
                        <div className="log-time-entry">
                          <span className="log-time-label">시작시간</span>
                          <span className="log-time-value">{formatHms(item.start_time)}</span>
                        </div>
                        <div className="log-time-entry">
                          <span className="log-time-label">종료시간</span>
                          <span className="log-time-value">{formatHms(item.end_time)}</span>
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
                <div className="log-download-button-container">
                  <button className="log-download-button" onClick={() => handleDownloadBatch(latestBatchId)} disabled={!latestBatchId}>
                    <img src="/img/download_icon.svg" alt="" className="download-icon" />
                    다운로드
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div className="text-6">{userDisplayName}</div>
        <img className="line-3" alt="Line" src="/img/line-1.svg" />
        <div className="logo-5">
          <img className="INU-logistics-5" alt="Inu logistics" src="/img/inu-logistics-4.png" />
          <div className="group-19">
            <div className="ellipse-19" />
            <div className="ellipse-20" />
            <div className="ellipse-21" />
          </div>
        </div>

        <div className="devider-2" />
        <img className="user-profile-2" alt="User profile" src="/img/user-profile.png" />
        <div className="left-menu-2">
          <Menu
            className="menu-2"
            icon={<Ic162Thone6 className="ic-3" />}
            menu="default"
            text1="대쉬보드"
            onClick={handleDashboard}
          />
          <Menu
            className="menu-2"
            icon={<Ic162Thone1 className="ic-3" color="#39424A" />}
            menu="default"
            text1="작업 현황"
            onClick={handleWorkStatus}
          />
          <Menu
            className="menu-2"
            icon={<Ic162Thone4 className="ic-3" color="#0177FB" />}
            menu="selected"
            text="운영캠 확인"
          />
          <Menu
            className="menu-2"
            icon={<Property1Variant5 className="ic-3" color="#39424A" />}
            menu="default"
            text1="초기화"
            onClick={handleReset}
          />
          <Menu
            className="menu-2"
            icon={<Property1LogOut className="ic-3" />}
            menu="default"
            text1="로그아웃"
            onClick={handleLogout}
          />
        </div>
      </div>
    </div>
  );
};

