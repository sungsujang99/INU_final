import React, { useState, useEffect, useCallback } from "react";
import { Ic } from "../../components/Ic";
import { Menu } from "../../components/Menu";
import { Ic162Thone1 } from "../../icons/Ic162Thone1";
import { Ic162Thone2 } from "../../icons/Ic162Thone2";
import { Ic162Thone4 } from "../../icons/Ic162Thone4";
import { Ic242Tone2 } from "../../icons/Ic242Tone2";
import { Ic242Tone6 } from "../../icons/Ic242Tone6";
import { Property1LogOut } from "../../icons/Property1LogOut";
import { Property1Variant5 } from "../../icons/Property1Variant5";
import "./style.css";
import { useNavigate } from "react-router-dom";
import { RackAProgress } from '../../components/RackProgress/RackAProgress';
import { RackBProgress } from '../../components/RackProgress/RackBProgress';
import { RackCProgress } from '../../components/RackProgress/RackCProgress';
import { TotalRackProgress } from '../../components/TotalRackProgress/TotalRackProgress';
import { getInventory, pingBackend, getWorkTasksByStatus, getPendingTaskCounts, logout, handleApiError, getSessionStatus } from "../../lib/api";
import { socket } from '../../socket';
import { jwtDecode } from "jwt-decode";
import { getApiBaseUrl } from "../../config";

