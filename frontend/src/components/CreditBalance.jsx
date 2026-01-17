import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Coins, AlertTriangle } from "lucide-react";
import { getBalance } from "../api";
import { useSocket } from "../context/SocketContext";

/**
 * Credit balance badge for navbar
 * Shows current credits with real-time WebSocket updates
 * ✅ Phase 2: Removed 60-second polling, added WebSocket listener
 */
export default function CreditBalance() {
    const [credits, setCredits] = useState(null);
    const [loading, setLoading] = useState(true);
    const { socket, connected } = useSocket();

    // Initial fetch (only once on mount, no more polling!)
    useEffect(() => {
        fetchBalance();
    }, []);

    // 🆕 Phase 2: WebSocket real-time updates
    useEffect(() => {
        if (!socket || !connected) return;

        const handleCreditUpdate = (data) => {
            console.log('💰 Credits updated via WebSocket:', data);
            setCredits(data.newBalance);

            // Optional: Future enhancement - show toast notification
            // if (data.change > 0) showToast(`+${data.change} credits added!`);
        };

        socket.on('credits:updated', handleCreditUpdate);

        // Cleanup listener on unmount
        return () => {
            socket.off('credits:updated', handleCreditUpdate);
        };
    }, [socket, connected]);

    const fetchBalance = async () => {
        try {
            const wallet = await getBalance();
            if (wallet) {
                setCredits(wallet.credits_remaining);
            }
        } catch {
            // Silently fail - billing might not be available
        } finally {
            setLoading(false);
        }
    };

    if (loading || credits === null) {
        return null; // Don't show if billing not available
    }

    const isLow = credits < 50;

    return (
        <Link
            to="/billing"
            className={`flex items-center gap-2 px-3 py-1 text-[10px] font-medium uppercase tracking-wider border transition-colors ${isLow
                ? 'border-red-500 text-red-500 hover:bg-red-50'
                : 'border-[var(--border-color)] text-[var(--text-secondary)] hover:border-[var(--text-primary)] hover:text-[var(--text-primary)]'
                }`}
            title={`${credits.toFixed(1)} credits remaining${connected ? ' (Real-time)' : ''}`}
        >
            {isLow ? (
                <AlertTriangle className="w-3 h-3" />
            ) : (
                <Coins className="w-3 h-3" />
            )}
            <span>{credits >= 1000 ? `${(credits / 1000).toFixed(1)}K` : credits.toFixed(0)}</span>
            {connected && <span className="text-green-500 text-[8px]">●</span>}
        </Link>
    );
}

