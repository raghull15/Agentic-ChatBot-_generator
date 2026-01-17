import React, { useState, useEffect } from "react";
import { useNavigate, useSearchParams, Link } from "react-router-dom";
import { resetPassword } from "../api";
import { useAuth } from "../context/AuthContext";
import { Eye, EyeOff, Lock, CheckCircle, ArrowRight } from "lucide-react";

export default function ResetPassword() {
    const [searchParams] = useSearchParams();
    const [password, setPassword] = useState("");
    const [confirmPassword, setConfirmPassword] = useState("");
    const [showPassword, setShowPassword] = useState(false);
    const [showConfirmPassword, setShowConfirmPassword] = useState(false);
    const [error, setError] = useState("");
    const [success, setSuccess] = useState(false);
    const [loading, setLoading] = useState(false);
    const navigate = useNavigate();
    const { setUser, setToken } = useAuth();

    const token = searchParams.get("token");

    useEffect(() => {
        if (!token) {
            setError("Invalid reset link. Please request a new password reset.");
        }
    }, [token]);

    const handleSubmit = async (e) => {
        e.preventDefault();

        if (!password || !confirmPassword) {
            setError("Please fill in all fields");
            return;
        }

        if (password.length < 6) {
            setError("Password must be at least 6 characters");
            return;
        }

        if (password !== confirmPassword) {
            setError("Passwords do not match");
            return;
        }

        try {
            setLoading(true);
            setError("");
            const result = await resetPassword(token, password);

            // Auto-login if token returned
            if (result.token && result.user) {
                localStorage.setItem("token", result.token);
                setToken(result.token);
                setUser(result.user);
            }

            setSuccess(true);
        } catch (err) {
            setError(err.message || "Failed to reset password. Please try again.");
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
                            Password Reset Successful
                        </h2>
                        <p className="text-[var(--text-muted)] mb-8">
                            Your password has been updated. You can now sign in with your new password.
                        </p>

                        <button
                            onClick={() => navigate("/home")}
                            className="btn btn-primary w-full"
                        >
                            Continue to Dashboard
                            <ArrowRight className="w-5 h-5" />
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
                    <div className="w-16 h-16 mx-auto mb-6 bg-gradient-to-br from-[var(--primary)] to-[var(--primary-hover)] rounded-2xl flex items-center justify-center shadow-lg">
                        <Lock className="w-8 h-8 text-white" />
                    </div>
                    <h1 className="text-3xl font-bold text-[var(--text-primary)] mb-2">
                        New Password
                    </h1>
                    <p className="text-[var(--text-muted)]">
                        Enter your new password below
                    </p>
                </div>

                {/* Form Card */}
                <div className="card p-8">
                    {error && (
                        <div className="alert alert-error mb-6">
                            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                            </svg>
                            <div>
                                {error}
                                {!token && (
                                    <Link
                                        to="/forgot-password"
                                        className="block mt-2 text-[var(--primary)] hover:text-[var(--primary-hover)] font-semibold"
                                    >
                                        Request new reset link
                                    </Link>
                                )}
                            </div>
                        </div>
                    )}

                    {token && (
                        <form onSubmit={handleSubmit} className="space-y-6">
                            <div>
                                <label className="block text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)] mb-2">
                                    New Password
                                </label>
                                <div className="input-with-icon">
                                    <input
                                        type={showPassword ? "text" : "password"}
                                        className="input"
                                        placeholder="At least 6 characters"
                                        value={password}
                                        onChange={(e) => setPassword(e.target.value)}
                                        disabled={loading}
                                    />
                                    <div
                                        className="input-icon"
                                        onClick={() => setShowPassword(!showPassword)}
                                    >
                                        {showPassword ? (
                                            <EyeOff className="w-5 h-5" />
                                        ) : (
                                            <Eye className="w-5 h-5" />
                                        )}
                                    </div>
                                </div>
                            </div>

                            <div>
                                <label className="block text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)] mb-2">
                                    Confirm Password
                                </label>
                                <div className="input-with-icon">
                                    <input
                                        type={showConfirmPassword ? "text" : "password"}
                                        className="input"
                                        placeholder="Re-enter your new password"
                                        value={confirmPassword}
                                        onChange={(e) => setConfirmPassword(e.target.value)}
                                        disabled={loading}
                                    />
                                    <div
                                        className="input-icon"
                                        onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                                    >
                                        {showConfirmPassword ? (
                                            <EyeOff className="w-5 h-5" />
                                        ) : (
                                            <Eye className="w-5 h-5" />
                                        )}
                                    </div>
                                </div>
                            </div>

                            <button
                                type="submit"
                                className="btn btn-primary w-full"
                                disabled={loading}
                            >
                                {loading ? (
                                    <>
                                        <div className="animate-spin w-5 h-5 border-2 border-white border-t-transparent rounded-full" />
                                        Resetting...
                                    </>
                                ) : (
                                    <>
                                        Reset Password
                                        <ArrowRight className="w-5 h-5" />
                                    </>
                                )}
                            </button>
                        </form>
                    )}

                    <div className="mt-6 pt-6 border-t border-[var(--border-color)] text-center">
                        <p className="text-sm text-[var(--text-muted)]">
                            <Link
                                to="/login"
                                className="text-[var(--primary)] hover:text-[var(--primary-hover)] font-semibold"
                            >
                                Back to Login
                            </Link>
                        </p>
                    </div>
                </div>
            </div>
        </div>
    );
}
