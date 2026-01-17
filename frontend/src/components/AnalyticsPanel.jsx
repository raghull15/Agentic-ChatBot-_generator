import React, { useState, useEffect } from "react";
import { RefreshCw, TrendingUp, Users, Activity, Zap } from "lucide-react";
import { adminGetAnalytics } from "../api";

/**
 * Analytics panel for admin dashboard
 */
export default function AnalyticsPanel() {
    const [analytics, setAnalytics] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [days, setDays] = useState(30);

    const fetchAnalytics = async () => {
        try {
            setLoading(true);
            setError(null);
            const data = await adminGetAnalytics(days);
            setAnalytics(data);
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchAnalytics();
    }, [days]);

    const formatNumber = (num) => {
        if (!num) return '0';
        if (num >= 1000000) return `${(num / 1000000).toFixed(1)}M`;
        if (num >= 1000) return `${(num / 1000).toFixed(1)}K`;
        return num.toString();
    };

    if (loading) {
        return (
            <div className="p-8 text-center text-[var(--text-muted)]">
                Loading analytics...
            </div>
        );
    }

    if (error) {
        return (
            <div className="p-4 border border-red-500 text-red-500 flex justify-between items-center">
                <span>{error}</span>
                <button onClick={fetchAnalytics} className="text-xs underline">Retry</button>
            </div>
        );
    }

    const { usage_stats, daily_usage, top_users, top_agents, user_summary } = analytics || {};

    return (
        <div className="space-y-8">
            {/* Header */}
            <div className="flex flex-wrap justify-between items-center gap-4 mb-2">
                <h3 className="text-lg font-bold text-[var(--text-primary)]">
                    Usage Analytics
                </h3>
                <div className="flex items-center gap-3">
                    <select
                        value={days}
                        onChange={(e) => setDays(parseInt(e.target.value))}
                        className="input text-sm"
                    >
                        <option value={7}>Last 7 days</option>
                        <option value={14}>Last 14 days</option>
                        <option value={30}>Last 30 days</option>
                        <option value={90}>Last 90 days</option>
                    </select>
                    <button
                        onClick={fetchAnalytics}
                        className="btn btn-secondary btn-sm"
                    >
                        <RefreshCw className="w-4 h-4" />
                    </button>
                </div>
            </div>

            {/* Stats Cards */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="card p-6 hover:shadow-lg transition-all">
                    <div className="flex items-center gap-2 mb-3">
                        <Activity className="w-5 h-5 text-[var(--secondary)]" />
                        <span className="text-xs font-semibold uppercase text-[var(--text-muted)]">Queries</span>
                    </div>
                    <p className="text-3xl font-bold text-[var(--text-primary)]">
                        {formatNumber(usage_stats?.total_queries)}
                    </p>
                </div>
                <div className="card p-6 hover:shadow-lg transition-all">
                    <div className="flex items-center gap-2 mb-3">
                        <Zap className="w-5 h-5 text-[var(--primary)]" />
                        <span className="text-xs font-semibold uppercase text-[var(--text-muted)]">Tokens</span>
                    </div>
                    <p className="text-3xl font-bold text-[var(--text-primary)]">
                        {formatNumber(usage_stats?.total_tokens)}
                    </p>
                </div>
                <div className="card p-6 hover:shadow-lg transition-all">
                    <div className="flex items-center gap-2 mb-3">
                        <TrendingUp className="w-5 h-5 text-[var(--accent)]" />
                        <span className="text-xs font-semibold uppercase text-[var(--text-muted)]">Credits Used</span>
                    </div>
                    <p className="text-3xl font-bold text-[var(--text-primary)]">
                        {formatNumber(usage_stats?.total_credits)}
                    </p>
                </div>
                <div className="card p-6 hover:shadow-lg transition-all">
                    <div className="flex items-center gap-2 mb-3">
                        <Users className="w-5 h-5 text-[var(--secondary)]" />
                        <span className="text-xs font-semibold uppercase text-[var(--text-muted)]">Active Users</span>
                    </div>
                    <p className="text-3xl font-bold text-[var(--text-primary)]">
                        {formatNumber(usage_stats?.active_users)}
                    </p>
                </div>
            </div>

            {/* User Summary */}
            {user_summary && (
                <div className="card p-6">
                    <h4 className="text-sm font-semibold uppercase tracking-wider text-[var(--text-primary)] mb-4">
                        User Summary
                    </h4>
                    <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                        <div>
                            <p className="text-xs text-[var(--text-muted)] mb-1">Total Users</p>
                            <p className="text-2xl font-bold text-[var(--text-primary)]">{user_summary.total_users || 0}</p>
                        </div>
                        <div>
                            <p className="text-xs text-[var(--text-muted)] mb-1">Active</p>
                            <p className="text-2xl font-bold text-[var(--secondary)]">{user_summary.active_users || 0}</p>
                        </div>
                        <div>
                            <p className="text-xs text-[var(--text-muted)] mb-1">Suspended</p>
                            <p className="text-2xl font-bold text-red-500">{user_summary.suspended_users || 0}</p>
                        </div>
                        <div>
                            <p className="text-xs text-[var(--text-muted)] mb-1">With Credits</p>
                            <p className="text-2xl font-bold text-[var(--text-primary)]">{user_summary.users_with_credits || 0}</p>
                        </div>
                        <div>
                            <p className="text-xs text-[var(--text-muted)] mb-1">Total Credits</p>
                            <p className="text-2xl font-bold text-gradient-success">{formatNumber(user_summary.total_credits_in_wallets)}</p>
                        </div>
                    </div>
                </div>
            )}

            {/* Daily Usage Chart Placeholder */}
            {daily_usage && daily_usage.length > 0 && (
                <div className="card p-6">
                    <h4 className="text-sm font-semibold uppercase tracking-wider text-[var(--text-primary)] mb-4">
                        Daily Usage (30 Days)
                    </h4>
                    <div className="h-64 flex items-end justify-between gap-1">
                        {daily_usage.slice(-30).map((day, idx) => {
                            const maxQueries = Math.max(...daily_usage.map(d => d.queries || 0));
                            const height = maxQueries > 0 ? (day.queries / maxQueries) * 100 : 0;
                            return (
                                <div
                                    key={idx}
                                    className="flex-1 bg-gradient-to-t from-[var(--secondary)] to-[var(--secondary-hover)] rounded-t hover:opacity-80 transition-opacity"
                                    style={{ height: `${height}%`, minHeight: '2px' }}
                                    title={`${day.date}: ${day.queries} queries`}
                                />
                            );
                        })}
                    </div>
                </div>
            )}

            {/* Top Users and Agents */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {/* Top Users */}
                <div className="card p-6">
                    <h4 className="text-sm font-semibold uppercase tracking-wider text-[var(--text-primary)] mb-4">
                        Top Users
                    </h4>
                    <div className="space-y-3">
                        {top_users && top_users.length > 0 ? (
                            top_users.slice(0, 5).map((user, idx) => (
                                <div key={idx} className="flex items-center justify-between p-3 bg-[var(--bg-tertiary)] rounded">
                                    <div>
                                        <p className="text-sm font-medium text-[var(--text-primary)]">{user.email || 'Unknown'}</p>
                                        <p className="text-xs text-[var(--text-muted)]">{formatNumber(user.query_count)} queries</p>
                                    </div>
                                    <p className="text-sm font-bold text-gradient-success">{formatNumber(user.credits_used)} credits</p>
                                </div>
                            ))
                        ) : (
                            <p className="text-sm text-[var(--text-muted)] text-center py-4">No data available</p>
                        )}
                    </div>
                </div>

                {/* Top Agents */}
                <div className="card p-6">
                    <h4 className="text-sm font-semibold uppercase tracking-wider text-[var(--text-primary)] mb-4">
                        Top Agents
                    </h4>
                    <div className="space-y-3">
                        {top_agents && top_agents.length > 0 ? (
                            top_agents.slice(0, 5).map((agent, idx) => (
                                <div key={idx} className="flex items-center justify-between p-3 bg-[var(--bg-tertiary)] rounded">
                                    <div>
                                        <p className="text-sm font-medium text-[var(--text-primary)]">{agent.name || agent.chatbot_id || 'Unknown'}</p>
                                        <p className="text-xs text-[var(--text-muted)]">{formatNumber(agent.query_count)} queries</p>
                                    </div>
                                    <p className="text-sm font-bold text-[var(--primary)]">{formatNumber(agent.total_tokens)} tokens</p>
                                </div>
                            ))
                        ) : (
                            <p className="text-sm text-[var(--text-muted)] text-center py-4">No data available</p>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
}
