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
import { getActivityLogs, logout, handleApiError } from "../../lib/api";
import { jwtDecode } from "jwt-decode";
import { getBackendUrl, getApiBaseUrl } from "../../config.js";

// Helper to format time, you might want to make this more robust or use a library
const formatLogTime = (timestamp) => {
  if (!timestamp) return "00:00:00";
  // Ensure toLocaleTimeString gets options for HH:MM:SS if that's desired
  return new Date(timestamp).toLocaleTimeString('ko-KR', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false
  });
};

export const Camera = () => {
  const navigate = useNavigate();
  const [selectedCamera, setSelectedCamera] = useState(0); // Default to camera 0 (0-indexed)
  const [availableCameras, setAvailableCameras] = useState([0]); // Default to camera 0
  const [groupedActivityLogs, setGroupedActivityLogs] = useState({}); // State for grouped logs
  const [userDisplayName, setUserDisplayName] = useState('');

  // Navigation handlers
  const handleDashboard = () => navigate('/dashboardu40onu41');
  const handleWorkStatus = () => navigate('/work-status');
  const handleLogout = () => {
    logout()
      .then(() => {
        localStorage.removeItem('inu_token');
        navigate('/');
      })
      .catch(error => {
        console.error('Logout error:', error);
        // Even if logout fails, clear local storage and redirect
        localStorage.removeItem('inu_token');
        navigate('/');
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

  // Camera selection handler with swap functionality
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
          alt={`카메라 ${selectedCamera} 라이브 스트림`} 
          className="camera-mjpeg-stream" // Add a class for styling if needed
          style={{ width: '100%', height: '100%', objectFit: 'cover' }} 
          // Basic error visual cue (you might want a more robust error handling)
          onError={(e) => {
            e.target.alt = `카메라 ${selectedCamera} 스트림을 불러올 수 없습니다.`; 
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
          카메라 {selectedCamera} 은(는) 현재 사용할 수 없습니다.
        </div>
      );
    }
  };

  // Render small camera preview for non-selected cameras
  const renderSmallCameraStream = (cameraNum) => {
    if (!availableCameras.includes(cameraNum)) {
      return (
        <div className="small-camera-unavailable">
          사용불가
        </div>
      );
    }

    const mjpegStreamUrl = `${getBackendUrl()}/api/camera/${cameraNum}/live_feed`;
    return (
      <img 
        src={mjpegStreamUrl} 
        alt={`카메라 ${cameraNum} 미리보기`} 
        className="small-camera-stream"
        style={{ width: '100%', height: '100%', objectFit: 'cover' }} 
        onError={(e) => {
          e.target.style.display = 'none';
        }}
      />
    );
  };

  // Render the main camera display
  const renderMainCamera = () => (
    <div className="frame-wrapper">
      <div 
        className="frame-16 camera-button camera-selected"
      >
        <div className="text-wrapper-31">운영 캠{selectedCamera}</div>
      </div>
      <div className="camera-display">
        {renderCameraStream()}
      </div>
    </div>
  );

  // Render the camera buttons (excluding the selected one)
  const renderCameraButtons = () => {
    const allCameras = [0, 1, 2, 3]; // 4 cameras (0-indexed)
    return allCameras
      .filter(camNum => camNum !== selectedCamera)
      .map(camNum => (
        <div 
          key={camNum}
          className="small-camera-wrapper"
          onClick={() => handleCameraSelect(camNum)}
        >
          <div className="small-camera-button">
            <div className="small-camera-text">운영 캠{camNum}</div>
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
        // setActivityLogs(rawLogs); // Store raw logs if you still need them separately

        const grouped = rawLogs.reduce((acc, log) => {
          const key = log.batch_id || `ungrouped-${log.id}`;
          if (!acc[key]) {
            acc[key] = {
              batch_id: log.batch_id,
              timestamps: [], // Store all timestamps to find overall batch start/end
              logs: [],
              // For ungrouped items, or as a fallback batch title
              representativeTitleInfo: { 
                rack: log.rack,
                slot: log.slot,
                movement_type: log.movement_type
              }
            };
          }
          acc[key].logs.push(log); // Add full log object to the logs array for this batch
          acc[key].timestamps.push(log.timestamp); // Collect all timestamps
          return acc;
        }, {});

        Object.values(grouped).forEach(batch => {
          if (batch.timestamps.length > 0) {
            batch.timestamps.sort((a,b) => new Date(a) - new Date(b)); // Sort timestamps chronologically
            batch.batchStartTime = batch.timestamps[0];
            batch.batchEndTime = batch.timestamps[batch.timestamps.length - 1];
          } else {
            batch.batchStartTime = null;
            batch.batchEndTime = null;
          }
          
          // Generate a title for the batch card itself (optional, could be empty)
          if (batch.batch_id) {
             // Example: if all logs in batch are for the same rack & movement
            const firstLog = batch.logs[0];
            const allSameRackAndMovement = batch.logs.every(l => l.rack === firstLog.rack && l.movement_type === firstLog.movement_type);
            if (allSameRackAndMovement) {
              batch.batchCardTitle = `${firstLog.rack}랙 일괄 ${firstLog.movement_type === 'IN' ? '입고' : '출고'} 작업`;
            } else {
              batch.batchCardTitle = `일괄 작업 ID: ${batch.batch_id.substring(0,8)}...`;
            }
          } else {
            // For ungrouped (single) items, this title might not be displayed if the item itself has a title bar
            batch.batchCardTitle = "개별 작업"; 
          }
        });

        setGroupedActivityLogs(grouped);
      } catch (error) {
        console.error("Failed to fetch or group activity logs:", error);
        setGroupedActivityLogs({});
      }
    };
    fetchAndGroupLogs();
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
            // Set the first available camera as selected
            setSelectedCamera(data.cameras[0]);
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
            {Object.keys(groupedActivityLogs).length === 0 ? (
              <p>표시할 로그가 없습니다.</p>
            ) : (
              Object.values(groupedActivityLogs).map((batch, index) => (
                <div className="group-10" key={batch.batch_id || `batch-outer-${index}`}> 
                  <div className="overlap-6"> 
                    {/* Optional: A title for the whole batch card, if different from the items within */}
                    {/* <h4 className="batch-main-title">{batch.batchCardTitle}</h4> */}

                    <div className="batch-internal-jobs-list"> 
                      {batch.logs.map((logEntry) => (
                        <div className="individual-job-item" key={logEntry.id}>
                          {/* Title bar for THIS specific job */}
                          <div className="group-11">
                            <div className="overlap-group-6">
                              <div className="log-title">
                                {logEntry.rack}랙 {logEntry.slot}칸 {logEntry.movement_type === 'IN' ? '입고' : '출고'}
                              </div>
                            </div>
                          </div>
                          {/* Times for THIS specific job */} 
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
                    
                    {/* Download button for the ENTIRE batch */} 
                    <div className="log-download-button-container">
                      <button 
                        className="log-download-button" 
                        onClick={() => handleDownloadBatch(batch.batch_id)} 
                        disabled={!batch.batch_id} // Disable if no batch_id (for ungrouped items)
                      >
                        <img src="/img/download_icon.svg" alt="" className="download-icon" />
                        다운로드
                      </button>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        <div className="text-6">{userDisplayName}</div>

        <img className="devider" alt="Devider" src="/img/line-1.svg" />

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

        <img
          className="user-profile-2"
          alt="User profile"
          src="/img/user-profile.png"
        />

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

