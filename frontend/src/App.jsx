import { Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider, useAuth } from "./context/AuthContext";
import ProtectedRoute from "./components/ProtectedRoute";
import Layout from "./components/Layout";
import Login from "./pages/Login";
import Register from "./pages/Register";
import Dashboard from "./pages/Dashboard";
import Chat from "./pages/Chat";
import History from "./pages/History";
import Profile from "./pages/Profile";
import CourseRequest from "./pages/CourseRequest";
import AdminDashboard from "./pages/admin/AdminDashboard";
import AdminResources from "./pages/admin/AdminResources";
import AdminUsers from "./pages/admin/AdminUsers";
import AdminSettings from "./pages/admin/AdminSettings";
import AdminRequests from "./pages/admin/AdminRequests";

function AppRoutes() {
  const { user } = useAuth();

  return (
    <Routes>
      <Route path="/login" element={user ? <Navigate to={user.role === "admin" ? "/admin" : "/dashboard"} replace /> : <Login />} />
      <Route path="/register" element={user ? <Navigate to={user.role === "admin" ? "/admin" : "/dashboard"} replace /> : <Register />} />

      <Route
        element={
          <ProtectedRoute>
            <Layout />
          </ProtectedRoute>
        }
      >
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/chat" element={<Chat />} />
        <Route path="/history" element={<History />} />
        <Route path="/profile" element={<Profile />} />
        <Route path="/course-request" element={<CourseRequest />} />
      </Route>

      <Route
        element={
          <ProtectedRoute adminOnly>
            <Layout />
          </ProtectedRoute>
        }
      >
        <Route path="/admin" element={<AdminDashboard />} />
        <Route path="/admin/resources" element={<AdminResources />} />
        <Route path="/admin/users" element={<AdminUsers />} />
        <Route path="/admin/settings" element={<AdminSettings />} />
        <Route path="/admin/requests" element={<AdminRequests />} />
      </Route>

      <Route path="/" element={<Navigate to="/dashboard" replace />} />
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <AppRoutes />
    </AuthProvider>
  );
}