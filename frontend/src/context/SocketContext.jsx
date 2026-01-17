import { createContext, useContext, useEffect, useState, useRef } from 'react';
import { io } from 'socket.io-client';
import { useAuth } from './AuthContext';

const SocketContext = createContext();

/**
 * SocketProvider - Manages WebSocket connection lifecycle
 * - Connects when user logs in
 * - Disconnects on logout
 * - Auto-reconnects on connection loss
 * - Syncs with AuthContext
 */
export function SocketProvider({ children }) {
    const [socket, setSocket] = useState(null);
    const [connected, setConnected] = useState(false);
    const [error, setError] = useState(null);
    const { token, user } = useAuth();
    const reconnectAttempts = useRef(0);

    useEffect(() => {
        // Don't connect if no token
        if (!token || !user) {
            // Disconnect existing socket if user logged out
            if (socket) {
                console.log('🔌 Disconnecting socket (user logged out)');
                socket.close();
                setSocket(null);
                setConnected(false);
            }
            return;
        }

        console.log('🔌 Initializing WebSocket connection...');

        // Create new socket connection
        const newSocket = io('http://localhost:3000', {
            auth: {
                token  // Send JWT token for authentication
            },
            // Connection options
            reconnection: true,
            reconnectionDelay: 1000,       // Start with 1s delay
            reconnectionDelayMax: 5000,    // Max 5s delay
            reconnectionAttempts: 10,      // Try 10 times before giving up
            // Prefer WebSocket, fallback to polling
            transports: ['websocket', 'polling'],
            // Timeouts
            timeout: 10000  // 10s connection timeout
        });

        // === EVENT HANDLERS ===

        newSocket.on('connect', () => {
            console.log('✅ WebSocket connected:', newSocket.id);
            setConnected(true);
            setError(null);
            reconnectAttempts.current = 0;
        });

        newSocket.on('disconnect', (reason) => {
            console.log('❌ WebSocket disconnected:', reason);
            setConnected(false);

            // Reasons that won't auto-reconnect:
            if (reason === 'io server disconnect') {
                // Server forced disconnect (e.g., token expired)
                setError('Disconnected by server. Please refresh the page.');
            } else if (reason === 'io client disconnect') {
                // Client intentionally disconnected (logout)
                setError(null);
            }
        });

        newSocket.on('connect_error', (err) => {
            console.error('⚠️ Socket connection error:', err.message);
            reconnectAttempts.current += 1;

            if (err.message.includes('Authentication') || err.message.includes('token')) {
                setError('Authentication failed. Please login again.');
                newSocket.close();  // Stop trying to reconnect
            } else {
                setError(`Connection error (attempt ${reconnectAttempts.current})`);
            }
        });

        newSocket.on('reconnect', (attemptNumber) => {
            console.log(`✅ Reconnected after ${attemptNumber} attempts`);
            setError(null);
        });

        newSocket.on('reconnect_attempt', (attemptNumber) => {
            console.log(`🔄 Reconnection attempt ${attemptNumber}...`);
        });

        newSocket.on('reconnect_failed', () => {
            console.error('❌ Reconnection failed after all attempts');
            setError('Failed to reconnect. Please refresh the page.');
        });

        setSocket(newSocket);

        // Cleanup on unmount or token change
        return () => {
            console.log('🔌 Closing WebSocket connection');
            newSocket.close();
        };
    }, [token, user]);  // Recreate socket when token/user changes

    const value = {
        socket,
        connected,
        error,
        // Utility function to check if connected before emitting
        emit: (event, data) => {
            if (socket && connected) {
                socket.emit(event, data);
                return true;
            } else {
                console.warn(`Cannot emit '${event}': Socket not connected`);
                return false;
            }
        }
    };

    return (
        <SocketContext.Provider value={value}>
            {children}
        </SocketContext.Provider>
    );
}

/**
 * Hook to access socket context
 * Must be used within SocketProvider
 */
export const useSocket = () => {
    const context = useContext(SocketContext);
    if (!context) {
        throw new Error('useSocket must be used within SocketProvider');
    }
    return context;
};
