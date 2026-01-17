import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import Navbar from "../components/Navbar";
import { useAuth } from "../context/AuthContext";
import { getAdminUsers, getAdminUsage, adminAddCredits, adminGetUserBalance, adminSuspendUser, adminUnsuspendUser } from "../api";
import { Coins, Plus, UserX, UserCheck, Shield, Users, Zap, TrendingUp, X, AlertCircle } from "lucide-react";
import SettingsPanel from "../components/SettingsPanel";
import PlansPanel from "../components/PlansPanel";
import AnalyticsPanel from "../components/AnalyticsPanel";

export default function AdminDashboard() {
    const navigate = useNavigate();
    const { user } = useAuth();
    const [activeTab, setActiveTab] = useState('users');
    const [users, setUsers] = useState([]);
    const [totals, setTotals] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [expandedUser, setExpandedUser] = useState(null);
    const [creditModal, setCreditModal] = useState(null);
    const [creditAmount, setCreditAmount] = useState('');
    const [addingCredits, setAddingCredits] = useState(false);
    const [userBalances, setUserBalances] = useState({});
    const [suspendedUsers, setSuspendedUsers] = useState({});
    const [suspending, setSuspending] = useState({});

    useEffect(() => {
        if (user && !user.isAdmin) {
            navigate("/home");
            return;
        }

        const fetchData = async () => {
            try {
                setLoading(true);
                setError(null);

                const [usersData, usageData] = await Promise.all([
                    getAdminUsers(),
                    getAdminUsage()
                ]);

                setUsers(usersData);
                setTotals(usageData.totals);

                // Fetch balances for all users
                const balances = {};
                await Promise.all(
                    usersData.map(async (u) => {
                        try {
                            const wallet = await adminGetUserBalance(u.id);
                            balances[u.id] = wallet?.credits_remaining || 0;
                        } catch {
                            balances[u.id] = 0;
                        }
                    })
                );
                setUserBalances(balances);
            } catch (err) {
                setError(err.message);
                if (err.message.includes("Admin access required")) {
                    navigate("/home");
                }
            } finally {
                setLoading(false);
            }
        };

        fetchData();
    }, [user, navigate]);

    const formatNumber = (num) => {
        if (num >= 1000000) return (num / 1000000).toFixed(1) + "M";
        if (num >= 1000) return (num / 1000).toFixed(1) + "K";
        return num?.toString() || "0";
    };

    const formatDate = (dateStr) => {
        if (!dateStr) return "—";
        return new Date(dateStr).toLocaleDateString("en-US", {
            month: "short",
            day: "numeric",
            year: "numeric"
        });
    };

    const fetchUserBalance = async (userId) => {
        try {
            const wallet = await adminGetUserBalance(userId);
            setUserBalances(prev => ({
                ...prev,
                [userId]: wallet?.credits_remaining || 0
            }));
        } catch (err) {
            console.error('Failed to fetch balance:', err);
        }
    };

    const handleAddCredits = async () => {
        if (!creditModal || !creditAmount || parseFloat(creditAmount) <= 0) {
            return;
        }

        try {
            setAddingCredits(true);
            const result = await adminAddCredits(creditModal.userId, parseFloat(creditAmount));

            setUserBalances(prev => ({
                ...prev,
                [creditModal.userId]: result.new_balance
            }));

            setCreditModal(null);
            setCreditAmount('');
        } catch (err) {
            setError('Failed to add credits: ' + err.message);
        } finally {
            setAddingCredits(false);
        }
    };

    const openCreditModal = async (u) => {
        setCreditModal({ userId: u.id, name: u.name, email: u.email });
        setCreditAmount('');
        await fetchUserBalance(u.id);
    };

    const handleSuspendUser = async (userId, isSuspended) => {
        try {
            setSuspending(prev => ({ ...prev, [userId]: true }));
            if (isSuspended) {
                await adminUnsuspendUser(userId);
                setSuspendedUsers(prev => ({ ...prev, [userId]: false }));
            } else {
                await adminSuspendUser(userId);
                setSuspendedUsers(prev => ({ ...prev, [userId]: true }));
            }
        } catch (err) {
            setError(`Failed to ${isSuspended ? 'unsuspend' : 'suspend'} user: ${err.message}`);
        } finally {
            setSuspending(prev => ({ ...prev, [userId]: false }));
        }
    };

    if (loading) {
        return (
            <div className="min-h-screen bg-[var(--bg-primary)]">
                <Navbar />
                <div className="max-w-7xl mx-auto px-4 py-8">
                    <div className="space-y-6">
                        <div className="skeleton h-8 w-48" />
                        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                            {[1, 2, 3, 4].map(i => (
                                <div key={i} className="skeleton h-24" />
                            ))}
                        </div>
                        <div className="skeleton h-96" />
                    </div>
                </div>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-[var(--bg-primary)]">
            <Navbar />

            <div className="max-w-7xl mx-auto px-4 py-6 sm:py-12">
                {/* Header */}
                <div className="mb-8 animate-fadeIn">
                    <div className="flex items-center gap-4 mb-2">
                        <div className="w-14 h-14 bg-gradient-to-br from-[var(--primary)] to-[var(--primary-hover)] rounded-2xl flex items-center justify-center shadow-lg">
                            <Shield className="w-7 h-7 text-white" />
                        </div>
                        <div>
                            <h1 className="text-3xl font-bold text-[var(--text-primary)]">
                                Admin Dashboard
                            </h1>
                            <p className="text-[var(--text-muted)]">
                                Control room • Manage users, settings, and analytics
                            </p>
                        </div>
                    </div>
                </div>

                {/* Error Alert */}
                {error && (
                    <div className="alert alert-error mb-6">
                        <AlertCircle className="w-5 h-5" />
                        <span>{error}</span>
                        <button onClick={() => setError(null)} className="ml-auto">
                            <X className="w-5 h-5" />
                        </button>
                    </div>
                )}

                {/* Stats Cards */}
                {totals && (
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
                        <div className="card p-4">
                            <div className="flex items-center gap-3 mb-2">
                                <Users className="w-5 h-5 text-[var(--primary)]" />
                                <p className="text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">
                                    Users
                                </p>
                            </div>
                            <p className="text-3xl font-bold text-[var(--text-primary)]">
                                {formatNumber(totals.total_users)}
                            </p>
                        </div>

                        <div className="card p-4">
                            <div className="flex items-center gap-3 mb-2">
                                <Zap className="w-5 h-5 text-[var(--accent)]" />
                                <p className="text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">
                                    Queries
                                </p>
                            </div>
                            <p className="text-3xl font-bold text-[var(--text-primary)]">
                                {formatNumber(totals.total_queries)}
                            </p>
                        </div>

                        <div className="card p-4">
                            <div className="flex items-center gap-3 mb-2">
                                <TrendingUp className="w-5 h-5 text-[var(--secondary)]" />
                                <p className="text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">
                                    Tokens
                                </p>
                            </div>
                            <p className="text-3xl font-bold text-[var(--text-primary)]">
                                {formatNumber(totals.total_tokens)}
                            </p>
                        </div>

                        <div className="card p-4">
                            <div className="flex items-center gap-3 mb-2">
                                <Coins className="w-5 h-5 text-[var(--warning)]" />
                                <p className="text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">
                                    Bots
                                </p>
                            </div>
                            <p className="text-3xl font-bold text-[var(--text-primary)]">
                                {formatNumber(totals.total_bots)}
                            </p>
                        </div>
                    </div>
                )}

                {/* Pill Tabs */}
                <div className="tabs mb-8">
                    {['users', 'settings', 'plans', 'analytics'].map(tab => (
                        <button
                            key={tab}
                            onClick={() => setActiveTab(tab)}
                            className={`tab ${activeTab === tab ? 'tab-active' : ''}`}
                        >
                            {tab.charAt(0).toUpperCase() + tab.slice(1)}
                        </button>
                    ))}
                </div>

                {/* Users Tab */}
                {activeTab === 'users' && (
                    <div className="card overflow-hidden">
                        <div className="overflow-x-auto">
                            <table className="table" style={{ tableLayout: 'fixed' }}>
                                <thead>
                                    <tr>
                                        <th style={{ width: '30%' }}>User</th>
                                        <th className="text-center" style={{ width: '10%' }}>Bots</th>
                                        <th className="text-center" style={{ width: '15%' }}>Queries</th>
                                        <th className="text-center" style={{ width: '15%' }}>Tokens</th>
                                        <th className="text-center" style={{ width: '15%' }}>Credits</th>
                                        <th className="text-center" style={{ width: '15%' }}>Actions</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {users.map((u, idx) => (
                                        <tr key={u.id}>
                                            <td style={{ width: '30%', padding: '12px 16px', verticalAlign: 'middle' }}>
                                                <div>
                                                    <div className="flex items-center gap-2">
                                                        <span className="font-semibold text-[var(--text-primary)]">
                                                            {u.name}
                                                        </span>
                                                        {u.isAdmin && (
                                                            <span className="badge badge-primary text-[10px]">
                                                                Admin
                                                            </span>
                                                        )}
                                                        {userBalances[u.id] > 1000 && (
                                                            <span className="badge badge-gold text-[10px]">
                                                                High Spender
                                                            </span>
                                                        )}
                                                    </div>
                                                    <div className="text-xs text-[var(--text-muted)]">
                                                        {u.email}
                                                    </div>
                                                </div>
                                            </td>
                                            <td className="text-center" style={{ width: '10%', padding: '12px 16px', verticalAlign: 'middle' }}>{u.bot_count || 0}</td>
                                            <td className="text-center" style={{ width: '15%', padding: '12px 16px', verticalAlign: 'middle' }}>{formatNumber(u.total_queries)}</td>
                                            <td className="text-center" style={{ width: '15%', padding: '12px 16px', verticalAlign: 'middle' }}>{formatNumber(u.total_tokens)}</td>
                                            <td className="text-center" style={{ width: '15%', padding: '12px 16px', verticalAlign: 'middle' }}>
                                                <span className="font-semibold text-gradient-success">
                                                    {Math.floor(userBalances[u.id] || 0)}
                                                </span>
                                            </td>
                                            <td className="text-center" style={{ width: '15%', padding: '12px 16px' }}>
                                                <div className="flex items-center justify-center gap-2">
                                                    <button
                                                        onClick={() => openCreditModal(u)}
                                                        className="btn btn-success btn-sm"
                                                        title="Add Credits"
                                                    >
                                                        <Plus className="w-3 h-3" />
                                                    </button>
                                                </div>
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </div>
                )}

                {/* Settings Tab */}
                {activeTab === 'settings' && <SettingsPanel />}

                {/* Plans Tab */}
                {activeTab === 'plans' && <PlansPanel />}

                {/* Analytics Tab */}
                {activeTab === 'analytics' && <AnalyticsPanel />}
            </div>

            {/* Add Credits Modal */}
            {creditModal && (
                <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4">
                    <div className="card max-w-md w-full p-6 animate-fadeIn">
                        <div className="flex items-center justify-between mb-6">
                            <h2 className="text-xl font-bold text-[var(--text-primary)]">
                                Add Credits
                            </h2>
                            <button
                                onClick={() => setCreditModal(null)}
                                className="text-[var(--text-muted)] hover:text-[var(--text-primary)]"
                            >
                                <X className="w-6 h-6" />
                            </button>
                        </div>

                        <div className="space-y-4">
                            <div>
                                <p className="text-sm text-[var(--text-muted)] mb-1">User</p>
                                <p className="font-semibold text-[var(--text-primary)]">
                                    {creditModal.name}
                                </p>
                                <p className="text-xs text-[var(--text-muted)]">
                                    {creditModal.email}
                                </p>
                            </div>

                            <div>
                                <p className="text-sm text-[var(--text-muted)] mb-1">Current Balance</p>
                                <p className="text-2xl font-bold text-gradient-success">
                                    {Math.floor(userBalances[creditModal.userId] || 0)} credits
                                </p>
                            </div>

                            <div>
                                <label className="block text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)] mb-2">
                                    Credits to Add
                                </label>
                                <input
                                    type="number"
                                    className="input"
                                    placeholder="100"
                                    value={creditAmount}
                                    onChange={(e) => setCreditAmount(e.target.value)}
                                    min="1"
                                    step="1"
                                />
                            </div>

                            <div className="flex gap-3 pt-4">
                                <button
                                    onClick={() => setCreditModal(null)}
                                    className="btn btn-secondary flex-1"
                                >
                                    Cancel
                                </button>
                                <button
                                    onClick={handleAddCredits}
                                    disabled={addingCredits || !creditAmount || parseFloat(creditAmount) <= 0}
                                    className="btn btn-success flex-1"
                                >
                                    {addingCredits ? (
                                        <>
                                            <div className="animate-spin w-4 h-4 border-2 border-white border-t-transparent rounded-full" />
                                            Adding...
                                        </>
                                    ) : (
                                        <>
                                            <Plus className="w-4 h-4" />
                                            Add Credits
                                        </>
                                    )}
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
