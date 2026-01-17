import dotenv from 'dotenv';

// Load environment variables FIRST (before other imports)
dotenv.config();

import express from 'express';
import cors from 'cors';
import mongoose from 'mongoose';
import { createServer } from 'http';
import SocketManager from './socket/socketManager.js';
import authRoutes from './routes/auth.js';
import paymentRoutes from './routes/payment.js';
import internalRoutes from './routes/internal.js';

const app = express();
const httpServer = createServer(app);  // Create HTTP server for Socket.IO
const PORT = process.env.PORT || 3000;

// Initialize Socket.IO
const socketManager = new SocketManager(httpServer);
export const io = socketManager.getIO();           // Export for use in routes
export const socketMgr = socketManager;             // Export manager utilities


// Middleware
app.use(cors({
    origin: ['http://localhost:5173', 'http://localhost:5000'],
    credentials: true
}));
app.use(express.json());

// Connect to MongoDB
const connectDB = async () => {
    try {
        await mongoose.connect(process.env.MONGODB_URI);
        console.log('✅ MongoDB connected successfully');
    } catch (error) {
        console.error('❌ MongoDB connection error:', error.message);
        process.exit(1);
    }
};

// Root route
app.get('/', (req, res) => {
    res.json({
        message: 'Auth Server API',
        version: '1.0.0',
        endpoints: {
            register: 'POST /auth/register',
            login: 'POST /auth/login',
            verify: 'GET /auth/verify',
            me: 'GET /auth/me',
            payment: 'POST /payment/create-order',
            health: 'GET /health'
        }
    });
});

// Routes
app.use('/auth', authRoutes);
app.use('/payment', paymentRoutes);
app.use('/internal', internalRoutes);  // Internal endpoints for Flask

// Health check
app.get('/health', (req, res) => {
    res.json({
        status: 'healthy',
        message: 'Auth server is running',
        mongodb: mongoose.connection.readyState === 1 ? 'connected' : 'disconnected'
    });
});

// Error handling middleware
app.use((err, req, res, next) => {
    console.error('Error:', err);
    res.status(500).json({
        success: false,
        error: 'Internal server error'
    });
});

// Start server
const startServer = async () => {
    await connectDB();

    httpServer.listen(PORT, () => {
        console.log('\n' + '='.repeat(60));
        console.log('AUTH SERVER + WEBSOCKET SERVER');
        console.log('='.repeat(60));
        console.log(`HTTP Server:      http://localhost:${PORT}`);
        console.log(`WebSocket Server: ws://localhost:${PORT}`);
        console.log('\nAvailable Endpoints:');
        console.log('  POST   /auth/register    - Register new user');
        console.log('  POST   /auth/login       - Login user');
        console.log('  GET    /auth/verify      - Verify JWT token');
        console.log('  GET    /auth/me          - Get current user info');
        console.log('  GET    /health           - Health check');
        console.log('\nWebSocket Features:');
        console.log('  📡 Real-time credit updates');
        console.log('  💬 Chat streaming (Phase 2)');
        console.log('  🤖 Agent notifications (Phase 2)');
        console.log('='.repeat(60) + '\n');
    });
};

startServer();
