import React from "react";
import { RouterProvider, createBrowserRouter, Outlet, Navigate } from "react-router-dom";
import { Camera } from "./screens/Camera";
import { DashboardOn } from "./screens/DashboardOn";
import { DivWrapper } from "./screens/DivWrapper";
import { Login } from "./screens/Login";
import { LoginScreen } from "./screens/LoginScreen";
import { WorkStatus } from "./screens/WorkStatus";
import SessionMonitor from "./components/SessionMonitor";

// Layout component that includes SessionMonitor
const Layout = () => {
  console.log('🌟🌟🌟 Layout component is rendering! 🌟🌟🌟');
  console.log('[Layout] Checking token status during layout render');
  const token = localStorage.getItem('inu_token');
  console.log(`[Layout] Token status: ${token ? 'EXISTS' : 'MISSING'}`);
  console.log(`[Layout] Current URL: ${window.location.pathname}`);
  
  return (
    <>
      <SessionMonitor />
      <Outlet />
    </>
  );
};

const router = createBrowserRouter([
  {
    path: "/",
    element: <Layout />,
    children: [
      {
        index: true,
        element: <Navigate to="/login" replace />,
      },
      {
        path: "/login",
        element: <Login />,
      },
      {
        path: "/dashboard",
        element: <DashboardOn />,
      },
      {
        path: "/login-password",
        element: <LoginScreen />,
      },
      {
        path: "/camera",
        element: <Camera />,
      },
      {
        path: "/work-status",
        element: <WorkStatus />,
      },
      {
        path: "*",
        element: <Navigate to="/login" replace />,
      },
    ]
  },
]);

export const App = () => {
  console.log('🌟🌟🌟 App component is rendering! 🌟🌟🌟');
  return <RouterProvider router={router} />;
};
