import React from 'react';
import { useSocket } from '../context/SocketContext';
import { useAuth } from '../context/AuthContext';

/**
 * SocketDebugPanel - Development tool to monitor WebSocket connection
 * Shows connection status, errors, and allows testing
 * Remove or hide in production
 */
export default function SocketDebugPanel() {
    const { socket, connected, error } = useSocket();
    const { user } = useAuth();

    if (!user) return null;  // Don't show if not logged in

    return (
        <div style={{
            position: 'fixed',
            bottom: '20px',
            right: '20px',
            backgroundColor: 'var(--bg-secondary)',
            border: `2px solid ${connected ? '#10b981' : error ? '#ef4444' : '#f59e0b'}`,
            padding: '12px 16px',
            borderRadius: '8px',
            fontSize: '12px',
            fontFamily: 'monospace',
            boxShadow: '0 4px 6px rgba(0,0,0,0.1)',
            zIndex: 9999,
            minWidth: '250px'
        }}>
            <div style={{ marginBottom: '8px', fontWeight: 'bold', display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ fontSize: '16px' }}>
                    {connected ? '🟢' : error ? '🔴' : '🟡'}
                </span>
                WebSocket Status
            </div>

            <div style={{ color: 'var(--text-secondary)', marginBottom: '4px' }}>
                <strong>State:</strong> {connected ? 'Connected' : 'Disconnected'}
            </div>

            {socket && (
                <div style={{ color: 'var(--text-secondary)', marginBottom: '4px' }}>
                    <strong>Socket ID:</strong> {socket.id || 'None'}
                </div>
            )}

            {user && (
                <div style={{ color: 'var(--text-secondary)', marginBottom: '4px' }}>
                    <strong>User ID:</strong> {user.id}
                </div>
            )}

            {error && (
                <div style={{ color: '#ef4444', marginTop: '8px', padding: '8px', backgroundColor: 'rgba(239, 68, 68, 0.1)', borderRadius: '4px' }}>
                    <strong>Error:</strong> {error}
                </div>
            )}

            {connected && (
                <div style={{ marginTop: '8px', color: '#10b981' }}>
                    ✓ Phase 1 Complete
                </div>
            )}
        </div>
    );
}
