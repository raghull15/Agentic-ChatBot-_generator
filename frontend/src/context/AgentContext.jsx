import React, { createContext, useContext, useEffect, useState, useCallback } from "react";
import { fetchAgents as apiFetchAgents, createAgent as apiCreateAgent, createAgentFromSource as apiCreateAgentFromSource, deleteAgent as apiDeleteAgent } from "../api";
import { useAuth } from "./AuthContext";

const AgentContext = createContext();

export function AgentProvider({ children }) {
  const [agents, setAgents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const { token, user } = useAuth();

  const loadAgents = useCallback(async () => {
    // Don't load if not authenticated
    if (!token) {
      setAgents([]);
      setLoading(false);
      return;
    }

    try {
      setLoading(true);
      setError(null);
      const agentList = await apiFetchAgents();
      setAgents(agentList);
    } catch (err) {
      setError(err.message);
      console.error("Failed to load agents:", err);
      // Clear agents on auth error
      if (err.message.includes('login')) {
        setAgents([]);
      }
    } finally {
      setLoading(false);
    }
  }, [token]);

  // Reload agents when token/user changes
  useEffect(() => {
    if (token && user) {
      loadAgents();
    } else {
      // Clear agents when logged out
      setAgents([]);
      setLoading(false);
    }
  }, [token, user, loadAgents]);

  const addAgent = async (agentName, domain, description, files) => {
    try {
      setError(null);
      const result = await apiCreateAgent(agentName, domain, description, files);
      await loadAgents(); // Refresh the list
      return result;
    } catch (err) {
      setError(err.message);
      throw err;
    }
  };

  const addAgentFromSource = async (agentName, domain, description, sourceType, sourceConfig) => {
    try {
      setError(null);
      const result = await apiCreateAgentFromSource(agentName, domain, description, sourceType, sourceConfig);
      await loadAgents(); // Refresh the list
      return result;
    } catch (err) {
      setError(err.message);
      throw err;
    }
  };

  const removeAgent = async (agentName) => {
    try {
      setError(null);
      await apiDeleteAgent(agentName);
      await loadAgents(); // Refresh the list
    } catch (err) {
      setError(err.message);
      throw err;
    }
  };

  const refreshAgents = () => {
    if (token) {
      loadAgents();
    }
  };

  // Clear agents (called on logout)
  const clearAgents = () => {
    setAgents([]);
    setError(null);
  };

  return (
    <AgentContext.Provider value={{
      agents,
      loading,
      error,
      addAgent,
      addAgentFromSource,
      removeAgent,
      refreshAgents,
      clearAgents
    }}>
      {children}
    </AgentContext.Provider>
  );
}

export const useAgent = () => useContext(AgentContext);
