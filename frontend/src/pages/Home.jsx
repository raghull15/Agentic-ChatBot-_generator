import React, { useEffect, useState, useMemo } from "react";
import Navbar from "../components/Navbar";
import { useAgent } from "../context/AgentContext";
import { useAuth } from "../context/AuthContext";
import AgentCard from "../components/AgentCard";
import { AgentCardSkeleton } from "../components/Skeleton";
import { checkHealth, getUserStats, getBalance } from "../api";
import { Gift, X, TrendingUp, Zap, Bot, AlertTriangle } from "lucide-react";

export default function Home() {
  const { agents, loading, error, refreshAgents } = useAgent();
  const { user } = useAuth();
  const [backendStatus, setBackendStatus] = useState(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [sortBy, setSortBy] = useState("name"); // 'name', 'date', 'documents'
  const [userStats, setUserStats] = useState(null);
  const [showWelcomeCredits, setShowWelcomeCredits] = useState(false);

  useEffect(() => {
    const checkServers = async () => {
      const healthy = await checkHealth();
      setBackendStatus(healthy);
    };
    checkServers();

    // Fetch user stats and balance
    const fetchStats = async () => {
      try {
        const [stats, wallet] = await Promise.all([
          getUserStats().catch(() => ({})),
          getBalance().catch(() => null)
        ]);

        setUserStats({
          ...stats,
          credits_remaining: wallet?.credits_remaining || 0
        });

        // Show welcome credits if user is new and has credits
        if (wallet?.credits_remaining > 0 && agents.length === 0) {
          setShowWelcomeCredits(true);
        }
      } catch (err) {
        console.error('Failed to fetch user stats:', err);
      }
    };
    fetchStats();
  }, [agents.length]);

  // Filter and sort agents
  const filteredAgents = useMemo(() => {
    let result = [...agents];

    // Filter by search query
    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase();
      result = result.filter(agent =>
        agent.name?.toLowerCase().includes(query) ||
        agent.domain?.toLowerCase().includes(query) ||
        agent.description?.toLowerCase().includes(query) ||
        agent.source_type?.toLowerCase().includes(query)
      );
    }

    // Sort
    result.sort((a, b) => {
      switch (sortBy) {
        case 'date':
          return new Date(b.created_at || 0) - new Date(a.created_at || 0);
        case 'documents':
          return (b.num_documents || 0) - (a.num_documents || 0);
        case 'name':
        default:
          return (a.name || '').localeCompare(b.name || '');
      }
    });

    return result;
  }, [agents, searchQuery, sortBy]);

  return (
    <div className="min-h-screen bg-[var(--bg-primary)]">
      <Navbar />

      <div className="max-w-7xl mx-auto px-4 py-6 sm:px-6 sm:py-8 md:py-12">
        {/* Welcome Section */}
        <div className="mb-8 sm:mb-12 animate-fadeIn">
          <h1 className="text-3xl sm:text-4xl font-bold text-[var(--text-primary)] mb-2">
            Welcome, {user?.name?.split(' ')[0] || 'there'}
          </h1>
          <p className="text-[var(--text-muted)]">
            Manage your AI agents and monitor usage
          </p>
        </div>

        {/* Status Banner - Backend Offline */}
        {backendStatus === false && (
          <div className="mb-6 sm:mb-8 p-4 bg-[var(--bg-secondary)] border-2 border-[var(--danger)] rounded-xl flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3 animate-fadeIn">
            <div className="flex items-start gap-3">
              <AlertTriangle className="w-5 h-5 text-[var(--danger)] flex-shrink-0 mt-0.5" />
              <div>
                <p className="font-semibold text-[var(--text-primary)] mb-1">
                  Backend offline
                </p>
                <p className="text-sm text-[var(--text-muted)]">
                  Start the Flask server to continue
                </p>
              </div>
            </div>
            <button
              onClick={() => checkHealth().then(setBackendStatus)}
              className="btn btn-secondary btn-sm"
            >
              Retry
            </button>
          </div>
        )}

        {/* Low Credits Banner - Warning (Amber) */}
        {userStats?.credits_remaining < 50 && userStats?.credits_remaining > 0 && (
          <div className="mb-6 sm:mb-8 p-4 bg-gradient-to-r from-[var(--warning)]/10 to-[var(--warning)]/5 border-2 border-[var(--warning)] rounded-xl flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3 animate-fadeIn">
            <div className="flex items-start gap-3">
              <AlertTriangle className="w-5 h-5 text-[var(--warning)] flex-shrink-0 mt-0.5" />
              <div>
                <p className="font-semibold text-[var(--text-primary)] mb-1">
                  Running low on credits
                </p>
                <p className="text-sm text-[var(--text-muted)]">
                  You have {Math.floor(userStats?.credits_remaining || 0)} credits remaining.
                </p>
              </div>
            </div>
            <button
              onClick={() => window.location.href = '/billing'}
              className="btn btn-success btn-sm"
            >
              Add Credits
            </button>
          </div>
        )}

        {/* Welcome Credits Alert */}
        {showWelcomeCredits && (
          <div className="mb-6 sm:mb-8 p-4 bg-gradient-to-r from-[var(--secondary)]/10 to-[var(--secondary)]/5 border-2 border-[var(--secondary)] rounded-xl flex justify-between items-center animate-fadeIn">
            <div className="flex items-center gap-3">
              <Gift className="w-6 h-6 text-[var(--secondary)]" />
              <span className="text-[var(--text-primary)] font-semibold">
                🎉 You have been rewarded <span className="text-gradient-success text-xl">{Math.floor(userStats.credits_remaining)}</span> free credits!
              </span>
            </div>
            <button
              onClick={() => setShowWelcomeCredits(false)}
              className="text-[var(--text-muted)] hover:text-[var(--text-primary)]"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        )}

        {/* Stats Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-6 mb-8 sm:mb-12">
          {/* Agents Card */}
          <div className="card p-6 hover:scale-105 transition-transform">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-12 h-12 bg-gradient-to-br from-[var(--primary)] to-[var(--primary-hover)] rounded-xl flex items-center justify-center">
                <Bot className="w-6 h-6 text-white" />
              </div>
              <p className="text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">Agents</p>
            </div>
            <p className="text-4xl font-bold text-[var(--text-primary)]">{agents.length}</p>
          </div>

          {/* Queries Card */}
          <div className="card p-6 hover:scale-105 transition-transform">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-12 h-12 bg-gradient-to-br from-[var(--accent)] to-[var(--accent-hover)] rounded-xl flex items-center justify-center">
                <Zap className="w-6 h-6 text-white" />
              </div>
              <p className="text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">Queries</p>
            </div>
            <p className="text-4xl font-bold text-[var(--text-primary)]">
              {userStats?.total_queries || 0}
            </p>
          </div>

          {/* Credits Card - Emerald Green with Sparkline */}
          <div
            className="card p-6 cursor-pointer hover:scale-105 transition-transform relative overflow-hidden"
            onClick={() => window.location.href = '/billing'}
          >
            {/* Sparkline Background */}
            <div className="absolute inset-0 opacity-10">
              <svg className="w-full h-full" viewBox="0 0 200 60" preserveAspectRatio="none">
                <polyline
                  fill="none"
                  stroke="var(--secondary)"
                  strokeWidth="2"
                  points="0,50 20,45 40,48 60,30 80,35 100,25 120,30 140,20 160,25 180,15 200,10"
                />
              </svg>
            </div>

            <div className="relative z-10">
              <div className="flex justify-between items-start mb-4">
                <div className="flex items-center gap-3">
                  <div className="w-12 h-12 bg-gradient-to-br from-[var(--secondary)] to-[var(--secondary-hover)] rounded-xl flex items-center justify-center glow-secondary">
                    <TrendingUp className="w-6 h-6 text-white" />
                  </div>
                  <p className="text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">Credits</p>
                </div>
                <div className="badge badge-secondary text-[10px]">
                  Add
                </div>
              </div>
              <p className="text-4xl font-bold text-gradient-success">
                {userStats?.credits_remaining ? Math.floor(userStats.credits_remaining).toLocaleString() : '0'}
              </p>
            </div>
          </div>
        </div>

        {/* Agents Section Header with Search */}
        <div className="flex flex-col sm:flex-row sm:justify-between sm:items-center gap-4 mb-6">
          <h2 className="text-xl font-bold text-[var(--text-primary)]">
            Your Agents {filteredAgents.length !== agents.length && `(${filteredAgents.length})`}
          </h2>

          <div className="flex flex-wrap gap-2 items-center">
            <input
              type="text"
              placeholder="Search agents..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="input flex-1 min-w-[180px]"
            />
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value)}
              className="input min-w-[120px]"
            >
              <option value="name">Name</option>
              <option value="date">Recent</option>
              <option value="documents">Documents</option>
            </select>
            <button
              onClick={refreshAgents}
              className="btn btn-secondary btn-sm"
            >
              Refresh
            </button>
          </div>
        </div>

        {error && (
          <div className="alert alert-error mb-6">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            {error}
          </div>
        )}

        {loading ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
            <AgentCardSkeleton />
            <AgentCardSkeleton />
            <AgentCardSkeleton />
          </div>
        ) : agents.length === 0 ? (
          <div className="card p-16 text-center">
            <div className="w-20 h-20 mx-auto mb-6 bg-gradient-to-br from-[var(--primary)] to-[var(--primary-hover)] rounded-2xl flex items-center justify-center">
              <Bot className="w-10 h-10 text-white" />
            </div>
            <h3 className="text-2xl font-bold text-[var(--text-primary)] mb-4">
              Get Started with Your First Bot
            </h3>
            <p className="text-[var(--text-muted)] mb-8 max-w-md mx-auto">
              Create an intelligent AI agent powered by your documents. Upload PDFs, connect databases, and more.
            </p>
            <button
              onClick={() => window.location.href = '/create-agent'}
              className="btn btn-primary"
            >
              <Bot className="w-5 h-5" />
              Create Your First Bot
            </button>
          </div>
        ) : filteredAgents.length === 0 ? (
          <div className="card p-12 text-center">
            <p className="text-[var(--text-muted)]">
              No agents match "{searchQuery}"
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
            {filteredAgents.map((agent, idx) => (
              <div key={agent.id || agent.name} className="animate-fadeIn" style={{ animationDelay: `${idx * 0.05}s` }}>
                <AgentCard agent={agent} />
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
