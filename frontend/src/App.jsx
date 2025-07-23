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

// Protected Route component
const ProtectedRoute = ({ children }) => {
  const token = localStorage.getItem('inu_token');
  console.log('[ProtectedRoute] Checking authentication...');
  
  if (!token) {
    console.log('[ProtectedRoute] No token found, redirecting to login');
    return <Navigate to="/login" replace />;
  }

  console.log('[ProtectedRoute] Token found, rendering protected content');
  return children;
};

// Protected Layout that includes SessionMonitor
const ProtectedLayout = () => {
  return (
    <ProtectedRoute>
      <Layout />
    </ProtectedRoute>
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
        path: "/login-password",
        element: <LoginScreen />,
      }
    ]
  },
  {
    path: "/",
    element: <ProtectedLayout />,
    children: [
      {
        path: "dashboard",
        element: <DashboardOn />,
      },
      {
        path: "camera",
        element: <Camera />,
      },
      {
        path: "work-status",
        element: <WorkStatus />,
      }
    ]
  },
  {
    path: "*",
    element: <Navigate to="/login" replace />,
  }
]);

export const App = () => {
  console.log('🌟🌟🌟 App component is rendering! 🌟🌟🌟');
  return <RouterProvider router={router} />;
};
