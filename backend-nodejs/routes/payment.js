import express from 'express';
import crypto from 'crypto';
import Razorpay from 'razorpay';
import jwt from 'jsonwebtoken';
import { io } from '../server.js';  // Import Socket.IO for real-time updates

const router = express.Router();

// Lazy-load Razorpay client (only when needed)
let razorpayClient = null;
function getRazorpay() {
    if (!razorpayClient) {
        const keyId = process.env.RAZORPAY_KEY_ID;
        const keySecret = process.env.RAZORPAY_KEY_SECRET;

        if (!keyId || !keySecret) {
            console.error('Razorpay config missing:', {
                hasKeyId: !!keyId,
                hasKeySecret: !!keySecret
            });
            throw new Error('Razorpay credentials not configured. Check RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET in .env');
        }

        razorpayClient = new Razorpay({
            key_id: keyId,
            key_secret: keySecret
        });
        console.log('Razorpay client initialized successfully');
    }
    return razorpayClient;
}

// Flask API URL for credits
const FLASK_API_URL = process.env.FLASK_API_URL || 'http://localhost:5000';
const INTERNAL_API_SECRET = process.env.INTERNAL_API_SECRET || "<shared-secret>"

// Log for debugging
console.log('🔑 Internal API Secret loaded:', INTERNAL_API_SECRET);

// JWT verification middleware
const verifyToken = (req, res, next) => {
    const authHeader = req.headers.authorization;
    if (!authHeader || !authHeader.startsWith('Bearer ')) {
        return res.status(401).json({ success: false, error: 'No token provided' });
    }

    const token = authHeader.split(' ')[1];
    try {
        const decoded = jwt.verify(token, process.env.JWT_SECRET);
        req.userId = decoded.id;  // JWT token has 'id' field, not 'userId'
        req.user = decoded;
        next();
    } catch (error) {
        return res.status(401).json({ success: false, error: 'Invalid token' });
    }
};

/**
 * GET /payment/plans - Get available plans from Flask
 */
router.get('/plans', async (req, res) => {
    try {
        const response = await fetch(`${FLASK_API_URL}/billing/plans`);
        const data = await response.json();
        res.json(data);
    } catch (error) {
        console.error('Error fetching plans:', error);
        res.status(500).json({ success: false, error: 'Failed to fetch plans' });
    }
});

/**
 * POST /payment/create-order - Create Razorpay order
 */
router.post('/create-order', verifyToken, async (req, res) => {
    try {
        const { plan_id, amount, credits, plan_name } = req.body;

        if (!plan_id || !amount) {
            return res.status(400).json({ success: false, error: 'plan_id and amount required' });
        }

        // Amount should be in paise
        const amountPaise = Math.round(amount * 100);

        const options = {
            amount: amountPaise,
            currency: 'INR',
            receipt: `rcpt_${Date.now()}`,  // Shortened to fit 40 char limit
            notes: {
                user_id: req.userId,
                plan_id: plan_id,
                credits: credits || 0,
                amount_paise: amountPaise  // Store for verification
            }
        };

        const order = await getRazorpay().orders.create(options);

        res.json({
            success: true,
            order: {
                id: order.id,
                amount: order.amount,
                currency: order.currency,
                key_id: process.env.RAZORPAY_KEY_ID
            }
        });
    } catch (error) {
        console.error('Error creating order:', error);
        res.status(500).json({ success: false, error: 'Failed to create order' });
    }
});

/**
 * POST /payment/verify - Verify payment and add credits
 */
router.post('/verify', verifyToken, async (req, res) => {
    try {
        const { razorpay_order_id, razorpay_payment_id, razorpay_signature, credits } = req.body;

        if (!razorpay_order_id || !razorpay_payment_id || !razorpay_signature) {
            return res.status(400).json({ success: false, error: 'Missing payment details' });
        }

        // Verify signature
        const body = razorpay_order_id + '|' + razorpay_payment_id;
        const expectedSignature = crypto
            .createHmac('sha256', process.env.RAZORPAY_KEY_SECRET)
            .update(body)
            .digest('hex');

        if (expectedSignature !== razorpay_signature) {
            return res.status(400).json({ success: false, error: 'Invalid signature' });
        }

        // Log what we received
        console.log('Payment verify request:', { userId: req.userId, credits, razorpay_payment_id });

        // Validate credits
        if (!credits || credits === 0) {
            return res.status(400).json({ success: false, error: 'Credits value is required and must be greater than 0' });
        }

        // Get order details from Razorpay to retrieve plan_id and amount
        const razorpay = getRazorpay();
        const order = await razorpay.orders.fetch(razorpay_order_id);
        const plan_id = order.notes?.plan_id || 'unknown';
        const amount = order.amount || 0;

        // Call Flask to add credits
        const flaskResponse = await fetch(`${FLASK_API_URL}/internal/add-credits`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Internal-Secret': INTERNAL_API_SECRET
            },
            body: JSON.stringify({
                user_id: req.userId,
                credits: credits,
                payment_id: razorpay_payment_id,
                order_id: razorpay_order_id,
                plan_id: plan_id,
                amount: amount
            })
        });

        const flaskData = await flaskResponse.json();

        if (!flaskData.success) {
            return res.status(500).json({ success: false, error: flaskData.error || 'Failed to add credits' });
        }

        res.json({
            success: true,
            message: 'Payment verified and credits added',
            credits_added: credits,
            new_balance: flaskData.new_balance
        });

        // 🆕 Emit real-time credit update via WebSocket
        io.to(`user:${req.userId}`).emit('credits:updated', {
            newBalance: flaskData.new_balance,
            change: credits,
            reason: 'payment',
            timestamp: new Date().toISOString(),
            details: {
                planId: plan_id,
                paymentId: razorpay_payment_id,
                amount: amount / 100  // Convert paise to rupees for display
            }
        });

        console.log(`💳 Payment verified: Added ${credits} credits to user ${req.userId} → Balance: ${flaskData.new_balance}`);
    } catch (error) {
        console.error('Error verifying payment:', error);
        res.status(500).json({ success: false, error: 'Payment verification failed' });
    }
});

export default router;
