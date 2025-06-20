import React, { useState, useEffect, useRef, useCallback } from "react";
import { Frame } from "../../components/Frame";
import { Menu } from "../../components/Menu";
import { Ic162Thone1 } from "../../icons/Ic162Thone1";
import { Ic162Thone4 } from "../../icons/Ic162Thone4";
import { Ic162Thone10 } from "../../icons/Ic162Thone10";
import { Ic242Tone2 } from "../../icons/Ic242Tone2";
import { Ic242Tone6 } from "../../icons/Ic242Tone6";
import { Property1LogOut } from "../../icons/Property1LogOut";
import { Property1Variant5 } from "../../icons/Property1Variant5";
import "./style.css";
import { useNavigate } from "react-router-dom";
import addDocumentUrl from '../../icons/add-document.svg'; // Default import gives URL
import inboxInUrl from '../../icons/inbox-in.svg';       // Default import gives URL
import { getInventory, getTaskQueues, uploadTasksBatch, getActivityLogs, getWorkTasksByStatus, logout, handleApiError } from "../../lib/api";
import { socket } from '../../socket';
import { jwtDecode } from "jwt-decode";
import { getApiBaseUrl } from "../../config";

export const WorkStatus = () => {
  const navigate = useNavigate();
  const [selectedRack, setSelectedRack] = useState('A'); // Default to Rack A
  const [inventoryData, setInventoryData] = useState({}); // Add state for inventory data
  const [pendingTasks, setPendingTasks] = useState([]);
  const [inProgressTasks, setInProgressTasks] = useState([]);
  const [doneTasks, setDoneTasks] = useState([]);
  const [userDisplayName, setUserDisplayName] = useState('');
  const [optionalModuleStatus, setOptionalModuleStatus] = useState({
    connected: false,
    healthy: false,
    status: 'offline'
  });

  const [activeBatch, setActiveBatch] = useState({
    id: null,
    totalTasks: 0,
    completedTasks: 0
  });

  // Create a ref for the hidden file input
  const fileInputRef = useRef(null);

  // Navigation handlers
  const handleDashboard = () => navigate('/dashboardu40onu41');
  const handleCamera = () => navigate('/camera-1');
  const handleLogout = () => {
    logout()
      .then(() => {
        localStorage.removeItem('inu_token');
        navigate('/'); // Navigate to login page
      })
      .catch(error => {
        console.error('Logout error:', error);
        // Even if logout fails, clear local storage and redirect
        localStorage.removeItem('inu_token');
        navigate('/');
      });
  };
  const handleRackSelection = (rack) => setSelectedRack(rack);

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

  // Optional module activation handler
  const handleOptionalModuleActivate = () => {
    const apiUrl = getApiBaseUrl();
    const activateUrl = apiUrl ? `${apiUrl}/api/optional-module/activate` : '/api/optional-module/activate';
    
    fetch(activateUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${localStorage.getItem('inu_token')}`
      }
    })
    .then(response => response.json())
    .then(data => {
      console.log('Optional module activation result:', data);
      if (data.success) {
        alert('모듈이 활성화되었습니다.');
      } else {
        alert(`모듈 활성화 실패: ${data.error || data.message}`);
      }
    })
    .catch(error => {
      console.error('Error activating optional module:', error);
      alert('모듈 활성화 중 오류가 발생했습니다.');
    });
  };

  // --- File Input Logic ---

  // Trigger the hidden file input when the Add Document button is clicked
  const handleAddDocumentClick = () => {
    fileInputRef.current.click(); // Programmatically click the hidden input
  };

  // Handle the file selection once the user chooses a file
  const handleFileChange = async (event) => {
    const file = event.target.files[0];
    if (file) {
      console.log('Selected file:', file.name);
      const reader = new FileReader();
      reader.onload = async (e) => {
        try {
          // Decode directly using UTF-8
          let csvContent;
          try {
            // Ensure e.target.result is an ArrayBuffer as read by reader.readAsArrayBuffer(file)
            if (!(e.target.result instanceof ArrayBuffer)) {
              console.error("FileReader did not produce an ArrayBuffer. Check reader.readAsArrayBuffer().");
              alert("File reading error: Expected ArrayBuffer.");
              return;
            }
            csvContent = new TextDecoder('utf-8').decode(e.target.result);
          } catch (decodeError) {
            console.error('Failed to decode as UTF-8:', decodeError);
            alert('Failed to decode the file as UTF-8. Please ensure the file is UTF-8 encoded.');
            return; 
          }

          let lines = csvContent.split(/\r\n|\n/).filter(line => line.trim() !== '');
          if (lines.length === 0) {
            alert("CSV file is empty.");
            return;
          }

          // Skip the header row explicitly
          if (lines.length > 0) {
            lines.shift(); // Removes the first element (header row)
          }

          if (lines.length === 0) {
            alert("CSV file contains only a header or is empty after removing header.");
            return;
          }

          // Assuming fixed column order
          const expectedColumnCount = 7;
          const tasks = lines.map((line, lineIndex) => {
            const values = line.split(',').map(v => v.trim());
            if (values.length !== expectedColumnCount) {
              console.warn(`Skipping line ${lineIndex + 1}: Expected ${expectedColumnCount} columns, but found ${values.length}. Line: "${line}"`);
              return null; // Skip malformed lines
            }
            
            // Fixed order mapping
            return {
              product_code: values[0],
              product_name: values[1],
              rack: values[2],
              slot: parseInt(values[3], 10) || 0,       // from 'inventory' column
              movement: values[4],    // from 'in_or_out' column
              quantity: parseInt(values[5], 10) || 0,
              cargo_owner: values[6] // from 'product_owner' column
            };
          }).filter(task => task !== null); // Remove any skipped lines

          if (tasks.length === 0) {
            alert("No valid tasks found in the CSV file. Please check the format.");
            event.target.value = null; // Reset file input
            return;
          }

          console.log('Parsed Tasks from CSV:', tasks);
          try {
            const result = await uploadTasksBatch(tasks);
            console.log('[handleFileChange] Upload tasks API response:', result);

            if (result && result.message) {
              alert(result.message);
            }

            // Initialize new batch progress tracking
            if (result && result.batch_id && typeof result.processed_count === 'number') {
              console.log("[handleFileChange] Initializing new batch:", {
                id: result.batch_id,
                totalTasks: result.processed_count
              });
              
              const newBatch = {
                id: result.batch_id,
                totalTasks: result.processed_count,
                completedTasks: 0
              };
              setActiveBatch(newBatch);

              // Initial progress check
              if (result.processed_count > 0) {
                await fetchAndSetBatchProgress(result.batch_id, result.processed_count);
              }
            } else {
              // Reset progress tracking if batch creation failed
              setActiveBatch({ id: null, totalTasks: 0, completedTasks: 0 });
            }

            // Refresh UI
            localStorage.setItem('dashboard_needs_refresh', 'true');
            await Promise.all([
              fetchInventoryData(),
              fetchPendingTasks(),
              fetchInProgressTasks(),
              fetchDoneTasks()
            ]);

          } catch (error) {
            console.error('Error in uploadTasksBatch:', error);
            alert('Failed to upload tasks: ' + (error.message || "Unknown error"));
            setActiveBatch({ id: null, totalTasks: 0, completedTasks: 0 });
          }
        } catch (error) {
          console.error('Error processing CSV or uploading tasks:', error);
          alert('Failed to process CSV or upload tasks. See console for details.');
        }
      };
      reader.onerror = (error) => {
        console.error('Error reading file:', error);
        alert('Failed to read the file.');
      };
      reader.readAsArrayBuffer(file); // Read as ArrayBuffer for TextDecoder
    }

    // Reset file input
    if (event.target) {
    event.target.value = null;
    }
  };

  // Placeholder handler for the Inbox In button
  const handleInboxIn = () => {
    console.log('Inbox In clicked for Rack:', selectedRack);
    // Add logic for this button
  };

  // Fetch optional module status
  const fetchOptionalModuleStatus = async () => {
    try {
      const apiUrl = getApiBaseUrl();
      const statusUrl = apiUrl ? `${apiUrl}/api/optional-module/status` : '/api/optional-module/status';
      
      const response = await fetch(statusUrl, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('inu_token')}`
        }
      });
      
      if (response.ok) {
        const data = await response.json();
        if (data.success) {
          setOptionalModuleStatus({
            connected: data.connected,
            healthy: data.healthy,
            status: data.status
          });
        }
      }
    } catch (error) {
      console.error('Error fetching optional module status:', error);
    }
  };

  // Split fetch functions
  const fetchInventoryData = async () => {
    try {
      const invData = await getInventory(selectedRack);
      const slotMap = {};
      invData.forEach(item => {
        slotMap[item.slot] = item;
      });
      setInventoryData(slotMap);
    } catch (error) {
      setInventoryData({});
    }
  };

  const fetchCompletedJobs = async () => {
    try {
      const allLogs = await getActivityLogs({ limit: 100, order: 'desc' });
      const rackLogs = allLogs
        .filter(log => log.rack === selectedRack)
        .sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp))
        .slice(0, 5);
      const simplifiedJobs = rackLogs.map(log => ({ 
        id: log.id,
        rack: log.rack,
        slot: log.slot,
        movement_type: log.movement_type,
      }));
      setCompletedJobsForSelectedRack(simplifiedJobs);
    } catch (error) {
      setCompletedJobsForSelectedRack([]);
    }
  };

  const fetchWaitingTasks = async () => {
    try {
      const queueData = await getTaskQueues();
      setWaitingTasks(queueData);
    } catch (error) {
      setWaitingTasks({});
    }
  };

  // Fetch tasks by status
  const fetchPendingTasks = async () => {
    const tasks = await getWorkTasksByStatus("pending");
    setPendingTasks(tasks.filter(t => t.rack === selectedRack));
  };
  const fetchInProgressTasks = async () => {
    const tasks = await getWorkTasksByStatus("in_progress");
    setInProgressTasks(tasks.filter(t => t.rack === selectedRack));
  };
  const fetchDoneTasks = async () => {
    const tasks = await getWorkTasksByStatus("done");
    setDoneTasks(tasks.filter(t => t.rack === selectedRack));
  };

  // Initial data fetch
  useEffect(() => {
    fetchInventoryData();
    fetchCompletedJobs();
    fetchWaitingTasks(); // This will fetch both pending and in-progress tasks
    fetchOptionalModuleStatus(); // Fetch initial optional module status
    // For now, progress starts when a new CSV is uploaded.
  }, [selectedRack]);

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

  // Socket listener for optional module status updates
  useEffect(() => {
    const handleOptionalModuleStatus = (data) => {
      console.log('[SocketIO] Optional module status update:', data);
      setOptionalModuleStatus({
        connected: data.connected,
        healthy: data.healthy,
        status: data.status
      });
    };

    socket.on('optional_module_status', handleOptionalModuleStatus);
    return () => socket.off('optional_module_status', handleOptionalModuleStatus);
  }, []);

  // Add fetchAndSetBatchProgress as a memoized callback
  const fetchAndSetBatchProgress = useCallback(async (batchId, totalTasksInBatch) => {
    if (!batchId || totalTasksInBatch <= 0) {
      console.log("[fetchAndSetBatchProgress] Invalid batch info:", { batchId, totalTasksInBatch });
      return;
    }

    try {
      // Get all done tasks for this batch
      const doneTasks = await getWorkTasksByStatus('done');
      const completedTasksForBatch = doneTasks.filter(task => task.batch_id === batchId);
      const newCompletedCount = completedTasksForBatch.length;

      console.log("[fetchAndSetBatchProgress] Progress update:", {
        batchId,
        totalTasksInBatch,
        newCompletedCount,
        completedTasksFound: completedTasksForBatch.length
      });

      setActiveBatch(prevBatch => {
        // Only update if this is still the active batch
        if (prevBatch.id === batchId) {
          const updatedBatch = {
            id: batchId,
            totalTasks: totalTasksInBatch,
            completedTasks: newCompletedCount
          };
          console.log("[fetchAndSetBatchProgress] Updating batch progress:", updatedBatch);
          return updatedBatch;
        }
        return prevBatch;
      });
    } catch (error) {
      console.error('[fetchAndSetBatchProgress] Error:', error);
    }
  }, []);

  // Update the socket effect to handle task status changes
  useEffect(() => {
    const handleTaskStatusChanged = async (data) => {
      console.log('[SocketIO] Task status changed:', data);
      
      // Refresh task lists
      await Promise.all([
        fetchPendingTasks(),
        fetchInProgressTasks(),
        fetchDoneTasks(),
        fetchInventoryData()
      ]);

      // Update batch progress if this task belongs to the active batch
      if (data.status === 'done' && data.batch_id && activeBatch.id === data.batch_id) {
        console.log('[SocketIO] Updating batch progress for completed task');
        await fetchAndSetBatchProgress(activeBatch.id, activeBatch.totalTasks);
      }
    };

    socket.on('task_status_changed', handleTaskStatusChanged);
    return () => socket.off('task_status_changed', handleTaskStatusChanged);
  }, [activeBatch.id, activeBatch.totalTasks, fetchAndSetBatchProgress, fetchPendingTasks, fetchInProgressTasks, fetchDoneTasks, fetchInventoryData]);

  // Update renderRackGrid to show product info
  const renderRackGrid = () => {
    const frames = [];
    for (let i = 1; i <= 80; i++) {
      let frameClassName = "frame-instance"; // Default class
      // Simplified class name logic for brevity in this example, assuming you have this defined
      if ([10, 13, 14, 15, 16, 18, 19, 20, 22, 23, 24, 25, 26, 28, 29, 30, 32, 33, 34, 35, 36, 37, 38, 39, 40, 42, 43, 44, 45, 46, 47, 48, 49, 50, 52, 53, 54, 55, 56, 57, 58, 59, 60, 62, 63, 64, 65, 66, 67, 68, 69, 70, 72, 73, 74, 75, 76, 77, 78, 79].includes(i)) {
        frameClassName = "frame-29";
      } else if ([7].includes(i)) {
        frameClassName = "frame-25";
      } else if ([11, 12, 17, 21, 27, 31, 41, 51, 61, 71].includes(i)) {
        frameClassName = "frame-26";
      } else if ([4].includes(i)) {
        frameClassName = "frame-117-instance";
      }
      
      const slotData = inventoryData[i];

      // Debugging logs
      if (selectedRack === 'A' && i === 10) { // ITEM-A1 was put in A, 10
        console.log(`WorkStatus - Rack A, Slot 10 - slotData:`, slotData);
        console.log(`WorkStatus - Rack A, Slot 10 - Props for Frame:`, { property1: slotData ? "variant-3" : "default", text: slotData ? undefined : i.toString(), productName: slotData?.product_name, cargoOwner: slotData?.cargo_owner });
      }
      if (selectedRack === 'B' && i === 5) { // ITEM-B1 was put in B, 5
        console.log(`WorkStatus - Rack B, Slot 5 - slotData:`, slotData);
        console.log(`WorkStatus - Rack B, Slot 5 - Props for Frame:`, { property1: slotData ? "variant-3" : "default", text: slotData ? undefined : i.toString(), productName: slotData?.product_name, cargoOwner: slotData?.cargo_owner });
      }
      if (selectedRack === 'C' && i === 30) { // ITEM-C1 was put in C, 30
        console.log(`WorkStatus - Rack C, Slot 30 - slotData:`, slotData);
        console.log(`WorkStatus - Rack C, Slot 30 - Props for Frame:`, { property1: slotData ? "variant-3" : "default", text: slotData ? undefined : i.toString(), productName: slotData?.product_name, cargoOwner: slotData?.cargo_owner });
      }
      
      frames.push(
        <Frame
          key={i}
          className="frame-117"
          frameClassName={frameClassName}
          property1={slotData ? "variant-3" : "default"}
          text={slotData ? undefined : i.toString()}
          productName={slotData?.product_name}
          cargoOwner={slotData?.cargo_owner}
        />
      );
    }
    return frames;
  };

  // Render current work status section (Completed Jobs)
  const renderCurrentWorkStatus = () => {
    // Helper to determine display properties based on task
    const getTaskDisplayProps = (task) => {
      let iconComponent;
      let itemClassName = "task-bar"; 
      let movementText = task.movement;
      let movementClassName = "";

      if (task.movement && task.movement.toUpperCase() === 'IN') {
        iconComponent = <Ic242Tone6 className="ic-4 task-bar-icon" color="#0177FB" />; // Use Ic242Tone6 (OUT icon shape) but colored Blue for IN
        itemClassName = "task-bar task-item-in";
        movementText = "입고"; // Korean for IN
        movementClassName = "task-bar-movement-in";
      } else if (task.movement && task.movement.toUpperCase() === 'OUT') {
        iconComponent = <Ic242Tone6 className="ic-4 task-bar-icon" color="#00BB80" />; // Green Ic242Tone6 (OUT icon shape) for OUT
        itemClassName = "task-bar task-item-out";
        movementText = "출고"; // Korean for OUT
        movementClassName = "task-bar-movement-out";
      } else { 
        iconComponent = <Ic242Tone2 className="ic-4 task-bar-icon" color="#FF0000" />; 
        itemClassName = "task-bar task-item-error";
        movementText = "오류"; 
        movementClassName = "task-bar-movement-error";
      }
      return { iconComponent, itemClassName, movementText, movementClassName };
    };

    return (
    <div className="frame-34"> 
      <div className="text-wrapper-56">{selectedRack}랙 작업 현황</div>
      <div className="frame-35"> 
          {doneTasks.length === 0 && (
          <p className="no-current-tasks">완료된 작업이 없습니다.</p>
        )}
          {doneTasks.map((task) => {
            const { iconComponent, itemClassName, movementText, movementClassName } = getTaskDisplayProps(task);
            return (
              <div key={task.id} className={itemClassName}> 
                {iconComponent}
              <p className="task-bar-text">
                  랙 {task.rack}{task.slot !== undefined && task.slot !== null ? task.slot : ''} <span className={movementClassName}>{movementText}</span>
                </p>
              </div>
            );
          })}
        </div>
      </div>
    );
  };

  // Updated renderWaitingWorkStatus section
  const renderWaitingWorkStatus = () => (
    <div className="frame-39"> 
      <div className="text-wrapper-56">{selectedRack}랙 작업 대기</div>
      <div className="frame-40"> 
        {(pendingTasks.length === 0 && inProgressTasks.length === 0) ? (
          <p className="no-waiting-tasks">대기 중인 작업이 없습니다.</p>
        ) : (
          <>
            {inProgressTasks.map((task) => {
              const movementText = task.movement === 'IN' ? '입고 (진행중)' : '출고 (진행중)';
              const iconColor = task.movement === 'IN' ? '#0177FB' : '#00BB80';
              const textColorClass = task.movement === 'IN' ? 'task-bar-movement-in' : 'task-bar-movement-out';
              // Use task-item-in or task-item-out for background consistency
              const backgroundClass = task.movement === 'IN' ? 'task-item-in' : 'task-item-out';

              return (
                <div key={`inprogress-${task.id}`} className={`waiting-task-item ${backgroundClass}`}>
                  <Ic242Tone6 className="ic-4" color={iconColor} />
                  <p className={`task-bar-text ${textColorClass}`}>
                    랙 {task.rack}{task.slot !== undefined && task.slot !== null ? task.slot : ''} {movementText}
                  </p>
                </div>
              );
            })}
            {pendingTasks.map((task) => {
              const movementText = task.movement === 'IN' ? '입고 (대기)' : '출고 (대기)';
              return (
                <div key={`pending-${task.id}`} className="waiting-task-item pending-task-item">
                  <Ic242Tone2 className="ic-4" color="#8C8C8C" /> {/* Grey icon for pending */}
                  <p className="task-bar-text">
                  랙 {task.rack}{task.slot !== undefined && task.slot !== null ? task.slot : ''} {movementText}
                  </p>
                </div>
              );
            })}
          </>
        )}
      </div>
    </div>
  );

  // Render left menu
  const renderLeftMenu = () => (
    <div className="left-menu-3">
      <Menu
        className="menu-3"
        icon={<Ic162Thone10 className="ic-5" />}
        menu="default"
        text1="대쉬보드"
        onClick={handleDashboard}
      />
      <Menu
        className="menu-3"
        icon={<Ic162Thone1 className="ic-5" color="#0177FB" />}
        menu="selected"
        text="작업 현황"
      />
      <Menu
        className="menu-3"
        icon={<Ic162Thone4 className="ic-5" color="#39424A" />}
        menu="default"
        text1="운영캠 확인"
        onClick={handleCamera}
      />
      <Menu
        className="menu-3"
        icon={<Property1Variant5 className="ic-5" color="#39424A" />}
        menu="default"
        text1="초기화"
        onClick={handleReset}
      />
      <Menu
        className="menu-3"
        icon={<Property1LogOut className="ic-5" />}
        menu="default"
        text1="로그아웃"
        onClick={handleLogout}
      />
    </div>
  );

  // Render rack selection buttons (NO icons here anymore)
  const renderRackSelectionButtons = () => (
    <div className="frame-19">
      <button
        className={`frame-20 rack-button ${selectedRack === 'A' ? 'selected' : ''}`}
        onClick={() => handleRackSelection('A')}
      >
        <div className="text-wrapper-51">랙 A</div>
      </button>

      <button
        className={`frame-21 rack-button ${selectedRack === 'B' ? 'selected' : ''}`}
        onClick={() => handleRackSelection('B')}
      >
        <div className="text-wrapper-51">랙 B</div>
      </button>

      {/* Rack C Button - renders normally */}
      <button
        className={`frame-22 rack-button ${selectedRack === 'C' ? 'selected' : ''}`}
        onClick={() => handleRackSelection('C')}
      >
        <div className="text-wrapper-51">랙 C</div>
      </button>
    </div>
  );

  // Update the progress bar render
  const renderProgressBar = () => {
    const currentBatchProgressPercentage = activeBatch.totalTasks > 0
      ? Math.round((activeBatch.completedTasks / activeBatch.totalTasks) * 100)
      : 0;

    console.log("Rendering progress bar:", {
      activeBatch,
      percentage: currentBatchProgressPercentage
    });

    return (
    <div className="frame-33">
      <div className="group-21">
        <div className="text-wrapper-54">전체 작업률</div>
          <div className="text-wrapper-55">{currentBatchProgressPercentage}%</div>
      </div>
      <div className="rectangle-wrapper">
        <div 
          className="rectangle-7" 
          style={{ 
              width: `${currentBatchProgressPercentage}%`,
            transition: 'width 0.5s ease-in-out'
          }}
        />
      </div>
    </div>
  );
  };

  return (
    <div className="work-status">
      <div className="div-7">
        {/* Ensure this container has relative positioning */}
        <div className="container-3" style={{ position: 'relative' }}>
          {/* Work Status Title */}
          <div className="text-wrapper-49">Work Status</div>

          {/* Icons positioned absolutely relative to container-3 */}
          <div style={{
            position: 'absolute',
            top: '25px',
            right: '60px',
            display: 'flex',
            gap: '6px',
            zIndex: 1,
            alignItems: 'center'
          }}>
            {/* Hidden File Input */}
            <input
              type="file"
              ref={fileInputRef}
              onChange={handleFileChange}
              style={{ display: 'none' }}
              accept=".csv"
            />

            {/* Add Document Button */}
            <button
              onClick={handleAddDocumentClick}
              style={{ background: 'none', border: 'none', padding: '0', cursor: 'pointer', lineHeight: 0 }}
              title="Import CSV"
            >
              <img src={addDocumentUrl} alt="Import CSV" style={{ width: '34px', height: '34px', display: 'block' }} />
            </button>

            {/* Optional Module Button */}
            <button
              onClick={handleOptionalModuleActivate}
              style={{ 
                background: 'none', 
                border: 'none', 
                padding: '0', 
                cursor: optionalModuleStatus.connected ? 'pointer' : 'not-allowed', 
                lineHeight: 0,
                filter: optionalModuleStatus.connected 
                  ? (optionalModuleStatus.healthy ? 'none' : 'hue-rotate(0deg) saturate(2) brightness(0.8)') 
                  : 'grayscale(100%) brightness(0.6)'
              }}
              title={`Optional Module: ${optionalModuleStatus.status}`}
              disabled={!optionalModuleStatus.connected}
            >
              <img 
                src={inboxInUrl} 
                alt="Optional Module" 
                style={{ 
                  width: '34px', 
                  height: '34px', 
                  display: 'block',
                  opacity: optionalModuleStatus.connected ? 1 : 0.5
                }} 
              />
            </button>
          </div>

          {/* Main Content */}
          <div className="frame-18">
            {renderRackSelectionButtons()}
             <div className="group-20">
              <div className="frame-23">
                {renderRackGrid()}
              </div>
            </div>
            {renderProgressBar()}
          </div>

          {renderCurrentWorkStatus()}
          {renderWaitingWorkStatus()}
        </div>

        <div className="text-7">{userDisplayName}</div>
        <img className="line-3" alt="Line" src="/img/line-1.svg" />
        <div className="logo-6">
          <img
            className="INU-logistics-6"
            alt="Inu logistics"
            src="/img/inu-logistics-5.png"
          />
          <div className="group-22">
            <div className="ellipse-22" />
            <div className="ellipse-23" />
            <div className="ellipse-24" />
          </div>
        </div>

        <div className="line-4" />
        <img className="user-profile-3" alt="User profile" src="/img/user-profile.png" />
        {renderLeftMenu()}
      </div>
    </div>
  );
};