export const DashboardOn = () => {
  const navigate = useNavigate();
  const [userDisplayName, setUserDisplayName] = useState('');
  
  const RACK_CAPACITY = 80;
  const TOTAL_CAPACITY = RACK_CAPACITY * 3;

  const [rackData, setRackData] = useState({
    rackA: { stock: 0, capacity: RACK_CAPACITY, percentage: 0 },
    rackB: { stock: 0, capacity: RACK_CAPACITY, percentage: 0 },
    rackC: { stock: 0, capacity: RACK_CAPACITY, percentage: 0 },
    total: { stock: 0, capacity: TOTAL_CAPACITY, percentage: 0 }
  });

  const [workStatus, setWorkStatus] = useState({
    waiting: { incoming: 0, outgoing: 0 },
    inProgress: { incoming: 0, outgoing: 0 },
    completed: { incoming: 0, outgoing: 0 } // Reverted to counts
  });

  const [deviceStatus, setDeviceStatus] = useState({
    isConnected: false // Default to false
  });

  const [sessionInfo, setSessionInfo] = useState({
    active: false,
    username: '',
    loginTime: ''
  });

  // Define fetchData at component level, wrapped in useCallback
  const fetchData = useCallback(async () => {
    try {
      const allInventory = await getInventory(); 
      console.log("Dashboard - Raw Inventory Data:", allInventory);
      
      let stockA = 0;
      let stockB = 0;
      let stockC = 0;
      allInventory.forEach(item => {
        if (item.rack === 'A') stockA++;
        else if (item.rack === 'B') stockB++;
        else if (item.rack === 'C') stockC++;
      });
      console.log(`Dashboard - Calculated Stocks - A: ${stockA}, B: ${stockB}, C: ${stockC}`);
      const totalStock = stockA + stockB + stockC;
      setRackData({
        rackA: { stock: stockA, capacity: RACK_CAPACITY, percentage: Math.round((stockA / RACK_CAPACITY) * 100) },
        rackB: { stock: stockB, capacity: RACK_CAPACITY, percentage: Math.round((stockB / RACK_CAPACITY) * 100) },
        rackC: { stock: stockC, capacity: RACK_CAPACITY, percentage: Math.round((stockC / RACK_CAPACITY) * 100) },
        total: { stock: totalStock, capacity: TOTAL_CAPACITY, percentage: Math.round((totalStock / TOTAL_CAPACITY) * 100) }
      });

      try {
        await pingBackend();
        setDeviceStatus({ isConnected: true });
      } catch (pingError) {
        console.error("Backend ping failed:", pingError);
        setDeviceStatus({ isConnected: false });
      }

      // Fetch session status
      try {
        const sessionData = await getSessionStatus();
        setSessionInfo({
          active: sessionData.active,
          username: sessionData.username || '',
          loginTime: sessionData.login_time || ''
        });
      } catch (sessionError) {
        console.error("Session status fetch failed:", sessionError);
        setSessionInfo({ active: false, username: '', loginTime: '' });
      }

      // Fetch pending task counts directly
      let pendingIncoming = 0;
      let pendingOutgoing = 0;
      try {
        const counts = await getPendingTaskCounts();
        console.log("Dashboard - fetchData - Fetched Pending Task Counts:", counts);
        pendingIncoming = counts.pending_in_count || 0;
        pendingOutgoing = counts.pending_out_count || 0;
      } catch (countsError) {
        console.error("Dashboard - Failed to fetch pending task counts:", countsError);
      }
      console.log(`Dashboard - fetchData - Pending counts - Incoming: ${pendingIncoming}, Outgoing: ${pendingOutgoing}`);
      
      let completedIncomingCount = 0;
      let completedOutgoingCount = 0;
      try {
        const allCompletedTasks = await getWorkTasksByStatus("done");
        allCompletedTasks.forEach(task => {
          if (task.movement === 'IN') {
            completedIncomingCount++;
          } else if (task.movement === 'OUT') {
            completedOutgoingCount++;
          }
            });
      } catch (completedError) {
        console.error("Dashboard - Failed to fetch completed tasks:", completedError);
      }

      // Calculate In-Progress task counts
      let inProgressIncomingCount = 0;
      let inProgressOutgoingCount = 0;
      try {
        const allInProgressTasks = await getWorkTasksByStatus("in_progress");
        allInProgressTasks.forEach(task => {
          if (task.movement === 'IN') {
            inProgressIncomingCount++;
          } else if (task.movement === 'OUT') {
            inProgressOutgoingCount++;
          }
        });
      } catch (inProgressError) {
        console.error("Dashboard - Failed to fetch in-progress tasks:", inProgressError);
      }

      setWorkStatus(prevStatus => ({
        ...prevStatus, 
        waiting: { incoming: pendingIncoming, outgoing: pendingOutgoing },
        inProgress: { incoming: inProgressIncomingCount, outgoing: inProgressOutgoingCount },
        completed: { incoming: completedIncomingCount, outgoing: completedOutgoingCount }
      }));
    } catch (error) {
      console.error("Dashboard - Failed to fetch dashboard data:", error);
    }
  }, []); // Empty dependency array for useCallback
            // (it uses state setters which are stable)

  useEffect(() => {
    // Initial data fetch and interval setup
    if (localStorage.getItem('dashboard_needs_refresh') === 'true') {
      console.log("Dashboard: Detected refresh flag, fetching data immediately.");
      fetchData();
      localStorage.removeItem('dashboard_needs_refresh');
    } else {
      fetchData();
    }

    const interval = setInterval(fetchData, 30000); 
    return () => clearInterval(interval);
  }, [fetchData]); // fetchData is now a stable dependency from useCallback

  useEffect(() => {
    // SocketIO listeners
    const handleTaskDone = (data) => {
      console.log('Dashboard: Received task_done (OLD LISTENER - TO BE REMOVED/REPLACED):', data);
      if (data.status === "done") {
      fetchData(); 
      }
    };

    const handleQueueSize = (data) => {
      console.log('Dashboard: Received queue_size (OLD LISTENER - TO BE REMOVED/REPLACED):', data);
      if (data.status === "done") {
        fetchData(); 
      }
    };

    const handleTaskStatusChanged = (data) => {
      console.log('Dashboard: Received task_status_changed:', data);
      // Any task status change could affect pending counts or other dashboard items
      fetchData(); 
    };

    // Keep old listeners for now if they serve other purposes, or remove if fully replaced
    socket.on('task_done', handleTaskDone); // Consider removing if task_status_changed covers it
    socket.on('queue_size', handleQueueSize); // Consider removing if task_status_changed covers it
    socket.on('task_status_changed', handleTaskStatusChanged); // New primary listener

    return () => {
      socket.off('task_done', handleTaskDone);
      socket.off('queue_size', handleQueueSize);
      socket.off('task_status_changed', handleTaskStatusChanged);
    };
  }, [fetchData]); // fetchData is now a stable dependency

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

  const handleWorkStatus = () => {
    navigate('/work-status');
  };

  const handleCamera = () => {
    navigate('/camera-1');
  };

  const handleLogout = () => {
    logout()
      .then(() => {
        localStorage.removeItem('inu_token');
        navigate('/'); // Navigate back to login screen
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

  return (
    <div className="dashboard-on">
      <div className="div-2">
        <div className="container">
          <div className="text-wrapper-5">Dash Board</div>

          <div className="overlap">
            <div className="overlap-group">
              <div className="rectangle-2" />

              <div className="rectangle-3" />

              <div className="overlap-wrapper">
                <div className="overlap-2">
                  <div className="overlap-3">
                    <div className="rectangle-4" />

                    <div className="text-wrapper-6">랙 A 현황 종합</div>

                    <div className="overlap-group-wrapper">
                      <div className="overlap-group-2">
                        <RackAProgress percentage={rackData.rackA.percentage} />
                        <img className="img" alt="Ellipse" src="/img/ellipse-5.svg" />
                      </div>
                    </div>

                    <div className="text-wrapper-7">{rackData.rackA.percentage}%</div>
                  </div>

                  <div className="frame-5">
                    <div className="text-wrapper-8">A</div>
                  </div>

                  <p className="p">
                    <span className="span">재고</span>
                    <span className="text-wrapper-9">&nbsp;</span>
                    <span className="text-wrapper-10">{rackData.rackA.stock}</span>
                    <span className="text-wrapper-9">/{rackData.rackA.capacity}({rackData.rackA.percentage}%)</span>
                  </p>
                </div>
              </div>

              <div className="group-2">
                <div className="overlap-2">
                  <div className="overlap-3">
                    <div className="rectangle-4" />

                    <div className="text-wrapper-6">랙 B 현황 종합</div>

                    <div className="overlap-group-wrapper">
                      <div className="overlap-group-2">
                        <RackBProgress percentage={rackData.rackB.percentage} />
                        <img className="img" alt="Ellipse" src="/img/ellipse-5.svg" />
                      </div>
                    </div>

                    <div className="text-wrapper-7">{rackData.rackB.percentage}%</div>
                  </div>

                  <div className="frame-5">
                    <div className="text-wrapper-8">B</div>
                  </div>

                  <p className="element-3">
                    <span className="span">재고</span>
                    <span className="text-wrapper-9">&nbsp;</span>
                    <span className="text-wrapper-10">{rackData.rackB.stock}</span>
                    <span className="text-wrapper-9">/{rackData.rackB.capacity}({rackData.rackB.percentage}%)</span>
                  </p>
                </div>
              </div>

              <div className="group-3">
                <div className="overlap-2">
                  <div className="overlap-3">
                    <div className="rectangle-4" />

                    <div className="text-wrapper-6">랙 C 현황 종합</div>

                    <div className="overlap-group-wrapper">
                      <div className="overlap-group-2">
                        <RackCProgress percentage={rackData.rackC.percentage} />
                        <img className="img" alt="Ellipse" src="/img/ellipse-5.svg" />
                      </div>
                    </div>

                    <div className="text-wrapper-11">{rackData.rackC.percentage}%</div>
                  </div>

                  <div className="frame-6">
                    <div className="text-wrapper-12">C</div>
                  </div>

                  <p className="element-4">
                    <span className="span">재고</span>
                    <span className="text-wrapper-9">&nbsp;</span>
                    <span className="text-wrapper-10">{rackData.rackC.stock}</span>
                    <span className="text-wrapper-9">/{rackData.rackC.capacity}({rackData.rackC.percentage}%)</span>
                  </p>
                </div>
              </div>

              <div className="title">
                <div className="text-wrapper-13">전체 랙 현황 종합</div>

                <p className="text-wrapper-14">* A,B,C 랙 통합 결과입니다.</p>
              </div>

              <div className="group-4">
                <div className="overlap-4">
                  <TotalRackProgress percentage={rackData.total.percentage} />
                  <img className="ellipse-6" alt="Ellipse" src="/img/ellipse-5-3.svg" />
                </div>
              </div>

              <div className="group-5">
                <div className="text-wrapper-15">{rackData.total.percentage}%</div>

                <p className="element-5">
                  <span className="span">재고: </span>
                  <span className="text-wrapper-16">{rackData.total.stock}</span>
                  <span className="span">/240</span>
                </p>
              </div>
            </div>

            <div className="frame-7">
              <div className="title-2">
                <div className="text-wrapper-13">장비 운영 상태</div>
              </div>

              <div className="frame-8">
                <p className="div-3">
                  <span className="text-wrapper-17">시리얼 연결</span>
                  <span className="text-wrapper-18">{deviceStatus.isConnected ? '성공' : '실패'}</span>
                </p>
                <div className="frame-9">
                  <div className="text-wrapper-19">{deviceStatus.isConnected ? 'ON' : 'OFF'}</div>
                </div>
              </div>
            </div>
          </div>

          <div className="frame-10">
            <div className="title-3">
              <div className="text-wrapper-20">대기 작업 현황</div>
            </div>

            <div className="frame-11">
              <div className="frame-12">
                <Ic property1="variant-4" />
                <div className="text-wrapper-21">입고</div>
                <div className="text-wrapper-22">{workStatus.waiting.incoming}건</div>
              </div>

              <div className="frame-12">
                <Ic property1="variant-3" />
                <div className="text-wrapper-21">출고</div>
                <div className="text-wrapper-22">{workStatus.waiting.outgoing}건</div>
              </div>
            </div>
          </div>

          <div className="frame-13">
            <div className="title-4">
              <div className="text-wrapper-20">진행중인 작업</div>
            </div>

            <div className="frame-11">
              <div className="frame-12">
                <Ic242Tone2 className="icon-instance-node" color="#39424A" />
                <div className="text-wrapper-21">입고</div>
                <div className="text-wrapper-22">{workStatus.inProgress.incoming}건</div>
              </div>

              <div className="frame-12">
                <Ic242Tone6 className="icon-instance-node" color="#39424A" />
                <div className="text-wrapper-21">출고</div>
                <div className="text-wrapper-22">{workStatus.inProgress.outgoing}건</div>
              </div>
            </div>
          </div>

          <div className="frame-14">
            <div className="title-5">
              <div className="text-wrapper-20">완료 작업</div>
            </div>
            <div className="frame-11">
              <div className="frame-12">
                <Ic242Tone2 className="icon-instance-node" color="#39424A" />
                <div className="text-wrapper-21">입고</div>
                <div className="text-wrapper-22">{workStatus.completed.incoming}건</div>
              </div>
              <div className="frame-12">
                <Ic242Tone6 className="icon-instance-node" color="#39424A" />
                <div className="text-wrapper-21">출고</div>
                <div className="text-wrapper-22">{workStatus.completed.outgoing}건</div>
              </div>
            </div>
          </div>
        </div>

        <img className="line" alt="Line" src="/img/line-1.svg" />

        <div className="line-2" />

        <img
          className="user-profile"
          alt="User profile"
          src="/img/user-profile.png"
        />

        <div className="left-menu">
          <Menu
            className="menu-instance"
            icon={<Ic162Thone2 className="ic-2" />}
            menu="selected"
            text="대쉬보드"
          />
          <Menu
            className="menu-instance"
            icon={<Ic162Thone1 className="ic-2" color="#39424A" />}
            menu="default"
            text1="작업현황"
            onClick={handleWorkStatus}
          />
          <Menu
            className="menu-instance"
            icon={<Ic162Thone4 className="ic-2" color="#39424A" />}
            menu="default"
            text1="운영캠 확인"
            onClick={handleCamera}
          />
          <Menu
            className="menu-instance"
            icon={<Property1Variant5 className="ic-2" color="#39424A" />}
            menu="default"
            text1="초기화"
            onClick={handleReset}
          />
          <Menu
            className="menu-instance"
            icon={<Property1LogOut className="ic-2" />}
            menu="default"
            text1="로그아웃"
            onClick={handleLogout}
          />
        </div>

        <div className="logo">
          <img
            className="INU-logistics"
            alt="Inu logistics"
            src="/img/inu-logistics.png"
          />

          <div className="group-6">
            <div className="ellipse-7" />

            <div className="ellipse-8" />

            <div className="ellipse-9" />
          </div>
        </div>
      </div>
    </div>
  );
};
