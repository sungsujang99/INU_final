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

// Helper to format time, you might want to make this more robust or use a library
const formatLogTime = (timestamp) => {
  if (!timestamp) return "00:00:00.000";
  
  const date = new Date(timestamp);
  
  // Format with milliseconds for precise timing
  return date.toLocaleTimeString('ko-KR', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false
  }) + '.' + date.getMilliseconds().toString().padStart(3, '0');
};

// Get camera display name
const getCameraName = (cameraNum) => {
  const names = {
    0: "메인화면",
    1: "A", 
    2: "B",
    3: "C"
  };
  return names[cameraNum] || `카메라 ${cameraNum}`;
};

export const Camera = () => {
  console.log('📷📷📷 Camera component is starting to load! 📷📷📷');
  console.log('[Camera] Component mount - checking initial token status');
  const initialToken = localStorage.getItem('inu_token');
  console.log(`[Camera] Initial token status: ${initialToken ? 'EXISTS' : 'MISSING'}`);
  console.log(`[Camera] Current URL: ${window.location.pathname}`);
  
  const navigate = useNavigate();
  const [selectedCamera, setSelectedCamera] = useState(0); // Start with camera 0 selected
  const [availableCameras, setAvailableCameras] = useState([0, 1, 2, 3]); // All 4 cameras available
  const [groupedActivityLogs, setGroupedActivityLogs] = useState({}); // State for grouped logs
  const [cameraHistory, setCameraHistory] = useState([]); // State for camera batch history
  const [userDisplayName, setUserDisplayName] = useState('');

  // Navigation handlers
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
        // Even if logout fails, clear local storage and redirect
        localStorage.removeItem('inu_token');
        navigate('/login');
      });
  };

  const handleReset = () => {
    // Send reset signal to backend using dynamic URL
    const apiUrl = getApiBaseUrl();
    const resetUrl = apiUrl ? `${apiUrl}/api/reset` : '/api/reset';
    
    fetch(resetUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${localStorage.getItem('inu_token')}`
      }
    })
    .then(response => response.json())
    .then(data => {
      console.log('Reset signal sent:', data);
      if (data.success) {
        alert('초기화 신호가 전송되었습니다.');
      } else {
        alert(`초기화 실패: ${data.message || data.error}`);
      }
    })
    .catch(error => {
      console.error('Error sending reset signal:', error);
      alert('초기화 신호 전송에 실패했습니다.');
    });
  };

  // Camera selection handler - only start streaming when selected
  const handleCameraSelect = (cameraNumber) => {
    setSelectedCamera(cameraNumber);
  };

  // Render the selected camera's live stream
  const renderCameraStream = () => {
    // Use dynamic backend URL instead of hardcoded one
    const mjpegStreamUrl = `${getBackendUrl()}/api/camera/${selectedCamera}/live_feed`;

    if (availableCameras.includes(selectedCamera)) {
      return (
        <img 
          src={mjpegStreamUrl} 
          alt={`${getCameraName(selectedCamera)} 라이브 스트림`} 
          className="camera-mjpeg-stream" // Add a class for styling if needed
          style={{ width: '100%', height: '100%', objectFit: 'cover' }} 
          // Basic error visual cue (you might want a more robust error handling)
          onError={(e) => {
            e.target.alt = `${getCameraName(selectedCamera)} 스트림을 불러올 수 없습니다.`; 
            // Optionally, replace with a placeholder image or hide:
            // e.target.src = "/img/camera_error_placeholder.png"; 
            // e.target.style.display = 'none'; 
          }}
        />
      );
    } else {
      // For unavailable cameras, show a placeholder or message
      return (
        <div className="camera-stream-placeholder">
          {getCameraName(selectedCamera)} 은(는) 현재 사용할 수 없습니다.
        </div>
      );
    }
  };

  // Render small camera preview - no streaming for unselected cameras
  const renderSmallCameraStream = (cameraNum) => {
    if (!availableCameras.includes(cameraNum)) {
      return (
        <div className="small-camera-unavailable">
          사용불가
        </div>
      );
    }

    // No streaming for unselected cameras - just show empty placeholder
    return (
      <div className="small-camera-placeholder">
      </div>
    );
  };

  // Render the main camera display
  const renderMainCamera = () => (
    <div className="frame-wrapper">
      <div 
        className="frame-16 camera-button camera-selected"
      >
        <div className="text-wrapper-31">{getCameraName(selectedCamera)}</div>
      </div>
      <div className="camera-display">
        {renderCameraStream()}
      </div>
    </div>
  );

  // Render the camera buttons - show all cameras as selectable
  const renderCameraButtons = () => {
    const allCameras = [0, 1, 2, 3]; // 4 cameras (0-indexed)
    return allCameras
      .filter(camNum => camNum !== selectedCamera) // Don't show the currently selected camera
      .map(camNum => (
        <div 
          key={camNum}
          className="small-camera-wrapper"
          onClick={() => handleCameraSelect(camNum)}
        >
          <div className="small-camera-button">
            <div className="small-camera-text">{getCameraName(camNum)}</div>
          </div>
          <div className="small-camera-display">
            {renderSmallCameraStream(camNum)}
          </div>
        </div>
      ));
  };

  const handleDownloadBatch = async (batchId) => {
    if (!batchId) {
      console.error("Batch ID is required for download.");
      return;
    }

    const token = localStorage.getItem('inu_token'); // Corrected token key
    if (!token) {
      console.error("Authentication token not found.");
      // Handle not authenticated, e.g., redirect to login or show message
      return;
    }

    // Use dynamic backend URL instead of hardcoded one
    const apiBaseUrl = getBackendUrl();
    const downloadUrl = `${apiBaseUrl}/api/download-batch-task/${batchId}`;

    try {
      const response = await fetch(downloadUrl, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      if (!response.ok) {
        // Try to get error message from backend if available
        const errorData = await response.json().catch(() => null);
        throw new Error(errorData?.message || `Failed to download batch task: ${response.statusText}`);
      }

      const blob = await response.blob();
      const suggestedFilename = response.headers.get('content-disposition')?.split('filename=')[1]?.replace(/"/g, '') || `batch_task_${batchId}.csv`;
      
      const link = document.createElement('a');
      link.href = window.URL.createObjectURL(blob);
      link.setAttribute('download', suggestedFilename);
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(link.href); // Clean up

    } catch (error) {
      console.error("Download error:", error);
      // Show user-friendly error message, e.g., using a toast notification
      alert(`Download failed: ${error.message}`);
    }
  };

  useEffect(() => {
    const fetchAndGroupLogs = async () => {
      try {
        const rawLogs = await getActivityLogs({ limit: 50, order: 'desc' });

        // First group by date
        const logsByDate = rawLogs.reduce((acc, log) => {
          const date = new Date(log.timestamp);
          const dateKey = date.toLocaleDateString('ko-KR', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit'
          });
          
          if (!acc[dateKey]) {
            acc[dateKey] = [];
          }
          acc[dateKey].push(log);
          return acc;
        }, {});

        // Then group each date's logs by batch
        const groupedByDateAndBatch = Object.entries(logsByDate).reduce((acc, [date, logs]) => {
          // Group logs by batch_id
          const batchGroups = logs.reduce((batchAcc, log) => {
            const key = log.batch_id || `ungrouped-${log.id}`;
            if (!batchAcc[key]) {
              batchAcc[key] = {
                batch_id: log.batch_id,
                timestamps: [],
                logs: [],
                representativeTitleInfo: {
                  rack: log.rack,
                  slot: log.slot,
                  movement_type: log.movement_type
                }
              };
            }
            batchAcc[key].logs.push(log);
            batchAcc[key].timestamps.push(log.timestamp);
            return batchAcc;
          }, {});

          // Convert batch groups object to array and process each batch
          const batchesArray = Object.values(batchGroups).map(batch => {
            batch.timestamps.sort((a,b) => new Date(a) - new Date(b));
            batch.batchStartTime = batch.timestamps[0];
            batch.batchEndTime = batch.timestamps[batch.timestamps.length - 1];
            
            if (batch.batch_id) {
              const firstLog = batch.logs[0];
              const allSameRackAndMovement = batch.logs.every(l => 
                l.rack === firstLog.rack && l.movement_type === firstLog.movement_type
              );
              if (allSameRackAndMovement) {
                batch.batchCardTitle = `${firstLog.rack}랙 일괄 ${firstLog.movement_type === 'IN' ? '입고' : '출고'} 작업`;
              } else {
                batch.batchCardTitle = `일괄 작업 ID: ${batch.batch_id.substring(0,8)}...`;
              }
            } else {
              batch.batchCardTitle = "개별 작업";
            }
            return batch;
          });

          acc[date] = batchesArray;
          return acc;
        }, {});

        setGroupedActivityLogs(groupedByDateAndBatch);
      } catch (error) {
        console.error("Failed to fetch or group activity logs:", error);
        setGroupedActivityLogs({});
      }
    };
    fetchAndGroupLogs();

    const fetchHistory = async () => {
      try {
        const historyData = await getCameraHistory({ limit: 50 });
        setCameraHistory(historyData);
      } catch (error) {
        console.error("Failed to fetch camera history:", error);
      }
    };
    fetchHistory();
  }, []);

  useEffect(() => {
    const token = localStorage.getItem('inu_token');
    if (token) {
      try {
        const decoded = jwtDecode(token);
        setUserDisplayName(decoded.display_name || 'Unknown User');
      } catch (error) {
        console.error('Error decoding token:', error);
        setUserDisplayName('Unknown User');
      }
    }
  }, []);

  // Fetch available cameras on component mount
  useEffect(() => {
    const fetchAvailableCameras = async () => {
      try {
        const apiUrl = getApiBaseUrl();
        const camerasUrl = apiUrl ? `${apiUrl}/api/cameras/available` : '/api/cameras/available';
        
        const response = await fetch(camerasUrl, {
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('inu_token')}`
          }
        });
        
        if (response.ok) {
          const data = await response.json();
          if (data.success && data.cameras.length > 0) {
            setAvailableCameras(data.cameras);
            // Don't automatically select any camera - let user choose
          }
        } else {
          console.warn('Failed to fetch available cameras, using defaults');
        }
      } catch (error) {
        console.error('Error fetching available cameras:', error);
        // Keep default camera setup
      }
    };
    
    fetchAvailableCameras();
  }, []);

  return (
    <div className="camera">
      <div className="div-5">
        <div className="container-2">
          <div className="text-wrapper-30">Camera</div>

          <div className="frame-15">
            {/* Main camera display */}
            {renderMainCamera()}

            {/* Other camera buttons */}
            {renderCameraButtons()}
          </div>

          <div className="frame-17">
            {/* Display Camera Batch History */}
            <div className="camera-history-list">
              <h4>최근 작업 배치 (카메라)</h4>
              {cameraHistory.length > 0 && (
                <ul>
                  {cameraHistory.map(item => (
                    <li key={item.id}>
                      Batch: {item.batch_id ? item.batch_id.substring(0, 8) : 'N/A'}... | 
                      Status: {item.status} | 
                      Time: {formatLogTime(item.start_time)} - {formatLogTime(item.end_time)}
                    </li>
                  ))}
                </ul>
              )}
            </div>

            {Object.keys(groupedActivityLogs).length > 0 && (
              Object.entries(groupedActivityLogs).map(([date, batches], dateIndex) => (
                <React.Fragment key={date}>
                  {/* Date divider */}
                  {dateIndex > 0 && <div className="date-divider" />}
                  <div className="date-header">{date}</div>
                  
                  {/* Batches for this date */}
                  {Array.isArray(batches) && batches.map((batch, batchIndex) => (
                    <div className="group-10" key={batch.batch_id || `batch-outer-${batchIndex}`}> 
                      <div className="overlap-6"> 
                        <div className="batch-internal-jobs-list"> 
                          {batch.logs.map((logEntry) => (
                            <div className="individual-job-item" key={logEntry.id}>
                              <div className="group-11">
                                <div className="overlap-group-6">
                                  <div className="log-title">
                                    {logEntry.rack}랙 {logEntry.slot}칸 {logEntry.movement_type === 'IN' ? '입고' : '출고'}
                                  </div>
                                </div>
                              </div>
                              <div className="log-times-container individual-job-times">
                                <div className="log-time-entry">
                                  <span className="log-time-label">시작시간</span>
                                  <span className="log-time-value">{formatLogTime(logEntry.start_time)}</span>
                                </div>
                                <div className="log-time-entry">
                                  <span className="log-time-label">종료시간</span>
                                  <span className="log-time-value">{formatLogTime(logEntry.end_time)}</span>
                                </div>
                              </div>
                            </div>
                          ))}
                        </div>
                        
                        <div className="log-download-button-container">
                          <button 
                            className="log-download-button" 
                            onClick={() => handleDownloadBatch(batch.batch_id)} 
                            disabled={!batch.batch_id}
                          >
                            <img src="/img/download_icon.svg" alt="" className="download-icon" />
                            다운로드
                          </button>
                        </div>
                      </div>
                    </div>
                  ))}
                </React.Fragment>
              ))
            )}
          </div>
        </div>

        <div className="text-6">{userDisplayName}</div>
        <img className="line-3" alt="Line" src="/img/line-1.svg" />
        <div className="logo-5">
          <img
            className="INU-logistics-5"
            alt="Inu logistics"
            src="/img/inu-logistics-4.png"
          />
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

