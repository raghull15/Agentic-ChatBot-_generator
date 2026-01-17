import express from 'express';
import { io } from '../server.js';

const router = express.Router();

/**
 * Internal endpoint for Flask to trigger credit update notifications
 * NOT exposed to public - called only by Flask backend
 * 
 * Security: In production, add internal API secret validation
 */
router.post('/credit-update', (req, res) => {
    const { userId, newBalance, change, reason, details } = req.body;

    // Validation
    if (!userId || newBalance === undefined) {
        return res.status(400).json({
            success: false,
            error: 'userId and newBalance required'
        });
    }

    // Emit to user's WebSocket room
    io.to(`user:${userId}`).emit('credits:updated', {
        newBalance: parseFloat(newBalance),
        change: parseFloat(change || 0),
        reason: reason || 'unknown',
        timestamp: new Date().toISOString(),
        details: details || {}
    });

    console.log(`📤 Credit update → User ${userId}: ${newBalance} (${change >= 0 ? '+' : ''}${change}) [${reason}]`);

    res.json({ success: true });
});

export default router;
