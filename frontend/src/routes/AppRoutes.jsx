import React from "react";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import LandingPage from "../pages/LandingPage";
import Login from "../pages/Login";
import Register from "../pages/Register";
import ForgotPassword from "../pages/ForgotPassword";
import ResetPassword from "../pages/ResetPassword";
import Home from "../pages/Home";
import CreateAgent from "../pages/CreateAgent";
import UpdateAgent from "../pages/UpdateAgent";
import AgentChat from "../pages/AgentChat";
import AdminDashboard from "../pages/AdminDashboard";
import EmbedPage from "../pages/EmbedPage";
import BillingPage from "../pages/BillingPage";
import ProtectedRoute from "./ProtectedRoute";

export default function AppRoutes() {
  return (
    <BrowserRouter>
      <Routes>
        {/* Public embed route - must be before other routes */}
        <Route path="/embed/:token" element={<EmbedPage />} />
        {/* Public landing page */}
        <Route path="/" element={<LandingPage />} />
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route path="/forgot-password" element={<ForgotPassword />} />
        <Route path="/reset-password" element={<ResetPassword />} />
        <Route path="/home" element={<ProtectedRoute><Home /></ProtectedRoute>} />
        <Route path="/create-agent" element={<ProtectedRoute><CreateAgent /></ProtectedRoute>} />
        <Route path="/create-demo" element={<ProtectedRoute><CreateAgent isDemo={true} /></ProtectedRoute>} />
        <Route path="/update-agent/:id" element={<ProtectedRoute><UpdateAgent /></ProtectedRoute>} />
        <Route path="/chat/:id" element={<ProtectedRoute><AgentChat /></ProtectedRoute>} />
        <Route path="/billing" element={<ProtectedRoute><BillingPage /></ProtectedRoute>} />
        <Route path="/admin" element={<ProtectedRoute><AdminDashboard /></ProtectedRoute>} />
      </Routes>
    </BrowserRouter>
  );
}
