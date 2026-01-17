import { Server } from 'socket.io';
import jwt from 'jsonwebtoken';
import ChatHandler from './chatHandler.js';

/**
 * SocketManager - Centralized WebSocket management
 * Handles authentication, room management, and event routing
 */
class SocketManager {
    constructor(httpServer) {
        this.io = new Server(httpServer, {
            cors: {
                origin: ['http://localhost:5173', 'http://localhost:3000'],
                credentials: true,
                methods: ['GET', 'POST']
            },
            // Connection stability
            pingTimeout: 60000,    // 60s - wait this long for ping response
            pingInterval: 25000,   // 25s - send ping this often
            // Connection limits
            maxHttpBufferSize: 1e6,  // 1MB max message size
            // Transports (prefer websocket, fallback to polling)
            transports: ['websocket', 'polling']
        });

        // Track connected users for debugging
        this.connectedUsers = new Map(); // userId -> Set of socket ids

        // Initialize chat handler
        this.chatHandler = new ChatHandler(this.io);

        this.setupMiddleware();
        this.setupEventHandlers();

        console.log('✅ Socket.IO server initialized');
    }

    /**
     * Authentication Middleware
     * Verifies JWT token before allowing connection
     */
    setupMiddleware() {
        this.io.use((socket, next) => {
            const token = socket.handshake.auth.token;

            if (!token) {
                console.log('❌ Socket connection rejected: No token');
                return next(new Error('Authentication token required'));
            }

            try {
                // Verify token using same secret as HTTP auth
                const decoded = jwt.verify(token, process.env.JWT_SECRET);

                // Attach user info to socket
                socket.userId = decoded.id;  // MongoDB ObjectId
                socket.userEmail = decoded.email || 'unknown';

                // Join user-specific room for targeted messages
                socket.join(`user:${decoded.id}`);

                console.log(`✅ Socket authenticated: User ${decoded.id} (${socket.id})`);
                next();
            } catch (err) {
                console.log(`❌ Socket auth failed: ${err.message}`);
                return next(new Error('Invalid authentication token'));
            }
        });
    }

    /**
     * Core Event Handlers
     */
    setupEventHandlers() {
        this.io.on('connection', (socket) => {
            const userId = socket.userId;

            // Track connection
            if (!this.connectedUsers.has(userId)) {
                this.connectedUsers.set(userId, new Set());
            }
            this.connectedUsers.get(userId).add(socket.id);

            console.log(`🔌 User ${userId} connected (${socket.id})`);
            console.log(`   Total connections for user: ${this.connectedUsers.get(userId).size}`);

            // ✨ Setup chat handlers for this socket
            this.chatHandler.setupHandlers(socket);

            // Handle disconnection
            socket.on('disconnect', (reason) => {
                const userSockets = this.connectedUsers.get(userId);
                if (userSockets) {
                    userSockets.delete(socket.id);
                    if (userSockets.size === 0) {
                        this.connectedUsers.delete(userId);
                    }
                }

                console.log(`❌ User ${userId} disconnected: ${reason}`);
            });

            // Handle errors
            socket.on('error', (error) => {
                console.error(`⚠️ Socket error for user ${userId}:`, error);
            });

            // Ping/pong for connection health (automatic, but we can monitor)
            socket.on('ping', () => {
                socket.emit('pong');
            });
        });

        // Monitor server-level events
        this.io.on('connection_error', (err) => {
            console.error('Socket.IO connection error:', err);
        });
    }

    /**
     * Emit event to specific user (all their connected sockets)
     * @param {string} userId - MongoDB user ID
     * @param {string} event - Event name
     * @param {*} data - Data to send
     */
    emitToUser(userId, event, data) {
        const room = `user:${userId}`;
        this.io.to(room).emit(event, data);
        console.log(`📤 Emitted '${event}' to user ${userId}`);
    }

    /**
     * Broadcast to ALL connected clients
     * @param {string} event - Event name
     * @param {*} data - Data to send
     */
    broadcast(event, data) {
        this.io.emit(event, data);
        console.log(`📢 Broadcasted '${event}' to all users`);
    }

    /**
     * Get number of connected users
     */
    getConnectedUserCount() {
        return this.connectedUsers.size;
    }

    /**
     * Check if user is currently connected
     */
    isUserConnected(userId) {
        return this.connectedUsers.has(userId) &&
            this.connectedUsers.get(userId).size > 0;
    }

    /**
     * Get Socket.IO instance (for use in other modules)
     */
    getIO() {
        return this.io;
    }
}

export default SocketManager;
