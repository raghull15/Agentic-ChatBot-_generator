import React, { useState } from "react";
import ReactDOM from "react-dom";
import { generateEmbedToken } from "../api";
import { X, Code2, Copy, Check } from "lucide-react";

export default function EmbedModal({ agent, onClose }) {
    const [token, setToken] = useState(agent.embed_token || null);
    const [loading, setLoading] = useState(false);
    const [copied, setCopied] = useState(false);
    const [error, setError] = useState(null);
    const [theme, setTheme] = useState('light');
    const [position, setPosition] = useState('bottom-right');
    const [width, setWidth] = useState('400');
    const [height, setHeight] = useState('600');
    const [embedFormat, setEmbedFormat] = useState('react');

    const handleGenerateToken = async () => {
        try {
            setLoading(true);
            setError(null);
            const result = await generateEmbedToken(agent.name);
            setToken(result.embed_token);
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    const getPositionCSS = () => {
        const positions = {
            'top-left': 'top: 20px; left: 20px;',
            'top-right': 'top: 20px; right: 20px;',
            'bottom-left': 'bottom: 20px; left: 20px;',
            'bottom-right': 'bottom: 20px; right: 20px;'
        };
        return positions[position] || positions['bottom-right'];
    };

    const getReactCode = () => `// ChatbotWidget.jsx
import React from 'react';

const ChatbotWidget = () => {
  const containerStyle = {
    position: 'fixed',
    ${position === 'top-left' ? 'top: 20,' : ''}${position === 'top-right' ? 'top: 20,' : ''}${position === 'bottom-left' ? 'bottom: 20,' : ''}${position === 'bottom-right' ? 'bottom: 20,' : ''}
    ${position === 'top-left' ? 'left: 20,' : ''}${position === 'top-right' ? 'right: 20,' : ''}${position === 'bottom-left' ? 'left: 20,' : ''}${position === 'bottom-right' ? 'right: 20,' : ''}
    zIndex: 9999,
    width: 'min(${width}px, calc(100vw - 40px))',
    height: 'min(${height}px, calc(100vh - 40px))',
  };

  return (
    <div style={containerStyle}>
      <iframe
        src="http://localhost:5173/embed/${token}?theme=${theme}"
        style={{width:'100%',height:'100%',border:'none',borderRadius:12,boxShadow:'0 4px 24px rgba(0,0,0,0.15)'}}
        allow="microphone"
        title="AI Chatbot"
      />
    </div>
  );
};

export default ChatbotWidget;`;

    const getIframeCode = () => `<!-- Chatbot Embed -->
<div id="chatbot-widget" style="
  position: fixed;
  ${getPositionCSS()}
  z-index: 9999;
  width: min(${width}px, calc(100vw - 40px));
  height: min(${height}px, calc(100vh - 40px));
">
  <iframe
    src="http://localhost:5173/embed/${token}?theme=${theme}"
    style="width:100%;height:100%;border:none;border-radius:12px;box-shadow:0 4px 24px rgba(0,0,0,0.15);"
    allow="microphone"
  ></iframe>
</div>`;

    const getSdkCode = () => `<!-- AgenticAI Chatbot SDK -->
<script>
  (function() {
    var container = document.createElement('div');
    container.style.cssText = 'position:fixed;${getPositionCSS()}z-index:9999;width:min(${width}px,calc(100vw-40px));height:min(${height}px,calc(100vh-40px));';
    var iframe = document.createElement('iframe');
    iframe.src = 'http://localhost:5173/embed/${token}?theme=${theme}';
    iframe.style.cssText = 'width:100%;height:100%;border:none;border-radius:12px;box-shadow:0 4px 24px rgba(0,0,0,0.15);';
    container.appendChild(iframe);
    document.body.appendChild(container);
  })();
</script>`;

    const getBackendCode = () => `// Backend API - Build your own UI
// Base: http://localhost:5000/v1 | Token: ${token}

// Query endpoint
fetch('http://localhost:5000/v1/embed/${token}/query', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ query: 'Your question' })
})
.then(res => res.json())
.then(data => console.log(data.data.answer));

// Rate limit: 20 req/min`;

    const getReactNativeCode = () => `// React Native SDK
import { AgenticChatbot } from 'react-native-agentic-chatbot';

export default function ChatScreen() {
  return (
    <AgenticChatbot
      token="${token}"
      apiUrl="http://localhost:5000/v1"
      theme="${theme}"
      onMessageSent={(msg) => console.log(msg)}
    />
  );
}`;

    const getFlutterCode = () => `// Flutter SDK
import 'package:agentic_chatbot_flutter/agentic_chatbot_flutter.dart';

class ChatScreen extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: AgenticChatbot(
        token: '${token}',
        apiUrl: 'http://localhost:5000/v1',
        theme: AgenticTheme.${theme},
      ),
    );
  }
}`;

    const getEmbedCode = () => {
        if (!token) return '';
        switch (embedFormat) {
            case 'react': return getReactCode();
            case 'iframe': return getIframeCode();
            case 'sdk': return getSdkCode();
            case 'backend': return getBackendCode();
            case 'react-native': return getReactNativeCode();
            case 'flutter': return getFlutterCode();
            default: return getReactCode();
        }
    };

    const embedCode = getEmbedCode();

    const handleCopy = () => {
        navigator.clipboard.writeText(embedCode);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };

    const modalContent = (
        <div
            className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-[99999] p-4"
            onClick={(e) => {
                if (e.target === e.currentTarget) onClose();
            }}
        >
            <div
                className="card w-full max-w-2xl max-h-[90vh] overflow-auto animate-fadeIn"
                onClick={(e) => e.stopPropagation()}
            >
                {/* Header */}
                <div className="flex items-center justify-between mb-6">
                    <div>
                        <h2 className="text-xl font-bold text-[var(--text-primary)] mb-1">
                            Embed Widget
                        </h2>
                        <p className="text-sm text-[var(--text-muted)]">{agent.name}</p>
                    </div>
                    <button
                        onClick={onClose}
                        className="text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors"
                    >
                        <X className="w-6 h-6" />
                    </button>
                </div>

                {/* Body */}
                {error && (
                    <div className="mb-4 p-4 bg-red-500/10 border border-red-500 text-red-500 text-sm rounded">
                        {error}
                    </div>
                )}

                {!token ? (
                    <div className="text-center py-12">
                        <div className="w-16 h-16 bg-[var(--bg-tertiary)] rounded-xl flex items-center justify-center mx-auto mb-4">
                            <Code2 className="w-8 h-8 text-[var(--secondary)]" />
                        </div>
                        <h3 className="text-lg font-bold text-[var(--text-primary)] mb-2">
                            Enable Embedding
                        </h3>
                        <p className="text-[var(--text-muted)] text-sm mb-6">
                            Generate a token to embed this agent.
                        </p>
                        <button
                            onClick={handleGenerateToken}
                            disabled={loading}
                            className="btn btn-primary"
                        >
                            {loading ? 'Generating...' : 'Generate Token'}
                        </button>
                    </div>
                ) : (
                    <div className="space-y-5">
                        {/* Options Grid */}
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            <div>
                                <label className="block text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)] mb-2">
                                    Theme
                                </label>
                                <div className="flex gap-2">
                                    <button
                                        onClick={() => setTheme('light')}
                                        className={`flex-1 py-2.5 rounded text-sm font-medium transition-all ${theme === 'light'
                                                ? 'bg-[var(--secondary)] text-white'
                                                : 'bg-[var(--bg-tertiary)] text-[var(--text-muted)] hover:bg-[var(--bg-secondary)]'
                                            }`}
                                    >
                                        Light
                                    </button>
                                    <button
                                        onClick={() => setTheme('dark')}
                                        className={`flex-1 py-2.5 rounded text-sm font-medium transition-all ${theme === 'dark'
                                                ? 'bg-[var(--secondary)] text-white'
                                                : 'bg-[var(--bg-tertiary)] text-[var(--text-muted)] hover:bg-[var(--bg-secondary)]'
                                            }`}
                                    >
                                        Dark
                                    </button>
                                </div>
                            </div>
                            <div>
                                <label className="block text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)] mb-2">
                                    Size
                                </label>
                                <div className="flex gap-2 items-center">
                                    <input
                                        type="number"
                                        value={width}
                                        onChange={(e) => setWidth(e.target.value)}
                                        className="input flex-1 text-center"
                                    />
                                    <span className="text-[var(--text-muted)]">×</span>
                                    <input
                                        type="number"
                                        value={height}
                                        onChange={(e) => setHeight(e.target.value)}
                                        className="input flex-1 text-center"
                                    />
                                </div>
                            </div>
                        </div>

                        {/* Position */}
                        <div>
                            <label className="block text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)] mb-2">
                                Position
                            </label>
                            <select
                                value={position}
                                onChange={(e) => setPosition(e.target.value)}
                                className="input w-full"
                            >
                                <option value="top-left">↖ Top Left</option>
                                <option value="top-right">↗ Top Right</option>
                                <option value="bottom-left">↙ Bottom Left</option>
                                <option value="bottom-right">↘ Bottom Right</option>
                            </select>
                        </div>

                        {/* Format Tabs */}
                        <div>
                            <label className="block text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)] mb-2">
                                Format
                            </label>
                            <div className="flex gap-2 flex-wrap">
                                {[
                                    { value: 'react', label: 'REACT' },
                                    { value: 'iframe', label: 'IFRAME' },
                                    { value: 'sdk', label: 'SDK' },
                                    { value: 'backend', label: 'API' },
                                    { value: 'react-native', label: 'RN' },
                                    { value: 'flutter', label: 'FLUTTER' }
                                ].map((fmt) => (
                                    <button
                                        key={fmt.value}
                                        onClick={() => setEmbedFormat(fmt.value)}
                                        className={`px-4 py-2 text-xs font-semibold uppercase tracking-wider rounded transition-all ${embedFormat === fmt.value
                                                ? 'bg-[var(--secondary)] text-white'
                                                : 'bg-[var(--bg-tertiary)] text-[var(--text-muted)] hover:bg-[var(--bg-secondary)]'
                                            }`}
                                    >
                                        {fmt.label}
                                    </button>
                                ))}
                            </div>
                        </div>

                        {/* Code Block */}
                        <div>
                            <div className="flex justify-between items-center mb-2">
                                <label className="text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">
                                    Code
                                </label>
                                <button
                                    onClick={handleCopy}
                                    className="flex items-center gap-2 text-sm font-medium text-[var(--secondary)] hover:text-[var(--secondary-hover)] transition-colors"
                                >
                                    {copied ? (
                                        <>
                                            <Check className="w-4 h-4" />
                                            Copied!
                                        </>
                                    ) : (
                                        <>
                                            <Copy className="w-4 h-4" />
                                            Copy
                                        </>
                                    )}
                                </button>
                            </div>
                            <pre className="bg-[#1a1a1a] text-[#00ff00] p-4 rounded-lg text-xs overflow-auto max-h-64 border border-[var(--border-color)]">
                                <code>{embedCode}</code>
                            </pre>
                        </div>

                        {/* Instructions */}
                        <div className="card p-4 bg-[var(--bg-tertiary)]">
                            <strong className="text-sm font-semibold text-[var(--text-primary)] block mb-2">
                                How to use:
                            </strong>
                            <ol className="text-xs text-[var(--text-muted)] space-y-1 pl-4">
                                {embedFormat === 'react' ? (
                                    <>
                                        <li>Copy the component code</li>
                                        <li>Create ChatbotWidget.jsx</li>
                                        <li>Import and use &lt;ChatbotWidget /&gt;</li>
                                    </>
                                ) : embedFormat === 'iframe' ? (
                                    <>
                                        <li>Copy the HTML code</li>
                                        <li>Paste in your HTML file</li>
                                        <li>Widget appears on load</li>
                                    </>
                                ) : embedFormat === 'backend' ? (
                                    <>
                                        <li>Use API to build custom UI</li>
                                        <li>POST to /query for chat</li>
                                        <li>Rate limit: 20 req/min</li>
                                    </>
                                ) : (
                                    <>
                                        <li>Copy the code above</li>
                                        <li>Add to your project</li>
                                        <li>Chatbot auto-initializes</li>
                                    </>
                                )}
                            </ol>
                        </div>
                    </div>
                )}

                {/* Footer */}
                {token && (
                    <div className="mt-6 pt-6 border-t border-[var(--border-color)]">
                        <button
                            onClick={onClose}
                            className="btn btn-secondary w-full"
                        >
                            Close
                        </button>
                    </div>
                )}
            </div>
        </div>
    );

    return ReactDOM.createPortal(modalContent, document.body);
}
