import React, { useEffect, useState, useRef } from "react";
import { useNavigate } from "react-router-dom";
import Navbar from "../components/Navbar";
import { useAuth } from "../context/AuthContext";
import { getBalance, getPlans, createOrder, verifyPayment, getUsageHistory, getPaymentHistory } from "../api";
import { CreditCard, Coins, TrendingUp, Clock, CheckCircle, AlertCircle, Loader2, Zap, ChevronLeft, ChevronRight } from "lucide-react";

// Razorpay key from environment
const RAZORPAY_KEY_ID = import.meta.env.VITE_RAZORPAY_KEY_ID || '';

export default function BillingPage() {
    const navigate = useNavigate();
    const { user } = useAuth();
    const [wallet, setWallet] = useState(null);
    const [plans, setPlans] = useState([]);
    const [usage, setUsage] = useState([]);
    const [payments, setPayments] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [purchasing, setPurchasing] = useState(null);
    const [activeTab, setActiveTab] = useState('plans');
    const scrollRef = useRef(null);

    const scrollPlans = (direction) => {
        if (scrollRef.current) {
            const scrollAmount = 400;
            scrollRef.current.scrollBy({
                left: direction === 'left' ? -scrollAmount : scrollAmount,
                behavior: 'smooth'
            });
        }
    };

    useEffect(() => {
        fetchData();
    }, []);

    const fetchData = async () => {
        try {
            setLoading(true);
            setError(null);

            const [walletData, plansData, usageData, paymentsData] = await Promise.all([
                getBalance().catch(() => null),
                getPlans().catch(() => []),
                getUsageHistory(20).catch(() => ({ usage: [], summary: {} })),
                getPaymentHistory(10).catch(() => [])
            ]);

            setWallet(walletData);
            setPlans(plansData);
            setUsage(usageData.usage || []);
            setPayments(paymentsData);
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    const handleBuyPlan = async (plan) => {
        try {
            setPurchasing(plan.id);
            setError(null);

            // Create order - pass full plan object
            const order = await createOrder(plan);

            // Get Razorpay key from order response
            if (!order.key_id) {
                setError("Payment service not configured. Please contact support.");
                return;
            }

            // Open Razorpay checkout
            const options = {
                key: order.key_id,
                amount: order.amount,
                currency: order.currency || 'INR',
                order_id: order.id,
                name: 'Agentic AI',
                description: `${plan.name} - ${plan.total_credits || plan.credits} Credits`,
                handler: async (response) => {
                    try {
                        await verifyPayment(
                            response.razorpay_order_id,
                            response.razorpay_payment_id,
                            response.razorpay_signature,
                            plan.total_credits || plan.credits
                        );
                        fetchData(); // Refresh data
                    } catch (err) {
                        setError("Payment verification failed: " + err.message);
                    }
                },
                prefill: {
                    email: user?.email || '',
                    name: user?.name || ''
                },
                theme: {
                    color: '#7C3AED'
                }
            };

            const razorpay = new window.Razorpay(options);
            razorpay.open();

        } catch (err) {
            setError(err.message);
        } finally {
            setPurchasing(null);
        }
    };

    const formatCredits = (credits) => {
        if (credits >= 1000) return `${(credits / 1000).toFixed(1)}K`;
        return credits?.toFixed(1) || '0';
    };

    const formatDate = (dateStr) => {
        if (!dateStr) return '—';
        return new Date(dateStr).toLocaleDateString('en-IN', {
            day: 'numeric',
            month: 'short',
            year: 'numeric'
        });
    };

    if (loading) {
        return (
            <div className="min-h-screen bg-[var(--bg-primary)]">
                <Navbar />
                <div className="max-w-6xl mx-auto px-4 py-8">
                    <div className="space-y-6">
                        <div className="skeleton h-8 w-48" />
                        <div className="skeleton h-32" />
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                            {[1, 2, 3].map(i => (
                                <div key={i} className="skeleton h-48" />
                            ))}
                        </div>
                    </div>
                </div>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-[var(--bg-primary)]">
            <Navbar />

            <div className="max-w-6xl mx-auto px-4 py-8 sm:py-12">
                {/* Header */}
                <div className="mb-8 animate-fadeIn">
                    <h1 className="text-3xl font-bold text-[var(--text-primary)] mb-2">
                        Billing & Credits
                    </h1>
                    <p className="text-[var(--text-muted)]">
                        Manage your credits and view usage
                    </p>
                </div>

                {/* Error */}
                {error && (
                    <div className="alert alert-error mb-6">
                        <AlertCircle className="w-5 h-5" />
                        <span>{error}</span>
                    </div>
                )}

                {/* Balance Card with Sparkline */}
                <div className="card p-8 mb-8 relative overflow-hidden">
                    {/* Sparkline Background */}
                    <div className="absolute inset-0 opacity-10">
                        <svg className="w-full h-full" viewBox="0 0 400 120" preserveAspectRatio="none">
                            <polyline
                                fill="none"
                                stroke="var(--secondary)"
                                strokeWidth="3"
                                points="0,100 40,90 80,95 120,60 160,70 200,50 240,60 280,40 320,50 360,30 400,20"
                            />
                        </svg>
                    </div>

                    <div className="relative z-10 grid grid-cols-1 md:grid-cols-3 gap-6">
                        <div>
                            <p className="text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)] mb-2">
                                Available Credits
                            </p>
                            <p className="text-5xl font-bold text-gradient-success">
                                {wallet ? formatCredits(wallet.credits_remaining) : '0'}
                            </p>
                        </div>
                        <div>
                            <p className="text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)] mb-2">
                                Today's Usage
                            </p>
                            <p className="text-2xl font-bold text-[var(--text-primary)]">
                                {wallet ? formatCredits(wallet.daily_usage) : '0'} / {wallet?.daily_limit || 100}
                            </p>
                        </div>
                        <div>
                            <p className="text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)] mb-2">
                                Total Purchased
                            </p>
                            <p className="text-2xl font-bold text-[var(--text-primary)]">
                                {wallet ? formatCredits(wallet.total_purchased) : '0'}
                            </p>
                        </div>
                    </div>
                </div>

                {/* Pill Tabs */}
                <div className="tabs mb-8">
                    {['plans', 'usage', 'payments'].map(tab => (
                        <button
                            key={tab}
                            onClick={() => setActiveTab(tab)}
                            className={`tab ${activeTab === tab ? 'tab-active' : ''}`}
                        >
                            {tab.charAt(0).toUpperCase() + tab.slice(1)}
                        </button>
                    ))}
                </div>

                {/* Plans Tab */}
                {activeTab === 'plans' && (
                    <div className="relative">
                        {plans.length > 3 && (
                            <>
                                <button onClick={() => scrollPlans('left')} className="absolute left-0 top-1/2 -translate-y-1/2 z-10 w-10 h-10 bg-[var(--bg-secondary)] border border-[var(--border-color)] rounded-full flex items-center justify-center hover:bg-[var(--bg-tertiary)] transition-colors shadow-lg">
                                    <ChevronLeft className="w-5 h-5 text-[var(--text-primary)]" />
                                </button>
                                <button onClick={() => scrollPlans('right')} className="absolute right-0 top-1/2 -translate-y-1/2 z-10 w-10 h-10 bg-[var(--bg-secondary)] border border-[var(--border-color)] rounded-full flex items-center justify-center hover:bg-[var(--bg-tertiary)] transition-colors shadow-lg">
                                    <ChevronRight className="w-5 h-5 text-[var(--text-primary)]" />
                                </button>
                            </>
                        )}
                        <div ref={scrollRef} className="flex gap-6 overflow-x-auto px-12" style={{ scrollbarWidth: 'none', msOverflowStyle: 'none' }}>
                            {plans.map((plan, idx) => (
                                <div
                                    key={plan.id}
                                    className={`card p-6 hover:scale-105 transition-all flex-shrink-0 w-80 flex flex-col ${idx === 1 ? 'border-2 border-[var(--primary)] shadow-xl' : ''
                                        }`}
                                    style={{ animationDelay: `${idx * 0.1}s` }}
                                >

                                    <div className="flex items-center gap-3 mb-4">
                                        <div className="w-12 h-12 bg-gradient-to-br from-[var(--secondary)] to-[var(--secondary-hover)] rounded-xl flex items-center justify-center">
                                            <Coins className="w-6 h-6 text-white" />
                                        </div>
                                        <h3 className="text-lg font-bold text-[var(--text-primary)]">
                                            {plan.name}
                                        </h3>
                                    </div>

                                    <div className="mb-6">
                                        <span className="text-4xl font-bold text-[var(--text-primary)]">
                                            ₹{plan.amount_inr}
                                        </span>
                                    </div>

                                    <div className="space-y-3 mb-6 flex-1">
                                        <div className="flex items-center justify-between">
                                            <span className="text-sm text-[var(--text-muted)]">Base Credits</span>
                                            <span className="text-sm font-semibold text-[var(--text-primary)]">
                                                {plan.credits.toLocaleString()}
                                            </span>
                                        </div>
                                        {plan.bonus_credits > 0 && (
                                            <div className="flex items-center justify-between">
                                                <span className="text-sm text-[var(--text-muted)]">Bonus</span>
                                                <span className="text-sm font-semibold text-[var(--secondary)]">
                                                    +{plan.bonus_credits.toLocaleString()}
                                                </span>
                                            </div>
                                        )}
                                        <div className="pt-3 border-t border-[var(--border-color)]">
                                            <div className="flex items-center justify-between">
                                                <span className="text-sm font-bold text-[var(--text-primary)]">Total</span>
                                                <span className="text-lg font-bold text-gradient-success">
                                                    {plan.total_credits.toLocaleString()}
                                                </span>
                                            </div>
                                        </div>
                                    </div>

                                    <button
                                        onClick={() => handleBuyPlan(plan)}
                                        disabled={purchasing === plan.id}
                                        className="btn btn-primary w-full mt-auto"
                                    >
                                        {purchasing === plan.id ? (
                                            <>
                                                <Loader2 className="w-4 h-4 animate-spin" />
                                                Processing...
                                            </>
                                        ) : (
                                            <>
                                                <CreditCard className="w-4 h-4" />
                                                Buy Now
                                            </>
                                        )}
                                    </button>
                                </div>
                            ))}
                        </div>
                    </div>
                )}

                {/* Usage Tab */}
                {activeTab === 'usage' && (
                    <div className="card overflow-hidden">
                        <div className="overflow-x-auto">
                            <table className="w-full" style={{ tableLayout: 'fixed' }}>
                                <thead>
                                    <tr className="border-b border-[var(--border-color)]">
                                        <th className="text-left p-4 text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]" style={{ width: '30%' }}>Chatbot</th>
                                        <th className="text-center p-4 text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]" style={{ width: '25%' }}>Tokens</th>
                                        <th className="text-center p-4 text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]" style={{ width: '20%' }}>Credits</th>
                                        <th className="text-right p-4 text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]" style={{ width: '25%' }}>Date</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {usage.length === 0 ? (
                                        <tr>
                                            <td colSpan={4} className="text-center py-8 text-[var(--text-muted)]">
                                                No usage data yet
                                            </td>
                                        </tr>
                                    ) : (
                                        usage.map((log, idx) => (
                                            <tr key={log.id || idx} className="border-b border-[var(--border-color)] hover:bg-[var(--bg-tertiary)] transition-colors">
                                                <td className="p-4 text-[var(--text-primary)]" style={{ width: '30%' }}>{log.chatbot_id || '—'}</td>
                                                <td className="p-4 text-center text-[var(--text-primary)]" style={{ width: '25%' }}>{log.total_tokens?.toLocaleString()}</td>
                                                <td className="p-4 text-center font-semibold text-[var(--text-primary)]" style={{ width: '20%' }}>{log.credits_used?.toFixed(2)}</td>
                                                <td className="p-4 text-right text-[var(--text-muted)]" style={{ width: '25%' }}>{formatDate(log.created_at)}</td>
                                            </tr>
                                        ))
                                    )}
                                </tbody>
                            </table>
                        </div>
                    </div>
                )}

                {/* Payments Tab */}
                {activeTab === 'payments' && (
                    <div className="card overflow-hidden">
                        <div className="overflow-x-auto">
                            <table className="w-full" style={{ tableLayout: 'fixed' }}>
                                <thead>
                                    <tr className="border-b border-[var(--border-color)]">
                                        <th className="text-left p-4 text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]" style={{ width: '20%' }}>Plan</th>
                                        <th className="text-center p-4 text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]" style={{ width: '20%' }}>Amount</th>
                                        <th className="text-center p-4 text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]" style={{ width: '20%' }}>Credits</th>
                                        <th className="text-center p-4 text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]" style={{ width: '20%' }}>Status</th>
                                        <th className="text-right p-4 text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]" style={{ width: '20%' }}>Date</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {payments.length === 0 ? (
                                        <tr>
                                            <td colSpan={5} className="text-center py-8 text-[var(--text-muted)]">
                                                No payments yet
                                            </td>
                                        </tr>
                                    ) : (
                                        payments.map((payment, idx) => (
                                            <tr key={payment.id || idx} className="border-b border-[var(--border-color)] hover:bg-[var(--bg-tertiary)] transition-colors">
                                                <td className="p-4 capitalize text-[var(--text-primary)]">{payment.plan || '—'}</td>
                                                <td className="p-4 text-center font-semibold text-[var(--text-primary)]">₹{payment.amount_inr}</td>
                                                <td className="p-4 text-center text-[var(--text-primary)]">
                                                    {(payment.credits_added || payment.credits || payment.total_credits || 0).toLocaleString()}
                                                </td>
                                                <td className="p-4 text-center">
                                                    <span className={`badge ${payment.status === 'completed' ? 'badge-secondary' :
                                                        payment.status === 'pending' ? 'badge-warning' :
                                                            'badge-danger'
                                                        }`}>
                                                        {payment.status === 'completed' && <CheckCircle className="w-3 h-3" />}
                                                        {payment.status}
                                                    </span>
                                                </td>
                                                <td className="p-4 text-right text-[var(--text-muted)]">{formatDate(payment.created_at)}</td>
                                            </tr>
                                        ))
                                    )}
                                </tbody>
                            </table>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}
