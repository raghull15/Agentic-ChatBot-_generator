import React, { useState, useRef, useEffect } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import { MessageSquare, Send, AlertCircle } from "lucide-react";
import { safeParseJson } from "../utils/safeJson";

const API_BASE = "http://localhost:5000";

export default function EmbedPage() {
    const { token } = useParams();
    const [searchParams] = useSearchParams();
    const theme = searchParams.get("theme") || "light";

    const [agentInfo, setAgentInfo] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [messages, setMessages] = useState([]);
    const [input, setInput] = useState("");
    const [sending, setSending] = useState(false);
    const messagesEndRef = useRef(null);

    const isDark = theme === "dark";

    // Theme-based colors
    const colors = isDark ? {
        bg: "#1a1a2e",
        surface: "#16213e",
        border: "#0f3460",
        text: "#ffffff",
        textMuted: "#a0aec0",
        primary: "#4f46e5",
        primaryHover: "#4338ca",
        userBubble: "#4f46e5",
        botBubble: "#16213e",
        inputBg: "#0f3460",
    } : {
        bg: "#f8fafc",
        surface: "#ffffff",
        border: "#e2e8f0",
        text: "#1e293b",
        textMuted: "#64748b",
        primary: "#2563eb",
        primaryHover: "#1d4ed8",
        userBubble: "#2563eb",
        botBubble: "#ffffff",
        inputBg: "#ffffff",
    };

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    };

    useEffect(() => {
        scrollToBottom();
    }, [messages]);

    // Fetch agent info on mount
    useEffect(() => {
        const fetchAgentInfo = async () => {
            try {
                const response = await fetch(`${API_BASE}/embed/${token}/info`);
                const data = await safeParseJson(response);

                if (!response.ok || !data.success) {
                    throw new Error(data.error || "Failed to load chatbot");
                }

                setAgentInfo(data);
                setLoading(false);
            } catch (err) {
                setError(err.message);
                setLoading(false);
            }
        };

        if (token) {
            fetchAgentInfo();
        }
    }, [token]);

    const handleSend = async () => {
        if (!input.trim() || sending) return;

        const userMessage = input.trim();
        setInput("");
        setMessages((prev) => [...prev, { role: "user", text: userMessage }]);
        setSending(true);

        try {
            const response = await fetch(`${API_BASE}/embed/${token}/query`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ query: userMessage }),
            });

            const data = await safeParseJson(response);

            if (!data.success) {
                throw new Error(data.error || "Failed to get response");
            }

            setMessages((prev) => [
                ...prev,
                { role: "assistant", text: data.answer },
            ]);
        } catch (err) {
            setMessages((prev) => [
                ...prev,
                { role: "assistant", text: `Error: ${err.message}`, isError: true },
            ]);
        } finally {
            setSending(false);
        }
    };

    const handleKeyPress = (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
    };

    // Loading state
    if (loading) {
        return (
            <div
                className="h-screen flex items-center justify-center font-sans"
                style={{ backgroundColor: colors.bg }}
            >
                <div className="text-center">
                    <div
                        className="w-10 h-10 border-3 rounded-full mx-auto mb-4 animate-spin"
                        style={{
                            borderColor: colors.border,
                            borderTopColor: colors.primary,
                        }}
                    />
                    <p className="text-sm" style={{ color: colors.textMuted }}>Loading chatbot...</p>
                </div>
            </div>
        );
    }

    // Error state
    if (error) {
        return (
            <div
                className="h-screen flex items-center justify-center font-sans p-6"
                style={{ backgroundColor: colors.bg }}
            >
                <div className="text-center max-w-xs">
                    <AlertCircle size={48} color="#ef4444" className="mx-auto mb-4" />
                    <h2 className="text-lg mb-2" style={{ color: colors.text }}>Unable to Load</h2>
                    <p className="text-sm" style={{ color: colors.textMuted }}>{error}</p>
                </div>
            </div>
        );
    }

    return (
        <div
            className="h-screen flex flex-col font-sans"
            style={{ backgroundColor: colors.bg }}
        >
            {/* Header */}
            <div
                className="p-3 sm:p-4 flex items-center gap-3"
                style={{
                    backgroundColor: colors.surface,
                    borderBottom: `1px solid ${colors.border}`,
                }}
            >
                <div
                    className="w-8 h-8 sm:w-10 sm:h-10 rounded-lg flex items-center justify-center flex-shrink-0"
                    style={{ backgroundColor: colors.primary }}
                >
                    <MessageSquare className="w-4 h-4 sm:w-5 sm:h-5 text-white" />
                </div>
                <div className="min-w-0 flex-1">
                    <h1
                        className="text-sm sm:text-base font-semibold m-0 truncate"
                        style={{ color: colors.text }}
                    >
                        {agentInfo?.name || "AI Assistant"}
                    </h1>
                    <p
                        className="text-xs m-0 truncate"
                        style={{ color: colors.textMuted }}
                    >
                        {agentInfo?.domain || "Ask me anything"}
                    </p>
                </div>
            </div>

            {/* Messages */}
            <div className="flex-1 overflow-y-auto p-4 sm:p-5">
                {messages.length === 0 && (
                    <div className="text-center mt-10">
                        <MessageSquare
                            size={32}
                            color={colors.textMuted}
                            className="mx-auto mb-3"
                        />
                        <p className="text-sm" style={{ color: colors.textMuted }}>
                            Start a conversation by typing below
                        </p>
                    </div>
                )}

                {messages.map((msg, idx) => (
                    <div
                        key={idx}
                        className={`flex mb-3 ${msg.role === "user" ? "justify-end" : "justify-start"}`}
                    >
                        <div
                            className="text-sm leading-relaxed max-w-[85%] sm:max-w-[80%]"
                            style={{
                                padding: "10px 14px",
                                borderRadius: msg.role === "user" ? "16px 16px 4px 16px" : "16px 16px 16px 4px",
                                backgroundColor: msg.role === "user"
                                    ? colors.userBubble
                                    : msg.isError
                                        ? "#fee2e2"
                                        : colors.botBubble,
                                color: msg.role === "user"
                                    ? "#fff"
                                    : msg.isError
                                        ? "#dc2626"
                                        : colors.text,
                                boxShadow: isDark ? "none" : "0 1px 2px rgba(0,0,0,0.05)",
                                border: msg.role === "user" ? "none" : `1px solid ${colors.border}`,
                            }}
                        >
                            {msg.text}
                        </div>
                    </div>
                ))}

                {sending && (
                    <div className="flex justify-start mb-3">
                        <div
                            className="p-3 rounded-2xl"
                            style={{
                                borderRadius: "16px 16px 16px 4px",
                                backgroundColor: colors.botBubble,
                                border: `1px solid ${colors.border}`,
                            }}
                        >
                            <div className="flex gap-1">
                                {[0, 1, 2].map((i) => (
                                    <div
                                        key={i}
                                        className="w-2 h-2 rounded-full animate-bounce"
                                        style={{
                                            backgroundColor: colors.primary,
                                            animationDelay: `${i * 0.16}s`,
                                        }}
                                    />
                                ))}
                            </div>
                        </div>
                    </div>
                )}
                <div ref={messagesEndRef} />
            </div>

            {/* Input */}
            <div
                className="p-3 sm:p-4"
                style={{
                    backgroundColor: colors.surface,
                    borderTop: `1px solid ${colors.border}`,
                }}
            >
                <div className="flex gap-2 sm:gap-3">
                    <input
                        type="text"
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onKeyPress={handleKeyPress}
                        placeholder="Type your message..."
                        disabled={sending}
                        className="flex-1 text-sm outline-none"
                        style={{
                            padding: "10px 14px",
                            borderRadius: 12,
                            border: `1px solid ${colors.border}`,
                            backgroundColor: colors.inputBg,
                            color: colors.text,
                        }}
                    />
                    <button
                        onClick={handleSend}
                        disabled={sending || !input.trim()}
                        className="flex items-center justify-center transition-colors"
                        style={{
                            padding: "10px 16px",
                            borderRadius: 12,
                            border: "none",
                            backgroundColor: sending || !input.trim() ? colors.border : colors.primary,
                            color: "#fff",
                            cursor: sending || !input.trim() ? "not-allowed" : "pointer",
                        }}
                    >
                        <Send className="w-4 h-4 sm:w-5 sm:h-5" />
                    </button>
                </div>
            </div>
        </div>
    );
}
