import React, { useState, useEffect } from "react";
import { Group } from "../../components/Group";
import { Menu } from "../../components/Menu";
import { Rectangle } from "../../components/Rectangle";
import { Ic162Thone1 } from "../../icons/Ic162Thone1";
import { Ic162Thone2 } from "../../icons/Ic162Thone2";
import { Ic162Thone4 } from "../../icons/Ic162Thone4";
import { Ic162Thone6 } from "../../icons/Ic162Thone6";
import { Property1LogOut } from "../../icons/Property1LogOut";
import "./style.css";
import { useNavigate } from "react-router-dom";
import { getActivityLogs, getApiBaseUrl } from "../../lib/api";

// Placeholder Stream URLs - REPLACE THESE WITH YOUR ACTUAL STREAM URLS
const CAMERA_STREAM_URLS = {
  1: "YOUR_CAMERA_1_STREAM_URL", // e.g., "http://example.com/stream1/playlist.m3u8"
  2: "YOUR_CAMERA_2_STREAM_URL",
  3: "YOUR_CAMERA_3_STREAM_URL",
  4: "YOUR_CAMERA_4_STREAM_URL",
};

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
  const [selectedCamera, setSelectedCamera] = useState(1); // Default to camera 1
  // const [activityLogs, setActivityLogs] = useState([]); // Raw logs, if needed for other purposes
  const [groupedActivityLogs, setGroupedActivityLogs] = useState({}); // State for grouped logs

  // Navigation handlers
  const handleDashboard = () => navigate('/dashboardu40onu41');
  const handleWorkStatus = () => navigate('/work-status');
  const handleLogout = () => navigate('/');

  // Camera selection handler with swap functionality
  const handleCameraSelect = (cameraNumber) => {
    setSelectedCamera(cameraNumber);
  };

  // Render the selected camera's live stream
  const renderCameraStream = () => {
    const streamUrl = CAMERA_STREAM_URLS[selectedCamera];

    if (!streamUrl || streamUrl.startsWith("YOUR_CAMERA_")) {
      return <div className="camera-stream-placeholder">카메라 {selectedCamera} 스트림 URL이 설정되지 않았습니다.</div>;
    }

    // Example using a generic video tag (suitable for some direct stream types or if ReactPlayer is too heavy)
    // For HLS/DASH, ReactPlayer or hls.js/dash.js integration is more robust.
    // If using ReactPlayer:
    // return (
    //   <ReactPlayer 
    //     url={streamUrl} 
    //     playing 
    //     controls={false} // Minimal controls, or true if you want them
    //     width="100%" 
    //     height="100%" 
    //     className="react-player-instance"
    //   />
    // );
    
    // Fallback to a simple placeholder if not using ReactPlayer or if URL is an MJPEG stream
    // If it IS an MJPEG stream, you might use an <img> tag:
    // if (streamUrl.includes('.mjpg') || streamUrl.includes('.cgi')) { // Basic check
    //   return <img src={streamUrl} alt={`카메라 ${selectedCamera} 스트림`} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />;
    // }

    // Default placeholder if no specific player logic is implemented yet for the URL type
    return (
      <div className="camera-stream-active">
        {/* This div will be styled to show the stream or a message */}
        {/* For a real stream, you'd embed a video player component here pointing to streamUrl */}
        <p>운영 캠{selectedCamera} 라이브 스트리밍 영역</p>
        <p style={{fontSize: '0.8em', wordBreak: 'break-all'}}>URL: {streamUrl}</p>
      </div>
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
    const cameras = [1, 2, 3, 4];
    return cameras
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
          <div className="small-camera-display"></div>
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

    const apiBaseUrl = getApiBaseUrl(); // Get your API base URL
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
                          <div className="group-11"> {/* Re-using .group-11 for job title bar style */}
                            <div className="overlap-group-6"> {/* Inner styling for job title bar */}
                              {/* <div className="rectangle-5" /> If background is on .group-11 */}
                              <div className="log-title"> {/* Title for the individual job */}
                                {logEntry.rack}랙 {logEntry.slot}칸 {logEntry.movement_type === 'IN' ? '입고' : '출고'}
                              </div>
                            </div>
                          </div>
                          {/* Times for THIS specific job */} 
                          <div className="log-times-container individual-job-times">
                            <div className="log-time-entry">
                              <span className="log-time-label">시작시간</span>
                              <span className="log-time-value">{formatLogTime(logEntry.timestamp)}</span>
                            </div>
                            <div className="log-time-entry">
                              <span className="log-time-label">종료시간</span>
                              <span className="log-time-value">{formatLogTime(logEntry.timestamp)}</span>
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

        <div className="text-6">User #1</div>

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

