import React from "react";
import { RouterProvider, createBrowserRouter } from "react-router-dom";
import { Camera } from "./screens/Camera";
import { DashboardOn } from "./screens/DashboardOn";
import { DivWrapper } from "./screens/DivWrapper";
import { Login } from "./screens/Login";
import { LoginScreen } from "./screens/LoginScreen";
import { WorkStatus } from "./screens/WorkStatus";
import io from 'socket.io-client';
import { start_global_worker } from './task_queue';

const router = createBrowserRouter([
  {
    path: "/*",
    element: <Login />,
  },
  {
    path: "/login1u40u4363u4449u4363u4469u4355u4469-u4363u4469u4536u4357u4455u4520u41",
    element: <Login />,
  },
  {
    path: "/dashboardu40onu41",
    element: <DashboardOn />,
  },
  {
    path: "/login2u40u4359u4469u4358u4469u4527u4359u4453u4523u4370u4457-u4363u4469u4536u4357u4455u4520u41",
    element: <LoginScreen />,
  },
  {
    path: "/login1u40u4363u4449u4363u4469u4355u4469-u4363u4469u4536u4357u4455u4520u41-u4363u4454u4357u4453",
    element: <DivWrapper />,
  },
  {
    path: "/camera-1",
    element: <Camera />,
  },
  {
    path: "/work-status",
    element: <WorkStatus />,
  },
]);

const socket = io();

export const App = () => {
  start_global_worker();
  return <RouterProvider router={router} />;
};
