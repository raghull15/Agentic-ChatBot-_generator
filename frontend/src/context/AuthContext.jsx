import React, { createContext, useContext, useState, useEffect, useCallback } from "react";
import { safeParseJson } from "../utils/safeJson";

const AuthContext = createContext();

// Request timeout for auth operations
const AUTH_TIMEOUT = 15000; // 15 seconds

/**
 * Fetch with timeout for auth requests
 */
async function fetchWithTimeout(url, options = {}, timeout = AUTH_TIMEOUT) {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeout);

    try {
        const response = await fetch(url, {
            ...options,
            signal: controller.signal
        });
        clearTimeout(timeoutId);
        return response;
    } catch (error) {
        clearTimeout(timeoutId);
        if (error.name === 'AbortError') {
            throw new Error('Request timeout - please check your connection');
        }
        throw error;
    }
}

export function AuthProvider({ children }) {
    const [user, setUser] = useState(null);
    const [token, setToken] = useState(localStorage.getItem("token") || null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    // Cross-tab logout synchronization
    useEffect(() => {
        const handleStorageChange = (e) => {
            if (e.key === 'token') {
                if (!e.newValue) {
                    // Token was removed in another tab, logout here too
                    setToken(null);
                    setUser(null);
                } else if (e.newValue !== token) {
                    // Token changed in another tab, update our state
                    setToken(e.newValue);
                    // Re-verify the new token
                    verifyToken();
                }
            }
        };

        window.addEventListener('storage', handleStorageChange);
        return () => window.removeEventListener('storage', handleStorageChange);
    }, [token]);

    // Verify token and load user on mount
    const verifyToken = useCallback(async () => {
        const storedToken = localStorage.getItem("token");
        if (!storedToken) {
            setLoading(false);
            return;
        }

        try {
            const response = await fetchWithTimeout("/auth/verify", {
                headers: {
                    Authorization: `Bearer ${storedToken}`,
                },
            });

            if (response.ok) {
                const data = await safeParseJson(response);
                setUser(data.user);
                setToken(storedToken);
            } else {
                // Token invalid, clear it
                console.warn("Token verification failed, clearing credentials");
                localStorage.removeItem("token");
                setToken(null);
                setUser(null);
            }
        } catch (err) {
            console.error("Token verification failed:", err.message);
            // Only clear on auth errors, not network errors
            if (err.message !== 'Request timeout - please check your connection') {
                localStorage.removeItem("token");
                setToken(null);
                setUser(null);
            }
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        verifyToken();
    }, [verifyToken]);

    // Register new user
    const register = async (name, email, phone, password) => {
        try {
            setError(null);
            const response = await fetchWithTimeout("/auth/register", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({ name, email, phone, password }),
            });

            const data = await safeParseJson(response);

            if (!response.ok) {
                throw new Error(data.error || "Registration failed");
            }

            // Store token and user
            localStorage.setItem("token", data.token);
            setToken(data.token);
            setUser(data.user);

            return data;
        } catch (err) {
            setError(err.message);
            throw err;
        }
    };

    // Login user
    const login = async (email, password) => {
        try {
            setError(null);
            const response = await fetchWithTimeout("/auth/login", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({ email, password }),
            });

            const data = await safeParseJson(response);

            if (!response.ok) {
                throw new Error(data.error || "Login failed");
            }

            // Store token and user
            localStorage.setItem("token", data.token);
            setToken(data.token);
            setUser(data.user);

            return data;
        } catch (err) {
            setError(err.message);
            throw err;
        }
    };

    // Logout user
    const logout = () => {
        localStorage.removeItem("token");
        setToken(null);
        setUser(null);
        setError(null);
    };

    // Check if user is authenticated
    const isAuthenticated = () => {
        return !!token && !!user;
    };

    // Get auth header for API calls
    const getAuthHeader = () => {
        return token ? { Authorization: `Bearer ${token}` } : {};
    };

    // Refresh authentication status
    const refreshAuth = async () => {
        await verifyToken();
    };

    return (
        <AuthContext.Provider
            value={{
                user,
                token,
                loading,
                error,
                register,
                login,
                logout,
                isAuthenticated,
                getAuthHeader,
                refreshAuth,
            }}
        >
            {children}
        </AuthContext.Provider>
    );
}

export const useAuth = () => useContext(AuthContext);

