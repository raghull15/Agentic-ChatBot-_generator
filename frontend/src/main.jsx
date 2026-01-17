import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./index.css";
import { AuthProvider } from "./context/AuthContext";
import { AgentProvider } from "./context/AgentContext";
import { SocketProvider } from "./context/SocketContext";

// Provider hierarchy:
// AuthProvider → SocketProvider → AgentProvider → App
// SocketProvider needs token from AuthProvider
// AgentProvider will use socket for real-time updates (Phase 2)
ReactDOM.createRoot(document.getElementById("root")).render(
  <AuthProvider>
    <SocketProvider>
      <AgentProvider>
        <App />
      </AgentProvider>
    </SocketProvider>
  </AuthProvider>
);
