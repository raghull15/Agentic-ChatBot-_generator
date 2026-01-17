import React, { useState, useRef, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useAgent } from "../context/AgentContext";
import { useSocketChat } from "../hooks/useSocketChat";
import { useTheme } from "../context/ThemeContext";
import { MessageSquare, Send, ArrowLeft, FileText, ChevronDown, ChevronUp, CreditCard, X, WifiOff, Coins, Sun, Moon, Home } from "lucide-react";
import { safeParseJson } from "../utils/safeJson";

export default function AgentChat() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { agents } = useAgent();
  const { isDark, toggleTheme } = useTheme();
  const agent = agents.find((a) => a.id === id);

  const {
    messages: chatMessages,
    isStreaming,
    isTyping,
    error: chatError,
    sendQuery,
    cancelQuery,
    connected: socketConnected
  } = useSocketChat(agent?.name, agent?.id);

  const [input, setInput] = useState("");
  const [expandedSources, setExpandedSources] = useState({});
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [chatMessages]);

  const toggleSources = (messageIndex) => {
    setExpandedSources(prev => ({
      ...prev,
      [messageIndex]: !prev[messageIndex]
    }));
  };

  if (!agent) {
    return (
      <div className="min-h-screen bg-[var(--bg-primary)]">
        <div className="flex items-center justify-center h-screen">
          <div className="text-center animate-fadeIn">
            <div className="w-16 h-16 mx-auto mb-6 bg-gradient-to-br from-[var(--primary)] to-[var(--primary-hover)] rounded-2xl flex items-center justify-center">
              <MessageSquare className="w-8 h-8 text-white" />
            </div>
            <h2 className="text-2xl font-bold text-[var(--text-primary)] mb-2">
              Agent not found
            </h2>
            <p className="text-[var(--text-muted)] mb-6">
              Agent ID "{id}" doesn't exist or you don't have access
            </p>
            <button
              onClick={() => navigate('/home')}
              className="btn btn-primary"
            >
              <ArrowLeft className="w-5 h-5" />
              Back to Dashboard
            </button>
          </div>
        </div>
      </div>
    );
  }

  const handleSend = () => {
    if (!input.trim() || isStreaming || !socketConnected) return;

    sendQuery(input.trim());
    setInput("");
  };

  const handleKeyPress = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="min-h-screen bg-[var(--bg-primary)] flex flex-col">
      {/* Compact Chat Header - No Navbar */}
      <div className="bg-[var(--bg-secondary)] border-b border-[var(--border-color)] px-4 py-3 flex-shrink-0">
        <div className="max-w-6xl mx-auto flex justify-between items-center">
          <div className="flex items-center gap-3">
            <button
              onClick={() => navigate('/home')}
              className="p-2 text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-tertiary)] rounded-lg transition-colors"
              title="Back to Dashboard"
            >
              <Home className="w-5 h-5" />
            </button>

            <div className="w-10 h-10 bg-gradient-to-br from-[var(--primary)] to-[var(--primary-hover)] rounded-xl flex items-center justify-center">
              <MessageSquare className="w-5 h-5 text-white" />
            </div>

            <div>
              <h1 className="text-base font-bold text-[var(--text-primary)]">
                {agent.name}
              </h1>
              <div className="flex items-center gap-2">
                <span className="status-dot status-dot-active" />
                <span className="text-xs text-[var(--text-muted)]">
                  {agent.domain || "General"}
                </span>
              </div>
            </div>
          </div>

          {/* Right Controls */}
          <div className="flex items-center gap-2">
            <button
              onClick={toggleTheme}
              className="p-2 text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-tertiary)] rounded-lg transition-colors"
              title={isDark ? 'Switch to Light Mode' : 'Switch to Dark Mode'}
            >
              {isDark ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
            </button>
          </div>
        </div>
      </div>

      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto p-4 md:p-6">
        <div className="max-w-4xl mx-auto space-y-4">
          {/* Offline Warning Toast */}
          {!socketConnected && (
            <div className="toast">
              <WifiOff className="w-5 h-5 text-[var(--warning)]" />
              <span className="text-sm text-[var(--text-primary)]">
                Reconnecting...
              </span>
            </div>
          )}

          {/* Chat Error Banner */}
          {chatError && (
            <div className="alert alert-error">
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <div className="flex-1">
                {chatError}
              </div>
              {chatError.includes('credits') && (
                <button
                  onClick={() => navigate('/billing')}
                  className="btn btn-success btn-sm"
                >
                  <CreditCard className="w-4 h-4" />
                  Buy Credits
                </button>
              )}
            </div>
          )}

          {/* Welcome Message */}
          {chatMessages.length === 0 && (
            <div className="text-center py-12 animate-fadeIn">
              <div className="w-20 h-20 mx-auto mb-6 bg-gradient-to-br from-[var(--primary)] to-[var(--primary-hover)] rounded-2xl flex items-center justify-center glow-primary">
                <MessageSquare className="w-10 h-10 text-white" />
              </div>
              <h2 className="text-2xl font-bold text-[var(--text-primary)] mb-2">
                Start a conversation
              </h2>
              <p className="text-[var(--text-muted)] max-w-md mx-auto">
                Ask me anything about your documents. I'll provide answers based on the knowledge I've been trained on.
              </p>
            </div>
          )}

          {/* Chat Messages */}
          {chatMessages.map((msg, idx) => (
            <div
              key={idx}
              className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'} animate - fadeIn`}
              style={{ animationDelay: `${idx * 0.05} s` }}
            >
              <div className={msg.role === 'user' ? 'chat-bubble-user' : 'chat-bubble-assistant'}>
                {/* Message Content */}
                <div className="whitespace-pre-wrap">
                  {msg.content}
                  {msg.role === 'assistant' && isStreaming && idx === chatMessages.length - 1 && (
                    <span className="streaming-cursor" />
                  )}
                </div>

                {/* Credits Used */}
                {msg.role === 'assistant' && msg.credits_used && (
                  <div className="mt-2 pt-2 border-t border-[var(--border-color)] flex items-center gap-2 text-xs text-[var(--text-muted)]">
                    <Coins className="w-3 h-3" />
                    <span>{msg.credits_used.toFixed(2)} credits used</span>
                  </div>
                )}

                {/* Sources Accordion */}
                {msg.role === 'assistant' && msg.sources && msg.sources.length > 0 && (
                  <div className="mt-3 pt-3 border-t border-[var(--border-color)]">
                    <button
                      onClick={() => toggleSources(idx)}
                      className="flex items-center justify-between w-full text-xs font-semibold text-[var(--text-primary)] hover:text-[var(--primary)] transition-colors"
                    >
                      <div className="flex items-center gap-2">
                        <FileText className="w-3 h-3" />
                        <span>{msg.sources.length} source{msg.sources.length !== 1 ? 's' : ''}</span>
                      </div>
                      {expandedSources[idx] ? (
                        <ChevronUp className="w-4 h-4" />
                      ) : (
                        <ChevronDown className="w-4 h-4" />
                      )}
                    </button>

                    {/* Accordion Content */}
                    {expandedSources[idx] && (
                      <div className="mt-2 space-y-2 max-h-48 overflow-y-auto">
                        {msg.sources.map((source, sIdx) => (
                          <div
                            key={sIdx}
                            className="p-2 bg-[var(--bg-primary)] border border-[var(--border-color)] rounded-lg text-xs"
                          >
                            <p className="text-[var(--text-secondary)] line-clamp-3">
                              {source.page_content || source}
                            </p>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          ))}

          {/* Typing Indicator - Bouncing Dots */}
          {isTyping && !isStreaming && (
            <div className="flex justify-start">
              <div className="chat-bubble-assistant">
                <div className="flex items-center gap-1">
                  <div className="w-2 h-2 bg-[var(--text-muted)] rounded-full bounce-1" />
                  <div className="w-2 h-2 bg-[var(--text-muted)] rounded-full bounce-2" />
                  <div className="w-2 h-2 bg-[var(--text-muted)] rounded-full bounce-3" />
                </div>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Input Area */}
      <div className="bg-[var(--bg-secondary)] border-t border-[var(--border-color)] p-4">
        <div className="max-w-4xl mx-auto">
          <div className="flex gap-3">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder={socketConnected ? "Type your message..." : "Connecting..."}
              disabled={!socketConnected || isStreaming}
              className="input flex-1 resize-none"
              rows={1}
              style={{
                minHeight: '48px',
                maxHeight: '120px'
              }}
            />

            {isStreaming ? (
              <button
                onClick={cancelQuery}
                className="btn btn-danger px-6"
              >
                <X className="w-5 h-5" />
                Cancel
              </button>
            ) : (
              <button
                onClick={handleSend}
                disabled={!input.trim() || !socketConnected}
                className="btn btn-primary px-6"
              >
                <Send className="w-5 h-5" />
              </button>
            )}
          </div>

          {/* Helper Text */}
          <p className="text-xs text-[var(--text-muted)] mt-2 text-center">
            Press Enter to send, Shift+Enter for new line
          </p>
        </div>
      </div>
    </div>
  );
}
