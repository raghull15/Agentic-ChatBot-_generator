import React, { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { forgotPassword } from "../api";
import { Mail, ArrowLeft, CheckCircle } from "lucide-react";

export default function ForgotPassword() {
    const [email, setEmail] = useState("");
    const [error, setError] = useState("");
    const [success, setSuccess] = useState(false);
    const [loading, setLoading] = useState(false);
    const navigate = useNavigate();

    const handleSubmit = async (e) => {
        e.preventDefault();

        if (!email) {
            setError("Please enter your email address");
            return;
        }

        try {
            setLoading(true);
            setError("");
            await forgotPassword(email);
            setSuccess(true);
        } catch (err) {
            setError(err.message || "Failed to send reset email. Please try again.");
        } finally {
            setLoading(false);
        }
    };

    if (success) {
        return (
            <div className="min-h-screen bg-[var(--bg-primary)] flex items-center justify-center p-4 sm:p-6">
                <div className="w-full max-w-md animate-fadeIn">
                    <div className="card p-8 text-center">
                        {/* Success Animation */}
                        <div className="w-20 h-20 mx-auto mb-6 bg-gradient-to-br from-[var(--secondary)] to-[var(--secondary-hover)] rounded-full flex items-center justify-center animate-fadeIn glow-secondary">
                            <CheckCircle className="w-10 h-10 text-white" />
                        </div>

                        <h2 className="text-2xl font-bold text-[var(--text-primary)] mb-3">
                            Check Your Email
                        </h2>
                        <p className="text-[var(--text-muted)] mb-2">
                            If an account with <span className="text-[var(--text-primary)] font-semibold">{email}</span> exists,
                            we've sent a password reset link.
                        </p>
                        <p className="text-sm text-[var(--text-muted)] mb-8">
                            The link will expire in 1 hour.
                        </p>

                        <button
                            onClick={() => navigate("/login")}
                            className="btn btn-primary w-full"
                        >
                            <ArrowLeft className="w-5 h-5" />
                            Back to Login
                        </button>
                    </div>
                </div>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-[var(--bg-primary)] flex items-center justify-center p-4 sm:p-6">
            <div className="w-full max-w-md animate-fadeIn">
                {/* Header */}
                <div className="text-center mb-8">
                    <div className="w-16 h-16 mx-auto mb-6 bg-gradient-to-br from-[var(--accent)] to-[var(--accent-hover)] rounded-2xl flex items-center justify-center shadow-lg">
                        <Mail className="w-8 h-8 text-white" />
                    </div>
                    <h1 className="text-3xl font-bold text-[var(--text-primary)] mb-2">
                        Reset Password
                    </h1>
                    <p className="text-[var(--text-muted)]">
                        Enter your email to receive a reset link
                    </p>
                </div>

                {/* Form Card */}
                <div className="card p-8">
                    {error && (
                        <div className="alert alert-error mb-6">
                            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                            </svg>
                            {error}
                        </div>
                    )}

                    <form onSubmit={handleSubmit} className="space-y-6">
                        <div>
                            <label className="block text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)] mb-2">
                                Email Address
                            </label>
                            <input
                                type="email"
                                className="input"
                                placeholder="you@example.com"
                                value={email}
                                onChange={(e) => setEmail(e.target.value)}
                                disabled={loading}
                            />
                        </div>

                        <button
                            type="submit"
                            className="btn btn-primary w-full"
                            disabled={loading}
                        >
                            {loading ? (
                                <>
                                    <div className="animate-spin w-5 h-5 border-2 border-white border-t-transparent rounded-full" />
                                    Sending...
                                </>
                            ) : (
                                <>
                                    <Mail className="w-5 h-5" />
                                    Send Reset Link
                                </>
                            )}
                        </button>
                    </form>

                    <div className="mt-6 pt-6 border-t border-[var(--border-color)] text-center">
                        <p className="text-sm text-[var(--text-muted)]">
                            Remember your password?{" "}
                            <Link
                                to="/login"
                                className="text-[var(--primary)] hover:text-[var(--primary-hover)] font-semibold"
                            >
                                Sign in
                            </Link>
                        </p>
                    </div>
                </div>
            </div>
        </div>
    );
}
