import nodemailer from 'nodemailer';

// Configure transporter based on environment
const createTransporter = () => {
    // For Gmail (most common for development)
    if (process.env.SMTP_SERVICE === 'gmail') {
        return nodemailer.createTransport({
            service: 'gmail',
            auth: {
                user: process.env.SMTP_USER,
                pass: process.env.SMTP_PASS // Use App Password for Gmail
            }
        });
    }

    // For custom SMTP (SendGrid, Mailgun, etc.)
    return nodemailer.createTransport({
        host: process.env.SMTP_HOST || 'smtp.gmail.com',
        port: parseInt(process.env.SMTP_PORT) || 587,
        secure: process.env.SMTP_SECURE === 'true', // true for 465, false for other ports
        auth: {
            user: process.env.SMTP_USER,
            pass: process.env.SMTP_PASS
        }
    });
};

// Create transporter (lazy initialization)
let transporter = null;

const getTransporter = () => {
    if (!transporter) {
        transporter = createTransporter();
    }
    return transporter;
};

/**
 * Send password reset email
 * @param {string} email - User's email address
 * @param {string} name - User's name
 * @param {string} resetToken - Password reset token
 * @returns {Promise<boolean>} - Success status
 */
export const sendPasswordResetEmail = async (email, name, resetToken) => {
    const frontendUrl = process.env.FRONTEND_URL || 'http://localhost:5173';
    const resetLink = `${frontendUrl}/reset-password?token=${resetToken}`;

    const mailOptions = {
        from: process.env.SMTP_FROM || `"AgenticAI" <${process.env.SMTP_USER}>`,
        to: email,
        subject: 'Reset Your Password - AgenticAI',
        html: `
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
            </head>
            <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #f5f5f5; margin: 0; padding: 40px 20px;">
                <div style="max-width: 480px; margin: 0 auto; background: #ffffff; border: 1px solid #e0e0e0;">
                    <div style="padding: 32px;">
                        <h1 style="font-size: 14px; font-weight: 500; text-transform: uppercase; letter-spacing: 0.1em; color: #666; margin: 0 0 24px 0;">Password Reset</h1>
                        
                        <p style="font-size: 15px; color: #333; line-height: 1.6; margin: 0 0 20px 0;">
                            Hi ${name},
                        </p>
                        
                        <p style="font-size: 15px; color: #333; line-height: 1.6; margin: 0 0 24px 0;">
                            We received a request to reset your password. Click the button below to create a new password:
                        </p>
                        
                        <a href="${resetLink}" style="display: inline-block; background: #000; color: #fff; text-decoration: none; padding: 12px 24px; font-size: 13px; font-weight: 500; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 24px;">
                            Reset Password
                        </a>
                        
                        <p style="font-size: 13px; color: #666; line-height: 1.6; margin: 24px 0 0 0;">
                            This link will expire in 1 hour. If you didn't request this, you can safely ignore this email.
                        </p>
                        
                        <hr style="border: none; border-top: 1px solid #e0e0e0; margin: 32px 0;">
                        
                        <p style="font-size: 12px; color: #999; margin: 0;">
                            If the button doesn't work, copy and paste this link:<br>
                            <a href="${resetLink}" style="color: #666; word-break: break-all;">${resetLink}</a>
                        </p>
                    </div>
                </div>
            </body>
            </html>
        `,
        text: `Hi ${name},\n\nWe received a request to reset your password.\n\nClick this link to reset your password: ${resetLink}\n\nThis link will expire in 1 hour.\n\nIf you didn't request this, you can safely ignore this email.`
    };

    try {
        // Check if SMTP is configured
        if (!process.env.SMTP_USER || !process.env.SMTP_PASS) {
            console.log('SMTP not configured. Would have sent email to:', email);
            console.log('Reset link:', resetLink);
            return true; // For development, return success
        }

        const info = await getTransporter().sendMail(mailOptions);
        console.log('Password reset email sent:', info.messageId);
        return true;
    } catch (error) {
        console.error('Error sending password reset email:', error);
        throw error;
    }
};

/**
 * Verify SMTP connection
 * @returns {Promise<boolean>}
 */
export const verifyConnection = async () => {
    try {
        if (!process.env.SMTP_USER || !process.env.SMTP_PASS) {
            console.log('SMTP not configured - emails will be logged to console');
            return false;
        }
        await getTransporter().verify();
        console.log('SMTP connection verified');
        return true;
    } catch (error) {
        console.error('SMTP connection failed:', error);
        return false;
    }
};

export default {
    sendPasswordResetEmail,
    verifyConnection
};
