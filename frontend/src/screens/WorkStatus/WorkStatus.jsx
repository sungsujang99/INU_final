import React, { useState, useEffect, useRef } from "react";
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
import { getInventory, getTaskQueues, uploadTasksBatch, getActivityLogs, getWorkTasksByStatus } from "../../lib/api";
import io from 'socket.io-client';

export const WorkStatus = () => {
  const navigate = useNavigate();
  const [selectedRack, setSelectedRack] = useState('A'); // Default to Rack A
  const [workProgress, setWorkProgress] = useState(0); // Add state for work progress percentage
  const [inventoryData, setInventoryData] = useState({}); // Add state for inventory data
  const [waitingTasks, setWaitingTasks] = useState({}); // Tasks per rack: e.g. { A: [], B: [], C: [] }
  const [completedJobsForSelectedRack, setCompletedJobsForSelectedRack] = useState([]); // New state for completed jobs
  const [pendingTasks, setPendingTasks] = useState([]);
  const [inProgressTasks, setInProgressTasks] = useState([]);
  const [doneTasks, setDoneTasks] = useState([]);

  // Create a ref for the hidden file input
  const fileInputRef = useRef(null);

  // Navigation handlers
  const handleDashboard = () => navigate('/dashboardu40onu41');
  const handleCamera = () => navigate('/camera-1');
  const handleLogout = () => navigate('/'); // Navigate to login page
  const handleRackSelection = (rack) => setSelectedRack(rack);

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
            return;
          }

          console.log('Parsed Tasks from CSV:', tasks);
          try {
            const result = await uploadTasksBatch(tasks); // Call the API function
            console.log('Upload tasks API response:', result); // Log the full response

            // Check for errors based on the backend's JSON structure for 207 Multi-Status
            // The backend returns a JSON with an "errors" array and "processed_tasks"
            if (result && result.errors && result.errors.length > 0) {
              // Display the specific errors from the 'errors' array
              alert('Some tasks failed:\n' + result.errors.join('\n'));
            } else if (result && result.processed_tasks && result.processed_tasks.some(task => task.status === 'error')) {
               // If no top-level 'errors' array, check individual tasks in 'processed_tasks'
               const errorMessages = result.processed_tasks
                   .filter(task => task.status === 'error')
                   .map(task => task.message || `Error processing task for product: ${task.task?.product_code || 'unknown'}`); // Access nested task data safely
               alert(`Processing complete with some errors:\n${errorMessages.join('\n')}\n\nOverall: ${result.message}`);
            } else if (result && result.message) {
              // If no explicit errors found, display the overall message from the backend
              // This will cover the "Successfully processed X tasks" case too.
              alert(result.message);
            } else {
              // Fallback if the response structure is unexpected but was 'ok'
              alert('Tasks submitted. Check status for details.');
            }

            // Common actions after try block (success or partial success)
            localStorage.setItem('dashboard_needs_refresh', 'true');
            fetchInventoryData();
            fetchCompletedJobs();

          } catch (error) {
            // This catch block handles errors thrown by uploadTasksBatch
            // (e.g., network errors, or if !response.ok and it throws like for 400/500)
            console.error('Error in uploadTasksBatch call:', error);
            alert('Failed to upload tasks: ' + error.message);
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

    // Reset the input value to allow selecting the same file again
    event.target.value = null;
  };

  // Placeholder handler for the Inbox In button
  const handleInboxIn = () => {
    console.log('Inbox In clicked for Rack:', selectedRack);
    // Add logic for this button
  };

  // Add useEffect to fetch work progress data
  useEffect(() => {
    // Simulated data fetch - replace with actual API call
    const fetchWorkProgress = async () => {
      try {
        // In a real app, this would be an API call
        // const response = await fetch('/api/work-progress');
        // const data = await response.json();
        // setWorkProgress(data.percentage);
        
        // For now, we'll use 0% as the default
        setWorkProgress(0);
      } catch (error) {
        console.error('Failed to fetch work progress:', error);
      }
    };

    fetchWorkProgress();
  }, [selectedRack]); // Refetch when rack selection changes

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

  // Fetch all on mount and when rack changes
  useEffect(() => {
    fetchInventoryData();
    fetchPendingTasks();
    fetchInProgressTasks();
    fetchDoneTasks();
    // ...fetch inventory if needed...
  }, [selectedRack]);

  // Listen for real-time updates
  useEffect(() => {
    const socket = io();
    socket.on("task_status_changed", (data) => {
      // Refetch all data that could have changed
      fetchInventoryData();
      fetchPendingTasks();
      fetchInProgressTasks();
      fetchDoneTasks();
    });
    // Clean up the socket listener when the component unmounts
    return () => {
      socket.off("task_status_changed");
      socket.disconnect(); // Optional: explicitly disconnect the socket
    };
  }, []); // <-- REMOVED selectedRack from dependency array

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
  const renderProgressBar = () => (
    <div className="frame-33">
      <div className="group-21">
        <div className="text-wrapper-54">전체 작업률</div>
        <div className="text-wrapper-55">{workProgress}%</div>
      </div>

      <div className="rectangle-wrapper">
        <div 
          className="rectangle-7" 
          style={{ 
            width: `${workProgress}%`,
            transition: 'width 0.5s ease-in-out'
          }}
        />
      </div>
    </div>
  );

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
            // --- VERTICAL POSITIONING ---
            // **ACTION NEEDED:** Inspect the "Work Status" title (text-wrapper-49)
            // in your browser's dev tools. Find its exact 'top' position relative to
            // 'container-3' and its height or line-height.
            // Adjust this 'top' value until the icons align vertically with the title.
            // Example: If title starts 20px down, set top close to 20px.
            top: '25px', // <--- FINE-TUNE THIS VALUE based on inspection

            // --- HORIZONTAL POSITIONING ---
            // **ACTION NEEDED:** Inspect the position/width of the Rack C button
            // (frame-22). Adjust 'right' until the icons are horizontally centered above it.
            right: '60px', // <--- FINE-TUNE THIS VALUE based on inspection

            display: 'flex',
            gap: '6px', // Adjusted gap for new size
            zIndex: 1, // Ensure icons are on top
            alignItems: 'center' // Vertically align icons with each other
          }}>
            {/* Hidden File Input */}
            <input
              type="file"
              ref={fileInputRef}
              onChange={handleFileChange}
              style={{ display: 'none' }} // Keep it hidden
              accept=".csv" // Only accept .csv files
            />

            {/* Add Document Button - Now triggers the hidden input */}
            <button
              onClick={handleAddDocumentClick} // Use the new click handler
              style={{ background: 'none', border: 'none', padding: '0', cursor: 'pointer', lineHeight: 0 }}
              title="Import CSV" // Updated tooltip
            >
              <img src={addDocumentUrl} alt="Import CSV" style={{ width: '34px', height: '34px', display: 'block' }} />
            </button>

            {/* Inbox In Button */}
            <button
              onClick={handleInboxIn}
              style={{ background: 'none', border: 'none', padding: '0', cursor: 'pointer', lineHeight: 0 }}
              title="Inbox In"
            >
              <img src={inboxInUrl} alt="Inbox In" style={{ width: '34px', height: '34px', display: 'block' }} />
            </button>
          </div>

          {/* Rest of the content */}
          <div className="frame-18">
            {renderRackSelectionButtons()} {/* Render buttons without icons */}
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

        <div className="text-7">User #1</div>
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
